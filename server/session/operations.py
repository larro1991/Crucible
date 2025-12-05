"""
Operation Tracker with State Machine

Tracks all operations with states: queued -> in_progress -> completed/failed
Provides operation history, retry support, and recovery capabilities.
"""

import os
import json
import time
import uuid
import fcntl
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path


class OperationState(Enum):
    """State machine for operations"""
    QUEUED = "queued"           # Waiting to execute
    IN_PROGRESS = "in_progress" # Currently executing
    COMPLETED = "completed"     # Successfully finished
    FAILED = "failed"           # Failed (may retry)
    CANCELLED = "cancelled"     # Manually cancelled
    RECOVERING = "recovering"   # Being recovered after drop


@dataclass
class Operation:
    """Represents a tracked operation"""
    op_id: str
    op_type: str                          # e.g., "execute", "verify", "file_write"
    state: OperationState
    args: Dict[str, Any]                  # Operation arguments
    created_at: str                       # ISO timestamp
    updated_at: str                       # ISO timestamp
    started_at: Optional[str] = None      # When execution began
    completed_at: Optional[str] = None    # When finished
    result: Optional[Any] = None          # Operation result
    error: Optional[str] = None           # Error message if failed
    retry_count: int = 0                  # Number of retries
    max_retries: int = 3                  # Max retry attempts
    parent_op_id: Optional[str] = None    # For nested operations
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        d = asdict(self)
        d['state'] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Operation':
        """Create from dictionary"""
        data = data.copy()
        data['state'] = OperationState(data['state'])
        return cls(**data)

    def can_retry(self) -> bool:
        """Check if operation can be retried"""
        return (
            self.state == OperationState.FAILED and
            self.retry_count < self.max_retries
        )


