"""
Memory Janitor - Automated cleanup and maintenance.

Provides scheduled maintenance tasks:
- Archive old sessions
- Decay stale fact confidence
- Clean up orphaned working memory
- Compress old episodes
- Generate summary reports
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .session import SessionMemory, SessionState
from .episodic import EpisodicMemory, Episode
from .semantic import SemanticMemory
from .working import WorkingMemory

logger = logging.getLogger('crucible.memory.janitor')


class MemoryJanitor:
    """
    Automated memory maintenance.

    Responsibilities:
    - Archive abandoned sessions (no activity for X days)
    - Decay confidence of unverified facts
    - Clean up completed working memory tasks
    - Compact episode history
    - Remove duplicate facts
    """

    def __init__(
        self,
        session: SessionMemory,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        working: WorkingMemory
    ):
        self.session = session
        self.episodic = episodic
        self.semantic = semantic
        self.working = working

    def run_maintenance(
        self,
        archive_sessions_days: int = 7,
        decay_facts_days: int = 30,
        decay_factor: float = 0.9,
        cleanup_working_days: int = 3
    ) -> Dict[str, int]:
        """
        Run all maintenance tasks.

        Args:
            archive_sessions_days: Archive sessions inactive for this many days
            decay_facts_days: Start decaying facts after this many days unverified
            decay_factor: Multiply confidence by this factor
            cleanup_working_days: Clean up working memory older than this

        Returns:
            Dictionary of actions taken
        """
        results = {
            'sessions_archived': 0,
            'facts_decayed': 0,
            'working_cleaned': 0,
            'duplicates_removed': 0,
            'errors': 0
        }

        try:
            results['sessions_archived'] = self._archive_old_sessions(archive_sessions_days)
        except Exception as e:
            logger.error(f"Error archiving sessions: {e}")
            results['errors'] += 1

        try:
            results['facts_decayed'] = self._decay_old_facts(decay_facts_days, decay_factor)
        except Exception as e:
            logger.error(f"Error decaying facts: {e}")
            results['errors'] += 1

        try:
            results['working_cleaned'] = self._cleanup_working_memory(cleanup_working_days)
        except Exception as e:
            logger.error(f"Error cleaning working memory: {e}")
            results['errors'] += 1

        try:
            results['duplicates_removed'] = self._remove_duplicate_facts()
        except Exception as e:
            logger.error(f"Error removing duplicates: {e}")
            results['errors'] += 1

        logger.info(f"Maintenance complete: {results}")
        return results

    def _archive_old_sessions(self, days_old: int) -> int:
        """Archive sessions that haven't been updated in a while."""
        archived = 0
        cutoff = (datetime.utcnow() - timedelta(days=days_old)).isoformat() + "Z"

        sessions_path = self.session.base_path
        archive_path = sessions_path / 'archive'
        archive_path.mkdir(exist_ok=True)

        for session_file in sessions_path.glob("sess_*.yaml"):
            try:
                content = session_file.read_text(encoding='utf-8')
                if HAS_YAML:
                    data = yaml.safe_load(content)
                else:
                    data = json.loads(content)

                updated_at = data.get('updated_at', '')
                if updated_at < cutoff:
                    # Convert to episode before archiving
                    session = SessionState(**data)
                    self.episodic.convert_session(session)

                    # Move to archive
                    session_file.rename(archive_path / session_file.name)
                    archived += 1
                    logger.info(f"Archived old session: {session_file.name}")

            except Exception as e:
                logger.warning(f"Error processing {session_file}: {e}")

        return archived

    def _decay_old_facts(self, days_old: int, decay_factor: float) -> int:
        """Reduce confidence of facts that haven't been verified recently."""
        decayed = 0
        cutoff = (datetime.utcnow() - timedelta(days=days_old)).isoformat() + "Z"

        for category in self.semantic.categories:
            file_path = self.semantic.base_path / f"{category}.yaml"
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding='utf-8')
            if not content.strip():
                continue

            if HAS_YAML:
                facts = yaml.safe_load(content)
            else:
                facts = json.loads(content)

            if not facts:
                continue

            modified = False
            for fact in facts:
                verified_at = fact.get('verified_at', '')
                if verified_at < cutoff:
                    old_conf = fact.get('confidence', 1.0)
                    new_conf = max(0.1, old_conf * decay_factor)
                    if abs(new_conf - old_conf) > 0.01:  # Only if meaningful change
                        fact['confidence'] = round(new_conf, 3)
                        modified = True
                        decayed += 1

            if modified:
                if HAS_YAML:
                    new_content = yaml.dump(facts, default_flow_style=False, sort_keys=False)
                else:
                    new_content = json.dumps(facts, indent=2)
                file_path.write_text(new_content, encoding='utf-8')

        return decayed

    def _cleanup_working_memory(self, days_old: int) -> int:
        """Clean up old working memory contexts."""
        cleaned = 0
        cutoff = (datetime.utcnow() - timedelta(days=days_old)).isoformat() + "Z"

        working_path = self.working.base_path
        completed_path = working_path / 'completed'
        completed_path.mkdir(exist_ok=True)

        for task_file in working_path.glob("task_*.yaml"):
            try:
                content = task_file.read_text(encoding='utf-8')
                if HAS_YAML:
                    data = yaml.safe_load(content)
                else:
                    data = json.loads(content)

                started_at = data.get('started_at', '')
                if started_at < cutoff:
                    # Move to completed/archived
                    task_file.rename(completed_path / task_file.name)
                    cleaned += 1
                    logger.info(f"Cleaned old task: {task_file.name}")

            except Exception as e:
                logger.warning(f"Error processing {task_file}: {e}")

        return cleaned

    def _remove_duplicate_facts(self) -> int:
        """Remove duplicate facts keeping the most confident/recent."""
        removed = 0

        for category in self.semantic.categories:
            file_path = self.semantic.base_path / f"{category}.yaml"
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding='utf-8')
            if not content.strip():
                continue

            if HAS_YAML:
                facts = yaml.safe_load(content)
            else:
                facts = json.loads(content)

            if not facts:
                continue

            # Group by subject+predicate
            seen = {}
            unique_facts = []

            for fact in facts:
                key = f"{fact.get('subject')}:{fact.get('predicate')}"

                if key in seen:
                    # Compare and keep better one
                    existing = seen[key]
                    existing_conf = existing.get('confidence', 0)
                    new_conf = fact.get('confidence', 0)

                    if new_conf > existing_conf:
                        # Replace with new one
                        unique_facts.remove(existing)
                        unique_facts.append(fact)
                        seen[key] = fact
                        removed += 1
                    else:
                        # Keep existing, discard new
                        removed += 1
                else:
                    seen[key] = fact
                    unique_facts.append(fact)

            if removed > 0:
                if HAS_YAML:
                    new_content = yaml.dump(unique_facts, default_flow_style=False, sort_keys=False)
                else:
                    new_content = json.dumps(unique_facts, indent=2)
                file_path.write_text(new_content, encoding='utf-8')

        return removed

    def generate_report(self) -> str:
        """Generate a status report of memory usage."""
        lines = ["=" * 60]
        lines.append("MEMORY SYSTEM STATUS REPORT")
        lines.append(f"Generated: {datetime.utcnow().isoformat()}")
        lines.append("=" * 60)
        lines.append("")

        # Sessions
        sessions = list(self.session.base_path.glob("sess_*.yaml"))
        archived = list((self.session.base_path / 'archive').glob("sess_*.yaml")) if (self.session.base_path / 'archive').exists() else []
        lines.append(f"Sessions:")
        lines.append(f"  Active: {len(sessions)}")
        lines.append(f"  Archived: {len(archived)}")
        lines.append("")

        # Episodes
        episode_files = list(self.episodic.base_path.glob("*.yaml"))
        total_episodes = 0
        for ef in episode_files:
            content = ef.read_text(encoding='utf-8')
            if content.strip():
                if HAS_YAML:
                    episodes = yaml.safe_load(content)
                else:
                    episodes = json.loads(content)
                if episodes:
                    total_episodes += len(episodes)

        lines.append(f"Episodes:")
        lines.append(f"  Total: {total_episodes}")
        lines.append(f"  Projects: {len(episode_files)}")
        lines.append("")

        # Semantic facts
        lines.append(f"Semantic Facts:")
        for category in self.semantic.categories:
            file_path = self.semantic.base_path / f"{category}.yaml"
            count = 0
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                if content.strip():
                    if HAS_YAML:
                        facts = yaml.safe_load(content)
                    else:
                        facts = json.loads(content)
                    if facts:
                        count = len(facts)
            lines.append(f"  {category}: {count}")
        lines.append("")

        # Working memory
        tasks = list(self.working.base_path.glob("task_*.yaml"))
        completed = list((self.working.base_path / 'completed').glob("task_*.yaml")) if (self.working.base_path / 'completed').exists() else []
        lines.append(f"Working Memory:")
        lines.append(f"  Active tasks: {len(tasks)}")
        lines.append(f"  Completed: {len(completed)}")
        lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, int]:
        """Get quick stats about memory usage."""
        stats = {
            'active_sessions': 0,
            'archived_sessions': 0,
            'total_episodes': 0,
            'total_facts': 0,
            'active_tasks': 0
        }

        # Sessions
        stats['active_sessions'] = len(list(self.session.base_path.glob("sess_*.yaml")))
        archive_path = self.session.base_path / 'archive'
        if archive_path.exists():
            stats['archived_sessions'] = len(list(archive_path.glob("sess_*.yaml")))

        # Episodes
        for ef in self.episodic.base_path.glob("*.yaml"):
            try:
                content = ef.read_text(encoding='utf-8')
                if content.strip():
                    if HAS_YAML:
                        episodes = yaml.safe_load(content)
                    else:
                        episodes = json.loads(content)
                    if episodes:
                        stats['total_episodes'] += len(episodes)
            except:
                pass

        # Facts
        for category in self.semantic.categories:
            file_path = self.semantic.base_path / f"{category}.yaml"
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding='utf-8')
                    if content.strip():
                        if HAS_YAML:
                            facts = yaml.safe_load(content)
                        else:
                            facts = json.loads(content)
                        if facts:
                            stats['total_facts'] += len(facts)
                except:
                    pass

        # Tasks
        stats['active_tasks'] = len(list(self.working.base_path.glob("task_*.yaml")))

        return stats
