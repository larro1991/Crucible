"""
Memory Manager - Unified interface to all memory systems.

Coordinates:
- SessionMemory: Current session state
- EpisodicMemory: Past session history
- SemanticMemory: Facts and knowledge
- WorkingMemory: Active task context

Provides high-level operations that span multiple memory types.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging

from .session import SessionMemory, SessionState
from .episodic import EpisodicMemory, Episode
from .semantic import SemanticMemory, Fact
from .working import WorkingMemory, TaskContext

logger = logging.getLogger('crucible.memory.manager')


class MemoryManager:
    """
    Unified memory management for Crucible.

    Provides a single interface to all memory systems, handling
    cross-memory operations and lifecycle management.
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path) / 'memory'
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Initialize all memory systems
        self.session = SessionMemory(self.base_path)
        self.episodic = EpisodicMemory(self.base_path)
        self.semantic = SemanticMemory(self.base_path)
        self.working = WorkingMemory(self.base_path)

        logger.info(f"Memory manager initialized at {self.base_path}")

    # === Session Lifecycle ===

    def begin_session(
        self,
        project: str = None,
        project_path: str = None,
        goal: str = None
    ) -> SessionState:
        """
        Begin a new session.

        Args:
            project: Project name
            project_path: Path to project
            goal: Primary goal

        Returns:
            SessionState for the new session
        """
        # Check for resumable sessions
        last_session = self.session.get_last_session(project)
        if last_session and last_session.tasks_pending:
            logger.info(f"Found unfinished session for {project}")
            # Could prompt user to resume here

        return self.session.start_session(
            project=project,
            project_path=project_path,
            goal=goal
        )

    def resume_session(self, session_id: str) -> Optional[SessionState]:
        """
        Resume a previous session.

        Args:
            session_id: Session to resume

        Returns:
            SessionState if found
        """
        return self.session.start_session(resume_from=session_id)

    def end_session(self, quality_score: float = None) -> str:
        """
        End the current session and convert to episodic memory.

        Args:
            quality_score: Self-assessment of session quality

        Returns:
            Session summary
        """
        session = self.session.get_current()
        if not session:
            return "No active session."

        # Convert to episode for long-term storage
        episode = self.episodic.convert_session(session, quality_score)
        logger.info(f"Converted session to episode: {episode.session_id}")

        # Extract and store any semantic knowledge
        self._extract_semantic_knowledge(session)

        # End the session
        return self.session.end_session()

    def _extract_semantic_knowledge(self, session: SessionState):
        """Extract facts from session and store in semantic memory."""
        # Store user preferences observed
        for key, value in session.user_preferences.items():
            self.semantic.learn_user_preference(key, value, source=session.session_id)

        # Store codebase notes as facts
        for key, note in session.codebase_notes.items():
            if session.project:
                self.semantic.learn_codebase(
                    project=session.project,
                    subject=key,
                    fact=note,
                    source=session.session_id
                )

    # === Working Memory ===

    def start_task(self, description: str) -> TaskContext:
        """
        Start a new task within the current session.

        Args:
            description: Task description

        Returns:
            TaskContext
        """
        # Record in session memory
        self.session.add_task(description, make_current=True)

        # Create working memory context
        return self.working.start_task(description)

    def complete_task(self, summary: str = None):
        """
        Complete the current task.

        Args:
            summary: Optional completion summary
        """
        ctx = self.working.get_context()
        if ctx:
            # Record completion in session
            self.session.complete_task(ctx.description)

            # Store any insights
            for note in ctx.notes:
                self.session.add_insight(note)

            # Complete in working memory
            self.working.complete_task(summary)

    # === Context Gathering ===

    def get_project_context(self, project: str) -> Dict[str, Any]:
        """
        Gather all context about a project.

        Args:
            project: Project name

        Returns:
            Dictionary with all relevant context
        """
        return {
            'semantic_facts': [
                {'subject': f.subject, 'predicate': f.predicate, 'value': f.value}
                for f in self.semantic.get_codebase_facts(project)
            ],
            'recent_episodes': [
                {
                    'date': e.date,
                    'goal': e.goal,
                    'accomplished': e.accomplished,
                    'unresolved': e.unresolved
                }
                for e in self.episodic.recall_project(project, limit=5)
            ],
            'unfinished_work': [
                {
                    'date': e.date,
                    'items': e.follow_up_needed + e.unresolved
                }
                for e in self.episodic.recall_unfinished(project)
            ],
            'timeline': self.episodic.get_project_timeline(project)
        }

    def get_session_context(self) -> Dict[str, Any]:
        """
        Get context for the current session.

        Returns:
            Dictionary with session context
        """
        session = self.session.get_current()
        if not session:
            return {'status': 'no_active_session'}

        working = self.working.get_context()

        return {
            'session': {
                'id': session.session_id,
                'project': session.project,
                'goal': session.primary_goal,
                'files_read': session.files_read,
                'files_modified': session.files_modified,
                'tasks_completed': session.tasks_completed,
                'tasks_pending': session.tasks_pending,
                'insights': session.key_insights,
                'decisions': session.decisions
            },
            'working': {
                'task': working.description if working else None,
                'relevant_files': working.relevant_files if working else [],
                'hypotheses': working.hypotheses if working else [],
                'blockers': working.blockers if working else [],
                'approach': working.current_approach if working else None
            }
        }

    def get_user_context(self) -> Dict[str, Any]:
        """
        Get context about user preferences.

        Returns:
            User preference context
        """
        return {
            'preferences': self.semantic.get_user_preferences(),
            'observed_from': [
                f.source for f in self.semantic.recall(category='user')
                if f.source
            ]
        }

    # === Memory Recording ===

    def remember_file_read(self, file_path: str, summary: str = None):
        """Record reading a file across memory systems."""
        self.session.record_file_read(file_path)
        self.working.record_read(file_path, summary)
        self.working.add_relevant_file(file_path)

    def remember_file_modified(self, file_path: str):
        """Record modifying a file."""
        self.session.record_file_modified(file_path)
        self.working.add_relevant_file(file_path)

    def remember_file_created(self, file_path: str):
        """Record creating a file."""
        self.session.record_file_created(file_path)
        self.working.add_relevant_file(file_path)

    def remember_decision(self, description: str, reasoning: str):
        """Record a decision made."""
        self.session.record_decision(description, reasoning)

    def remember_problem(self, description: str, resolution: str = None):
        """Record a problem encountered."""
        self.session.record_problem(description, resolution)
        if not resolution:
            self.working.add_blocker(description)

    def remember_insight(self, insight: str):
        """Record an insight discovered."""
        self.session.add_insight(insight)
        self.working.add_note(insight)

    def remember_error(self, error: str, context: str = None):
        """Record an error."""
        self.working.record_error(error, context)

    def remember_output(self, command: str, output: str, success: bool = True):
        """Record command output."""
        self.working.record_output(command, output, success)

    # === Learning ===

    def learn_fact(
        self,
        category: str,
        subject: str,
        predicate: str,
        value: Any,
        **kwargs
    ) -> Fact:
        """
        Learn a new fact.

        Args:
            category: Fact category
            subject: What it's about
            predicate: The relationship
            value: The value
            **kwargs: Additional fact parameters

        Returns:
            The stored Fact
        """
        session = self.session.get_current()
        if session:
            kwargs.setdefault('source', session.session_id)
            kwargs.setdefault('project', session.project)

        return self.semantic.learn(category, subject, predicate, value, **kwargs)

    def learn_preference(self, preference: str, value: Any):
        """Learn a user preference."""
        self.semantic.learn_user_preference(preference, value)
        session = self.session.get_current()
        if session:
            session.observe_preference(preference, value)

    def learn_pattern(self, name: str, description: str, example: str = None):
        """Learn a coding pattern."""
        session = self.session.get_current()
        project = session.project if session else None
        self.semantic.learn_pattern(name, description, example, project)

    # === Recall ===

    def recall_facts(self, **kwargs) -> List[Fact]:
        """Recall facts from semantic memory."""
        return self.semantic.recall(**kwargs)

    def recall_episodes(self, project: str = None, limit: int = 10) -> List[Episode]:
        """Recall past episodes."""
        if project:
            return self.episodic.recall_project(project, limit)
        return self.episodic.recall_recent(limit=limit)

    def search_memory(self, query: str) -> Dict[str, Any]:
        """
        Search across all memory systems.

        Args:
            query: Search term

        Returns:
            Combined search results
        """
        return {
            'facts': [
                {'subject': f.subject, 'predicate': f.predicate, 'value': f.value}
                for f in self.semantic.recall()
                if query.lower() in str(f.value).lower() or
                   query.lower() in f.subject.lower()
            ][:10],
            'episodes': [
                {'date': e.date, 'project': e.project, 'goal': e.goal}
                for e in self.episodic.search_episodes(query)
            ][:10]
        }

    # === Summary ===

    def get_full_summary(self) -> str:
        """
        Get a complete summary of all memory.

        Returns:
            Formatted summary string
        """
        lines = ["=" * 60]
        lines.append("CRUCIBLE MEMORY SUMMARY")
        lines.append("=" * 60)
        lines.append("")

        # Session
        session = self.session.get_current()
        if session:
            lines.append("## Active Session")
            lines.append(f"   ID: {session.session_id}")
            lines.append(f"   Project: {session.project or 'None'}")
            lines.append(f"   Goal: {session.primary_goal or 'None'}")
            lines.append(f"   Files touched: {len(session.files_read) + len(session.files_modified)}")
            lines.append(f"   Tasks completed: {len(session.tasks_completed)}")
            lines.append(f"   Tasks pending: {len(session.tasks_pending)}")
            lines.append("")
        else:
            lines.append("## No Active Session")
            lines.append("")

        # Working Memory
        working = self.working.get_context()
        if working:
            lines.append("## Working Memory")
            lines.append(f"   Task: {working.description}")
            lines.append(f"   Relevant files: {len(working.relevant_files)}")
            lines.append(f"   Active hypotheses: {len([h for h in working.hypotheses if h.get('status') == 'active'])}")
            lines.append(f"   Blockers: {len(working.blockers)}")
            lines.append("")

        # Semantic Memory
        lines.append("## Semantic Memory")
        lines.append(self.semantic.summarize_knowledge())
        lines.append("")

        # Episodic Memory
        recent_episodes = self.episodic.recall_recent(days=30, limit=5)
        lines.append(f"## Episodic Memory (Last 30 days: {len(recent_episodes)} episodes)")
        for ep in recent_episodes[:3]:
            lines.append(f"   {ep.date}: {ep.project or 'general'} - {ep.goal or 'no goal'}")
        lines.append("")

        return "\n".join(lines)
