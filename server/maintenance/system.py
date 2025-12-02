"""
System Janitor - Unified interface to all maintenance systems.

Coordinates:
- Memory cleanup (sessions, facts, working memory)
- Filesystem cleanup (temp, logs, cache)
- Docker cleanup (containers, images, volumes)

Provides scheduled maintenance and on-demand cleanup.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from .filesystem import FilesystemJanitor
from .docker_cleanup import DockerJanitor

logger = logging.getLogger('crucible.maintenance.system')


class SystemJanitor:
    """
    Unified system maintenance.

    Coordinates all cleanup operations:
    - Memory: Old sessions, stale facts, working memory
    - Filesystem: Temp files, logs, cache, execution artifacts
    - Docker: Containers, images, volumes, build cache

    Can be run on-demand or scheduled via cron/systemd timer.
    """

    def __init__(self, base_path: Path, memory_janitor=None):
        """
        Initialize system janitor.

        Args:
            base_path: Crucible base directory
            memory_janitor: Optional MemoryJanitor instance
        """
        self.base_path = Path(base_path)
        self.filesystem = FilesystemJanitor(base_path)
        self.docker = DockerJanitor()
        self.memory_janitor = memory_janitor

    def run_full_maintenance(
        self,
        # Memory settings
        memory_archive_days: int = 7,
        memory_decay_days: int = 30,
        memory_cleanup_days: int = 3,
        # Filesystem settings
        temp_max_age_hours: int = 24,
        log_max_age_days: int = 7,
        log_max_size_mb: int = 100,
        cache_max_age_days: int = 30,
        # Docker settings
        docker_container_age_hours: int = 1,
        docker_prune_images: bool = True,
        docker_prune_volumes: bool = False,
        docker_prune_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Run complete system maintenance.

        Args:
            memory_archive_days: Archive sessions older than this
            memory_decay_days: Decay facts older than this
            memory_cleanup_days: Clean working memory older than this
            temp_max_age_hours: Delete temp files older than this
            log_max_age_days: Delete logs older than this
            log_max_size_mb: Max total log size
            cache_max_age_days: Delete cache older than this
            docker_container_age_hours: Remove containers older than this
            docker_prune_images: Prune dangling images
            docker_prune_volumes: Prune unused volumes (dangerous!)
            docker_prune_cache: Prune build cache

        Returns:
            Combined results from all janitors
        """
        results = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'memory': {},
            'filesystem': {},
            'docker': {},
            'total_space_freed_mb': 0,
            'errors': []
        }

        # Memory cleanup
        if self.memory_janitor:
            try:
                results['memory'] = self.memory_janitor.run_maintenance(
                    archive_sessions_days=memory_archive_days,
                    decay_facts_days=memory_decay_days,
                    cleanup_working_days=memory_cleanup_days
                )
            except Exception as e:
                logger.error(f"Memory maintenance failed: {e}")
                results['errors'].append(f"memory: {str(e)}")

        # Filesystem cleanup
        try:
            results['filesystem'] = self.filesystem.run_cleanup(
                temp_max_age_hours=temp_max_age_hours,
                log_max_age_days=log_max_age_days,
                log_max_size_mb=log_max_size_mb,
                cache_max_age_days=cache_max_age_days
            )

            # Add execution artifact cleanup
            exec_result = self.filesystem.clean_execution_artifacts(
                max_age_hours=temp_max_age_hours
            )
            results['filesystem']['exec_files_deleted'] = exec_result['files']
            results['filesystem']['exec_bytes_freed'] = exec_result['bytes']

            # Calculate filesystem space freed
            fs_bytes = (
                results['filesystem'].get('temp_bytes_freed', 0) +
                results['filesystem'].get('log_bytes_freed', 0) +
                results['filesystem'].get('cache_bytes_freed', 0) +
                results['filesystem'].get('exec_bytes_freed', 0)
            )
            results['total_space_freed_mb'] += fs_bytes / (1024 * 1024)

        except Exception as e:
            logger.error(f"Filesystem maintenance failed: {e}")
            results['errors'].append(f"filesystem: {str(e)}")

        # Docker cleanup
        try:
            results['docker'] = self.docker.run_cleanup(
                container_max_age_hours=docker_container_age_hours,
                prune_images=docker_prune_images,
                prune_volumes=docker_prune_volumes,
                prune_build_cache=docker_prune_cache
            )

            results['total_space_freed_mb'] += results['docker'].get('space_reclaimed_mb', 0)

        except Exception as e:
            logger.error(f"Docker maintenance failed: {e}")
            results['errors'].append(f"docker: {str(e)}")

        results['total_space_freed_mb'] = round(results['total_space_freed_mb'], 2)

        logger.info(f"Full maintenance complete. Space freed: {results['total_space_freed_mb']} MB")
        return results

    def run_quick_cleanup(self) -> Dict[str, Any]:
        """
        Run quick cleanup with safe defaults.

        Good for frequent (hourly) runs.
        """
        return self.run_full_maintenance(
            # Memory: gentle
            memory_archive_days=14,
            memory_decay_days=60,
            memory_cleanup_days=7,
            # Filesystem: aggressive on temp, gentle on logs
            temp_max_age_hours=6,
            log_max_age_days=14,
            log_max_size_mb=200,
            cache_max_age_days=7,
            # Docker: only containers
            docker_container_age_hours=1,
            docker_prune_images=False,
            docker_prune_volumes=False,
            docker_prune_cache=False
        )

    def run_deep_cleanup(self) -> Dict[str, Any]:
        """
        Run deep cleanup.

        Good for weekly runs. More aggressive but still safe.
        """
        return self.run_full_maintenance(
            # Memory: moderate
            memory_archive_days=7,
            memory_decay_days=30,
            memory_cleanup_days=3,
            # Filesystem: aggressive
            temp_max_age_hours=12,
            log_max_age_days=7,
            log_max_size_mb=100,
            cache_max_age_days=14,
            # Docker: full except volumes
            docker_container_age_hours=1,
            docker_prune_images=True,
            docker_prune_volumes=False,  # Still dangerous
            docker_prune_cache=True
        )

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get complete system status.

        Returns disk usage, Docker stats, and memory stats.
        """
        status = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'filesystem': self.filesystem.get_disk_usage(),
            'docker': self.docker.get_docker_stats(),
            'memory': {}
        }

        if self.memory_janitor:
            status['memory'] = self.memory_janitor.get_stats()

        # Calculate totals
        total_mb = 0
        for name, data in status['filesystem'].items():
            total_mb += data.get('mb', 0)

        status['summary'] = {
            'filesystem_mb': round(total_mb, 2),
            'docker_images_mb': status['docker'].get('images', {}).get('size_mb', 0),
            'docker_available': status['docker'].get('available', False)
        }

        return status

    def generate_report(self) -> str:
        """Generate a human-readable maintenance report."""
        status = self.get_system_status()

        lines = [
            "=" * 60,
            "CRUCIBLE SYSTEM STATUS REPORT",
            f"Generated: {status['timestamp']}",
            "=" * 60,
            "",
            "## Filesystem Usage",
        ]

        for name, data in status['filesystem'].items():
            lines.append(f"  {name}: {data['files']} files, {data['mb']} MB")

        lines.append("")
        lines.append(f"  Total: {status['summary']['filesystem_mb']} MB")
        lines.append("")

        # Docker
        docker = status['docker']
        lines.append("## Docker Status")
        if docker['available']:
            lines.append(f"  Containers: {docker['containers']['running']} running, {docker['containers']['stopped']} stopped")
            lines.append(f"  Images: {docker['images']['count']} ({docker['images']['size_mb']} MB)")
            lines.append(f"  Volumes: {docker['volumes']['count']}")
        else:
            lines.append("  Docker not available")

        lines.append("")

        # Memory
        if status['memory']:
            mem = status['memory']
            lines.append("## Memory System")
            lines.append(f"  Active sessions: {mem.get('active_sessions', 0)}")
            lines.append(f"  Archived sessions: {mem.get('archived_sessions', 0)}")
            lines.append(f"  Total episodes: {mem.get('total_episodes', 0)}")
            lines.append(f"  Total facts: {mem.get('total_facts', 0)}")
            lines.append(f"  Active tasks: {mem.get('active_tasks', 0)}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)


def run_scheduled_maintenance():
    """
    Entry point for scheduled maintenance (cron/systemd timer).

    Can be called directly:
        python -m server.maintenance.system
    """
    import sys

    # Determine base path
    base_path = Path(__file__).parent.parent.parent

    # Try to import and set up memory janitor
    memory_janitor = None
    try:
        from ..memory.manager import MemoryManager
        from ..memory.janitor import MemoryJanitor

        mm = MemoryManager(base_path / 'data')
        memory_janitor = MemoryJanitor(
            mm.session, mm.episodic, mm.semantic, mm.working
        )
    except ImportError:
        logger.warning("Could not import memory module")

    # Create system janitor
    janitor = SystemJanitor(base_path, memory_janitor)

    # Check for command line args
    if len(sys.argv) > 1:
        if sys.argv[1] == 'quick':
            results = janitor.run_quick_cleanup()
        elif sys.argv[1] == 'deep':
            results = janitor.run_deep_cleanup()
        elif sys.argv[1] == 'status':
            print(janitor.generate_report())
            return
        else:
            results = janitor.run_full_maintenance()
    else:
        results = janitor.run_quick_cleanup()

    # Print summary
    print(f"Maintenance complete. Space freed: {results['total_space_freed_mb']} MB")
    if results['errors']:
        print(f"Errors: {results['errors']}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_scheduled_maintenance()
