"""
Fixture Store - Persistent storage for test fixtures.

Fixtures are captured command outputs or sample data used for testing.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger('crucible.fixtures')


class FixtureStore:
    """
    Manage fixture files on disk.

    Structure:
        fixtures/
        ├── linux/
        │   ├── lspci.txt
        │   ├── lspci.meta.json
        │   └── ...
        ├── commands/
        │   └── ...
        └── apis/
            └── ...
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self._ensure_directories()

    def _ensure_directories(self):
        """Create directory structure if needed."""
        for category in ['linux', 'commands', 'apis']:
            (self.base_path / category).mkdir(parents=True, exist_ok=True)

    def save(
        self,
        name: str,
        category: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """
        Save a fixture.

        Args:
            name: Fixture name (without extension)
            category: Category directory
            content: Fixture content
            metadata: Optional metadata dict
        """
        category_path = self.base_path / category
        category_path.mkdir(parents=True, exist_ok=True)

        # Save content
        content_path = category_path / f"{name}.txt"
        content_path.write_text(content, encoding='utf-8')

        # Save metadata
        if metadata:
            meta_path = category_path / f"{name}.meta.json"
            meta_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')

        logger.info(f"Saved fixture: {category}/{name}")

    def get(
        self,
        name: str,
        category: str = None
    ) -> str:
        """
        Retrieve a fixture.

        Args:
            name: Fixture name
            category: Category (if known)

        Returns:
            Fixture content or error message
        """
        # If category specified, look there
        if category:
            content_path = self.base_path / category / f"{name}.txt"
            if content_path.exists():
                return content_path.read_text(encoding='utf-8')
            return f"Fixture not found: {category}/{name}"

        # Search all categories
        for cat_dir in self.base_path.iterdir():
            if cat_dir.is_dir():
                content_path = cat_dir / f"{name}.txt"
                if content_path.exists():
                    return content_path.read_text(encoding='utf-8')

        return f"Fixture not found: {name}"

    def get_metadata(
        self,
        name: str,
        category: str
    ) -> Optional[Dict[str, Any]]:
        """Get fixture metadata."""
        meta_path = self.base_path / category / f"{name}.meta.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text(encoding='utf-8'))
        return None

    def list_fixtures(self, category: str = None) -> str:
        """
        List available fixtures.

        Args:
            category: Filter by category

        Returns:
            Formatted list
        """
        lines = ["=== Available Fixtures ===", ""]

        categories = [category] if category else [
            d.name for d in self.base_path.iterdir() if d.is_dir()
        ]

        total = 0
        for cat in sorted(categories):
            cat_path = self.base_path / cat
            if not cat_path.exists():
                continue

            fixtures = [
                f.stem for f in cat_path.glob("*.txt")
            ]

            if fixtures:
                lines.append(f"{cat}/")
                for name in sorted(fixtures):
                    meta = self.get_metadata(name, cat)
                    desc = ""
                    if meta and meta.get("description"):
                        desc = f" - {meta['description'][:50]}"
                    lines.append(f"  {name}{desc}")
                    total += 1
                lines.append("")

        if total == 0:
            return "No fixtures stored yet."

        lines.insert(1, f"Total: {total} fixture(s)")
        return "\n".join(lines)

    def delete(self, name: str, category: str) -> bool:
        """Delete a fixture."""
        content_path = self.base_path / category / f"{name}.txt"
        meta_path = self.base_path / category / f"{name}.meta.json"

        deleted = False
        if content_path.exists():
            content_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()

        return deleted

    def exists(self, name: str, category: str = None) -> bool:
        """Check if fixture exists."""
        if category:
            return (self.base_path / category / f"{name}.txt").exists()

        for cat_dir in self.base_path.iterdir():
            if cat_dir.is_dir():
                if (cat_dir / f"{name}.txt").exists():
                    return True
        return False
