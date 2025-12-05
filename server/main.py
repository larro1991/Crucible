#!/usr/bin/env python3
"""
Crucible MCP Server

Main entry point for the Crucible MCP server that provides
AI development verification infrastructure.

Usage:
    python -m server.main
    python -m server.main --host 0.0.0.0 --port 8080
"""

import asyncio
import argparse
import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        CallToolResult,
    )
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("Warning: MCP SDK not installed. Install with: pip install mcp")

# Local imports
from .tools.execute import ExecutionTool
from .tools.verify import VerificationTool
from .tools.capture import CaptureTool
from .tools.learn import LearningsTool
from .tools.memory import MemoryTools
from .tools.maintenance import MaintenanceTools
from .persistence.fixtures import FixtureStore
from .persistence.learnings import LearningsStore
from .memory.manager import MemoryManager
from .memory.janitor import MemoryJanitor
from .plugins import get_plugin_manager
from .tools.robust_session import TOOLS as ROBUST_SESSION_TOOLS, HANDLERS as ROBUST_SESSION_HANDLERS, get_all_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crucible')

# Paths
BASE_DIR = Path(__file__).parent.parent
FIXTURES_DIR = BASE_DIR / 'fixtures'
LEARNINGS_DIR = BASE_DIR / 'learnings'
DATA_DIR = BASE_DIR / 'data'  # For memory system


