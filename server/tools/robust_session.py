"""
MCP Tools for Robust Session Management

Provides tools for:
- Starting/resuming sessions that survive connection drops
- Tracking operations with state machine
- Manual checkpointing
- Recovery and status queries
"""

from mcp.types import Tool


# Tool definitions
TOOLS = [
    Tool(
        name="crucible_robust_start",
        description="""Start a new robust session that survives connection drops.

This creates a session with:
- Operation tracking (all operations logged with state machine)
- Write-ahead logging (operations logged BEFORE execution)
- Automatic checkpointing (state saved periodically)
- Heartbeat monitoring (detect connection drops)

If connection drops, use crucible_robust_resume to recover.""",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name"
                },
                "project_path": {
                    "type": "string",
                    "description": "Path to project directory"
                },
                "goal": {
                    "type": "string",
                    "description": "Session goal/objective"
                },
                "context": {
                    "type": "object",
                    "description": "Optional initial context to persist"
                }
            },
            "required": ["project", "project_path", "goal"]
        }
    ),
    Tool(
        name="crucible_robust_resume",
        description="""Resume a session after connection drop.

Automatically:
- Recovers last session state from checkpoint
- Identifies interrupted operations
- Finds uncommitted operations from WAL
- Restores working context

Call this at the start of a new connection to recover previous work.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Specific session ID to resume. If not provided, resumes the most recent session."
                }
            }
        }
    ),
    Tool(
        name="crucible_robust_status",
        description="""Get comprehensive status of current robust session.

Returns:
- Session info (project, goal, status, uptime)
- Operation counts by state (queued, in_progress, completed, failed)
- WAL statistics
- Checkpoint status
- Recovery information""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="crucible_robust_checkpoint",
        description="""Force an immediate checkpoint of session state.

Use this before risky operations or when you want to ensure
state is persisted immediately.

Checkpoints capture:
- Full session state
- All operation statuses
- Working context
- WAL sequence number""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="crucible_robust_end",
        description="""End the current robust session.

Creates final checkpoint and marks session as completed.
Use this when work is done.""",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Optional summary of what was accomplished"
                }
            }
        }
    ),
    Tool(
        name="crucible_op_status",
        description="""Get status of a specific tracked operation.

Returns operation details including:
- State (queued, in_progress, completed, failed)
- Arguments
- Result or error
- Timing information
- Retry count""",
        inputSchema={
            "type": "object",
            "properties": {
                "op_id": {
                    "type": "string",
                    "description": "Operation ID to query"
                }
            },
            "required": ["op_id"]
        }
    ),
    Tool(
        name="crucible_op_list",
        description="""List operations by state or get history.

Can filter by:
- pending: Operations waiting to execute
- failed: Failed operations (optionally only retryable)
- history: Recent operation history""",
        inputSchema={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "enum": ["pending", "failed", "failed_retryable", "history"],
                    "description": "Filter operations by state"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number to return (default 50)"
                }
            },
            "required": ["filter"]
        }
    ),
    Tool(
        name="crucible_op_retry",
        description="""Retry a failed operation.

Only works for operations that:
- Are in 'failed' state
- Have not exceeded max_retries

Operation will be re-queued for execution.""",
        inputSchema={
            "type": "object",
            "properties": {
                "op_id": {
                    "type": "string",
                    "description": "Operation ID to retry"
                }
            },
            "required": ["op_id"]
        }
    ),
    Tool(
        name="crucible_op_cancel",
        description="""Cancel a pending operation.

Only works for operations in 'queued' or 'recovering' state.
Cannot cancel operations that are already in_progress.""",
        inputSchema={
            "type": "object",
            "properties": {
                "op_id": {
                    "type": "string",
                    "description": "Operation ID to cancel"
                }
            },
            "required": ["op_id"]
        }
    ),
    Tool(
        name="crucible_context_set",
        description="""Store a value in session context.

Context is persisted with checkpoints and survives connection drops.
Use this for important state you need to recover.""",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Context key"
                },
                "value": {
                    "type": ["string", "number", "boolean", "object", "array"],
                    "description": "Value to store"
                }
            },
            "required": ["key", "value"]
        }
    ),
    Tool(
        name="crucible_context_get",
        description="""Get a value from session context.""",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Context key to retrieve"
                }
            },
            "required": ["key"]
        }
    ),
    Tool(
        name="crucible_sessions_list",
        description="""List available robust sessions.

Shows recent sessions with their status, useful for finding
sessions to resume.""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number to return (default 10)"
                }
            }
        }
    ),
    # Session Management Tools
    Tool(
        name="crucible_session_rename",
        description="""Rename a session (set a user-friendly display name).

Works on both the current session and past sessions.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to rename"
                },
                "name": {
                    "type": "string",
                    "description": "New display name for the session"
                }
            },
            "required": ["session_id", "name"]
        }
    ),
    Tool(
        name="crucible_session_search",
        description="""Search sessions with filters.

Can search by:
- query: Text search in name, goal, project
- tags: Filter by session tags
- project: Filter by project name
- status: Filter by status (active, completed, etc.)""",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to filter by"
                },
                "project": {
                    "type": "string",
                    "description": "Project name to filter by"
                },
                "status": {
                    "type": "string",
                    "description": "Status to filter by"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 20)"
                }
            }
        }
    ),
    Tool(
        name="crucible_session_delete",
        description="""Delete a session permanently.

Cannot delete the currently active session.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to delete"
                }
            },
            "required": ["session_id"]
        }
    ),
    # GitHub Connection Tools
    Tool(
        name="crucible_github_connect",
        description="""Connect the current session to a GitHub repository.

Stores the repository information with the session for context.""",
        inputSchema={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "GitHub repository URL (e.g., https://github.com/user/repo)"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (default: main)"
                }
            },
            "required": ["repo_url"]
        }
    ),
    Tool(
        name="crucible_github_disconnect",
        description="""Disconnect GitHub from the current session.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="crucible_github_info",
        description="""Get GitHub connection info for the current session.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    # Document Management Tools
    Tool(
        name="crucible_doc_add",
        description="""Add a document to the current session.

Documents can be files, URLs, or text snippets that provide context.""",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Display name for the document"
                },
                "path": {
                    "type": "string",
                    "description": "File path or URL"
                },
                "doc_type": {
                    "type": "string",
                    "enum": ["file", "url", "text"],
                    "description": "Type of document (default: file)"
                },
                "description": {
                    "type": "string",
                    "description": "Description of what the document contains"
                }
            },
            "required": ["name", "path"]
        }
    ),
    Tool(
        name="crucible_doc_remove",
        description="""Remove a document from the current session.""",
        inputSchema={
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "Document ID to remove"
                }
            },
            "required": ["doc_id"]
        }
    ),
    Tool(
        name="crucible_doc_list",
        description="""List all documents attached to the current session.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    # Tag Management Tools
    Tool(
        name="crucible_tags_add",
        description="""Add tags to the current session for organization.""",
        inputSchema={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to add"
                }
            },
            "required": ["tags"]
        }
    ),
    Tool(
        name="crucible_tags_remove",
        description="""Remove tags from the current session.""",
        inputSchema={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to remove"
                }
            },
            "required": ["tags"]
        }
    ),
    # Template Tools
    Tool(
        name="crucible_template_list",
        description="""List available session templates.

Built-in templates: blank, bugfix, feature, refactor, research, review, ops""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="crucible_template_use",
        description="""Start a new session from a template.""",
        inputSchema={
            "type": "object",
            "properties": {
                "template_id": {
                    "type": "string",
                    "description": "Template ID to use"
                },
                "project": {
                    "type": "string",
                    "description": "Project name"
                },
                "project_path": {
                    "type": "string",
                    "description": "Path to project"
                },
                "goal_vars": {
                    "type": "object",
                    "description": "Variables to fill in the goal template"
                }
            },
            "required": ["template_id", "project", "project_path"]
        }
    ),
    Tool(
        name="crucible_template_create",
        description="""Create a new custom template.""",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Template name"
                },
                "description": {
                    "type": "string",
                    "description": "What this template is for"
                },
                "goal_template": {
                    "type": "string",
                    "description": "Goal with {placeholders}"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Default tags"
                }
            },
            "required": ["name", "description"]
        }
    ),
    Tool(
        name="crucible_template_from_session",
        description="""Create a template from an existing session.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to create template from"
                },
                "name": {
                    "type": "string",
                    "description": "Name for the new template"
                }
            },
            "required": ["session_id", "name"]
        }
    ),
    # Export/Import Tools
    Tool(
        name="crucible_session_export",
        description="""Export a session to a JSON file for backup.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to export"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (optional)"
                },
                "include_checkpoints": {
                    "type": "boolean",
                    "description": "Include checkpoint data (default: true)"
                }
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="crucible_session_import",
        description="""Import a session from an exported JSON file.""",
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Path to exported session file"
                },
                "new_session_id": {
                    "type": "string",
                    "description": "Optional new session ID"
                }
            },
            "required": ["input_path"]
        }
    ),
    Tool(
        name="crucible_session_clone",
        description="""Clone an existing session as a new session.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to clone"
                },
                "new_goal": {
                    "type": "string",
                    "description": "Goal for the cloned session"
                }
            },
            "required": ["session_id"]
        }
    ),
    # Analytics Tools
    Tool(
        name="crucible_analytics_summary",
        description="""Get overall session analytics and statistics.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="crucible_analytics_project",
        description="""Get analytics for a specific project.""",
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
        name="crucible_analytics_timeline",
        description="""Get session activity timeline.""",
        inputSchema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 30)"
                }
            }
        }
    ),
    Tool(
        name="crucible_analytics_tags",
        description="""Get tag usage analysis across all sessions.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
]


async def handle_robust_start(args: dict) -> str:
    """Handle crucible_robust_start tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()

    result = await manager.start_session(
        project=args['project'],
        project_path=args['project_path'],
        goal=args['goal'],
        context=args.get('context')
    )

    return json.dumps(result, indent=2)


async def handle_robust_resume(args: dict) -> str:
    """Handle crucible_robust_resume tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()

    result = await manager.resume_session(
        session_id=args.get('session_id')
    )

    return json.dumps(result, indent=2)


async def handle_robust_status(args: dict) -> str:
    """Handle crucible_robust_status tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.get_status()

    return json.dumps(result, indent=2)


async def handle_robust_checkpoint(args: dict) -> str:
    """Handle crucible_robust_checkpoint tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = await manager.force_checkpoint()

    return json.dumps(result, indent=2)


async def handle_robust_end(args: dict) -> str:
    """Handle crucible_robust_end tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = await manager.end_session(
        summary=args.get('summary')
    )

    return json.dumps(result, indent=2)


async def handle_op_status(args: dict) -> str:
    """Handle crucible_op_status tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.get_operation_status(args['op_id'])

    if result:
        return json.dumps(result, indent=2)
    return json.dumps({'error': f"Operation {args['op_id']} not found"})


async def handle_op_list(args: dict) -> str:
    """Handle crucible_op_list tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    filter_type = args['filter']
    limit = args.get('limit', 50)

    if filter_type == 'pending':
        result = manager.get_pending_operations()
    elif filter_type == 'failed':
        result = manager.get_failed_operations(retryable_only=False)
    elif filter_type == 'failed_retryable':
        result = manager.get_failed_operations(retryable_only=True)
    elif filter_type == 'history':
        result = manager.get_operation_history(limit)
    else:
        return json.dumps({'error': f'Unknown filter: {filter_type}'})

    return json.dumps(result[:limit], indent=2)


async def handle_op_retry(args: dict) -> str:
    """Handle crucible_op_retry tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = await manager.retry_operation(args['op_id'])

    return json.dumps(result, indent=2)


async def handle_op_cancel(args: dict) -> str:
    """Handle crucible_op_cancel tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.cancel_operation(args['op_id'])

    return json.dumps(result, indent=2)


async def handle_context_set(args: dict) -> str:
    """Handle crucible_context_set tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    manager.update_context(args['key'], args['value'])

    return json.dumps({
        'status': 'stored',
        'key': args['key']
    })


async def handle_context_get(args: dict) -> str:
    """Handle crucible_context_get tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    value = manager.get_context(args['key'])

    return json.dumps({
        'key': args['key'],
        'value': value,
        'found': value is not None
    })


async def handle_sessions_list(args: dict) -> str:
    """Handle crucible_sessions_list tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    limit = args.get('limit', 10)
    result = manager.list_sessions(limit)

    return json.dumps(result, indent=2)


# Session Management Handlers
async def handle_session_rename(args: dict) -> str:
    """Handle crucible_session_rename tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.rename_session(args['session_id'], args['name'])

    return json.dumps(result, indent=2)


async def handle_session_search(args: dict) -> str:
    """Handle crucible_session_search tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.search_sessions(
        query=args.get('query'),
        tags=args.get('tags'),
        project=args.get('project'),
        status=args.get('status'),
        limit=args.get('limit', 20)
    )

    return json.dumps(result, indent=2)


async def handle_session_delete(args: dict) -> str:
    """Handle crucible_session_delete tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.delete_session(args['session_id'])

    return json.dumps(result, indent=2)


# GitHub Connection Handlers
async def handle_github_connect(args: dict) -> str:
    """Handle crucible_github_connect tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.connect_github(
        repo_url=args['repo_url'],
        branch=args.get('branch', 'main')
    )

    return json.dumps(result, indent=2)


async def handle_github_disconnect(args: dict) -> str:
    """Handle crucible_github_disconnect tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.disconnect_github()

    return json.dumps(result, indent=2)


async def handle_github_info(args: dict) -> str:
    """Handle crucible_github_info tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.get_github_info()

    if result:
        return json.dumps(result, indent=2)
    return json.dumps({'status': 'not_connected'})


# Document Management Handlers
async def handle_doc_add(args: dict) -> str:
    """Handle crucible_doc_add tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.add_document(
        name=args['name'],
        path=args['path'],
        doc_type=args.get('doc_type', 'file'),
        description=args.get('description', '')
    )

    return json.dumps(result, indent=2)


async def handle_doc_remove(args: dict) -> str:
    """Handle crucible_doc_remove tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.remove_document(args['doc_id'])

    return json.dumps(result, indent=2)


async def handle_doc_list(args: dict) -> str:
    """Handle crucible_doc_list tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.list_documents()

    return json.dumps(result, indent=2)


# Tag Management Handlers
async def handle_tags_add(args: dict) -> str:
    """Handle crucible_tags_add tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.add_tags(args['tags'])

    return json.dumps(result, indent=2)


async def handle_tags_remove(args: dict) -> str:
    """Handle crucible_tags_remove tool"""
    from ..session import get_robust_session_manager
    import json

    manager = get_robust_session_manager()
    result = manager.remove_tags(args['tags'])

    return json.dumps(result, indent=2)


# Template Handlers
async def handle_template_list(args: dict) -> str:
    """Handle crucible_template_list tool"""
    from ..session.templates import get_template_manager
    import json

    tm = get_template_manager()
    result = tm.list_templates()
    return json.dumps(result, indent=2)


async def handle_template_use(args: dict) -> str:
    """Handle crucible_template_use tool"""
    from ..session import get_robust_session_manager
    from ..session.templates import get_template_manager
    import json

    tm = get_template_manager()
    manager = get_robust_session_manager()

    template = tm.get_template(args['template_id'])
    if not template:
        return json.dumps({'status': 'error', 'error': 'Template not found'})

    # Fill in goal template
    goal = template.goal_template
    if args.get('goal_vars'):
        try:
            goal = goal.format(**args['goal_vars'])
        except KeyError as e:
            goal = template.goal_template  # Use as-is if vars missing

    result = await manager.start_session(
        project=args['project'],
        project_path=args['project_path'],
        goal=goal or f"Session from template: {template.name}",
        context=template.context.copy()
    )

    # Add template tags
    if template.tags:
        manager.add_tags(template.tags)

    # Connect GitHub if specified
    if template.github_repo:
        manager.connect_github(template.github_repo)

    tm.record_use(args['template_id'])

    result['template'] = template.name
    return json.dumps(result, indent=2)


async def handle_template_create(args: dict) -> str:
    """Handle crucible_template_create tool"""
    from ..session.templates import get_template_manager
    import json

    tm = get_template_manager()
    result = tm.create_template(
        name=args['name'],
        description=args['description'],
        goal_template=args.get('goal_template', ''),
        tags=args.get('tags')
    )
    return json.dumps(result, indent=2)


async def handle_template_from_session(args: dict) -> str:
    """Handle crucible_template_from_session tool"""
    from ..session import get_robust_session_manager
    from ..session.templates import get_template_manager
    import json
    from pathlib import Path

    manager = get_robust_session_manager()
    tm = get_template_manager()

    # Load session data
    session_file = Path("data/session") / f"robust_{args['session_id']}.json"
    if not session_file.exists():
        return json.dumps({'status': 'error', 'error': 'Session not found'})

    with open(session_file, 'r') as f:
        session_data = json.load(f)

    result = tm.create_template_from_session(session_data, args['name'])
    return json.dumps(result, indent=2)


# Export/Import Handlers
async def handle_session_export(args: dict) -> str:
    """Handle crucible_session_export tool"""
    from ..session.templates import get_exporter
    import json

    exporter = get_exporter()
    result = exporter.export_session(
        session_id=args['session_id'],
        output_path=args.get('output_path'),
        include_checkpoints=args.get('include_checkpoints', True)
    )
    return json.dumps(result, indent=2)


async def handle_session_import(args: dict) -> str:
    """Handle crucible_session_import tool"""
    from ..session.templates import get_exporter
    import json

    exporter = get_exporter()
    result = exporter.import_session(
        input_path=args['input_path'],
        new_session_id=args.get('new_session_id')
    )
    return json.dumps(result, indent=2)


async def handle_session_clone(args: dict) -> str:
    """Handle crucible_session_clone tool"""
    from ..session import get_robust_session_manager
    from ..session.templates import get_exporter
    import json
    from pathlib import Path
    import tempfile

    exporter = get_exporter()
    manager = get_robust_session_manager()

    # Export to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name

    export_result = exporter.export_session(
        args['session_id'],
        temp_path,
        include_checkpoints=False
    )

    if export_result['status'] != 'exported':
        return json.dumps(export_result)

    # Import as new session
    import_result = exporter.import_session(temp_path)

    # Clean up
    Path(temp_path).unlink()

    if import_result['status'] == 'imported' and args.get('new_goal'):
        # Update goal in new session
        new_session_file = Path("data/session") / f"robust_{import_result['session_id']}.json"
        with open(new_session_file, 'r') as f:
            data = json.load(f)
        data['goal'] = args['new_goal']
        with open(new_session_file, 'w') as f:
            json.dump(data, f, indent=2)
        import_result['goal'] = args['new_goal']

    return json.dumps(import_result, indent=2)


# Analytics Handlers
async def handle_analytics_summary(args: dict) -> str:
    """Handle crucible_analytics_summary tool"""
    from ..session.templates import get_analytics
    import json

    analytics = get_analytics()
    result = analytics.get_summary_stats()
    return json.dumps(result, indent=2)


async def handle_analytics_project(args: dict) -> str:
    """Handle crucible_analytics_project tool"""
    from ..session.templates import get_analytics
    import json

    analytics = get_analytics()
    result = analytics.get_project_stats(args['project'])
    return json.dumps(result, indent=2)


async def handle_analytics_timeline(args: dict) -> str:
    """Handle crucible_analytics_timeline tool"""
    from ..session.templates import get_analytics
    import json

    analytics = get_analytics()
    result = analytics.get_activity_timeline(args.get('days', 30))
    return json.dumps(result, indent=2)


async def handle_analytics_tags(args: dict) -> str:
    """Handle crucible_analytics_tags tool"""
    from ..session.templates import get_analytics
    import json

    analytics = get_analytics()
    result = analytics.get_tag_analysis()
    return json.dumps(result, indent=2)


# Handler mapping
HANDLERS = {
    "crucible_robust_start": handle_robust_start,
    "crucible_robust_resume": handle_robust_resume,
    "crucible_robust_status": handle_robust_status,
    "crucible_robust_checkpoint": handle_robust_checkpoint,
    "crucible_robust_end": handle_robust_end,
    "crucible_op_status": handle_op_status,
    "crucible_op_list": handle_op_list,
    "crucible_op_retry": handle_op_retry,
    "crucible_op_cancel": handle_op_cancel,
    "crucible_context_set": handle_context_set,
    "crucible_context_get": handle_context_get,
    "crucible_sessions_list": handle_sessions_list,
    # Session management
    "crucible_session_rename": handle_session_rename,
    "crucible_session_search": handle_session_search,
    "crucible_session_delete": handle_session_delete,
    # GitHub
    "crucible_github_connect": handle_github_connect,
    "crucible_github_disconnect": handle_github_disconnect,
    "crucible_github_info": handle_github_info,
    # Documents
    "crucible_doc_add": handle_doc_add,
    "crucible_doc_remove": handle_doc_remove,
    "crucible_doc_list": handle_doc_list,
    # Tags
    "crucible_tags_add": handle_tags_add,
    "crucible_tags_remove": handle_tags_remove,
    # Templates
    "crucible_template_list": handle_template_list,
    "crucible_template_use": handle_template_use,
    "crucible_template_create": handle_template_create,
    "crucible_template_from_session": handle_template_from_session,
    # Export/Import
    "crucible_session_export": handle_session_export,
    "crucible_session_import": handle_session_import,
    "crucible_session_clone": handle_session_clone,
    # Analytics
    "crucible_analytics_summary": handle_analytics_summary,
    "crucible_analytics_project": handle_analytics_project,
    "crucible_analytics_timeline": handle_analytics_timeline,
    "crucible_analytics_tags": handle_analytics_tags,
}
