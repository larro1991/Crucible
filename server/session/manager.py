"""
Robust Session Manager

The main coordinator that integrates:
- Operation tracking
- Write-ahead logging
- Checkpointing
- Session recovery

Provides a unified interface for connection-resilient sessions.
"""

import os
import json
import time
import uuid
import asyncio
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Awaitable
from pathlib import Path
from contextlib import asynccontextmanager

from .operations import OperationTracker, Operation, OperationState, get_operation_tracker
from .wal import WriteAheadLog, WALEntry, WALEntryType, get_wal
from .checkpoint import CheckpointManager, Checkpoint, get_checkpoint_manager


@dataclass
class Document:
    """A document attached to a session"""
    doc_id: str
    name: str
    path: str                            # Local path or URL
    doc_type: str                        # file, url, text
    content_hash: Optional[str] = None   # For detecting changes
    added_at: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        return cls(**data)


@dataclass
class GitHubConnection:
    """GitHub repository connection for a session"""
    repo_url: str                        # e.g., https://github.com/user/repo
    repo_owner: str
    repo_name: str
    branch: str = "main"
    connected_at: str = ""
    last_sync: Optional[str] = None
    auth_method: str = "none"            # none, token, ssh
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GitHubConnection':
        return cls(**data)


@dataclass
class SessionState:
    """Complete session state for persistence"""
    session_id: str
    project: str
    project_path: str
    goal: str
    started_at: str
    updated_at: str
    status: str  # active, paused, recovered, completed
    heartbeat_at: str
    name: str = ""                       # User-friendly display name
    connection_drops: int = 0
    recoveries: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    github: Optional[Dict[str, Any]] = None  # GitHubConnection as dict
    documents: List[Dict[str, Any]] = field(default_factory=list)  # List of Document dicts
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        # Handle missing fields for backwards compatibility
        data.setdefault('name', '')
        data.setdefault('github', None)
        data.setdefault('documents', [])
        data.setdefault('tags', [])
        return cls(**data)