class CrucibleServer:
    """
    Crucible MCP Server

    Provides tools for:
    - Code execution in isolated environments
    - Verification (syntax, imports, types, lint, security)
    - Fixture capture and management
    - Persistent learnings across sessions
    - Memory system (session, episodic, semantic, working)
    - System maintenance (filesystem, Docker, memory cleanup)
    """

    def __init__(self):
        self.fixture_store = FixtureStore(FIXTURES_DIR)
        self.learnings_store = LearningsStore(LEARNINGS_DIR)
        self.memory_manager = MemoryManager(DATA_DIR)

        # Create memory janitor for maintenance integration
        self.memory_janitor = MemoryJanitor(
            self.memory_manager.session,
            self.memory_manager.episodic,
            self.memory_manager.semantic,
            self.memory_manager.working
        )

        self.execution_tool = ExecutionTool()
        self.verification_tool = VerificationTool()
        self.capture_tool = CaptureTool(self.fixture_store)
        self.learnings_tool = LearningsTool(self.learnings_store)
        self.memory_tools = MemoryTools(self.memory_manager)
        self.maintenance_tools = MaintenanceTools(BASE_DIR, self.memory_janitor)

        # Plugin system
        self.plugin_manager = get_plugin_manager()
        self.plugin_manager.load_enabled_plugins()

        if HAS_MCP:
            self.server = Server("crucible")
            self._register_handlers()

    def _register_handlers(self):
        """Register MCP tool handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="crucible_execute",
                    description="Execute code or commands in an isolated environment. Use this to test code before delivering to user.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Code to execute"
                            },
                            "language": {
                                "type": "string",
                                "enum": ["python", "bash", "javascript", "go"],
                                "description": "Programming language",
                                "default": "python"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Timeout in seconds",
                                "default": 30
                            },
                            "isolated": {
                                "type": "boolean",
                                "description": "Run in Docker container for isolation",
                                "default": True
                            }
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="crucible_verify",
                    description="Verify code for syntax errors, import issues, type problems, and security concerns.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Code to verify"
                            },
                            "language": {
                                "type": "string",
                                "enum": ["python", "javascript", "go"],
                                "description": "Programming language",
                                "default": "python"
                            },
                            "checks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Checks to run: syntax, imports, types, lint, security",
                                "default": ["syntax", "imports"]
                            }
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="crucible_capture",
                    description="Capture output from a command as a fixture for testing.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Command to run and capture"
                            },
                            "name": {
                                "type": "string",
                                "description": "Name for the fixture"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category (linux, commands, apis)",
                                "default": "commands"
                            },
                            "description": {
                                "type": "string",
                                "description": "Description of what this fixture contains"
                            }
                        },
                        "required": ["command", "name"]
                    }
                ),
                Tool(
                    name="crucible_fixture",
                    description="Retrieve a stored fixture for testing.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the fixture"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category to search in"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="crucible_note",
                    description="Store a learning or note for future reference across sessions.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "Topic/category for this learning"
                            },
                            "title": {
                                "type": "string",
                                "description": "Brief title"
                            },
                            "content": {
                                "type": "string",
                                "description": "The learning content"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags for searching"
                            },
                            "project": {
                                "type": "string",
                                "description": "Related project (ember, cinder, intuitive-os)"
                            }
                        },
                        "required": ["topic", "title", "content"]
                    }
                ),
                Tool(
                    name="crucible_recall",
                    description="Retrieve stored learnings by topic, tag, or search.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "Topic to retrieve"
                            },
                            "tag": {
                                "type": "string",
                                "description": "Tag to filter by"
                            },
                            "search": {
                                "type": "string",
                                "description": "Search term"
                            },
                            "project": {
                                "type": "string",
                                "description": "Filter by project"
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_list_fixtures",
                    description="List all available fixtures.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Category to list (optional)"
                            }
                        }
                    }
                ),
                # Memory System Tools
                Tool(
                    name="crucible_session_start",
                    description="Start a new memory session. Call this at the beginning of work to enable context tracking.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "description": "Project name (ember, cinder, intuitive-os, etc.)"
                            },
                            "project_path": {
                                "type": "string",
                                "description": "Path to project directory"
                            },
                            "goal": {
                                "type": "string",
                                "description": "Primary goal for this session"
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_session_resume",
                    description="Resume a previous session to restore context.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "ID of session to resume"
                            }
                        },
                        "required": ["session_id"]
                    }
                ),
                Tool(
                    name="crucible_session_end",
                    description="End current session and save to long-term memory.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "quality_score": {
                                "type": "number",
                                "description": "Self-assessment of session quality (0-1)"
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_session_status",
                    description="Get current session status and context.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="crucible_remember",
                    description="Store something in memory (file read, decision, problem, insight, error).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "what": {
                                "type": "string",
                                "description": "What to remember"
                            },
                            "category": {
                                "type": "string",
                                "enum": ["file", "decision", "problem", "insight", "error", "note"],
                                "description": "Type of memory",
                                "default": "note"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context"
                            }
                        },
                        "required": ["what"]
                    }
                ),
                Tool(
                    name="crucible_recall",
                    description="Retrieve information from memory by search or filters.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search term"
                            },
                            "category": {
                                "type": "string",
                                "description": "Filter by category"
                            },
                            "project": {
                                "type": "string",
                                "description": "Filter by project"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum results",
                                "default": 10
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_recall_project",
                    description="Get all context and history for a specific project.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "description": "Project name"
                            }
                        },
                        "required": ["project"]
                    }
                ),
                Tool(
                    name="crucible_learn",
                    description="Learn a fact about a codebase, tool, or pattern.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "subject": {
                                "type": "string",
                                "description": "What the fact is about"
                            },
                            "fact": {
                                "type": "string",
                                "description": "The fact to learn"
                            },
                            "category": {
                                "type": "string",
                                "enum": ["codebase", "user", "tool", "api", "pattern"],
                                "description": "Type of knowledge",
                                "default": "codebase"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "How confident (0-1)",
                                "default": 1.0
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags for searching"
                            }
                        },
                        "required": ["subject", "fact"]
                    }
                ),
                Tool(
                    name="crucible_learn_preference",
                    description="Learn a user preference for future sessions.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "preference": {
                                "type": "string",
                                "description": "Preference name"
                            },
                            "value": {
                                "type": "string",
                                "description": "Preference value"
                            }
                        },
                        "required": ["preference", "value"]
                    }
                ),
                Tool(
                    name="crucible_context",
                    description="Get current context including session, working memory, and user preferences.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="crucible_reflect",
                    description="Get a full summary of all memory systems.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="crucible_task_start",
                    description="Start a task within the current session to enable working memory.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What we're trying to accomplish"
                            }
                        },
                        "required": ["description"]
                    }
                ),
                Tool(
                    name="crucible_task_complete",
                    description="Complete the current task.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Completion summary"
                            }
                        }
                    }
                ),
                # Maintenance Tools
                Tool(
                    name="crucible_maintenance",
                    description="Run memory maintenance (archive old sessions, decay stale facts, cleanup).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "archive_days": {
                                "type": "integer",
                                "description": "Archive sessions older than this many days",
                                "default": 7
                            },
                            "decay_days": {
                                "type": "integer",
                                "description": "Decay facts unverified for this many days",
                                "default": 30
                            },
                            "cleanup_days": {
                                "type": "integer",
                                "description": "Clean up working memory older than this",
                                "default": 3
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_memory_stats",
                    description="Get memory usage statistics.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                # System Maintenance Tools
                Tool(
                    name="crucible_cleanup",
                    description="Run system cleanup (memory, filesystem, Docker). Modes: 'quick' (safe, frequent), 'deep' (weekly), 'full' (aggressive).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["quick", "deep", "full"],
                                "description": "Cleanup mode",
                                "default": "quick"
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_cleanup_docker",
                    description="Docker-specific cleanup: containers, images, volumes, build cache.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "containers": {
                                "type": "boolean",
                                "description": "Remove stopped containers",
                                "default": True
                            },
                            "images": {
                                "type": "boolean",
                                "description": "Prune dangling images",
                                "default": True
                            },
                            "volumes": {
                                "type": "boolean",
                                "description": "Prune unused volumes (DANGEROUS!)",
                                "default": False
                            },
                            "cache": {
                                "type": "boolean",
                                "description": "Prune build cache",
                                "default": True
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_cleanup_filesystem",
                    description="Filesystem cleanup: temp files, logs, cache, execution artifacts.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "temp_hours": {
                                "type": "integer",
                                "description": "Delete temp files older than this many hours",
                                "default": 24
                            },
                            "log_days": {
                                "type": "integer",
                                "description": "Delete logs older than this many days",
                                "default": 7
                            },
                            "cache_days": {
                                "type": "integer",
                                "description": "Delete cache older than this many days",
                                "default": 30
                            }
                        }
                    }
                ),
                Tool(
                    name="crucible_system_status",
                    description="Get complete system status (disk usage, Docker stats, memory stats).",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="crucible_disk_usage",
                    description="Get detailed disk usage for Crucible directories.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="crucible_docker_status",
                    description="Get Docker resource status (containers, images, volumes).",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                # Plugin Management Tools
                Tool(
                    name="crucible_plugin_list",
                    description="List available and loaded plugins.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="crucible_plugin_load",
                    description="Load a plugin to add new tools.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Plugin name (e.g., 'devops')"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="crucible_plugin_unload",
                    description="Unload a plugin to remove its tools.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Plugin name to unload"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="crucible_plugin_reload",
                    description="Reload a plugin (picks up code changes).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Plugin name to reload"
                            }
                        },
                        "required": ["name"]
                    }
                ),
            ] + get_all_tools() + self.plugin_manager.get_tools()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            try:
                result = await self._handle_tool(name, arguments)
                return CallToolResult(
                    content=[TextContent(type="text", text=result)]
                )
            except Exception as e:
                logger.exception(f"Tool {name} failed")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: {str(e)}")]
                )

    async def _handle_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Route tool calls to appropriate handlers."""

        if name == "crucible_execute":
            return await self.execution_tool.execute(
                code=args["code"],
                language=args.get("language", "python"),
                timeout=args.get("timeout", 30),
                isolated=args.get("isolated", True)
            )

        elif name == "crucible_verify":
            return await self.verification_tool.verify(
                code=args["code"],
                language=args.get("language", "python"),
                checks=args.get("checks", ["syntax", "imports"])
            )

        elif name == "crucible_capture":
            return await self.capture_tool.capture(
                command=args["command"],
                name=args["name"],
                category=args.get("category", "commands"),
                description=args.get("description", "")
            )

        elif name == "crucible_fixture":
            return self.fixture_store.get(
                name=args["name"],
                category=args.get("category")
            )

        elif name == "crucible_note":
            return self.learnings_tool.note(
                topic=args["topic"],
                title=args["title"],
                content=args["content"],
                tags=args.get("tags", []),
                project=args.get("project")
            )

        elif name == "crucible_recall":
            return self.learnings_tool.recall(
                topic=args.get("topic"),
                tag=args.get("tag"),
                search=args.get("search"),
                project=args.get("project")
            )

        elif name == "crucible_list_fixtures":
            return self.fixture_store.list_fixtures(
                category=args.get("category")
            )

        # Memory System Tools
        elif name == "crucible_session_start":
            return self.memory_tools.session_start(
                project=args.get("project"),
                project_path=args.get("project_path"),
                goal=args.get("goal")
            )

        elif name == "crucible_session_resume":
            return self.memory_tools.session_resume(
                session_id=args["session_id"]
            )

        elif name == "crucible_session_end":
            return self.memory_tools.session_end(
                quality_score=args.get("quality_score")
            )

        elif name == "crucible_session_status":
            return self.memory_tools.session_status()

        elif name == "crucible_remember":
            return self.memory_tools.remember(
                what=args["what"],
                category=args.get("category", "note"),
                context=args.get("context")
            )

        elif name == "crucible_recall":
            return self.memory_tools.recall(
                query=args.get("query"),
                category=args.get("category"),
                project=args.get("project"),
                limit=args.get("limit", 10)
            )

        elif name == "crucible_recall_project":
            return self.memory_tools.recall_project(
                project=args["project"]
            )

        elif name == "crucible_learn":
            return self.memory_tools.learn(
                subject=args["subject"],
                fact=args["fact"],
                category=args.get("category", "codebase"),
                confidence=args.get("confidence", 1.0),
                tags=args.get("tags")
            )

        elif name == "crucible_learn_preference":
            return self.memory_tools.learn_preference(
                preference=args["preference"],
                value=args["value"]
            )

        elif name == "crucible_context":
            return self.memory_tools.context()

        elif name == "crucible_reflect":
            return self.memory_tools.reflect()

        elif name == "crucible_task_start":
            return self.memory_tools.task_start(
                description=args["description"]
            )

        elif name == "crucible_task_complete":
            return self.memory_tools.task_complete(
                summary=args.get("summary")
            )

        # Maintenance Tools
        elif name == "crucible_maintenance":
            return self.memory_tools.maintenance(
                archive_days=args.get("archive_days", 7),
                decay_days=args.get("decay_days", 30),
                cleanup_days=args.get("cleanup_days", 3)
            )

        elif name == "crucible_memory_stats":
            return self.memory_tools.memory_stats()

        # System Maintenance Tools
        elif name == "crucible_cleanup":
            return self.maintenance_tools.cleanup(
                mode=args.get("mode", "quick")
            )

        elif name == "crucible_cleanup_docker":
            return self.maintenance_tools.cleanup_docker(
                containers=args.get("containers", True),
                images=args.get("images", True),
                volumes=args.get("volumes", False),
                cache=args.get("cache", True)
            )

        elif name == "crucible_cleanup_filesystem":
            return self.maintenance_tools.cleanup_filesystem(
                temp_hours=args.get("temp_hours", 24),
                log_days=args.get("log_days", 7),
                cache_days=args.get("cache_days", 30)
            )

        elif name == "crucible_system_status":
            return self.maintenance_tools.system_status()

        elif name == "crucible_disk_usage":
            return self.maintenance_tools.disk_usage()

        elif name == "crucible_docker_status":
            return self.maintenance_tools.docker_status()

        # Plugin Management Tools
        elif name == "crucible_plugin_list":
            return self.plugin_manager.status()

        elif name == "crucible_plugin_load":
            plugin_name = args.get("name")
            if not plugin_name:
                return "Error: plugin name required"
            success = self.plugin_manager.load_plugin(plugin_name)
            if success:
                return f"Plugin '{plugin_name}' loaded successfully.\n\n{self.plugin_manager.status()}"
            return f"Failed to load plugin '{plugin_name}'"

        elif name == "crucible_plugin_unload":
            plugin_name = args.get("name")
            if not plugin_name:
                return "Error: plugin name required"
            success = self.plugin_manager.unload_plugin(plugin_name)
            if success:
                return f"Plugin '{plugin_name}' unloaded.\n\n{self.plugin_manager.status()}"
            return f"Failed to unload plugin '{plugin_name}'"

        elif name == "crucible_plugin_reload":
            plugin_name = args.get("name")
            if not plugin_name:
                return "Error: plugin name required"
            success = self.plugin_manager.reload_plugin(plugin_name)
            if success:
                return f"Plugin '{plugin_name}' reloaded.\n\n{self.plugin_manager.status()}"
            return f"Failed to reload plugin '{plugin_name}'"

        # Check robust session handlers
        elif name in ROBUST_SESSION_HANDLERS:
            handler = ROBUST_SESSION_HANDLERS[name]
            return await handler(args)

        else:
            # Check if plugin can handle this tool
            result = await self.plugin_manager.handle_tool(name, args)
            if result is not None:
                return result
            return f"Unknown tool: {name}"

    async def run_stdio(self):
        """Run server using stdio transport (for Claude Code integration)."""
        if not HAS_MCP:
            raise RuntimeError("MCP SDK not installed")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

    async def run_http(self, host: str = "0.0.0.0", port: int = 8080):
        """Run server as HTTP endpoint (for remote access)."""
        # Future: Implement HTTP transport
        raise NotImplementedError("HTTP transport not yet implemented")


def main():
    parser = argparse.ArgumentParser(description="Crucible MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                       help="Transport method")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    server = CrucibleServer()

    if args.transport == "stdio":
        asyncio.run(server.run_stdio())
    else:
        asyncio.run(server.run_http(args.host, args.port))


if __name__ == "__main__":
    main()
