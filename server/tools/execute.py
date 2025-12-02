"""
Execution Tool - Run code in isolated or direct environments.
"""

import asyncio
import subprocess
import tempfile
import os
import json
import shutil
from typing import Optional
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger('crucible.execute')


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    isolated: bool

    def to_string(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"=== Execution {status} ===",
            f"Exit Code: {self.exit_code}",
            f"Duration: {self.duration_ms:.1f}ms",
            f"Isolated: {self.isolated}",
        ]
        if self.stdout.strip():
            lines.append("")
            lines.append("--- STDOUT ---")
            lines.append(self.stdout.strip())
        if self.stderr.strip():
            lines.append("")
            lines.append("--- STDERR ---")
            lines.append(self.stderr.strip())
        return "\n".join(lines)


class ExecutionTool:
    """
    Execute code in various languages with optional isolation.

    Supports:
    - Python
    - Bash
    - JavaScript (Node.js)
    - Go
    """

    # Docker images for isolated execution
    DOCKER_IMAGES = {
        "python": "python:3.11-slim",
        "bash": "ubuntu:22.04",
        "javascript": "node:20-slim",
        "go": "golang:1.21-alpine",
    }

    # File extensions
    EXTENSIONS = {
        "python": ".py",
        "bash": ".sh",
        "javascript": ".js",
        "go": ".go",
    }

    # Execution commands
    COMMANDS = {
        "python": ["python"],
        "bash": ["bash"],
        "javascript": ["node"],
        "go": ["go", "run"],
    }

    def __init__(self, docker_available: Optional[bool] = None):
        """Initialize execution tool."""
        if docker_available is None:
            self.docker_available = self._check_docker()
        else:
            self.docker_available = docker_available

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
        isolated: bool = True
    ) -> str:
        """
        Execute code and return results.

        Args:
            code: Code to execute
            language: Programming language
            timeout: Timeout in seconds
            isolated: Run in Docker container if True

        Returns:
            Formatted execution result string
        """
        if language not in self.COMMANDS:
            return f"Unsupported language: {language}. Supported: {list(self.COMMANDS.keys())}"

        if isolated and self.docker_available:
            result = await self._execute_docker(code, language, timeout)
        else:
            if isolated and not self.docker_available:
                logger.warning("Docker not available, falling back to direct execution")
            result = await self._execute_direct(code, language, timeout)

        return result.to_string()

    async def _execute_direct(
        self,
        code: str,
        language: str,
        timeout: int
    ) -> ExecutionResult:
        """Execute code directly on the host."""
        import time

        # Create temp file with code
        ext = self.EXTENSIONS[language]
        with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            cmd = self.COMMANDS[language] + [temp_path]
            start_time = time.time()

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                exit_code = process.returncode
            except asyncio.TimeoutError:
                process.kill()
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {timeout} seconds",
                    duration_ms=(time.time() - start_time) * 1000,
                    isolated=False
                )

            duration_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                success=exit_code == 0,
                exit_code=exit_code,
                stdout=stdout.decode('utf-8', errors='replace'),
                stderr=stderr.decode('utf-8', errors='replace'),
                duration_ms=duration_ms,
                isolated=False
            )

        finally:
            os.unlink(temp_path)

    async def _execute_docker(
        self,
        code: str,
        language: str,
        timeout: int
    ) -> ExecutionResult:
        """Execute code in Docker container."""
        import time

        image = self.DOCKER_IMAGES[language]
        ext = self.EXTENSIONS[language]

        # Create temp directory with code
        temp_dir = tempfile.mkdtemp()
        code_file = Path(temp_dir) / f"code{ext}"
        code_file.write_text(code)

        try:
            # Build Docker command
            cmd_in_container = self.COMMANDS[language] + [f"/code/code{ext}"]

            docker_cmd = [
                "docker", "run",
                "--rm",                          # Remove container after
                "--network", "none",             # No network access
                "--memory", "256m",              # Memory limit
                "--cpus", "1",                   # CPU limit
                "--read-only",                   # Read-only filesystem
                "--tmpfs", "/tmp:size=64m",      # Temp space
                "-v", f"{temp_dir}:/code:ro",    # Mount code read-only
                "-w", "/code",
                image,
                *cmd_in_container
            ]

            start_time = time.time()

            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout + 10  # Extra time for Docker overhead
                )
                exit_code = process.returncode
            except asyncio.TimeoutError:
                # Kill container
                subprocess.run(["docker", "kill", process.pid], capture_output=True)
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {timeout} seconds",
                    duration_ms=(time.time() - start_time) * 1000,
                    isolated=True
                )

            duration_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                success=exit_code == 0,
                exit_code=exit_code,
                stdout=stdout.decode('utf-8', errors='replace'),
                stderr=stderr.decode('utf-8', errors='replace'),
                duration_ms=duration_ms,
                isolated=True
            )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def execute_bash_command(
        self,
        command: str,
        timeout: int = 30
    ) -> ExecutionResult:
        """Execute a bash command directly (for captures)."""
        import time

        start_time = time.time()

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            exit_code = process.returncode
        except asyncio.TimeoutError:
            process.kill()
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                duration_ms=(time.time() - start_time) * 1000,
                isolated=False
            )

        duration_ms = (time.time() - start_time) * 1000

        return ExecutionResult(
            success=exit_code == 0,
            exit_code=exit_code,
            stdout=stdout.decode('utf-8', errors='replace'),
            stderr=stderr.decode('utf-8', errors='replace'),
            duration_ms=duration_ms,
            isolated=False
        )
