"""
Maintenance Tools - MCP tools for system cleanup.

Provides Claude with tools to:
- Clean up temp files, logs, cache
- Manage Docker resources
- Run scheduled maintenance
- Get system status
"""

from typing import Optional, Dict, Any
import logging
from pathlib import Path

from ..maintenance.system import SystemJanitor

logger = logging.getLogger('crucible.tools.maintenance')


class MaintenanceTools:
    """
    MCP tools for system maintenance.

    Tools:
    - crucible_cleanup: Run cleanup (quick, deep, or full)
    - crucible_cleanup_docker: Docker-specific cleanup
    - crucible_cleanup_filesystem: Filesystem-specific cleanup
    - crucible_system_status: Get system status
    - crucible_disk_usage: Get disk usage details
    """

    def __init__(self, base_path: Path, memory_janitor=None):
        """
        Initialize maintenance tools.

        Args:
            base_path: Crucible base directory
            memory_janitor: Optional MemoryJanitor for memory cleanup
        """
        self.janitor = SystemJanitor(base_path, memory_janitor)

    def cleanup(self, mode: str = "quick") -> str:
        """
        Run system cleanup.

        Args:
            mode: "quick" (safe, frequent), "deep" (weekly), or "full" (aggressive)

        Returns:
            Cleanup report
        """
        if mode == "quick":
            results = self.janitor.run_quick_cleanup()
        elif mode == "deep":
            results = self.janitor.run_deep_cleanup()
        else:
            results = self.janitor.run_full_maintenance()

        lines = [f"=== System Cleanup Complete ({mode}) ===", ""]

        # Memory results
        if results.get('memory'):
            mem = results['memory']
            lines.append("Memory:")
            lines.append(f"  Sessions archived: {mem.get('sessions_archived', 0)}")
            lines.append(f"  Facts decayed: {mem.get('facts_decayed', 0)}")
            lines.append(f"  Working memory cleaned: {mem.get('working_cleaned', 0)}")
            lines.append("")

        # Filesystem results
        if results.get('filesystem'):
            fs = results['filesystem']
            lines.append("Filesystem:")
            lines.append(f"  Temp files deleted: {fs.get('temp_files_deleted', 0)}")
            lines.append(f"  Log files deleted: {fs.get('log_files_deleted', 0)}")
            lines.append(f"  Cache files deleted: {fs.get('cache_files_deleted', 0)}")
            temp_mb = round(fs.get('temp_bytes_freed', 0) / (1024*1024), 2)
            log_mb = round(fs.get('log_bytes_freed', 0) / (1024*1024), 2)
            cache_mb = round(fs.get('cache_bytes_freed', 0) / (1024*1024), 2)
            lines.append(f"  Space freed: {temp_mb + log_mb + cache_mb} MB")
            lines.append("")

        # Docker results
        if results.get('docker'):
            docker = results['docker']
            if docker.get('docker_available'):
                lines.append("Docker:")
                lines.append(f"  Containers removed: {docker.get('containers_removed', 0)}")
                lines.append(f"  Images removed: {docker.get('images_removed', 0)}")
                lines.append(f"  Space reclaimed: {docker.get('space_reclaimed_mb', 0)} MB")
            else:
                lines.append("Docker: Not available")
            lines.append("")

        # Summary
        lines.append(f"Total space freed: {results.get('total_space_freed_mb', 0)} MB")

        if results.get('errors'):
            lines.append("")
            lines.append("Errors:")
            for err in results['errors']:
                lines.append(f"  - {err}")

        return "\n".join(lines)

    def cleanup_docker(
        self,
        containers: bool = True,
        images: bool = True,
        volumes: bool = False,
        cache: bool = True
    ) -> str:
        """
        Docker-specific cleanup.

        Args:
            containers: Remove stopped containers
            images: Prune dangling images
            volumes: Prune unused volumes (dangerous!)
            cache: Prune build cache

        Returns:
            Docker cleanup report
        """
        results = self.janitor.docker.run_cleanup(
            container_max_age_hours=1,
            prune_images=images,
            prune_volumes=volumes,
            prune_build_cache=cache
        )

        lines = ["=== Docker Cleanup ===", ""]

        if not results.get('docker_available'):
            return "Docker is not available on this system."

        lines.append(f"Containers removed: {results.get('containers_removed', 0)}")
        lines.append(f"Images removed: {results.get('images_removed', 0)}")
        lines.append(f"Volumes removed: {results.get('volumes_removed', 0)}")
        lines.append(f"Build cache cleared: {results.get('cache_cleared', False)}")
        lines.append("")
        lines.append(f"Space reclaimed: {results.get('space_reclaimed_mb', 0)} MB")

        if results.get('errors'):
            lines.append("")
            lines.append("Errors:")
            for err in results['errors']:
                lines.append(f"  - {err}")

        return "\n".join(lines)

    def cleanup_filesystem(
        self,
        temp_hours: int = 24,
        log_days: int = 7,
        cache_days: int = 30
    ) -> str:
        """
        Filesystem-specific cleanup.

        Args:
            temp_hours: Delete temp files older than this
            log_days: Delete logs older than this
            cache_days: Delete cache older than this

        Returns:
            Filesystem cleanup report
        """
        results = self.janitor.filesystem.run_cleanup(
            temp_max_age_hours=temp_hours,
            log_max_age_days=log_days,
            cache_max_age_days=cache_days
        )

        # Also clean execution artifacts
        exec_results = self.janitor.filesystem.clean_execution_artifacts(
            max_age_hours=temp_hours
        )

        lines = ["=== Filesystem Cleanup ===", ""]

        lines.append(f"Temp files deleted: {results.get('temp_files_deleted', 0)}")
        lines.append(f"Log files deleted: {results.get('log_files_deleted', 0)}")
        lines.append(f"Cache files deleted: {results.get('cache_files_deleted', 0)}")
        lines.append(f"Execution artifacts deleted: {exec_results.get('files', 0)}")
        lines.append("")

        total_bytes = (
            results.get('temp_bytes_freed', 0) +
            results.get('log_bytes_freed', 0) +
            results.get('cache_bytes_freed', 0) +
            exec_results.get('bytes', 0)
        )
        total_mb = round(total_bytes / (1024 * 1024), 2)

        lines.append(f"Total space freed: {total_mb} MB")

        if results.get('errors'):
            lines.append("")
            lines.append("Errors:")
            for err in results['errors']:
                lines.append(f"  - {err}")

        return "\n".join(lines)

    def system_status(self) -> str:
        """
        Get complete system status.

        Returns:
            System status report
        """
        return self.janitor.generate_report()

    def disk_usage(self) -> str:
        """
        Get detailed disk usage.

        Returns:
            Disk usage report
        """
        usage = self.janitor.filesystem.get_disk_usage()

        lines = ["=== Crucible Disk Usage ===", ""]

        total_files = 0
        total_mb = 0

        for name, data in usage.items():
            lines.append(f"{name}:")
            lines.append(f"  Files: {data['files']}")
            lines.append(f"  Size: {data['mb']} MB")
            lines.append("")
            total_files += data['files']
            total_mb += data['mb']

        lines.append(f"Total: {total_files} files, {round(total_mb, 2)} MB")

        return "\n".join(lines)

    def docker_status(self) -> str:
        """
        Get Docker status.

        Returns:
            Docker status report
        """
        stats = self.janitor.docker.get_docker_stats()

        lines = ["=== Docker Status ===", ""]

        if not stats.get('available'):
            return "Docker is not available on this system."

        containers = stats.get('containers', {})
        lines.append("Containers:")
        lines.append(f"  Running: {containers.get('running', 0)}")
        lines.append(f"  Stopped: {containers.get('stopped', 0)}")
        lines.append(f"  Total: {containers.get('total', 0)}")
        lines.append("")

        images = stats.get('images', {})
        lines.append("Images:")
        lines.append(f"  Count: {images.get('count', 0)}")
        lines.append(f"  Size: {images.get('size_mb', 0)} MB")
        lines.append("")

        volumes = stats.get('volumes', {})
        lines.append(f"Volumes: {volumes.get('count', 0)}")
        lines.append("")

        system = stats.get('system', {})
        if system:
            lines.append("System Disk Usage:")
            for type_name, data in system.items():
                lines.append(f"  {type_name}: {data.get('size', 'N/A')} (reclaimable: {data.get('reclaimable', 'N/A')})")

        return "\n".join(lines)
