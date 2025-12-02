"""
Semantic Memory - Facts and knowledge about codebases.

Stores structured knowledge:
- Codebase architecture facts
- User preferences
- Tool configurations
- API patterns
- Common solutions
"""

import json
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

logger = logging.getLogger('crucible.memory.semantic')


@dataclass
class Fact:
    """
    A single fact or piece of knowledge.

    Facts are structured knowledge that can be:
    - Verified/updated over time
    - Linked to sources
    - Categorized for retrieval
    """
    category: str  # codebase, user, tool, api, pattern
    subject: str   # What is this about
    predicate: str # The relationship or property
    value: Any     # The actual fact

    # Metadata
    confidence: float = 1.0  # 0-1, how confident we are
    source: Optional[str] = None  # Where did we learn this
    project: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # Timestamps
    learned_at: str = ""
    verified_at: str = ""
    id: str = ""

    def __post_init__(self):
        now = datetime.utcnow().isoformat() + "Z"
        if not self.learned_at:
            self.learned_at = now
        if not self.verified_at:
            self.verified_at = now
        if not self.id:
            content = f"{self.category}:{self.subject}:{self.predicate}"
            self.id = hashlib.md5(content.encode()).hexdigest()[:12]


class SemanticMemory:
    """
    Manage factual knowledge storage.

    Allows Claude to:
    - Store facts about codebases, users, tools
    - Query knowledge efficiently
    - Update facts as things change
    - Maintain confidence levels
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path) / 'semantic'
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Category-specific files
        self.categories = ['codebase', 'user', 'tool', 'api', 'pattern']
        for cat in self.categories:
            (self.base_path / f"{cat}.yaml").touch(exist_ok=True)

    def learn(
        self,
        category: str,
        subject: str,
        predicate: str,
        value: Any,
        confidence: float = 1.0,
        source: str = None,
        project: str = None,
        tags: List[str] = None
    ) -> Fact:
        """
        Store a new fact or update existing one.

        Args:
            category: Type of knowledge (codebase, user, tool, api, pattern)
            subject: What the fact is about
            predicate: The relationship/property
            value: The actual value
            confidence: How confident (0-1)
            source: Where we learned this
            project: Related project
            tags: Tags for searching

        Returns:
            The stored Fact
        """
        fact = Fact(
            category=category,
            subject=subject,
            predicate=predicate,
            value=value,
            confidence=confidence,
            source=source,
            project=project,
            tags=tags or []
        )

        # Check for existing fact with same subject/predicate
        file_path = self.base_path / f"{category}.yaml"
        facts = self._load_file(file_path)

        existing_idx = None
        for i, f in enumerate(facts):
            if f.get('subject') == subject and f.get('predicate') == predicate:
                existing_idx = i
                break

        fact_dict = asdict(fact)
        if existing_idx is not None:
            # Update existing - keep original learned_at
            fact_dict['learned_at'] = facts[existing_idx].get('learned_at', fact.learned_at)
            facts[existing_idx] = fact_dict
            logger.info(f"Updated fact: {subject}.{predicate}")
        else:
            facts.append(fact_dict)
            logger.info(f"Learned fact: {subject}.{predicate}")

        self._save_file(file_path, facts)
        return fact

    def recall(
        self,
        subject: str = None,
        category: str = None,
        predicate: str = None,
        project: str = None,
        tag: str = None,
        min_confidence: float = 0.0
    ) -> List[Fact]:
        """
        Query stored facts.

        Args:
            subject: Filter by subject
            category: Filter by category
            predicate: Filter by predicate
            project: Filter by project
            tag: Filter by tag
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching Facts
        """
        all_facts = []

        # Load from relevant categories
        categories_to_search = [category] if category else self.categories

        for cat in categories_to_search:
            file_path = self.base_path / f"{cat}.yaml"
            if file_path.exists():
                facts = self._load_file(file_path)
                all_facts.extend(facts)

        # Apply filters
        results = []
        for f in all_facts:
            if subject and f.get('subject') != subject:
                continue
            if predicate and f.get('predicate') != predicate:
                continue
            if project and f.get('project') != project:
                continue
            if tag and tag not in f.get('tags', []):
                continue
            if f.get('confidence', 1.0) < min_confidence:
                continue

            results.append(Fact(**f))

        # Sort by confidence descending
        results.sort(key=lambda x: x.confidence, reverse=True)

        return results

    def get_fact(self, subject: str, predicate: str, category: str = None) -> Optional[Fact]:
        """
        Get a specific fact.

        Args:
            subject: The subject
            predicate: The predicate
            category: Optional category to narrow search

        Returns:
            The Fact if found, None otherwise
        """
        facts = self.recall(subject=subject, predicate=predicate, category=category)
        return facts[0] if facts else None

    def forget(self, fact_id: str) -> bool:
        """
        Remove a fact by ID.

        Args:
            fact_id: The fact ID

        Returns:
            True if removed, False if not found
        """
        for cat in self.categories:
            file_path = self.base_path / f"{cat}.yaml"
            facts = self._load_file(file_path)
            original_len = len(facts)

            facts = [f for f in facts if f.get('id') != fact_id]

            if len(facts) < original_len:
                self._save_file(file_path, facts)
                logger.info(f"Forgot fact: {fact_id}")
                return True

        return False

    def verify(self, fact_id: str, new_confidence: float = None) -> bool:
        """
        Mark a fact as verified (updates verified_at timestamp).

        Args:
            fact_id: The fact to verify
            new_confidence: Optionally update confidence

        Returns:
            True if found and updated
        """
        for cat in self.categories:
            file_path = self.base_path / f"{cat}.yaml"
            facts = self._load_file(file_path)

            for i, f in enumerate(facts):
                if f.get('id') == fact_id:
                    f['verified_at'] = datetime.utcnow().isoformat() + "Z"
                    if new_confidence is not None:
                        f['confidence'] = new_confidence
                    facts[i] = f
                    self._save_file(file_path, facts)
                    return True

        return False

    def decay_confidence(self, days_old: int = 30, decay_factor: float = 0.9):
        """
        Reduce confidence of old unverified facts.

        Args:
            days_old: How old before decay applies
            decay_factor: Multiplier to apply to confidence
        """
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days_old)).isoformat() + "Z"

        for cat in self.categories:
            file_path = self.base_path / f"{cat}.yaml"
            facts = self._load_file(file_path)
            modified = False

            for f in facts:
                if f.get('verified_at', '') < cutoff:
                    old_conf = f.get('confidence', 1.0)
                    new_conf = max(0.1, old_conf * decay_factor)  # Floor at 0.1
                    if new_conf != old_conf:
                        f['confidence'] = new_conf
                        modified = True

            if modified:
                self._save_file(file_path, facts)

    # === High-level knowledge helpers ===

    def learn_codebase(
        self,
        project: str,
        subject: str,
        fact: str,
        source: str = None
    ) -> Fact:
        """Learn something about a codebase."""
        return self.learn(
            category='codebase',
            subject=f"{project}:{subject}",
            predicate='is',
            value=fact,
            source=source,
            project=project
        )

    def learn_user_preference(
        self,
        preference: str,
        value: Any,
        source: str = "observation"
    ) -> Fact:
        """Learn a user preference."""
        return self.learn(
            category='user',
            subject='preferences',
            predicate=preference,
            value=value,
            source=source
        )

    def learn_pattern(
        self,
        pattern_name: str,
        description: str,
        example: str = None,
        project: str = None
    ) -> Fact:
        """Learn a coding pattern."""
        return self.learn(
            category='pattern',
            subject=pattern_name,
            predicate='description',
            value={'description': description, 'example': example},
            project=project,
            tags=['pattern']
        )

    def get_codebase_facts(self, project: str) -> List[Fact]:
        """Get all facts about a codebase."""
        facts = self.recall(category='codebase', project=project)
        # Also get facts with subject starting with project:
        all_facts = self.recall(category='codebase')
        for f in all_facts:
            if f.subject.startswith(f"{project}:") and f not in facts:
                facts.append(f)
        return facts

    def get_user_preferences(self) -> Dict[str, Any]:
        """Get all user preferences as a dictionary."""
        facts = self.recall(category='user', subject='preferences')
        return {f.predicate: f.value for f in facts}

    def summarize_knowledge(self, project: str = None) -> str:
        """
        Generate a summary of stored knowledge.

        Args:
            project: Optionally filter by project

        Returns:
            Formatted summary string
        """
        lines = ["=== Semantic Memory Summary ===", ""]

        for cat in self.categories:
            file_path = self.base_path / f"{cat}.yaml"
            facts = self._load_file(file_path)

            if project:
                facts = [f for f in facts if f.get('project') == project or
                        f.get('subject', '').startswith(f"{project}:")]

            if facts:
                lines.append(f"## {cat.title()} ({len(facts)} facts)")
                for f in facts[:10]:  # Limit display
                    conf = f.get('confidence', 1.0)
                    lines.append(f"  • {f.get('subject')}.{f.get('predicate')} = {f.get('value')} (conf: {conf:.2f})")
                if len(facts) > 10:
                    lines.append(f"  ... and {len(facts) - 10} more")
                lines.append("")

        return "\n".join(lines)

    def _load_file(self, path: Path) -> List[Dict]:
        """Load facts from a file."""
        if not path.exists():
            return []

        content = path.read_text(encoding='utf-8')
        if not content.strip():
            return []

        if HAS_YAML:
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)

        return data if isinstance(data, list) else []

    def _save_file(self, path: Path, facts: List[Dict]):
        """Save facts to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_YAML:
            content = yaml.dump(facts, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(facts, indent=2)

        path.write_text(content, encoding='utf-8')
