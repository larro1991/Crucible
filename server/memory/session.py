"""
Session Memory - Tracks current session state.

Captures:
- What project we're working on
- What files have been touched
- Decisions made during the session
- Current task stack
- Problems encountered
"""

import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
import logging
import hashlib

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger('crucible.memory.session')


@dataclass
class Decision:
    """A decision made during the session."""
    description: str
    reasoning: str
    timestamp: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class Problem:
    """A problem encountered during the session."""
    description: str
    resolution: Optional[str] = None
    resolved: bool = False
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class SessionState:
    """
    Complete state of a session.

    Designed to be serialized and resumed.
    """
    session_id: str = ""
    started_at: str = ""
    updated_at: str = ""

    # What are we working on?
    project: Optional[str] = None
    project_path: Optional[str] = None
    primary_goal: Optional[str] = None

    # What have we touched?
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)

    # What have we decided?
    decisions: List[Dict] = field(default_factory=list)

    # What problems came up?
    problems: List[Dict] = field(default_factory=list)

    # Task tracking
    tasks_completed: List[str] = field(default_factory=list)
    tasks_pending: List[str] = field(default_factory=list)
    current_task: Optional[str] = None

    # Context accumulation
    key_insights: List[str] = field(default_factory=list)
    codebase_notes: Dict[str, str] = field(default_factory=dict)

    # User preferences observed
    user_preferences: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        now = datetime.utcnow().isoformat() + "Z"
        if not self.started_at:
            self.started_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.session_id:
            self.session_id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate a unique session ID."""
        content = f"{self.started_at}:{self.project or 'none'}"
        hash_val = hashlib.md5(content.encode()).hexdigest()[:8]
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return f"sess_{date_str}_{hash_val}"


class SessionMemory:
    """
    Manage session state persistence.

    Allows Claude to:
    - Resume sessions after terminal closes
    - Build context continuity across conversations
    - Track what was accomplished
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path) / 'sessions'
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[SessionState] = None
        self._active_file: Optional[Path] = None

    def start_session(
        self,
        project: str = None,
        project_path: str = None,
        goal: str = None,
        resume_from: str = None
    ) -> SessionState:
        """
        Start a new session or resume an existing one.

        Args:
            project: Project name
            project_path: Path to project directory
            goal: Primary goal for this session
            resume_from: Session ID to resume from

        Returns:
            SessionState object
        """
        if resume_from:
            session = self._load_session(resume_from)
            if session:
                self.current_session = session
                self._active_file = self.base_path / f"{resume_from}.yaml"
                logger.info(f"Resumed session: {resume_from}")
                return session
            else:
                logger.warning(f"Could not find session {resume_from}, starting new")

        # Start new session
        self.current_session = SessionState(
            project=project,
            project_path=project_path,
            primary_goal=goal
        )
        self._active_file = self.base_path / f"{self.current_session.session_id}.yaml"
        self._save()

        logger.info(f"Started session: {self.current_session.session_id}")
        return self.current_session

    def get_current(self) -> Optional[SessionState]:
        """Get current session state."""
        return self.current_session

    def update(self, **kwargs) -> SessionState:
        """
        Update current session state.

        Args:
            **kwargs: Fields to update on SessionState

        Returns:
            Updated SessionState
        """
        if not self.current_session:
            raise RuntimeError("No active session. Call start_session first.")

        for key, value in kwargs.items():
            if hasattr(self.current_session, key):
                setattr(self.current_session, key, value)

        self.current_session.updated_at = datetime.utcnow().isoformat() + "Z"
        self._save()
        return self.current_session

    def record_file_read(self, file_path: str):
        """Record that a file was read."""
        if not self.current_session:
            return
        if file_path not in self.current_session.files_read:
            self.current_session.files_read.append(file_path)
            self._save()

    def record_file_modified(self, file_path: str):
        """Record that a file was modified."""
        if not self.current_session:
            return
        if file_path not in self.current_session.files_modified:
            self.current_session.files_modified.append(file_path)
            self._save()

    def record_file_created(self, file_path: str):
        """Record that a file was created."""
        if not self.current_session:
            return
        if file_path not in self.current_session.files_created:
            self.current_session.files_created.append(file_path)
            self._save()

    def record_decision(self, description: str, reasoning: str, context: Dict = None):
        """Record a decision made during the session."""
        if not self.current_session:
            return
        decision = Decision(
            description=description,
            reasoning=reasoning,
            context=context or {}
        )
        self.current_session.decisions.append(asdict(decision))
        self._save()

    def record_problem(self, description: str, resolution: str = None):
        """Record a problem encountered."""
        if not self.current_session:
            return
        problem = Problem(
            description=description,
            resolution=resolution,
            resolved=resolution is not None
        )
        self.current_session.problems.append(asdict(problem))
        self._save()

    def resolve_problem(self, problem_index: int, resolution: str):
        """Mark a problem as resolved."""
        if not self.current_session:
            return
        if 0 <= problem_index < len(self.current_session.problems):
            self.current_session.problems[problem_index]['resolved'] = True
            self.current_session.problems[problem_index]['resolution'] = resolution
            self._save()

    def add_insight(self, insight: str):
        """Add a key insight discovered during the session."""
        if not self.current_session:
            return
        if insight not in self.current_session.key_insights:
            self.current_session.key_insights.append(insight)
            self._save()

    def note_codebase(self, key: str, note: str):
        """Add a note about the codebase."""
        if not self.current_session:
            return
        self.current_session.codebase_notes[key] = note
        self._save()

    def observe_preference(self, key: str, value: Any):
        """Record an observed user preference."""
        if not self.current_session:
            return
        self.current_session.user_preferences[key] = value
        self._save()

    def complete_task(self, task: str):
        """Mark a task as completed."""
        if not self.current_session:
            return
        if task not in self.current_session.tasks_completed:
            self.current_session.tasks_completed.append(task)
        if task in self.current_session.tasks_pending:
            self.current_session.tasks_pending.remove(task)
        if self.current_session.current_task == task:
            self.current_session.current_task = None
        self._save()

    def add_task(self, task: str, make_current: bool = False):
        """Add a pending task."""
        if not self.current_session:
            return
        if task not in self.current_session.tasks_pending:
            self.current_session.tasks_pending.append(task)
        if make_current:
            self.current_session.current_task = task
        self._save()

    def end_session(self) -> str:
        """
        End the current session and create summary.

        Returns:
            Summary of the session
        """
        if not self.current_session:
            return "No active session."

        session = self.current_session

        summary_lines = [
            f"=== Session {session.session_id} Summary ===",
            f"Project: {session.project or 'None'}",
            f"Goal: {session.primary_goal or 'None'}",
            f"Duration: {session.started_at} to {session.updated_at}",
            "",
            f"Files read: {len(session.files_read)}",
            f"Files modified: {len(session.files_modified)}",
            f"Files created: {len(session.files_created)}",
            f"Tasks completed: {len(session.tasks_completed)}",
            f"Decisions made: {len(session.decisions)}",
            f"Problems encountered: {len(session.problems)}",
            f"Insights captured: {len(session.key_insights)}",
        ]

        if session.tasks_pending:
            summary_lines.append(f"\nPending tasks: {len(session.tasks_pending)}")
            for task in session.tasks_pending:
                summary_lines.append(f"  - {task}")

        # Save final state
        self._save()

        # Move to archive
        archive_path = self.base_path / 'archive'
        archive_path.mkdir(exist_ok=True)
        if self._active_file and self._active_file.exists():
            self._active_file.rename(archive_path / self._active_file.name)

        self.current_session = None
        self._active_file = None

        return "\n".join(summary_lines)

    def list_sessions(self, include_archived: bool = False) -> List[Dict]:
        """List available sessions."""
        sessions = []

        # Active sessions
        for f in self.base_path.glob("sess_*.yaml"):
            sessions.append({
                'id': f.stem,
                'path': str(f),
                'archived': False
            })

        # Archived sessions
        if include_archived:
            archive_path = self.base_path / 'archive'
            if archive_path.exists():
                for f in archive_path.glob("sess_*.yaml"):
                    sessions.append({
                        'id': f.stem,
                        'path': str(f),
                        'archived': True
                    })

        return sessions

    def get_last_session(self, project: str = None) -> Optional[SessionState]:
        """
        Get the most recent session, optionally filtered by project.

        Args:
            project: Filter by project name

        Returns:
            Most recent SessionState or None
        """
        sessions = []

        for f in list(self.base_path.glob("sess_*.yaml")) + \
                 list((self.base_path / 'archive').glob("sess_*.yaml")):
            state = self._load_session_from_file(f)
            if state:
                if project is None or state.project == project:
                    sessions.append((state, f))

        if not sessions:
            return None

        # Sort by updated_at descending
        sessions.sort(key=lambda x: x[0].updated_at, reverse=True)
        return sessions[0][0]

    def _save(self):
        """Save current session to disk."""
        if not self.current_session or not self._active_file:
            return

        data = asdict(self.current_session)

        if HAS_YAML:
            content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(data, indent=2)

        self._active_file.write_text(content, encoding='utf-8')

    def _load_session(self, session_id: str) -> Optional[SessionState]:
        """Load a session by ID."""
        # Check active sessions
        path = self.base_path / f"{session_id}.yaml"
        if path.exists():
            return self._load_session_from_file(path)

        # Check archive
        archive_path = self.base_path / 'archive' / f"{session_id}.yaml"
        if archive_path.exists():
            return self._load_session_from_file(archive_path)

        return None

    def _load_session_from_file(self, path: Path) -> Optional[SessionState]:
        """Load session from a specific file."""
        try:
            content = path.read_text(encoding='utf-8')
            if HAS_YAML:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
            return SessionState(**data)
        except Exception as e:
            logger.error(f"Failed to load session from {path}: {e}")
            return None
