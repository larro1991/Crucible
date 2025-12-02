"""
Docker Janitor - Cleanup Docker resources.

Handles:
- Stopped containers from code execution
- Dangling images
- Unused volumes
- Build cache
"""

import logging
import subprocess
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger('crucible.maintenance.docker')


class DockerJanitor:
    """
    Automated Docker cleanup.

    Cleans up Docker resources created during code execution:
    - Containers that have exited
    - Unused images (especially execution images)
    - Orphaned volumes
    - Build cache
    """

    # Prefix used for Crucible-created containers
    CONTAINER_PREFIX = "crucible_exec_"

    # Images we use for execution
    EXECUTION_IMAGES = [
        "python:3.11-slim",
        "python:3.10-slim",
        "node:18-slim",
        "ubuntu:22.04",
        "golang:1.21-alpine"
    ]

    def __init__(self):
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def run_cleanup(
        self,
        container_max_age_hours: int = 1,
        prune_images: bool = True,
        prune_volumes: bool = False,  # Dangerous, disabled by default
        prune_build_cache: bool = True
    ) -> Dict[str, any]:
        """
        Run Docker cleanup tasks.

        Args:
            container_max_age_hours: Remove stopped containers older than this
            prune_images: Remove dangling images
            prune_volumes: Remove unused volumes (dangerous!)
            prune_build_cache: Remove build cache

        Returns:
            Cleanup statistics
        """
        results = {
            'docker_available': self._docker_available,
            'containers_removed': 0,
            'images_removed': 0,
            'volumes_removed': 0,
            'cache_cleared': False,
            'space_reclaimed_mb': 0,
            'errors': []
        }

        if not self._docker_available:
            results['errors'].append("Docker not available")
            return results

        # Clean old containers
        try:
            results['containers_removed'] = self._clean_old_containers(container_max_age_hours)
        except Exception as e:
            logger.error(f"Error cleaning containers: {e}")
            results['errors'].append(f"containers: {str(e)}")

        # Prune dangling images
        if prune_images:
            try:
                img_result = self._prune_images()
                results['images_removed'] = img_result['count']
                results['space_reclaimed_mb'] += img_result['space_mb']
            except Exception as e:
                logger.error(f"Error pruning images: {e}")
                results['errors'].append(f"images: {str(e)}")

        # Prune unused volumes (only if explicitly enabled)
        if prune_volumes:
            try:
                vol_result = self._prune_volumes()
                results['volumes_removed'] = vol_result['count']
                results['space_reclaimed_mb'] += vol_result['space_mb']
            except Exception as e:
                logger.error(f"Error pruning volumes: {e}")
                results['errors'].append(f"volumes: {str(e)}")

        # Clear build cache
        if prune_build_cache:
            try:
                cache_result = self._prune_build_cache()
                results['cache_cleared'] = cache_result['cleared']
                results['space_reclaimed_mb'] += cache_result['space_mb']
            except Exception as e:
                logger.error(f"Error pruning build cache: {e}")
                results['errors'].append(f"cache: {str(e)}")

        logger.info(f"Docker cleanup complete: {results}")
        return results

    def _clean_old_containers(self, max_age_hours: int) -> int:
        """Remove stopped containers older than max_age_hours."""
        removed = 0

        # List all containers (including stopped)
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return 0

            cutoff = datetime.now() - timedelta(hours=max_age_hours)

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    container = json.loads(line)
                    container_id = container.get('ID', '')
                    status = container.get('Status', '')
                    names = container.get('Names', '')

                    # Only clean Crucible containers or exited containers
                    is_crucible = names.startswith(self.CONTAINER_PREFIX)
                    is_exited = 'Exited' in status

                    if is_exited and (is_crucible or self._is_old_container(container_id, cutoff)):
                        self._remove_container(container_id)
                        removed += 1

                except json.JSONDecodeError:
                    continue

        except subprocess.TimeoutExpired:
            logger.warning("Docker ps timed out")
        except Exception as e:
            logger.error(f"Error listing containers: {e}")

        return removed

    def _is_old_container(self, container_id: str, cutoff: datetime) -> bool:
        """Check if container is older than cutoff."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.Created}}", container_id],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                created_str = result.stdout.strip()
                # Parse Docker timestamp format
                created = datetime.fromisoformat(created_str.replace('Z', '+00:00').split('.')[0])
                return created.replace(tzinfo=None) < cutoff

        except Exception:
            pass

        return False

    def _remove_container(self, container_id: str) -> bool:
        """Remove a specific container."""
        try:
            result = subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.debug(f"Removed container: {container_id}")
                return True
        except Exception as e:
            logger.warning(f"Failed to remove container {container_id}: {e}")

        return False

    def _prune_images(self) -> Dict[str, any]:
        """Remove dangling images."""
        result = {'count': 0, 'space_mb': 0}

        try:
            proc = subprocess.run(
                ["docker", "image", "prune", "-f"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if proc.returncode == 0:
                # Parse output for reclaimed space
                output = proc.stdout
                if 'Total reclaimed space' in output:
                    # Extract size (e.g., "Total reclaimed space: 1.2GB")
                    for line in output.split('\n'):
                        if 'reclaimed' in line.lower():
                            result['space_mb'] = self._parse_size_to_mb(line)
                            break

                # Count removed images
                result['count'] = output.count('Deleted')

        except subprocess.TimeoutExpired:
            logger.warning("Image prune timed out")
        except Exception as e:
            logger.error(f"Error pruning images: {e}")

        return result

    def _prune_volumes(self) -> Dict[str, any]:
        """Remove unused volumes."""
        result = {'count': 0, 'space_mb': 0}

        try:
            proc = subprocess.run(
                ["docker", "volume", "prune", "-f"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if proc.returncode == 0:
                output = proc.stdout
                if 'Total reclaimed space' in output:
                    for line in output.split('\n'):
                        if 'reclaimed' in line.lower():
                            result['space_mb'] = self._parse_size_to_mb(line)
                            break

        except subprocess.TimeoutExpired:
            logger.warning("Volume prune timed out")
        except Exception as e:
            logger.error(f"Error pruning volumes: {e}")

        return result

    def _prune_build_cache(self) -> Dict[str, any]:
        """Clear Docker build cache."""
        result = {'cleared': False, 'space_mb': 0}

        try:
            proc = subprocess.run(
                ["docker", "builder", "prune", "-f"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if proc.returncode == 0:
                result['cleared'] = True
                output = proc.stdout
                if 'Total reclaimed space' in output or 'reclaimed' in output.lower():
                    for line in output.split('\n'):
                        if 'reclaimed' in line.lower():
                            result['space_mb'] = self._parse_size_to_mb(line)
                            break

        except subprocess.TimeoutExpired:
            logger.warning("Builder prune timed out")
        except Exception as e:
            logger.error(f"Error pruning build cache: {e}")

        return result

    def _parse_size_to_mb(self, text: str) -> float:
        """Parse Docker size string to MB."""
        import re

        # Look for patterns like "1.2GB", "500MB", "100kB"
        match = re.search(r'([\d.]+)\s*(GB|MB|KB|B)', text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).upper()

            if unit == 'GB':
                return value * 1024
            elif unit == 'MB':
                return value
            elif unit == 'KB':
                return value / 1024
            elif unit == 'B':
                return value / (1024 * 1024)

        return 0

    def get_docker_stats(self) -> Dict[str, any]:
        """Get Docker resource usage statistics."""
        stats = {
            'available': self._docker_available,
            'containers': {'running': 0, 'stopped': 0, 'total': 0},
            'images': {'count': 0, 'size_mb': 0},
            'volumes': {'count': 0},
            'system': {}
        }

        if not self._docker_available:
            return stats

        # Container stats
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                statuses = result.stdout.strip().split('\n')
                stats['containers']['total'] = len([s for s in statuses if s])
                stats['containers']['running'] = len([s for s in statuses if s and 'Up' in s])
                stats['containers']['stopped'] = stats['containers']['total'] - stats['containers']['running']
        except:
            pass

        # Image stats
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Size}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                sizes = result.stdout.strip().split('\n')
                stats['images']['count'] = len([s for s in sizes if s])
                total_mb = sum(self._parse_size_to_mb(s) for s in sizes if s)
                stats['images']['size_mb'] = round(total_mb, 2)
        except:
            pass

        # Volume count
        try:
            result = subprocess.run(
                ["docker", "volume", "ls", "-q"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                volumes = result.stdout.strip().split('\n')
                stats['volumes']['count'] = len([v for v in volumes if v])
        except:
            pass

        # System disk usage
        try:
            result = subprocess.run(
                ["docker", "system", "df", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            data = json.loads(line)
                            stats['system'][data.get('Type', 'unknown')] = {
                                'size': data.get('Size', '0B'),
                                'reclaimable': data.get('Reclaimable', '0B')
                            }
                        except:
                            pass
        except:
            pass

        return stats

    def pull_execution_images(self) -> Dict[str, bool]:
        """Pre-pull execution images."""
        results = {}

        for image in self.EXECUTION_IMAGES:
            try:
                result = subprocess.run(
                    ["docker", "pull", image],
                    capture_output=True,
                    timeout=300  # 5 min timeout per image
                )
                results[image] = result.returncode == 0
            except Exception as e:
                logger.error(f"Failed to pull {image}: {e}")
                results[image] = False

        return results
