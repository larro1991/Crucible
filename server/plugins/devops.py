"""
DevOps Plugin for Crucible

Provides tools for:
- Docker management (ps, logs, exec, compose)
- File operations (read, write, list)
- Shell execution (with safety limits)

Enable by adding to plugins.json or calling crucible_plugin_load("devops")
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import logging

logger = logging.getLogger('crucible.plugins.devops')

# Import MCP types
try:
    from mcp.types import Tool
except ImportError:
    # Fallback for testing
    class Tool:
        def __init__(self, name, description, inputSchema):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema


# Configuration - set via init() or plugins.json
CONFIG = {
    "allowed_paths": ["/mnt", "/appdata", "/home", "/tmp", "/var/log", "/crucible"],
    "blocked_commands": ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:", "chmod -R 777 /", "chown -R"],
    "docker_enabled": True,
    "max_file_size_mb": 10,
}


def init(settings: Dict[str, Any]):
    """Initialize plugin with settings from plugins.json."""
    global CONFIG
    CONFIG.update(settings)
    logger.info(f"DevOps plugin initialized with: {CONFIG}")


def cleanup():
    """Cleanup when plugin is unloaded."""
    logger.info("DevOps plugin unloaded")


# =============================================================================
# DOCKER TOOLS
# =============================================================================

async def docker_ps(args: Dict[str, Any]) -> str:
    """List Docker containers."""
    if not CONFIG["docker_enabled"]:
        return "Error: Docker tools disabled in plugin config"

    try:
        all_containers = args.get("all", False)
        format_str = args.get("format", "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}")

        cmd = ["docker", "ps"]
        if all_containers:
            cmd.append("-a")
        cmd.extend(["--format", format_str])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        return f"=== Docker Containers ===\n{result.stdout}"

    except FileNotFoundError:
        return "Error: Docker CLI not installed"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"


async def docker_logs(args: Dict[str, Any]) -> str:
    """Get container logs."""
    if not CONFIG["docker_enabled"]:
        return "Error: Docker tools disabled"

    container = args.get("container")
    if not container:
        return "Error: container name required"

    try:
        tail = args.get("tail", 100)
        cmd = ["docker", "logs", "--tail", str(tail), container]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        output = result.stdout + result.stderr
        return f"=== Logs: {container} (last {tail} lines) ===\n{output}"

    except Exception as e:
        return f"Error: {str(e)}"


async def docker_exec(args: Dict[str, Any]) -> str:
    """Execute command in a container."""
    if not CONFIG["docker_enabled"]:
        return "Error: Docker tools disabled"

    container = args.get("container")
    command = args.get("command")

    if not container or not command:
        return "Error: container and command required"

    # Safety check
    for blocked in CONFIG["blocked_commands"]:
        if blocked in command:
            return f"Error: Command blocked for safety: {blocked}"

    try:
        cmd = ["docker", "exec", container, "sh", "-c", command]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        output = result.stdout + result.stderr
        status = "SUCCESS" if result.returncode == 0 else f"FAILED (exit {result.returncode})"

        return f"=== docker exec {container} ===\nStatus: {status}\n\n{output}"

    except subprocess.TimeoutExpired:
        return "Error: Command timed out (60s limit)"
    except Exception as e:
        return f"Error: {str(e)}"


async def docker_compose(args: Dict[str, Any]) -> str:
    """Docker Compose operations."""
    if not CONFIG["docker_enabled"]:
        return "Error: Docker tools disabled"

    action = args.get("action")  # up, down, restart, ps, logs
    path = args.get("path", ".")
    service = args.get("service")

    if action not in ["up", "down", "restart", "ps", "logs", "pull"]:
        return f"Error: Invalid action. Use: up, down, restart, ps, logs, pull"

    # Validate path
    if not _is_path_allowed(path):
        return f"Error: Path not in allowed list: {path}"

    try:
        # Build command
        cmd = ["docker", "compose", "-f", f"{path}/docker-compose.yml"]

        if action == "up":
            cmd.extend(["up", "-d"])
        elif action == "down":
            cmd.append("down")
        elif action == "restart":
            cmd.append("restart")
        elif action == "ps":
            cmd.append("ps")
        elif action == "logs":
            cmd.extend(["logs", "--tail", "50"])
        elif action == "pull":
            cmd.append("pull")

        if service:
            cmd.append(service)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        output = result.stdout + result.stderr
        status = "SUCCESS" if result.returncode == 0 else f"FAILED (exit {result.returncode})"

        return f"=== docker compose {action} ===\nPath: {path}\nStatus: {status}\n\n{output}"

    except subprocess.TimeoutExpired:
        return "Error: Command timed out (120s limit)"
    except Exception as e:
        return f"Error: {str(e)}"


async def docker_inspect(args: Dict[str, Any]) -> str:
    """Inspect a container or image."""
    if not CONFIG["docker_enabled"]:
        return "Error: Docker tools disabled"

    target = args.get("target")
    if not target:
        return "Error: target (container/image name) required"

    try:
        cmd = ["docker", "inspect", target]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        # Parse and format key info
        data = json.loads(result.stdout)
        if data:
            info = data[0]
            summary = {
                "Id": info.get("Id", "")[:12],
                "Name": info.get("Name", "").lstrip("/"),
                "State": info.get("State", {}),
                "Image": info.get("Config", {}).get("Image", ""),
                "Ports": info.get("NetworkSettings", {}).get("Ports", {}),
                "Mounts": [m.get("Source", "") + " -> " + m.get("Destination", "")
                          for m in info.get("Mounts", [])],
            }
            return f"=== Docker Inspect: {target} ===\n{json.dumps(summary, indent=2)}"

        return result.stdout

    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# FILE TOOLS
# =============================================================================

def _is_path_allowed(path: str) -> bool:
    """Check if path is within allowed directories."""
    path = os.path.abspath(path)
    return any(path.startswith(allowed) for allowed in CONFIG["allowed_paths"])


async def file_read(args: Dict[str, Any]) -> str:
    """Read a file."""
    path = args.get("path")
    if not path:
        return "Error: path required"

    if not _is_path_allowed(path):
        return f"Error: Path not allowed. Allowed: {CONFIG['allowed_paths']}"

    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return f"Error: File not found: {path}"

        if not path_obj.is_file():
            return f"Error: Not a file: {path}"

        size_mb = path_obj.stat().st_size / (1024 * 1024)
        if size_mb > CONFIG["max_file_size_mb"]:
            return f"Error: File too large ({size_mb:.1f}MB > {CONFIG['max_file_size_mb']}MB)"

        content = path_obj.read_text()

        # Truncate if too long
        max_chars = args.get("max_chars", 50000)
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n... [truncated, {len(content)} total chars]"

        return f"=== {path} ===\n{content}"

    except Exception as e:
        return f"Error reading file: {str(e)}"


async def file_write(args: Dict[str, Any]) -> str:
    """Write to a file."""
    path = args.get("path")
    content = args.get("content")

    if not path or content is None:
        return "Error: path and content required"

    if not _is_path_allowed(path):
        return f"Error: Path not allowed. Allowed: {CONFIG['allowed_paths']}"

    try:
        path_obj = Path(path)

        # Create parent directories if needed
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Backup existing file
        backup = args.get("backup", True)
        if backup and path_obj.exists():
            backup_path = path_obj.with_suffix(path_obj.suffix + '.bak')
            shutil.copy2(path_obj, backup_path)

        path_obj.write_text(content)

        return f"=== Written: {path} ===\n{len(content)} bytes written"

    except Exception as e:
        return f"Error writing file: {str(e)}"


async def file_list(args: Dict[str, Any]) -> str:
    """List directory contents."""
    path = args.get("path", ".")

    if not _is_path_allowed(path):
        return f"Error: Path not allowed. Allowed: {CONFIG['allowed_paths']}"

    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return f"Error: Path not found: {path}"

        if not path_obj.is_dir():
            return f"Error: Not a directory: {path}"

        entries = []
        for item in sorted(path_obj.iterdir()):
            try:
                stat = item.stat()
                size = stat.st_size if item.is_file() else 0
                type_char = "d" if item.is_dir() else "f"
                entries.append(f"{type_char} {size:>10} {item.name}")
            except PermissionError:
                entries.append(f"? {'???':>10} {item.name}")

        return f"=== {path} ===\n" + "\n".join(entries)

    except Exception as e:
        return f"Error listing directory: {str(e)}"


# =============================================================================
# SHELL TOOLS
# =============================================================================

async def shell_exec(args: Dict[str, Any]) -> str:
    """Execute a shell command (with safety restrictions)."""
    command = args.get("command")
    if not command:
        return "Error: command required"

    # Safety checks
    for blocked in CONFIG["blocked_commands"]:
        if blocked in command:
            return f"Error: Command blocked for safety"

    # Working directory check
    cwd = args.get("cwd", "/tmp")
    if not _is_path_allowed(cwd):
        return f"Error: Working directory not allowed"

    try:
        timeout = min(args.get("timeout", 30), 120)  # Max 2 minutes

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )

        output = result.stdout + result.stderr
        status = "SUCCESS" if result.returncode == 0 else f"EXIT {result.returncode}"

        return f"=== Shell: {command[:50]}{'...' if len(command) > 50 else ''} ===\nStatus: {status}\nCWD: {cwd}\n\n{output}"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out ({timeout}s limit)"
    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOLS = [
    Tool(
        name="crucible_docker_ps",
        description="List Docker containers on the host.",
        inputSchema={
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": "Show all containers (including stopped)",
                    "default": False
                },
                "format": {
                    "type": "string",
                    "description": "Output format (Go template)",
                    "default": "table {{.Names}}\t{{.Status}}\t{{.Image}}"
                }
            }
        }
    ),
    Tool(
        name="crucible_docker_logs",
        description="Get logs from a Docker container.",
        inputSchema={
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name or ID"
                },
                "tail": {
                    "type": "integer",
                    "description": "Number of lines to show",
                    "default": 100
                }
            },
            "required": ["container"]
        }
    ),
    Tool(
        name="crucible_docker_exec",
        description="Execute a command inside a Docker container.",
        inputSchema={
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name or ID"
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                }
            },
            "required": ["container", "command"]
        }
    ),
    Tool(
        name="crucible_docker_compose",
        description="Run docker-compose commands (up, down, restart, ps, logs, pull).",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["up", "down", "restart", "ps", "logs", "pull"],
                    "description": "Compose action to perform"
                },
                "path": {
                    "type": "string",
                    "description": "Path to directory containing docker-compose.yml",
                    "default": "."
                },
                "service": {
                    "type": "string",
                    "description": "Specific service (optional)"
                }
            },
            "required": ["action"]
        }
    ),
    Tool(
        name="crucible_docker_inspect",
        description="Inspect a Docker container or image.",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Container or image name/ID"
                }
            },
            "required": ["target"]
        }
    ),
    Tool(
        name="crucible_file_read",
        description="Read contents of a file on the host.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file"
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return",
                    "default": 50000
                }
            },
            "required": ["path"]
        }
    ),
    Tool(
        name="crucible_file_write",
        description="Write content to a file on the host.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                },
                "backup": {
                    "type": "boolean",
                    "description": "Backup existing file first",
                    "default": True
                }
            },
            "required": ["path", "content"]
        }
    ),
    Tool(
        name="crucible_file_list",
        description="List contents of a directory.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path",
                    "default": "."
                }
            }
        }
    ),
    Tool(
        name="crucible_shell",
        description="Execute a shell command on the host (with safety restrictions).",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory",
                    "default": "/tmp"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (max 120)",
                    "default": 30
                }
            },
            "required": ["command"]
        }
    ),
]

# Handler mapping
HANDLERS = {
    "crucible_docker_ps": docker_ps,
    "crucible_docker_logs": docker_logs,
    "crucible_docker_exec": docker_exec,
    "crucible_docker_compose": docker_compose,
    "crucible_docker_inspect": docker_inspect,
    "crucible_file_read": file_read,
    "crucible_file_write": file_write,
    "crucible_file_list": file_list,
    "crucible_shell": shell_exec,
}
