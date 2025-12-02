"""
Capture Tool - Capture command outputs as fixtures for testing.
"""

import asyncio
from datetime import datetime
from typing import Optional
import logging

from .execute import ExecutionTool
from ..persistence.fixtures import FixtureStore

logger = logging.getLogger('crucible.capture')


class CaptureTool:
    """
    Capture command output and store as fixtures.

    Fixtures can be used for:
    - Testing code against real command outputs
    - Regression testing
    - Documentation of expected formats
    """

    def __init__(self, fixture_store: FixtureStore):
        self.fixture_store = fixture_store
        self.executor = ExecutionTool(docker_available=False)  # Direct execution for captures

    async def capture(
        self,
        command: str,
        name: str,
        category: str = "commands",
        description: str = ""
    ) -> str:
        """
        Run a command and save its output as a fixture.

        Args:
            command: Command to run
            name: Name for the fixture
            category: Category (linux, commands, apis)
            description: Description of what this captures

        Returns:
            Status message
        """
        logger.info(f"Capturing command: {command}")

        # Execute command
        result = await self.executor.execute_bash_command(command, timeout=60)

        if not result.success:
            return f"Command failed (exit {result.exit_code}):\n{result.stderr}"

        # Build fixture metadata
        metadata = {
            "command": command,
            "description": description,
            "captured_at": datetime.utcnow().isoformat() + "Z",
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
        }

        # Save fixture
        self.fixture_store.save(
            name=name,
            category=category,
            content=result.stdout,
            metadata=metadata
        )

        lines_count = len(result.stdout.strip().split('\n'))
        return f"Captured '{name}' in {category}/ ({lines_count} lines, {len(result.stdout)} bytes)"

    async def capture_multiple(
        self,
        commands: dict,
        category: str = "linux"
    ) -> str:
        """
        Capture multiple commands at once.

        Args:
            commands: Dict of {name: command}
            category: Category for all captures

        Returns:
            Status summary
        """
        results = []

        for name, command in commands.items():
            try:
                msg = await self.capture(command, name, category)
                results.append(f"✓ {name}: {msg}")
            except Exception as e:
                results.append(f"✗ {name}: {str(e)}")

        return "\n".join(results)


# Common Linux captures for bootstrapping
LINUX_CAPTURES = {
    "lspci": "lspci -mm -nn -k",
    "lsusb": "lsusb",
    "lscpu": "lscpu",
    "cpuinfo": "cat /proc/cpuinfo",
    "meminfo": "cat /proc/meminfo",
    "lsblk": "lsblk -d -o NAME,SIZE,TYPE,MODEL,VENDOR,RM,TRAN -n -b",
    "ip_link": "ip link show",
    "uname": "uname -a",
    "os_release": "cat /etc/os-release",
    "dmi_system": "cat /sys/class/dmi/id/sys_vendor 2>/dev/null; cat /sys/class/dmi/id/product_name 2>/dev/null",
}