class RobustSessionManager:
    """
    Connection-resilient session manager.

    Features:
    - Survives connection drops with automatic recovery
    - Tracks all operations with state machine
    - Write-ahead logging for atomic operations
    - Automatic checkpointing
    - Operation replay on recovery
    - Heartbeat tracking for drop detection
    """

    HEARTBEAT_INTERVAL = 30  # seconds
    DROP_DETECTION_TIMEOUT = 120  # seconds without heartbeat = drop

    def __init__(
        self,
        data_dir: str = "data/session",
        operation_tracker: Optional[OperationTracker] = None,
        wal: Optional[WriteAheadLog] = None,
        checkpoint_manager: Optional[CheckpointManager] = None
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Components
        self.tracker = operation_tracker or get_operation_tracker()
        self.wal = wal or get_wal()
        self.checkpointer = checkpoint_manager or get_checkpoint_manager()

        # State
        self.session: Optional[SessionState] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._shutdown = False

    def _now(self) -> str:
        """Get current ISO timestamp"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _get_session_file(self, session_id: str) -> Path:
        """Get path to session state file"""
        return self.data_dir / f"robust_{session_id}.json"

    def _save_session(self) -> None:
        """Persist session state to disk"""
        if not self.session:
            return

        file_path = self._get_session_file(self.session.session_id)
        temp_path = file_path.with_suffix('.tmp')

        try:
            with open(temp_path, 'w') as f:
                json.dump(self.session.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.rename(temp_path, file_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            print(f"Warning: Could not save session: {e}")

    def _load_session(self, session_id: str) -> Optional[SessionState]:
        """Load session state from disk"""
        file_path = self._get_session_file(session_id)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return SessionState.from_dict(data)
        except Exception as e:
            print(f"Warning: Could not load session: {e}")
            return None

    def _find_latest_session(self) -> Optional[str]:
        """Find the most recent session ID"""
        session_files = sorted(
            self.data_dir.glob("robust_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if session_files:
            # Extract session ID from filename
            return session_files[0].stem.replace('robust_', '')
        return None

    async def start_session(
        self,
        project: str,
        project_path: str,
        goal: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Start a new robust session"""
        now = self._now()

        # Generate session ID if not provided
        if not session_id:
            session_id = f"rsess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Create session state
        self.session = SessionState(
            session_id=session_id,
            project=project,
            project_path=project_path,
            goal=goal,
            started_at=now,
            updated_at=now,
            status='active',
            heartbeat_at=now,
            context=context or {},
            metadata=metadata or {}
        )

        # Initialize components
        self.tracker.start_session(session_id)
        self.wal.start_session(session_id)
        self.checkpointer.start_session(session_id)

        # Log session start
        self.wal.log_begin('_session_start', 'session_start', {
            'project': project,
            'goal': goal
        })

        # Save initial state
        self._save_session()

        # Create initial checkpoint
        await self._create_checkpoint(force=True)

        # Start heartbeat
        await self._start_heartbeat()

        return {
            'session_id': session_id,
            'status': 'started',
            'project': project,
            'goal': goal,
            'started_at': now
        }

    async def resume_session(
        self,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resume a previous session after connection drop"""
        # Find session to resume
        if not session_id:
            session_id = self._find_latest_session()

        if not session_id:
            return {
                'status': 'error',
                'error': 'No session found to resume'
            }

        # Load session state
        self.session = self._load_session(session_id)

        if not self.session:
            return {
                'status': 'error',
                'error': f'Could not load session {session_id}'
            }

        now = self._now()

        # Update session
        self.session.status = 'recovered'
        self.session.recoveries += 1
        self.session.connection_drops += 1
        self.session.updated_at = now
        self.session.heartbeat_at = now

        # Re-initialize components
        self.tracker.start_session(session_id)
        self.wal.start_session(session_id)
        self.checkpointer.start_session(session_id)

        # Find interrupted operations
        interrupted_ops = self.tracker.recover_interrupted_operations()
        uncommitted = self.wal.get_uncommitted_operations()

        # Log recovery
        self.wal.log_begin('_session_recovery', 'session_recovery', {
            'interrupted_operations': interrupted_ops,
            'uncommitted_operations': len(uncommitted)
        })

        self._save_session()

        # Start heartbeat
        await self._start_heartbeat()

        return {
            'session_id': session_id,
            'status': 'resumed',
            'project': self.session.project,
            'goal': self.session.goal,
            'recoveries': self.session.recoveries,
            'interrupted_operations': interrupted_ops,
            'uncommitted_operations': uncommitted,
            'last_checkpoint': self.checkpointer.get_recovery_info()
        }

    async def _start_heartbeat(self) -> None:
        """Start background heartbeat task"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def heartbeat_loop():
            while not self._shutdown and self.session:
                try:
                    self.session.heartbeat_at = self._now()
                    self.session.updated_at = self._now()
                    self._save_session()
                    await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Heartbeat error: {e}")
                    await asyncio.sleep(5)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _stop_heartbeat(self) -> None:
        """Stop heartbeat task"""
        self._shutdown = True
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    @asynccontextmanager
    async def tracked_operation(
        self,
        op_type: str,
        args: Dict[str, Any],
        max_retries: int = 3
    ):
        """
        Context manager for tracked operations.

        Usage:
            async with manager.tracked_operation("execute", {"code": "..."}) as op:
                result = await do_something()
                op.set_result(result)
        """
        if not self.session:
            raise RuntimeError("No active session")

        # Queue operation
        op_id = self.tracker.queue_operation(
            op_type=op_type,
            args=args,
            max_retries=max_retries
        )

        # Log to WAL
        self.wal.log_begin(op_id, op_type, args)

        # Start operation
        self.tracker.start_operation(op_id)

        class OperationContext:
            def __init__(ctx_self):
                ctx_self.op_id = op_id
                ctx_self.result = None
                ctx_self.error = None

            def set_result(ctx_self, result: Any):
                ctx_self.result = result

            def set_error(ctx_self, error: str):
                ctx_self.error = error

            def log_data(ctx_self, key: str, value: Any):
                self.wal.log_data(op_id, key, value)

        ctx = OperationContext()

        try:
            yield ctx

            if ctx.error:
                # Operation failed
                self.tracker.fail_operation(op_id, ctx.error)
                self.wal.log_rollback(op_id, ctx.error)
            else:
                # Operation succeeded
                self.tracker.complete_operation(op_id, ctx.result)
                self.wal.log_commit(op_id, ctx.result)

        except Exception as e:
            # Unexpected error
            error_msg = str(e)
            self.tracker.fail_operation(op_id, error_msg)
            self.wal.log_rollback(op_id, error_msg)
            raise

        finally:
            # Record operation for checkpoint tracking
            self.checkpointer.record_operation()

            # Auto-checkpoint if needed
            if self.checkpointer.should_checkpoint():
                await self._create_checkpoint()

    async def execute_tracked(
        self,
        op_type: str,
        args: Dict[str, Any],
        executor: Callable[..., Awaitable[Any]],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute an operation with full tracking.

        Args:
            op_type: Type of operation
            args: Operation arguments
            executor: Async function to execute
            max_retries: Maximum retry attempts

        Returns:
            Dict with op_id, result, and status
        """
        async with self.tracked_operation(op_type, args, max_retries) as op:
            try:
                result = await executor(**args)
                op.set_result(result)
                return {
                    'op_id': op.op_id,
                    'status': 'completed',
                    'result': result
                }
            except Exception as e:
                op.set_error(str(e))
                return {
                    'op_id': op.op_id,
                    'status': 'failed',
                    'error': str(e)
                }

    async def _create_checkpoint(self, force: bool = False) -> Optional[Checkpoint]:
        """Create a checkpoint with current state"""
        if not self.session:
            return None

        # Gather state
        state = self.session.to_dict()

        # Get operation status
        pending = [op.op_id for op in self.tracker.get_queued_operations()]
        in_progress = [op.op_id for op in self.tracker.get_in_progress_operations()]

        # Get working memory (from session context)
        working_memory = self.session.context.copy()

        # Update sequence
        self.checkpointer.update_sequence(self.wal._sequence)

        checkpoint = self.checkpointer.create_checkpoint(
            state=state,
            operations_pending=pending,
            operations_in_progress=in_progress,
            working_memory=working_memory,
            force=force
        )

        if checkpoint:
            # Also log checkpoint to WAL
            self.wal.write_checkpoint({
                'checkpoint_id': checkpoint.checkpoint_id,
                'sequence': checkpoint.sequence
            })

        return checkpoint

    def update_context(self, key: str, value: Any) -> None:
        """Update session context (for checkpointing)"""
        if self.session:
            self.session.context[key] = value
            self.session.updated_at = self._now()
            self._save_session()

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get value from session context"""
        if self.session:
            return self.session.context.get(key, default)
        return default

    async def end_session(self, summary: Optional[str] = None) -> Dict[str, Any]:
        """End the current session"""
        if not self.session:
            return {'status': 'error', 'error': 'No active session'}

        await self._stop_heartbeat()

        now = self._now()

        # Create final checkpoint
        await self._create_checkpoint(force=True)

        # Log session end
        self.wal.log_commit('_session_end', {
            'summary': summary,
            'ended_at': now
        })

        # Update session status
        self.session.status = 'completed'
        self.session.updated_at = now
        self._save_session()

        # Get final stats
        stats = self.get_status()

        self.session = None

        return {
            'status': 'ended',
            'summary': summary,
            **stats
        }

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive session status"""
        if not self.session:
            return {'status': 'no_session'}

        return {
            'session': self.session.to_dict(),
            'operations': self.tracker.get_status_summary(),
            'wal': self.wal.get_stats(),
            'checkpoints': self.checkpointer.get_stats(),
            'recovery_info': self.checkpointer.get_recovery_info()
        }

    def get_operation_status(self, op_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific operation"""
        op = self.tracker.get_operation(op_id)
        if op:
            return op.to_dict()
        return None

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """Get all pending operations"""
        return [op.to_dict() for op in self.tracker.get_queued_operations()]

    def get_failed_operations(self, retryable_only: bool = False) -> List[Dict[str, Any]]:
        """Get failed operations"""
        return [
            op.to_dict()
            for op in self.tracker.get_failed_operations(retryable_only)
        ]

    async def retry_operation(self, op_id: str) -> Dict[str, Any]:
        """Retry a failed operation"""
        if not self.tracker.retry_operation(op_id):
            return {
                'status': 'error',
                'error': f'Cannot retry operation {op_id}'
            }

        return {
            'status': 'queued_for_retry',
            'op_id': op_id
        }

    def cancel_operation(self, op_id: str) -> Dict[str, Any]:
        """Cancel a pending operation"""
        if self.tracker.cancel_operation(op_id):
            self.wal.log_rollback(op_id, 'cancelled')
            return {'status': 'cancelled', 'op_id': op_id}
        return {'status': 'error', 'error': f'Cannot cancel operation {op_id}'}

    def get_operation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get operation history"""
        return self.tracker.get_operation_history(limit)

    async def force_checkpoint(self) -> Dict[str, Any]:
        """Force immediate checkpoint"""
        checkpoint = await self._create_checkpoint(force=True)
        if checkpoint:
            return {
                'status': 'checkpointed',
                'checkpoint_id': checkpoint.checkpoint_id,
                'timestamp': checkpoint.timestamp
            }
        return {'status': 'error', 'error': 'Failed to create checkpoint'}

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List available sessions"""
        session_files = sorted(
            self.data_dir.glob("robust_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]

        sessions = []
        for f in session_files:
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                sessions.append({
                    'session_id': data.get('session_id'),
                    'name': data.get('name', ''),
                    'project': data.get('project'),
                    'goal': data.get('goal'),
                    'status': data.get('status'),
                    'started_at': data.get('started_at'),
                    'updated_at': data.get('updated_at'),
                    'recoveries': data.get('recoveries', 0),
                    'has_github': data.get('github') is not None,
                    'document_count': len(data.get('documents', [])),
                    'tags': data.get('tags', [])
                })
            except:
                pass

        return sessions

    def rename_session(self, session_id: str, new_name: str) -> Dict[str, Any]:
        """Rename a session (set display name)"""
        # If renaming current session
        if self.session and self.session.session_id == session_id:
            self.session.name = new_name
            self.session.updated_at = self._now()
            self._save_session()
            return {'status': 'renamed', 'session_id': session_id, 'name': new_name}

        # Renaming a different session
        file_path = self._get_session_file(session_id)
        if not file_path.exists():
            return {'status': 'error', 'error': f'Session {session_id} not found'}

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            data['name'] = new_name
            data['updated_at'] = self._now()

            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)

            return {'status': 'renamed', 'session_id': session_id, 'name': new_name}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def connect_github(
        self,
        repo_url: str,
        branch: str = "main",
        auth_method: str = "none"
    ) -> Dict[str, Any]:
        """Connect current session to a GitHub repository"""
        if not self.session:
            return {'status': 'error', 'error': 'No active session'}

        # Parse repo URL
        import re
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$', repo_url)
        if not match:
            return {'status': 'error', 'error': 'Invalid GitHub URL format'}

        owner, repo = match.groups()

        connection = GitHubConnection(
            repo_url=repo_url.rstrip('/').replace('.git', ''),
            repo_owner=owner,
            repo_name=repo,
            branch=branch,
            connected_at=self._now(),
            auth_method=auth_method
        )

        self.session.github = connection.to_dict()
        self.session.updated_at = self._now()
        self._save_session()

        return {
            'status': 'connected',
            'repo': f'{owner}/{repo}',
            'branch': branch,
            'url': connection.repo_url
        }

    def disconnect_github(self) -> Dict[str, Any]:
        """Disconnect GitHub from current session"""
        if not self.session:
            return {'status': 'error', 'error': 'No active session'}

        if not self.session.github:
            return {'status': 'error', 'error': 'No GitHub connection'}

        self.session.github = None
        self.session.updated_at = self._now()
        self._save_session()

        return {'status': 'disconnected'}

    def get_github_info(self) -> Optional[Dict[str, Any]]:
        """Get GitHub connection info for current session"""
        if self.session and self.session.github:
            return self.session.github
        return None

    def add_document(
        self,
        name: str,
        path: str,
        doc_type: str = "file",
        description: str = ""
    ) -> Dict[str, Any]:
        """Add a document to the current session"""
        if not self.session:
            return {'status': 'error', 'error': 'No active session'}

        import hashlib

        doc_id = f"doc_{uuid.uuid4().hex[:8]}"

        # Calculate content hash for files
        content_hash = None
        if doc_type == "file" and Path(path).exists():
            try:
                with open(path, 'rb') as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            except:
                pass

        doc = Document(
            doc_id=doc_id,
            name=name,
            path=path,
            doc_type=doc_type,
            content_hash=content_hash,
            added_at=self._now(),
            description=description
        )

        self.session.documents.append(doc.to_dict())
        self.session.updated_at = self._now()
        self._save_session()

        return {
            'status': 'added',
            'doc_id': doc_id,
            'name': name,
            'type': doc_type
        }

    def remove_document(self, doc_id: str) -> Dict[str, Any]:
        """Remove a document from the current session"""
        if not self.session:
            return {'status': 'error', 'error': 'No active session'}

        original_count = len(self.session.documents)
        self.session.documents = [
            d for d in self.session.documents
            if d.get('doc_id') != doc_id
        ]

        if len(self.session.documents) == original_count:
            return {'status': 'error', 'error': f'Document {doc_id} not found'}

        self.session.updated_at = self._now()
        self._save_session()

        return {'status': 'removed', 'doc_id': doc_id}

    def list_documents(self) -> List[Dict[str, Any]]:
        """List documents attached to current session"""
        if not self.session:
            return []
        return self.session.documents

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID"""
        if not self.session:
            return None

        for doc in self.session.documents:
            if doc.get('doc_id') == doc_id:
                return doc
        return None

    def add_tags(self, tags: List[str]) -> Dict[str, Any]:
        """Add tags to current session"""
        if not self.session:
            return {'status': 'error', 'error': 'No active session'}

        for tag in tags:
            if tag not in self.session.tags:
                self.session.tags.append(tag)

        self.session.updated_at = self._now()
        self._save_session()

        return {'status': 'added', 'tags': self.session.tags}

    def remove_tags(self, tags: List[str]) -> Dict[str, Any]:
        """Remove tags from current session"""
        if not self.session:
            return {'status': 'error', 'error': 'No active session'}

        self.session.tags = [t for t in self.session.tags if t not in tags]
        self.session.updated_at = self._now()
        self._save_session()

        return {'status': 'removed', 'tags': self.session.tags}

    def search_sessions(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search sessions with filters"""
        all_sessions = self.list_sessions(limit=100)  # Get more for filtering

        results = []
        for sess in all_sessions:
            # Filter by status
            if status and sess.get('status') != status:
                continue

            # Filter by project
            if project and sess.get('project') != project:
                continue

            # Filter by tags
            if tags:
                session_tags = sess.get('tags', [])
                if not any(t in session_tags for t in tags):
                    continue

            # Filter by query (search in name, goal, project)
            if query:
                query_lower = query.lower()
                searchable = ' '.join([
                    sess.get('name', ''),
                    sess.get('goal', ''),
                    sess.get('project', ''),
                    sess.get('session_id', '')
                ]).lower()
                if query_lower not in searchable:
                    continue

            results.append(sess)

            if len(results) >= limit:
                break

        return results

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        """Delete a session permanently"""
        # Prevent deleting active session
        if self.session and self.session.session_id == session_id:
            return {'status': 'error', 'error': 'Cannot delete active session'}

        file_path = self._get_session_file(session_id)
        if not file_path.exists():
            return {'status': 'error', 'error': f'Session {session_id} not found'}

        try:
            file_path.unlink()
            return {'status': 'deleted', 'session_id': session_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    async def cleanup_old_data(
        self,
        session_days: int = 7,
        checkpoint_days: int = 3
    ) -> Dict[str, int]:
        """Clean up old session data"""
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        session_cutoff = now - timedelta(days=session_days)
        checkpoint_cutoff = now - timedelta(days=checkpoint_days)

        removed = {
            'sessions': 0,
            'operations': 0,
            'checkpoints': 0,
            'wal_entries': 0
        }

        # Clean old sessions
        for f in self.data_dir.glob("robust_*.json"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < session_cutoff:
                    f.unlink()
                    removed['sessions'] += 1
            except:
                pass

        # Clean completed operations
        removed['operations'] = self.tracker.cleanup_completed(
            older_than_hours=session_days * 24
        )

        # Compact WAL
        removed['wal_entries'] = self.wal.compact()

        return removed


# Global instance
_manager: Optional[RobustSessionManager] = None

def get_robust_session_manager() -> RobustSessionManager:
    """Get the global robust session manager instance"""
    global _manager
    if _manager is None:
        _manager = RobustSessionManager()
    return _manager
