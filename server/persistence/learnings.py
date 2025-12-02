"""
Learnings Store - Persistent knowledge base.

Stores learnings in YAML files organized by topic.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger('crucible.learnings')


@dataclass
class Learning:
    """A single learning entry."""
    topic: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    project: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    id: str = ""

    def __post_init__(self):
        now = datetime.utcnow().isoformat() + "Z"
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.id:
            import hashlib
            # Create deterministic ID from content
            content_hash = hashlib.md5(
                f"{self.topic}:{self.title}".encode()
            ).hexdigest()[:8]
            self.id = f"{self.topic[:3]}_{content_hash}"


class LearningsStore:
    """
    Manage learning files on disk.

    Structure:
        learnings/
        ├── patterns.yaml
        ├── mistakes.yaml
        ├── projects/
        │   ├── ember.yaml
        │   ├── cinder.yaml
        │   └── intuitive-os.yaml
        └── index.json  (search index)
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / 'projects').mkdir(exist_ok=True)

    def save(self, learning: Learning):
        """
        Save a learning.

        Args:
            learning: Learning object to save
        """
        learning.updated_at = datetime.utcnow().isoformat() + "Z"

        # Determine file path
        if learning.project:
            file_path = self.base_path / 'projects' / f"{learning.project}.yaml"
        else:
            file_path = self.base_path / f"{learning.topic}.yaml"

        # Load existing learnings
        learnings = self._load_file(file_path)

        # Update or append
        existing_idx = None
        for i, l in enumerate(learnings):
            if l.get('id') == learning.id or (
                l.get('topic') == learning.topic and
                l.get('title') == learning.title
            ):
                existing_idx = i
                break

        learning_dict = asdict(learning)
        if existing_idx is not None:
            learnings[existing_idx] = learning_dict
        else:
            learnings.append(learning_dict)

        # Save
        self._save_file(file_path, learnings)
        logger.info(f"Saved learning: {learning.topic}/{learning.title}")

    def search(
        self,
        topic: str = None,
        tag: str = None,
        search: str = None,
        project: str = None
    ) -> List[Learning]:
        """
        Search learnings.

        Args:
            topic: Filter by topic
            tag: Filter by tag
            search: Search in title and content
            project: Filter by project

        Returns:
            List of matching Learning objects
        """
        all_learnings = self._load_all()
        results = []

        for l in all_learnings:
            # Topic filter
            if topic and l.get('topic') != topic:
                continue

            # Tag filter
            if tag and tag not in l.get('tags', []):
                continue

            # Project filter
            if project and l.get('project') != project:
                continue

            # Search filter
            if search:
                search_lower = search.lower()
                if (search_lower not in l.get('title', '').lower() and
                    search_lower not in l.get('content', '').lower()):
                    continue

            results.append(Learning(**l))

        # Sort by created_at descending
        results.sort(key=lambda x: x.created_at, reverse=True)

        return results

    def get_topics(self) -> Dict[str, int]:
        """Get all topics with counts."""
        all_learnings = self._load_all()
        topics = {}

        for l in all_learnings:
            topic = l.get('topic', 'unknown')
            topics[topic] = topics.get(topic, 0) + 1

        return topics

    def get_projects(self) -> Dict[str, int]:
        """Get all projects with counts."""
        all_learnings = self._load_all()
        projects = {}

        for l in all_learnings:
            project = l.get('project')
            if project:
                projects[project] = projects.get(project, 0) + 1

        return projects

    def _load_file(self, path: Path) -> List[Dict]:
        """Load learnings from a single file."""
        if not path.exists():
            return []

        content = path.read_text(encoding='utf-8')

        if HAS_YAML:
            data = yaml.safe_load(content)
        else:
            # Fallback to JSON
            data = json.loads(content)

        return data if isinstance(data, list) else []

    def _save_file(self, path: Path, learnings: List[Dict]):
        """Save learnings to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_YAML:
            content = yaml.dump(learnings, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(learnings, indent=2)

        path.write_text(content, encoding='utf-8')

    def _load_all(self) -> List[Dict]:
        """Load all learnings from all files."""
        all_learnings = []

        # Load topic files
        for yaml_file in self.base_path.glob("*.yaml"):
            all_learnings.extend(self._load_file(yaml_file))

        # Load project files
        projects_dir = self.base_path / 'projects'
        if projects_dir.exists():
            for yaml_file in projects_dir.glob("*.yaml"):
                all_learnings.extend(self._load_file(yaml_file))

        return all_learnings

    def delete(self, learning_id: str) -> bool:
        """Delete a learning by ID."""
        # Search all files for the learning
        for yaml_file in list(self.base_path.glob("*.yaml")) + \
                         list((self.base_path / 'projects').glob("*.yaml")):
            learnings = self._load_file(yaml_file)
            original_len = len(learnings)

            learnings = [l for l in learnings if l.get('id') != learning_id]

            if len(learnings) < original_len:
                self._save_file(yaml_file, learnings)
                return True

        return False
