"""
Memory Tools - MCP tools for Crucible memory system.

Provides Claude with tools to:
- Manage sessions (start, resume, end)
- Record and recall information
- Build and query knowledge
- Track task context
"""

from typing import Optional, List, Dict, Any
import logging

from ..memory.manager import MemoryManager
from ..memory.janitor import MemoryJanitor

logger = logging.getLogger('crucible.tools.memory')


class MemoryTools:
    """
    MCP tools for memory management.

    Tools:
    - crucible_session_start: Begin a new session
    - crucible_session_resume: Resume a previous session
    - crucible_session_end: End current session
    - crucible_session_status: Get current session status
    - crucible_remember: Store information in memory
    - crucible_recall: Retrieve information from memory
    - crucible_context: Get context for current work
    - crucible_task_start: Start a task within session
    - crucible_task_complete: Complete current task
    - crucible_learn: Learn a fact or preference
    - crucible_reflect: Get memory summary
    """

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.janitor = MemoryJanitor(
            memory_manager.session,
            memory_manager.episodic,
            memory_manager.semantic,
            memory_manager.working
        )

    # === Session Management ===

    def session_start(
        self,
        project: str = None,
        project_path: str = None,
        goal: str = None
    ) -> str:
        """
        Start a new session.

        Args:
            project: Project name
            project_path: Path to project directory
            goal: Primary goal for this session

        Returns:
            Session information
        """
        session = self.memory.begin_session(
            project=project,
            project_path=project_path,
            goal=goal
        )

        lines = [
            "=== Session Started ===",
            f"Session ID: {session.session_id}",
            f"Project: {session.project or 'None'}",
            f"Goal: {session.primary_goal or 'None'}",
            "",
            "Memory systems active:",
            "  • Session memory (tracking this session)",
            "  • Working memory (task context)",
            "  • Semantic memory (facts & knowledge)",
            "  • Episodic memory (session history)",
        ]

        # Check for unfinished work
        unfinished = self.memory.episodic.recall_unfinished(project)
        if unfinished:
            lines.append("")
            lines.append(f"Note: Found {len(unfinished)} previous session(s) with unfinished items:")
            for ep in unfinished[:3]:
                lines.append(f"  - {ep.date}: {len(ep.follow_up_needed)} follow-ups, {len(ep.unresolved)} unresolved")

        return "\n".join(lines)

    def session_resume(self, session_id: str) -> str:
        """
        Resume a previous session.

        Args:
            session_id: ID of session to resume

        Returns:
            Session information
        """
        session = self.memory.resume_session(session_id)
        if not session:
            return f"Session not found: {session_id}"

        lines = [
            "=== Session Resumed ===",
            f"Session ID: {session.session_id}",
            f"Project: {session.project or 'None'}",
            f"Goal: {session.primary_goal or 'None'}",
            f"Originally started: {session.started_at}",
            "",
            f"Previous progress:",
            f"  Files read: {len(session.files_read)}",
            f"  Files modified: {len(session.files_modified)}",
            f"  Tasks completed: {len(session.tasks_completed)}",
        ]

        if session.tasks_pending:
            lines.append("")
            lines.append("Pending tasks:")
            for task in session.tasks_pending:
                lines.append(f"  • {task}")

        if session.key_insights:
            lines.append("")
            lines.append("Previous insights:")
            for insight in session.key_insights[-3:]:
                lines.append(f"  • {insight}")

        return "\n".join(lines)

    def session_end(self, quality_score: float = None) -> str:
        """
        End the current session and save to long-term memory.

        Args:
            quality_score: Optional self-assessment (0-1)

        Returns:
            Session summary
        """
        return self.memory.end_session(quality_score)

    def session_status(self) -> str:
        """
        Get current session status.

        Returns:
            Session status information
        """
        context = self.memory.get_session_context()

        if context.get('status') == 'no_active_session':
            # List available sessions
            sessions = self.memory.session.list_sessions(include_archived=False)
            if sessions:
                lines = ["No active session.", "", "Available sessions:"]
                for s in sessions[:5]:
                    lines.append(f"  - {s['id']}")
                return "\n".join(lines)
            return "No active session. Use session_start to begin."

        session = context['session']
        working = context['working']

        lines = [
            "=== Session Status ===",
            f"Session: {session['id']}",
            f"Project: {session['project'] or 'None'}",
            f"Goal: {session['goal'] or 'None'}",
            "",
            f"Files read: {len(session['files_read'])}",
            f"Files modified: {len(session['files_modified'])}",
            f"Tasks completed: {len(session['tasks_completed'])}",
            f"Tasks pending: {len(session['tasks_pending'])}",
            f"Insights: {len(session['insights'])}",
            f"Decisions: {len(session['decisions'])}",
        ]

        if working['task']:
            lines.append("")
            lines.append(f"Current Task: {working['task']}")
            lines.append(f"  Relevant files: {len(working['relevant_files'])}")
            lines.append(f"  Blockers: {len(working['blockers'])}")
            if working['approach']:
                lines.append(f"  Approach: {working['approach']}")

        return "\n".join(lines)

    def session_list(self, include_archived: bool = False) -> str:
        """
        List available sessions.

        Args:
            include_archived: Include archived sessions

        Returns:
            List of sessions
        """
        sessions = self.memory.session.list_sessions(include_archived)

        if not sessions:
            return "No sessions found."

        lines = ["=== Available Sessions ===", ""]

        for s in sessions:
            status = "[archived]" if s['archived'] else "[active]"
            lines.append(f"  {s['id']} {status}")

        return "\n".join(lines)

    # === Task Management ===

    def task_start(self, description: str) -> str:
        """
        Start a new task within the current session.

        Args:
            description: What we're trying to accomplish

        Returns:
            Task confirmation
        """
        ctx = self.memory.start_task(description)

        return f"Task started: {ctx.task_id}\nDescription: {description}\n\nWorking memory initialized."

    def task_complete(self, summary: str = None) -> str:
        """
        Complete the current task.

        Args:
            summary: Optional completion summary

        Returns:
            Confirmation
        """
        self.memory.complete_task(summary)
        return f"Task completed.\nSummary: {summary or 'No summary provided'}"

    def task_status(self) -> str:
        """
        Get current task status.

        Returns:
            Working memory summary
        """
        return self.memory.working.get_summary()

    # === Memory Recording ===

    def remember(
        self,
        what: str,
        category: str = "note",
        context: str = None
    ) -> str:
        """
        Store something in memory.

        Args:
            what: What to remember
            category: Type (file, decision, problem, insight, note)
            context: Additional context

        Returns:
            Confirmation
        """
        if category == "file":
            self.memory.remember_file_read(what, context)
            return f"Remembered file read: {what}"

        elif category == "decision":
            self.memory.remember_decision(what, context or "No reasoning provided")
            return f"Remembered decision: {what}"

        elif category == "problem":
            self.memory.remember_problem(what, context)
            return f"Remembered problem: {what}"

        elif category == "insight":
            self.memory.remember_insight(what)
            return f"Remembered insight: {what}"

        elif category == "error":
            self.memory.remember_error(what, context)
            return f"Remembered error: {what}"

        else:  # Generic note
            self.memory.working.add_note(what)
            return f"Noted: {what}"

    def hypothesis(
        self,
        description: str,
        confidence: float = 0.5,
        evidence: str = None,
        against: bool = False
    ) -> str:
        """
        Record or update a hypothesis.

        Args:
            description: The hypothesis
            confidence: Confidence level (0-1)
            evidence: Evidence for/against
            against: If True, evidence is against the hypothesis

        Returns:
            Confirmation
        """
        working = self.memory.working

        if not working.current_context:
            return "No active task. Start a task first."

        # Check if hypothesis exists
        existing_idx = None
        for i, h in enumerate(working.current_context.hypotheses):
            if h.get('description') == description:
                existing_idx = i
                break

        if existing_idx is not None:
            # Update existing
            if evidence:
                working.update_hypothesis(
                    existing_idx,
                    evidence_against=evidence if against else None,
                    evidence_for=evidence if not against else None
                )
            return f"Updated hypothesis: {description}"
        else:
            # Create new
            idx = working.add_hypothesis(description, confidence)
            if evidence:
                working.update_hypothesis(
                    idx,
                    evidence_against=evidence if against else None,
                    evidence_for=evidence if not against else None
                )
            return f"Added hypothesis [{confidence:.0%}]: {description}"

    def approach(self, description: str) -> str:
        """
        Set the current approach being tried.

        Args:
            description: The approach

        Returns:
            Confirmation
        """
        self.memory.working.set_approach(description)
        return f"Approach set: {description}"

    def blocker(self, description: str, resolved: bool = False) -> str:
        """
        Record or resolve a blocker.

        Args:
            description: The blocker
            resolved: If True, mark as resolved

        Returns:
            Confirmation
        """
        if resolved:
            self.memory.working.remove_blocker(description)
            return f"Blocker resolved: {description}"
        else:
            self.memory.working.add_blocker(description)
            return f"Blocker added: {description}"

    # === Learning ===

    def learn(
        self,
        subject: str,
        fact: str,
        category: str = "codebase",
        confidence: float = 1.0,
        tags: List[str] = None
    ) -> str:
        """
        Learn a new fact.

        Args:
            subject: What the fact is about
            fact: The fact itself
            category: Type (codebase, user, tool, api, pattern)
            confidence: How confident (0-1)
            tags: Tags for searching

        Returns:
            Confirmation
        """
        stored = self.memory.learn_fact(
            category=category,
            subject=subject,
            predicate="is",
            value=fact,
            confidence=confidence,
            tags=tags or []
        )

        return f"Learned [{category}]: {subject} → {fact} (confidence: {confidence:.0%})"

    def learn_preference(self, preference: str, value: Any) -> str:
        """
        Learn a user preference.

        Args:
            preference: The preference name
            value: The preference value

        Returns:
            Confirmation
        """
        self.memory.learn_preference(preference, value)
        return f"Learned preference: {preference} = {value}"

    def learn_pattern(
        self,
        name: str,
        description: str,
        example: str = None
    ) -> str:
        """
        Learn a coding pattern.

        Args:
            name: Pattern name
            description: What the pattern does
            example: Optional code example

        Returns:
            Confirmation
        """
        self.memory.learn_pattern(name, description, example)
        return f"Learned pattern: {name}\n{description}"

    # === Recall ===

    def recall(
        self,
        query: str = None,
        category: str = None,
        project: str = None,
        limit: int = 10
    ) -> str:
        """
        Recall information from memory.

        Args:
            query: Search term
            category: Filter by category
            project: Filter by project
            limit: Maximum results

        Returns:
            Formatted results
        """
        if query:
            results = self.memory.search_memory(query)
            lines = [f"=== Search Results for '{query}' ===", ""]

            if results['facts']:
                lines.append("Facts:")
                for f in results['facts'][:limit]:
                    lines.append(f"  • {f['subject']}: {f['value']}")
                lines.append("")

            if results['episodes']:
                lines.append("Episodes:")
                for e in results['episodes'][:limit]:
                    lines.append(f"  • {e['date']} [{e['project']}]: {e['goal']}")

            return "\n".join(lines)

        else:
            # Get facts with filters
            facts = self.memory.recall_facts(
                category=category,
                project=project
            )[:limit]

            if not facts:
                return "No facts found matching criteria."

            lines = ["=== Recalled Facts ===", ""]
            for f in facts:
                lines.append(f"[{f.category}] {f.subject}.{f.predicate} = {f.value}")
                lines.append(f"    Confidence: {f.confidence:.0%}, Learned: {f.learned_at[:10]}")
                lines.append("")

            return "\n".join(lines)

    def recall_project(self, project: str) -> str:
        """
        Get all context for a project.

        Args:
            project: Project name

        Returns:
            Project context
        """
        context = self.memory.get_project_context(project)

        lines = [f"=== Project Context: {project} ===", ""]

        if context['semantic_facts']:
            lines.append("Known Facts:")
            for f in context['semantic_facts'][:10]:
                lines.append(f"  • {f['subject']}: {f['value']}")
            lines.append("")

        if context['recent_episodes']:
            lines.append("Recent Sessions:")
            for e in context['recent_episodes']:
                lines.append(f"  • {e['date']}: {e['goal'] or 'No goal'}")
                if e['accomplished']:
                    lines.append(f"    Accomplished: {', '.join(e['accomplished'][:3])}")
            lines.append("")

        if context['unfinished_work']:
            lines.append("Unfinished Work:")
            for u in context['unfinished_work']:
                lines.append(f"  • {u['date']}: {len(u['items'])} items")
            lines.append("")

        return "\n".join(lines)

    def recall_history(self, days: int = 7) -> str:
        """
        Get recent session history.

        Args:
            days: How far back to look

        Returns:
            Session history
        """
        episodes = self.memory.episodic.recall_recent(days=days, limit=20)

        if not episodes:
            return f"No sessions in the last {days} days."

        lines = [f"=== Session History (Last {days} days) ===", ""]

        for ep in episodes:
            lines.append(f"## {ep.date} - {ep.project or 'general'}")
            if ep.goal:
                lines.append(f"   Goal: {ep.goal}")
            if ep.accomplished:
                lines.append(f"   Done: {', '.join(ep.accomplished[:3])}")
            if ep.unresolved:
                lines.append(f"   Unresolved: {len(ep.unresolved)} items")
            lines.append("")

        return "\n".join(lines)

    # === Reflection ===

    def reflect(self) -> str:
        """
        Get a full summary of memory state.

        Returns:
            Memory summary
        """
        return self.memory.get_full_summary()

    def context(self) -> str:
        """
        Get context for current work.

        Returns:
            Combined session and working memory context
        """
        session_ctx = self.memory.get_session_context()
        user_ctx = self.memory.get_user_context()

        lines = ["=== Current Context ===", ""]

        # Session info
        if session_ctx.get('status') != 'no_active_session':
            s = session_ctx['session']
            lines.append(f"Session: {s['id']}")
            lines.append(f"Project: {s['project'] or 'None'}")
            lines.append(f"Goal: {s['goal'] or 'None'}")
            lines.append("")

            w = session_ctx['working']
            if w['task']:
                lines.append(f"Current Task: {w['task']}")
                if w['approach']:
                    lines.append(f"Approach: {w['approach']}")
                if w['blockers']:
                    lines.append(f"Blockers: {', '.join(w['blockers'])}")
                lines.append("")

        # User preferences
        if user_ctx['preferences']:
            lines.append("User Preferences:")
            for k, v in list(user_ctx['preferences'].items())[:5]:
                lines.append(f"  • {k}: {v}")
            lines.append("")

        return "\n".join(lines)

    # === Maintenance ===

    def maintenance(
        self,
        archive_days: int = 7,
        decay_days: int = 30,
        cleanup_days: int = 3
    ) -> str:
        """
        Run memory maintenance tasks.

        Args:
            archive_days: Archive sessions inactive for this many days
            decay_days: Decay facts unverified for this many days
            cleanup_days: Clean up working memory older than this

        Returns:
            Maintenance report
        """
        results = self.janitor.run_maintenance(
            archive_sessions_days=archive_days,
            decay_facts_days=decay_days,
            cleanup_working_days=cleanup_days
        )

        lines = ["=== Memory Maintenance Complete ===", ""]
        lines.append(f"Sessions archived: {results['sessions_archived']}")
        lines.append(f"Facts decayed: {results['facts_decayed']}")
        lines.append(f"Working memory cleaned: {results['working_cleaned']}")
        lines.append(f"Duplicate facts removed: {results['duplicates_removed']}")

        if results['errors'] > 0:
            lines.append(f"Errors encountered: {results['errors']}")

        return "\n".join(lines)

    def memory_stats(self) -> str:
        """
        Get memory usage statistics.

        Returns:
            Stats summary
        """
        stats = self.janitor.get_stats()

        lines = ["=== Memory Statistics ===", ""]
        lines.append(f"Active sessions: {stats['active_sessions']}")
        lines.append(f"Archived sessions: {stats['archived_sessions']}")
        lines.append(f"Total episodes: {stats['total_episodes']}")
        lines.append(f"Total facts: {stats['total_facts']}")
        lines.append(f"Active tasks: {stats['active_tasks']}")

        return "\n".join(lines)

    def memory_report(self) -> str:
        """
        Generate detailed memory status report.

        Returns:
            Full report
        """
        return self.janitor.generate_report()