class OperationTracker:
    """
    Tracks all operations with persistent state.
    Survives connection drops by persisting to disk.
    """

    def __init__(self, data_dir: str = "data/session/operations"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.operations: Dict[str, Operation] = {}
        self.session_id: Optional[str] = None
        self._lock_file: Optional[int] = None

        # Load existing operations
        self._load_operations()

    def _now(self) -> str:
        """Get current ISO timestamp"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _get_session_file(self, session_id: str) -> Path:
        """Get path to session operations file"""
        return self.data_dir / f"ops_{session_id}.json"

    def _load_operations(self) -> None:
        """Load operations from most recent session file"""
        try:
            # Find most recent session file
            session_files = sorted(
                self.data_dir.glob("ops_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            if session_files:
                latest = session_files[0]
                with open(latest, 'r') as f:
                    data = json.load(f)
                    self.session_id = data.get('session_id')
                    for op_data in data.get('operations', []):
                        op = Operation.from_dict(op_data)
                        self.operations[op.op_id] = op
        except Exception as e:
            print(f"Warning: Could not load operations: {e}")

    def _save_operations(self) -> None:
        """Persist operations to disk with file locking"""
        if not self.session_id:
            return

        file_path = self._get_session_file(self.session_id)
        temp_path = file_path.with_suffix('.tmp')

        try:
            data = {
                'session_id': self.session_id,
                'updated_at': self._now(),
                'operations': [op.to_dict() for op in self.operations.values()]
            }

            # Write to temp file first (atomic write)
            with open(temp_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            os.rename(temp_path, file_path)

        except Exception as e:
            print(f"Warning: Could not save operations: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def start_session(self, session_id: Optional[str] = None) -> str:
        """Start a new tracking session or resume existing"""
        if session_id:
            # Try to load existing session
            file_path = self._get_session_file(session_id)
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    self.operations = {}
                    for op_data in data.get('operations', []):
                        op = Operation.from_dict(op_data)
                        self.operations[op.op_id] = op
                self.session_id = session_id
                return session_id

        # Create new session
        self.session_id = session_id or f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.operations = {}
        self._save_operations()
        return self.session_id

    def queue_operation(
        self,
        op_type: str,
        args: Dict[str, Any],
        parent_op_id: Optional[str] = None,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Queue a new operation for tracking"""
        op_id = f"op_{uuid.uuid4().hex[:12]}"
        now = self._now()

        op = Operation(
            op_id=op_id,
            op_type=op_type,
            state=OperationState.QUEUED,
            args=args,
            created_at=now,
            updated_at=now,
            max_retries=max_retries,
            parent_op_id=parent_op_id,
            metadata=metadata or {}
        )

        self.operations[op_id] = op
        self._save_operations()
        return op_id

    def start_operation(self, op_id: str) -> bool:
        """Mark operation as in progress"""
        if op_id not in self.operations:
            return False

        op = self.operations[op_id]
        if op.state not in (OperationState.QUEUED, OperationState.RECOVERING):
            return False

        now = self._now()
        op.state = OperationState.IN_PROGRESS
        op.started_at = now
        op.updated_at = now

        self._save_operations()
        return True

    def complete_operation(self, op_id: str, result: Any = None) -> bool:
        """Mark operation as completed"""
        if op_id not in self.operations:
            return False

        op = self.operations[op_id]
        if op.state != OperationState.IN_PROGRESS:
            return False

        now = self._now()
        op.state = OperationState.COMPLETED
        op.completed_at = now
        op.updated_at = now
        op.result = result

        self._save_operations()
        return True

    def fail_operation(self, op_id: str, error: str) -> bool:
        """Mark operation as failed"""
        if op_id not in self.operations:
            return False

        op = self.operations[op_id]
        if op.state != OperationState.IN_PROGRESS:
            return False

        now = self._now()
        op.state = OperationState.FAILED
        op.completed_at = now
        op.updated_at = now
        op.error = error

        self._save_operations()
        return True

    def retry_operation(self, op_id: str) -> bool:
        """Retry a failed operation"""
        if op_id not in self.operations:
            return False

        op = self.operations[op_id]
        if not op.can_retry():
            return False

        now = self._now()
        op.state = OperationState.QUEUED
        op.retry_count += 1
        op.updated_at = now
        op.started_at = None
        op.completed_at = None
        op.error = None
        op.result = None

        self._save_operations()
        return True

    def cancel_operation(self, op_id: str) -> bool:
        """Cancel a queued operation"""
        if op_id not in self.operations:
            return False

        op = self.operations[op_id]
        if op.state not in (OperationState.QUEUED, OperationState.RECOVERING):
            return False

        now = self._now()
        op.state = OperationState.CANCELLED
        op.updated_at = now

        self._save_operations()
        return True

    def get_operation(self, op_id: str) -> Optional[Operation]:
        """Get operation by ID"""
        return self.operations.get(op_id)

    def get_operations_by_state(self, state: OperationState) -> List[Operation]:
        """Get all operations in a given state"""
        return [op for op in self.operations.values() if op.state == state]

    def get_in_progress_operations(self) -> List[Operation]:
        """Get operations that were in progress (may need recovery)"""
        return self.get_operations_by_state(OperationState.IN_PROGRESS)

    def get_queued_operations(self) -> List[Operation]:
        """Get queued operations ready to execute"""
        return self.get_operations_by_state(OperationState.QUEUED)

    def get_failed_operations(self, retryable_only: bool = False) -> List[Operation]:
        """Get failed operations, optionally only those that can retry"""
        failed = self.get_operations_by_state(OperationState.FAILED)
        if retryable_only:
            failed = [op for op in failed if op.can_retry()]
        return failed

    def recover_interrupted_operations(self) -> List[str]:
        """
        Find operations that were in_progress when connection dropped.
        Mark them for recovery.
        """
        recovered = []
        for op in self.get_in_progress_operations():
            op.state = OperationState.RECOVERING
            op.updated_at = self._now()
            recovered.append(op.op_id)

        if recovered:
            self._save_operations()

        return recovered

    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all operations"""
        by_state = {}
        for state in OperationState:
            ops = self.get_operations_by_state(state)
            by_state[state.value] = len(ops)

        return {
            'session_id': self.session_id,
            'total_operations': len(self.operations),
            'by_state': by_state,
            'in_progress': [op.op_id for op in self.get_in_progress_operations()],
            'queued': [op.op_id for op in self.get_queued_operations()],
            'failed_retryable': [op.op_id for op in self.get_failed_operations(retryable_only=True)],
        }

    def get_operation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent operation history"""
        ops = sorted(
            self.operations.values(),
            key=lambda o: o.updated_at,
            reverse=True
        )[:limit]

        return [op.to_dict() for op in ops]

    def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Remove old completed operations to save space"""
        cutoff = datetime.now(timezone.utc).timestamp() - (older_than_hours * 3600)
        removed = 0

        to_remove = []
        for op_id, op in self.operations.items():
            if op.state == OperationState.COMPLETED and op.completed_at:
                try:
                    completed_ts = datetime.fromisoformat(
                        op.completed_at.replace('Z', '+00:00')
                    ).timestamp()
                    if completed_ts < cutoff:
                        to_remove.append(op_id)
                except:
                    pass

        for op_id in to_remove:
            del self.operations[op_id]
            removed += 1

        if removed:
            self._save_operations()

        return removed


# Global instance
_tracker: Optional[OperationTracker] = None

def get_operation_tracker() -> OperationTracker:
    """Get the global operation tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = OperationTracker()
    return _tracker
