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
}
