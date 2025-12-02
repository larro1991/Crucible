"""
Filesystem Janitor - Cleanup temp files, logs, and orphaned data.

Handles:
- Temp files from code execution
- Log file rotation/cleanup
- Orphaned fixture files
- Old verification results
- General filesystem hygiene
"""

import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import shutil

logger = logging.getLogger('crucible.maintenance.filesystem')


class FilesystemJanitor:
    """
    Automated filesystem cleanup.

    Responsibilities:
    - Clean temp directories
    - Rotate and trim log files
    - Remove orphaned files
    - Enforce disk usage limits
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)

        # Directories to manage
        self.temp_dir = self.base_path / 'temp'
        self.logs_dir = self.base_path / 'logs'
        self.cache_dir = self.base_path / 'cache'

        # Ensure directories exist
        for d in [self.temp_dir, self.logs_dir, self.cache_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def run_cleanup(
        self,
        temp_max_age_hours: int = 24,
        log_max_age_days: int = 7,
        log_max_size_mb: int = 100,
        cache_max_age_days: int = 30
    ) -> Dict[str, any]:
        """
        Run all filesystem cleanup tasks.

        Args:
            temp_max_age_hours: Delete temp files older than this
            log_max_age_days: Delete logs older than this
            log_max_size_mb: Max total log size before trimming
            cache_max_age_days: Delete cache files older than this

        Returns:
            Cleanup statistics
        """
        results = {
            'temp_files_deleted': 0,
            'temp_bytes_freed': 0,
            'log_files_deleted': 0,
            'log_bytes_freed': 0,
            'cache_files_deleted': 0,
            'cache_bytes_freed': 0,
            'errors': []
        }

        # Clean temp files
        try:
            temp_result = self._clean_temp_files(temp_max_age_hours)
            results['temp_files_deleted'] = temp_result['files']
            results['temp_bytes_freed'] = temp_result['bytes']
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
            results['errors'].append(f"temp: {str(e)}")

        # Clean log files
        try:
            log_result = self._clean_log_files(log_max_age_days, log_max_size_mb)
            results['log_files_deleted'] = log_result['files']
            results['log_bytes_freed'] = log_result['bytes']
        except Exception as e:
            logger.error(f"Error cleaning log files: {e}")
            results['errors'].append(f"logs: {str(e)}")

        # Clean cache files
        try:
            cache_result = self._clean_cache_files(cache_max_age_days)
            results['cache_files_deleted'] = cache_result['files']
            results['cache_bytes_freed'] = cache_result['bytes']
        except Exception as e:
            logger.error(f"Error cleaning cache files: {e}")
            results['errors'].append(f"cache: {str(e)}")

        logger.info(f"Filesystem cleanup complete: {results}")
        return results

    def _clean_temp_files(self, max_age_hours: int) -> Dict[str, int]:
        """Clean temporary files older than max_age_hours."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        return self._delete_old_files(self.temp_dir, cutoff)

    def _clean_log_files(self, max_age_days: int, max_size_mb: int) -> Dict[str, int]:
        """
        Clean log files.

        1. Delete logs older than max_age_days
        2. If total size > max_size_mb, delete oldest until under limit
        """
        result = {'files': 0, 'bytes': 0}

        # Phase 1: Delete old logs
        cutoff = datetime.now() - timedelta(days=max_age_days)
        age_result = self._delete_old_files(self.logs_dir, cutoff, pattern="*.log")
        result['files'] += age_result['files']
        result['bytes'] += age_result['bytes']

        # Phase 2: Enforce size limit
        max_bytes = max_size_mb * 1024 * 1024
        size_result = self._enforce_size_limit(self.logs_dir, max_bytes, pattern="*.log")
        result['files'] += size_result['files']
        result['bytes'] += size_result['bytes']

        return result

    def _clean_cache_files(self, max_age_days: int) -> Dict[str, int]:
        """Clean cache files older than max_age_days."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        return self._delete_old_files(self.cache_dir, cutoff)

    def _delete_old_files(
        self,
        directory: Path,
        cutoff: datetime,
        pattern: str = "*"
    ) -> Dict[str, int]:
        """Delete files older than cutoff datetime."""
        result = {'files': 0, 'bytes': 0}

        if not directory.exists():
            return result

        for file_path in directory.rglob(pattern):
            if not file_path.is_file():
                continue

            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff:
                    size = file_path.stat().st_size
                    file_path.unlink()
                    result['files'] += 1
                    result['bytes'] += size
                    logger.debug(f"Deleted old file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

        return result

    def _enforce_size_limit(
        self,
        directory: Path,
        max_bytes: int,
        pattern: str = "*"
    ) -> Dict[str, int]:
        """Delete oldest files until directory is under size limit."""
        result = {'files': 0, 'bytes': 0}

        if not directory.exists():
            return result

        # Get all matching files with their sizes and mtimes
        files = []
        total_size = 0
        for file_path in directory.rglob(pattern):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    files.append({
                        'path': file_path,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    })
                    total_size += stat.st_size
                except:
                    pass

        if total_size <= max_bytes:
            return result

        # Sort by mtime (oldest first)
        files.sort(key=lambda x: x['mtime'])

        # Delete until under limit
        for f in files:
            if total_size <= max_bytes:
                break

            try:
                f['path'].unlink()
                result['files'] += 1
                result['bytes'] += f['size']
                total_size -= f['size']
                logger.debug(f"Deleted for size limit: {f['path']}")
            except Exception as e:
                logger.warning(f"Failed to delete {f['path']}: {e}")

        return result

    def clean_execution_artifacts(self, max_age_hours: int = 6) -> Dict[str, int]:
        """
        Clean up artifacts from code execution.

        This includes:
        - Temp Python files created for execution
        - Output capture files
        - Verification result files
        """
        result = {'files': 0, 'bytes': 0}
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        # Clean execution temp directory
        exec_temp = self.base_path / 'execution_temp'
        if exec_temp.exists():
            r = self._delete_old_files(exec_temp, cutoff)
            result['files'] += r['files']
            result['bytes'] += r['bytes']

        # Clean verification results
        verify_temp = self.base_path / 'verification_temp'
        if verify_temp.exists():
            r = self._delete_old_files(verify_temp, cutoff)
            result['files'] += r['files']
            result['bytes'] += r['bytes']

        return result

    def get_disk_usage(self) -> Dict[str, any]:
        """Get disk usage statistics for Crucible directories."""
        stats = {}

        directories = {
            'temp': self.temp_dir,
            'logs': self.logs_dir,
            'cache': self.cache_dir,
            'fixtures': self.base_path / 'fixtures',
            'learnings': self.base_path / 'learnings',
            'data': self.base_path / 'data'
        }

        for name, path in directories.items():
            if path.exists():
                total_size = 0
                file_count = 0
                for f in path.rglob('*'):
                    if f.is_file():
                        try:
                            total_size += f.stat().st_size
                            file_count += 1
                        except:
                            pass

                stats[name] = {
                    'files': file_count,
                    'bytes': total_size,
                    'mb': round(total_size / (1024 * 1024), 2)
                }
            else:
                stats[name] = {'files': 0, 'bytes': 0, 'mb': 0}

        return stats

    def create_temp_file(self, prefix: str = "crucible_", suffix: str = "") -> Path:
        """
        Create a temp file that will be auto-cleaned.

        Args:
            prefix: File name prefix
            suffix: File extension

        Returns:
            Path to temp file
        """
        import tempfile
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=self.temp_dir)
        os.close(fd)
        return Path(path)

    def create_temp_dir(self, prefix: str = "crucible_") -> Path:
        """
        Create a temp directory that will be auto-cleaned.

        Args:
            prefix: Directory name prefix

        Returns:
            Path to temp directory
        """
        import tempfile
        return Path(tempfile.mkdtemp(prefix=prefix, dir=self.temp_dir))
