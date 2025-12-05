"""
Checkpoint System for Session State

Provides automatic and manual checkpointing of session state for recovery.
Checkpoints capture:
- Full session state
- Operation status
- Working memory
- User context
"""

import os
import json
import fcntl
import hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class Checkpoint:
    """A point-in-time snapshot of session state"""
    checkpoint_id: str
    session_id: str
    sequence: int                    # WAL sequence at checkpoint
    timestamp: str                   # ISO timestamp
    state: Dict[str, Any]            # Full session state
    operations_pending: List[str]    # Pending operation IDs
    operations_in_progress: List[str]  # In-progress operation IDs
    working_memory: Dict[str, Any]   # Current working memory
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create from dictionary"""
        return cls(**data)

    def get_checksum(self) -> str:
        """Generate checksum for integrity verification"""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class CheckpointManager:
    """
    Manages checkpoint creation, storage, and recovery.

    Features:
    - Automatic periodic checkpoints
    - Manual checkpoint triggers
    - Checkpoint pruning
    - Integrity verification
    - Fast recovery to latest state
    """

    MAX_CHECKPOINTS = 10        # Keep last N checkpoints
    AUTO_CHECKPOINT_OPS = 10    # Checkpoint every N operations
    AUTO_CHECKPOINT_SECS = 300  # Checkpoint every N seconds

    def __init__(self, data_dir: str = "data/session/checkpoints"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.session_id: Optional[str] = None
        self._ops_since_checkpoint: int = 0
        self._last_checkpoint_time: float = 0
        self._current_sequence: int = 0

    def _now(self) -> str:
        """Get current ISO timestamp"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get path to checkpoint file"""
        return self.data_dir / f"ckpt_{checkpoint_id}.json"

    def _list_checkpoints(self, session_id: Optional[str] = None) -> List[Path]:
        """List all checkpoint files, optionally filtered by session"""
        pattern = f"ckpt_*.json"
        checkpoints = list(self.data_dir.glob(pattern))

        if session_id:
            # Filter by session ID (encoded in checkpoint ID)
            checkpoints = [
                p for p in checkpoints
                if session_id in p.stem
            ]

        return sorted(checkpoints, key=lambda p: p.stat().st_mtime, reverse=True)

    def start_session(self, session_id: str) -> None:
        """Start checkpoint tracking for a session"""
        self.session_id = session_id
        self._ops_since_checkpoint = 0
        self._last_checkpoint_time = datetime.now(timezone.utc).timestamp()
        self._current_sequence = 0

    def should_checkpoint(self) -> bool:
        """Check if automatic checkpoint is due"""
        if not self.session_id:
            return False

        # Check operation count
        if self._ops_since_checkpoint >= self.AUTO_CHECKPOINT_OPS:
            return True

        # Check time
        now = datetime.now(timezone.utc).timestamp()
        if now - self._last_checkpoint_time >= self.AUTO_CHECKPOINT_SECS:
            return True

        return False

    def record_operation(self) -> None:
        """Record that an operation completed (for auto-checkpoint tracking)"""
        self._ops_since_checkpoint += 1

    def update_sequence(self, sequence: int) -> None:
        """Update current WAL sequence"""
        self._current_sequence = sequence

    def create_checkpoint(
        self,
        state: Dict[str, Any],
        operations_pending: List[str],
        operations_in_progress: List[str],
        working_memory: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[Checkpoint]:
        """Create a new checkpoint"""
        if not self.session_id:
            return None

        # Check if checkpoint needed (unless forced)
        if not force and not self.should_checkpoint():
            return None

        # Generate checkpoint ID
        timestamp = datetime.now(timezone.utc)
        checkpoint_id = f"{self.session_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            session_id=self.session_id,
            sequence=self._current_sequence,
            timestamp=timestamp.isoformat().replace('+00:00', 'Z'),
            state=state,
            operations_pending=operations_pending,
            operations_in_progress=operations_in_progress,
            working_memory=working_memory,
            metadata=metadata or {}
        )

        # Save checkpoint with checksum
        self._save_checkpoint(checkpoint)

        # Update tracking
        self._ops_since_checkpoint = 0
        self._last_checkpoint_time = timestamp.timestamp()

        # Prune old checkpoints
        self._prune_checkpoints()

        return checkpoint

    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to disk with integrity verification"""
        file_path = self._get_checkpoint_path(checkpoint.checkpoint_id)
        temp_path = file_path.with_suffix('.tmp')

        data = checkpoint.to_dict()
        data['_checksum'] = checkpoint.get_checksum()

        try:
            with open(temp_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            os.rename(temp_path, file_path)

        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to save checkpoint: {e}")

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a specific checkpoint"""
        file_path = self._get_checkpoint_path(checkpoint_id)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Verify checksum
            stored_checksum = data.pop('_checksum', None)
            checkpoint = Checkpoint.from_dict(data)

            if stored_checksum:
                actual_checksum = checkpoint.get_checksum()
                if stored_checksum != actual_checksum:
                    print(f"Warning: Checkpoint {checkpoint_id} has invalid checksum")
                    return None

            return checkpoint

        except Exception as e:
            print(f"Error loading checkpoint {checkpoint_id}: {e}")
            return None

    def get_latest_checkpoint(self, session_id: Optional[str] = None) -> Optional[Checkpoint]:
        """Get the most recent checkpoint for a session"""
        session = session_id or self.session_id
        checkpoints = self._list_checkpoints(session)

        for ckpt_path in checkpoints:
            checkpoint_id = ckpt_path.stem.replace('ckpt_', '')
            checkpoint = self.load_checkpoint(checkpoint_id)
            if checkpoint:
                return checkpoint

        return None

    def list_checkpoints(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List available checkpoints"""
        session = session_id or self.session_id
        checkpoint_files = self._list_checkpoints(session)[:limit]

        result = []
        for ckpt_path in checkpoint_files:
            checkpoint_id = ckpt_path.stem.replace('ckpt_', '')
            try:
                with open(ckpt_path, 'r') as f:
                    data = json.load(f)
                result.append({
                    'checkpoint_id': checkpoint_id,
                    'session_id': data.get('session_id'),
                    'timestamp': data.get('timestamp'),
                    'sequence': data.get('sequence'),
                    'ops_pending': len(data.get('operations_pending', [])),
                    'ops_in_progress': len(data.get('operations_in_progress', [])),
                })
            except:
                pass

        return result

    def _prune_checkpoints(self) -> int:
        """Remove old checkpoints beyond MAX_CHECKPOINTS"""
        if not self.session_id:
            return 0

        checkpoints = self._list_checkpoints(self.session_id)

        removed = 0
        for ckpt_path in checkpoints[self.MAX_CHECKPOINTS:]:
            try:
                ckpt_path.unlink()
                removed += 1
            except:
                pass

        return removed

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a specific checkpoint"""
        file_path = self._get_checkpoint_path(checkpoint_id)

        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except:
                return False
        return False

    def recover_from_checkpoint(
        self,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Recover session state from a checkpoint.
        Returns dict with recovered state or None if recovery failed.
        """
        if checkpoint_id:
            checkpoint = self.load_checkpoint(checkpoint_id)
        else:
            checkpoint = self.get_latest_checkpoint()

        if not checkpoint:
            return None

        return {
            'checkpoint_id': checkpoint.checkpoint_id,
            'session_id': checkpoint.session_id,
            'sequence': checkpoint.sequence,
            'timestamp': checkpoint.timestamp,
            'state': checkpoint.state,
            'operations_pending': checkpoint.operations_pending,
            'operations_in_progress': checkpoint.operations_in_progress,
            'working_memory': checkpoint.working_memory,
            'metadata': checkpoint.metadata
        }

    def get_recovery_info(self) -> Dict[str, Any]:
        """Get information useful for recovery decisions"""
        latest = self.get_latest_checkpoint()

        return {
            'has_checkpoint': latest is not None,
            'latest_checkpoint_id': latest.checkpoint_id if latest else None,
            'latest_timestamp': latest.timestamp if latest else None,
            'latest_sequence': latest.sequence if latest else 0,
            'available_checkpoints': len(self._list_checkpoints(self.session_id)),
            'session_id': self.session_id
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint statistics"""
        checkpoints = self._list_checkpoints(self.session_id)

        total_size = sum(p.stat().st_size for p in checkpoints if p.exists())

        return {
            'session_id': self.session_id,
            'checkpoint_count': len(checkpoints),
            'total_size_bytes': total_size,
            'ops_since_checkpoint': self._ops_since_checkpoint,
            'secs_since_checkpoint': (
                datetime.now(timezone.utc).timestamp() - self._last_checkpoint_time
            ),
            'should_checkpoint': self.should_checkpoint()
        }


# Global instance
_checkpoint_manager: Optional[CheckpointManager] = None

def get_checkpoint_manager() -> CheckpointManager:
    """Get the global checkpoint manager instance"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager
