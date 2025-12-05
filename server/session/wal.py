"""
Write-Ahead Log (WAL) for Atomic Operations

Ensures operations are logged BEFORE execution, allowing for:
- Recovery after crashes/connection drops
- Operation replay
- Audit trail
- Transaction consistency
"""

import os
import json
import fcntl
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Iterator
from pathlib import Path
from enum import Enum


class WALEntryType(Enum):
    """Types of WAL entries"""
    BEGIN = "begin"           # Operation starting
    COMMIT = "commit"         # Operation completed successfully
    ROLLBACK = "rollback"     # Operation failed/rolled back
    CHECKPOINT = "checkpoint" # Checkpoint marker
    DATA = "data"             # Intermediate data


@dataclass
class WALEntry:
    """A single WAL entry"""
    sequence: int                    # Monotonic sequence number
    entry_type: WALEntryType
    op_id: str                       # Operation ID
    timestamp: str                   # ISO timestamp
    data: Dict[str, Any]             # Entry payload

    def to_line(self) -> str:
        """Convert to JSON line for append"""
        d = asdict(self)
        d['entry_type'] = self.entry_type.value
        return json.dumps(d, separators=(',', ':'))

    @classmethod
    def from_line(cls, line: str) -> 'WALEntry':
        """Parse from JSON line"""
        d = json.loads(line.strip())
        d['entry_type'] = WALEntryType(d['entry_type'])
        return cls(**d)


class WriteAheadLog:
    """
    Append-only Write-Ahead Log for operation durability.

    Design:
    - One WAL file per session
    - JSON Lines format (one entry per line)
    - Append-only with fsync for durability
    - Automatic rotation based on size
    - Checkpoint markers for recovery optimization
    """

    MAX_WAL_SIZE = 10 * 1024 * 1024  # 10MB before rotation
    CHECKPOINT_INTERVAL = 100        # Entries between checkpoints

    def __init__(self, data_dir: str = "data/session/wal"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.session_id: Optional[str] = None
        self._current_file: Optional[Path] = None
        self._sequence: int = 0
        self._entries_since_checkpoint: int = 0
        self._file_handle = None

    def _now(self) -> str:
        """Get current ISO timestamp"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _get_wal_path(self, session_id: str, index: int = 0) -> Path:
        """Get WAL file path"""
        if index == 0:
            return self.data_dir / f"wal_{session_id}.log"
        return self.data_dir / f"wal_{session_id}.{index}.log"

    def _find_latest_wal(self, session_id: str) -> Optional[Path]:
        """Find most recent WAL file for session"""
        base = self.data_dir / f"wal_{session_id}"

        # Check numbered files first (higher numbers are newer)
        numbered = sorted(
            self.data_dir.glob(f"wal_{session_id}.*.log"),
            key=lambda p: int(p.suffixes[0][1:]) if p.suffixes else 0,
            reverse=True
        )

        if numbered:
            return numbered[0]

        # Fall back to base file
        base_file = self._get_wal_path(session_id)
        if base_file.exists():
            return base_file

        return None

    def _get_last_sequence(self, wal_path: Path) -> int:
        """Get the last sequence number from a WAL file"""
        last_seq = 0
        try:
            with open(wal_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = WALEntry.from_line(line)
                            last_seq = max(last_seq, entry.sequence)
                        except:
                            pass
        except:
            pass
        return last_seq

    def start_session(self, session_id: str) -> None:
        """Start or resume a WAL session"""
        self.session_id = session_id

        # Check for existing WAL
        existing = self._find_latest_wal(session_id)
        if existing:
            self._current_file = existing
            self._sequence = self._get_last_sequence(existing)
        else:
            self._current_file = self._get_wal_path(session_id)
            self._sequence = 0

        self._entries_since_checkpoint = 0

    def _append_entry(self, entry: WALEntry) -> None:
        """Append an entry to the WAL with durability guarantees"""
        if not self._current_file:
            raise RuntimeError("No active WAL session")

        line = entry.to_line() + "\n"

        # Check if rotation needed
        if self._current_file.exists():
            size = self._current_file.stat().st_size
            if size + len(line) > self.MAX_WAL_SIZE:
                self._rotate()

        # Append with fsync
        with open(self._current_file, 'a') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        self._entries_since_checkpoint += 1

        # Auto checkpoint
        if self._entries_since_checkpoint >= self.CHECKPOINT_INTERVAL:
            self.write_checkpoint()

    def _rotate(self) -> None:
        """Rotate WAL file when too large"""
        if not self._current_file or not self.session_id:
            return

        # Find next index
        existing = list(self.data_dir.glob(f"wal_{self.session_id}.*.log"))
        next_index = len(existing) + 1

        # Create new file
        self._current_file = self._get_wal_path(self.session_id, next_index)

        # Write checkpoint at start of new file
        self.write_checkpoint()

    def log_begin(self, op_id: str, op_type: str, args: Dict[str, Any]) -> int:
        """Log operation beginning (BEFORE execution)"""
        self._sequence += 1
        entry = WALEntry(
            sequence=self._sequence,
            entry_type=WALEntryType.BEGIN,
            op_id=op_id,
            timestamp=self._now(),
            data={
                'op_type': op_type,
                'args': args
            }
        )
        self._append_entry(entry)
        return self._sequence

    def log_data(self, op_id: str, key: str, value: Any) -> int:
        """Log intermediate data during operation"""
        self._sequence += 1
        entry = WALEntry(
            sequence=self._sequence,
            entry_type=WALEntryType.DATA,
            op_id=op_id,
            timestamp=self._now(),
            data={key: value}
        )
        self._append_entry(entry)
        return self._sequence

    def log_commit(self, op_id: str, result: Any = None) -> int:
        """Log successful operation completion"""
        self._sequence += 1
        entry = WALEntry(
            sequence=self._sequence,
            entry_type=WALEntryType.COMMIT,
            op_id=op_id,
            timestamp=self._now(),
            data={'result': result}
        )
        self._append_entry(entry)
        return self._sequence

    def log_rollback(self, op_id: str, error: str) -> int:
        """Log operation failure/rollback"""
        self._sequence += 1
        entry = WALEntry(
            sequence=self._sequence,
            entry_type=WALEntryType.ROLLBACK,
            op_id=op_id,
            timestamp=self._now(),
            data={'error': error}
        )
        self._append_entry(entry)
        return self._sequence

    def write_checkpoint(self, state: Optional[Dict[str, Any]] = None) -> int:
        """Write a checkpoint marker"""
        self._sequence += 1
        entry = WALEntry(
            sequence=self._sequence,
            entry_type=WALEntryType.CHECKPOINT,
            op_id='_checkpoint',
            timestamp=self._now(),
            data=state or {'checkpoint_seq': self._sequence}
        )
        self._append_entry(entry)
        self._entries_since_checkpoint = 0
        return self._sequence

    def read_entries(
        self,
        from_sequence: int = 0,
        entry_types: Optional[List[WALEntryType]] = None
    ) -> Iterator[WALEntry]:
        """Read entries from WAL, optionally from a sequence number"""
        if not self.session_id:
            return

        # Get all WAL files for session
        files = [self._get_wal_path(self.session_id)]
        files.extend(sorted(
            self.data_dir.glob(f"wal_{self.session_id}.*.log"),
            key=lambda p: int(p.suffixes[0][1:]) if p.suffixes else 0
        ))

        for wal_file in files:
            if not wal_file.exists():
                continue

            with open(wal_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = WALEntry.from_line(line)
                        if entry.sequence > from_sequence:
                            if entry_types is None or entry.entry_type in entry_types:
                                yield entry
                    except Exception as e:
                        print(f"Warning: Could not parse WAL entry: {e}")

    def get_uncommitted_operations(self) -> List[Dict[str, Any]]:
        """Find operations that started but never committed/rolled back"""
        begun = {}   # op_id -> entry
        completed = set()  # op_ids that committed or rolled back

        for entry in self.read_entries():
            if entry.entry_type == WALEntryType.BEGIN:
                begun[entry.op_id] = entry
            elif entry.entry_type in (WALEntryType.COMMIT, WALEntryType.ROLLBACK):
                completed.add(entry.op_id)

        # Find uncommitted
        uncommitted = []
        for op_id, entry in begun.items():
            if op_id not in completed:
                uncommitted.append({
                    'op_id': op_id,
                    'sequence': entry.sequence,
                    'timestamp': entry.timestamp,
                    'op_type': entry.data.get('op_type'),
                    'args': entry.data.get('args', {})
                })

        return sorted(uncommitted, key=lambda x: x['sequence'])

    def get_last_checkpoint(self) -> Optional[WALEntry]:
        """Find the most recent checkpoint"""
        last_checkpoint = None
        for entry in self.read_entries(entry_types=[WALEntryType.CHECKPOINT]):
            last_checkpoint = entry
        return last_checkpoint

    def replay_from_checkpoint(
        self,
        checkpoint_seq: Optional[int] = None
    ) -> Iterator[WALEntry]:
        """Replay entries from last checkpoint (or specified sequence)"""
        if checkpoint_seq is None:
            checkpoint = self.get_last_checkpoint()
            checkpoint_seq = checkpoint.sequence if checkpoint else 0

        # Yield all entries after checkpoint
        for entry in self.read_entries(from_sequence=checkpoint_seq):
            if entry.entry_type != WALEntryType.CHECKPOINT:
                yield entry

    def get_operation_log(self, op_id: str) -> List[WALEntry]:
        """Get all WAL entries for a specific operation"""
        entries = []
        for entry in self.read_entries():
            if entry.op_id == op_id:
                entries.append(entry)
        return entries

    def compact(self, keep_entries: int = 1000) -> int:
        """Compact WAL by removing old committed entries"""
        if not self._current_file or not self._current_file.exists():
            return 0

        entries = list(self.read_entries())
        if len(entries) <= keep_entries:
            return 0

        # Keep recent entries and all uncommitted
        uncommitted_ids = {e['op_id'] for e in self.get_uncommitted_operations()}

        to_keep = []
        for entry in entries[-keep_entries:]:
            to_keep.append(entry)

        # Also keep all uncommitted operation entries
        for entry in entries[:-keep_entries]:
            if entry.op_id in uncommitted_ids:
                to_keep.append(entry)

        # Sort by sequence
        to_keep.sort(key=lambda e: e.sequence)

        # Rewrite
        removed = len(entries) - len(to_keep)
        if removed > 0:
            temp_path = self._current_file.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                for entry in to_keep:
                    f.write(entry.to_line() + "\n")
                f.flush()
                os.fsync(f.fileno())

            os.rename(temp_path, self._current_file)

        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Get WAL statistics"""
        entries = list(self.read_entries())

        by_type = {}
        for t in WALEntryType:
            by_type[t.value] = sum(1 for e in entries if e.entry_type == t)

        file_size = 0
        if self._current_file and self._current_file.exists():
            file_size = self._current_file.stat().st_size

        return {
            'session_id': self.session_id,
            'current_sequence': self._sequence,
            'total_entries': len(entries),
            'by_type': by_type,
            'uncommitted_count': len(self.get_uncommitted_operations()),
            'file_size_bytes': file_size,
            'entries_since_checkpoint': self._entries_since_checkpoint
        }


# Global instance
_wal: Optional[WriteAheadLog] = None

def get_wal() -> WriteAheadLog:
    """Get the global WAL instance"""
    global _wal
    if _wal is None:
        _wal = WriteAheadLog()
    return _wal
