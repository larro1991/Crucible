"""
Episodic Memory - History of past sessions.

Stores summaries of what happened in previous sessions:
- What was accomplished
- What problems occurred
- What was learned
- Patterns across sessions
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .session import SessionState

logger = logging.getLogger('crucible.memory.episodic')


@dataclass
class Episode:
    """
    Summary of a session converted to long-term memory.

    More compact than full SessionState - focuses on what matters
    for future recall.
    """
    session_id: str
    date: str
    project: Optional[str]
    goal: Optional[str]

    # Outcomes
    accomplished: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)

    # Key information
    decisions: List[str] = field(default_factory=list)
    problems_solved: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)

    # Unfinished business
    unresolved: List[str] = field(default_factory=list)
    follow_up_needed: List[str] = field(default_factory=list)

    # User context
    user_preferences_learned: Dict[str, Any] = field(default_factory=dict)

    # Meta
    duration_minutes: int = 0
    quality_score: Optional[float] = None  # Self-assessment: 0-1

    @classmethod
    def from_session(cls, session: SessionState, quality_score: float = None) -> 'Episode':
        """
        Convert a SessionState to an Episode for long-term storage.

        Args:
            session: The session to convert
            quality_score: Optional self-assessment of session quality

        Returns:
            Episode summary
        """
        # Calculate duration
        try:
            start = datetime.fromisoformat(session.started_at.rstrip('Z'))
            end = datetime.fromisoformat(session.updated_at.rstrip('Z'))
            duration = int((end - start).total_seconds() / 60)
        except:
            duration = 0

        # Extract decision summaries
        decisions = [d.get('description', '') for d in session.decisions]

        # Extract solved problems
        solved = [
            p.get('description', '')
            for p in session.problems
            if p.get('resolved', False)
        ]

        # Extract unresolved issues
        unresolved = [
            p.get('description', '')
            for p in session.problems
            if not p.get('resolved', False)
        ]

        # All changed files
        files_changed = list(set(
            session.files_modified + session.files_created
        ))

        return cls(
            session_id=session.session_id,
            date=session.started_at[:10],  # Just date portion
            project=session.project,
            goal=session.primary_goal,
            accomplished=session.tasks_completed,
            files_changed=files_changed,
            decisions=decisions,
            problems_solved=solved,
            insights=session.key_insights,
            unresolved=unresolved,
            follow_up_needed=session.tasks_pending,
            user_preferences_learned=session.user_preferences,
            duration_minutes=duration,
            quality_score=quality_score
        )


class EpisodicMemory:
    """
    Manage long-term episode storage.

    Allows Claude to:
    - Remember what happened in past sessions
    - Learn from previous experiences
    - Identify patterns across sessions
    - Resume work where left off
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path) / 'episodes'
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store_episode(self, episode: Episode):
        """
        Store an episode in long-term memory.

        Args:
            episode: Episode to store
        """
        # Store by project if available, otherwise general
        if episode.project:
            file_path = self.base_path / f"{episode.project}.yaml"
        else:
            file_path = self.base_path / "general.yaml"

        # Load existing episodes
        episodes = self._load_file(file_path)

        # Check for duplicate
        existing_idx = None
        for i, e in enumerate(episodes):
            if e.get('session_id') == episode.session_id:
                existing_idx = i
                break

        episode_dict = asdict(episode)
        if existing_idx is not None:
            episodes[existing_idx] = episode_dict
        else:
            episodes.append(episode_dict)

        self._save_file(file_path, episodes)
        logger.info(f"Stored episode: {episode.session_id}")

    def convert_session(self, session: SessionState, quality_score: float = None) -> Episode:
        """
        Convert a session to an episode and store it.

        Args:
            session: Session to convert
            quality_score: Optional quality assessment

        Returns:
            The created Episode
        """
        episode = Episode.from_session(session, quality_score)
        self.store_episode(episode)
        return episode

    def recall_project(self, project: str, limit: int = 10) -> List[Episode]:
        """
        Recall episodes for a specific project.

        Args:
            project: Project name
            limit: Maximum episodes to return

        Returns:
            List of Episodes, most recent first
        """
        file_path = self.base_path / f"{project}.yaml"
        episodes = self._load_file(file_path)

        # Convert to Episode objects
        result = [Episode(**e) for e in episodes]

        # Sort by date descending
        result.sort(key=lambda x: x.date, reverse=True)

        return result[:limit]

    def recall_recent(self, days: int = 7, limit: int = 20) -> List[Episode]:
        """
        Recall recent episodes across all projects.

        Args:
            days: How far back to look
            limit: Maximum episodes to return

        Returns:
            List of Episodes, most recent first
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        all_episodes = []
        for yaml_file in self.base_path.glob("*.yaml"):
            episodes = self._load_file(yaml_file)
            for e in episodes:
                if e.get('date', '') >= cutoff:
                    all_episodes.append(Episode(**e))

        # Sort by date descending
        all_episodes.sort(key=lambda x: x.date, reverse=True)

        return all_episodes[:limit]

    def recall_unfinished(self, project: str = None) -> List[Episode]:
        """
        Recall episodes with unfinished business.

        Args:
            project: Optionally filter by project

        Returns:
            Episodes that have unresolved items or follow-up needed
        """
        all_episodes = []

        if project:
            file_path = self.base_path / f"{project}.yaml"
            if file_path.exists():
                all_episodes = [Episode(**e) for e in self._load_file(file_path)]
        else:
            for yaml_file in self.base_path.glob("*.yaml"):
                episodes = self._load_file(yaml_file)
                all_episodes.extend([Episode(**e) for e in episodes])

        # Filter to those with unfinished items
        unfinished = [
            e for e in all_episodes
            if e.unresolved or e.follow_up_needed
        ]

        # Sort by date descending
        unfinished.sort(key=lambda x: x.date, reverse=True)

        return unfinished

    def search_episodes(
        self,
        query: str,
        project: str = None,
        limit: int = 10
    ) -> List[Episode]:
        """
        Search episodes by keyword.

        Args:
            query: Search term
            project: Optionally filter by project
            limit: Maximum results

        Returns:
            Matching Episodes
        """
        all_episodes = []

        if project:
            file_path = self.base_path / f"{project}.yaml"
            if file_path.exists():
                all_episodes = self._load_file(file_path)
        else:
            for yaml_file in self.base_path.glob("*.yaml"):
                all_episodes.extend(self._load_file(yaml_file))

        query_lower = query.lower()
        matches = []

        for e in all_episodes:
            # Search in various fields
            searchable = [
                e.get('goal', ''),
                ' '.join(e.get('accomplished', [])),
                ' '.join(e.get('decisions', [])),
                ' '.join(e.get('insights', [])),
                ' '.join(e.get('problems_solved', [])),
            ]

            if any(query_lower in s.lower() for s in searchable):
                matches.append(Episode(**e))

        # Sort by date descending
        matches.sort(key=lambda x: x.date, reverse=True)

        return matches[:limit]

    def get_project_timeline(self, project: str) -> str:
        """
        Get a narrative timeline for a project.

        Args:
            project: Project name

        Returns:
            Formatted timeline string
        """
        episodes = self.recall_project(project, limit=50)

        if not episodes:
            return f"No history found for project: {project}"

        lines = [f"=== Timeline: {project} ===", ""]

        for ep in reversed(episodes):  # Oldest first
            lines.append(f"## {ep.date} (Session: {ep.session_id})")
            if ep.goal:
                lines.append(f"   Goal: {ep.goal}")

            if ep.accomplished:
                lines.append("   Accomplished:")
                for item in ep.accomplished:
                    lines.append(f"     - {item}")

            if ep.problems_solved:
                lines.append("   Problems Solved:")
                for item in ep.problems_solved:
                    lines.append(f"     - {item}")

            if ep.insights:
                lines.append("   Insights:")
                for item in ep.insights:
                    lines.append(f"     - {item}")

            if ep.unresolved:
                lines.append("   Left Unresolved:")
                for item in ep.unresolved:
                    lines.append(f"     - {item}")

            lines.append("")

        return "\n".join(lines)

    def get_patterns(self, project: str = None, min_occurrences: int = 2) -> Dict[str, int]:
        """
        Identify recurring patterns across episodes.

        Args:
            project: Optionally filter by project
            min_occurrences: Minimum times something must appear

        Returns:
            Dictionary of patterns and their counts
        """
        all_episodes = []

        if project:
            file_path = self.base_path / f"{project}.yaml"
            if file_path.exists():
                all_episodes = self._load_file(file_path)
        else:
            for yaml_file in self.base_path.glob("*.yaml"):
                all_episodes.extend(self._load_file(yaml_file))

        # Count problem types, insight themes, etc.
        patterns = {}

        for e in all_episodes:
            # Look at problems
            for problem in e.get('problems_solved', []):
                # Extract key words/themes
                key = problem.lower()[:50]  # First 50 chars as key
                patterns[f"problem:{key}"] = patterns.get(f"problem:{key}", 0) + 1

            # Look at insights
            for insight in e.get('insights', []):
                key = insight.lower()[:50]
                patterns[f"insight:{key}"] = patterns.get(f"insight:{key}", 0) + 1

        # Filter to min occurrences
        return {k: v for k, v in patterns.items() if v >= min_occurrences}

    def _load_file(self, path: Path) -> List[Dict]:
        """Load episodes from a file."""
        if not path.exists():
            return []

        content = path.read_text(encoding='utf-8')

        if HAS_YAML:
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)

        return data if isinstance(data, list) else []

    def _save_file(self, path: Path, episodes: List[Dict]):
        """Save episodes to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_YAML:
            content = yaml.dump(episodes, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(episodes, indent=2)

        path.write_text(content, encoding='utf-8')


# Need timedelta for recall_recent
from datetime import timedelta
