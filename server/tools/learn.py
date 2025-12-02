"""
Learnings Tool - Persistent knowledge across sessions.

Allows Claude to:
- Store learnings about projects, patterns, mistakes
- Recall learnings by topic, tag, or search
- Build institutional knowledge over time
"""

from typing import Optional, List
import logging

from ..persistence.learnings import LearningsStore, Learning

logger = logging.getLogger('crucible.learn')


class LearningsTool:
    """
    Manage persistent learnings.

    Categories of learnings:
    - patterns: What works well
    - mistakes: What to avoid
    - projects: Project-specific knowledge
    - tools: Tool usage and quirks
    """

    def __init__(self, learnings_store: LearningsStore):
        self.store = learnings_store

    def note(
        self,
        topic: str,
        title: str,
        content: str,
        tags: List[str] = None,
        project: str = None
    ) -> str:
        """
        Store a learning.

        Args:
            topic: Category (patterns, mistakes, projects, tools, etc.)
            title: Brief title
            content: The learning content
            tags: Optional tags for searching
            project: Related project name

        Returns:
            Confirmation message
        """
        learning = Learning(
            topic=topic,
            title=title,
            content=content,
            tags=tags or [],
            project=project
        )

        self.store.save(learning)

        tag_str = f" [tags: {', '.join(tags)}]" if tags else ""
        project_str = f" [project: {project}]" if project else ""

        return f"Noted: '{title}' under {topic}{tag_str}{project_str}"

    def recall(
        self,
        topic: str = None,
        tag: str = None,
        search: str = None,
        project: str = None
    ) -> str:
        """
        Retrieve learnings.

        Args:
            topic: Filter by topic
            tag: Filter by tag
            search: Search in title and content
            project: Filter by project

        Returns:
            Formatted learnings
        """
        learnings = self.store.search(
            topic=topic,
            tag=tag,
            search=search,
            project=project
        )

        if not learnings:
            filters = []
            if topic: filters.append(f"topic={topic}")
            if tag: filters.append(f"tag={tag}")
            if search: filters.append(f"search='{search}'")
            if project: filters.append(f"project={project}")

            filter_str = ", ".join(filters) if filters else "none"
            return f"No learnings found (filters: {filter_str})"

        lines = [f"=== Found {len(learnings)} learning(s) ===", ""]

        for l in learnings:
            lines.append(f"## [{l.topic}] {l.title}")
            if l.project:
                lines.append(f"   Project: {l.project}")
            if l.tags:
                lines.append(f"   Tags: {', '.join(l.tags)}")
            lines.append(f"   Recorded: {l.created_at[:10]}")
            lines.append("")
            # Indent content
            for content_line in l.content.split('\n'):
                lines.append(f"   {content_line}")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def list_topics(self) -> str:
        """List all topics with counts."""
        topics = self.store.get_topics()

        if not topics:
            return "No learnings stored yet."

        lines = ["=== Learning Topics ===", ""]
        for topic, count in sorted(topics.items()):
            lines.append(f"  {topic}: {count} learning(s)")

        return "\n".join(lines)

    def list_projects(self) -> str:
        """List all projects with learning counts."""
        projects = self.store.get_projects()

        if not projects:
            return "No project-specific learnings stored."

        lines = ["=== Projects with Learnings ===", ""]
        for project, count in sorted(projects.items()):
            lines.append(f"  {project}: {count} learning(s)")

        return "\n".join(lines)


# Seed learnings to bootstrap the system
SEED_LEARNINGS = [
    {
        "topic": "patterns",
        "title": "Always write tests alongside code",
        "content": "When writing a function, also write at least one test case. "
                   "This catches errors before delivery and demonstrates intended usage.",
        "tags": ["testing", "quality"]
    },
    {
        "topic": "patterns",
        "title": "Use mock mode for cross-platform code",
        "content": "When writing code that depends on Linux tools (lspci, etc.), "
                   "include a mock_mode parameter that returns sample data. "
                   "This allows testing on Windows during development.",
        "tags": ["cross-platform", "testing"]
    },
    {
        "topic": "mistakes",
        "title": "Don't assume imports work",
        "content": "Always verify imports actually resolve. Just because syntax is correct "
                   "doesn't mean the module exists or is installed. "
                   "Use try/except ImportError guards for optional dependencies.",
        "tags": ["imports", "dependencies"]
    },
    {
        "topic": "tools",
        "title": "Python subprocess timeout",
        "content": "Always use timeout parameter with subprocess.run(). "
                   "Without it, a hanging process will block forever. "
                   "Default to 30 seconds for most operations.",
        "tags": ["python", "subprocess"]
    },
]
