"""
Working Memory - Active task context.

Short-term memory for the current task:
- What files are relevant right now
- What we're trying to accomplish
- Recent outputs and results
- Active hypotheses and approaches
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from collections import deque
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger('crucible.memory.working')


@dataclass
class RecentItem:
    """A recently accessed item in working memory."""
    item_type: str  # file, output, result, thought
    content: Any
    timestamp: str = ""
    relevance: float = 1.0  # Decays over time

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class Hypothesis:
    """An active hypothesis or approach being considered."""
    description: str
    confidence: float = 0.5  # 0-1
    evidence_for: List[str] = field(default_factory=list)
    evidence_against: List[str] = field(default_factory=list)
    status: str = "active"  # active, confirmed, rejected


@dataclass
class TaskContext:
    """
    Complete context for the current task.

    This is the "scratch pad" for active work.
    """
    task_id: str = ""
    description: str = ""
    started_at: str = ""

    # What we're working with
    relevant_files: List[str] = field(default_factory=list)
    relevant_functions: List[str] = field(default_factory=list)
    relevant_concepts: List[str] = field(default_factory=list)

    # Recent activity (ring buffer behavior)
    recent_reads: List[Dict] = field(default_factory=list)
    recent_outputs: List[Dict] = field(default_factory=list)
    recent_errors: List[Dict] = field(default_factory=list)

    # Current understanding
    hypotheses: List[Dict] = field(default_factory=list)
    current_approach: Optional[str] = None
    blockers: List[str] = field(default_factory=list)

    # Scratchpad for notes
    notes: List[str] = field(default_factory=list)

    # Dependencies discovered
    dependencies: Dict[str, List[str]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat() + "Z"
        if not self.task_id:
            import hashlib
            content = f"{self.description}:{self.started_at}"
            self.task_id = f"task_{hashlib.md5(content.encode()).hexdigest()[:8]}"


class WorkingMemory:
    """
    Manage active task context.

    Provides a "working memory" buffer for the current task:
    - Track what files/concepts are relevant
    - Remember recent outputs and errors
    - Maintain hypotheses about what's happening
    - Keep scratchpad notes

    Unlike session memory, working memory is task-focused
    and more volatile.
    """

    MAX_RECENT_ITEMS = 20  # Ring buffer size

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path) / 'working'
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.current_context: Optional[TaskContext] = None
        self._context_file: Optional[Path] = None

    def start_task(self, description: str, relevant_files: List[str] = None) -> TaskContext:
        """
        Start a new task context.

        Args:
            description: What we're trying to do
            relevant_files: Initial relevant files

        Returns:
            New TaskContext
        """
        # Save previous context if exists
        if self.current_context:
            self._save()

        self.current_context = TaskContext(
            description=description,
            relevant_files=relevant_files or []
        )
        self._context_file = self.base_path / f"{self.current_context.task_id}.yaml"
        self._save()

        logger.info(f"Started task: {self.current_context.task_id}")
        return self.current_context

    def get_context(self) -> Optional[TaskContext]:
        """Get current task context."""
        return self.current_context

    def load_task(self, task_id: str) -> Optional[TaskContext]:
        """
        Load a specific task context.

        Args:
            task_id: The task ID to load

        Returns:
            TaskContext if found
        """
        path = self.base_path / f"{task_id}.yaml"
        if not path.exists():
            return None

        content = path.read_text(encoding='utf-8')
        if HAS_YAML:
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)

        self.current_context = TaskContext(**data)
        self._context_file = path
        return self.current_context

    def add_relevant_file(self, file_path: str):
        """Mark a file as relevant to current task."""
        if not self.current_context:
            return
        if file_path not in self.current_context.relevant_files:
            self.current_context.relevant_files.append(file_path)
            self._save()

    def add_relevant_function(self, function_name: str):
        """Mark a function as relevant to current task."""
        if not self.current_context:
            return
        if function_name not in self.current_context.relevant_functions:
            self.current_context.relevant_functions.append(function_name)
            self._save()

    def add_relevant_concept(self, concept: str):
        """Mark a concept as relevant to current task."""
        if not self.current_context:
            return
        if concept not in self.current_context.relevant_concepts:
            self.current_context.relevant_concepts.append(concept)
            self._save()

    def record_read(self, file_path: str, summary: str = None):
        """
        Record that a file was read.

        Args:
            file_path: Path to file
            summary: Optional summary of what was found
        """
        if not self.current_context:
            return

        item = RecentItem(
            item_type='file',
            content={'path': file_path, 'summary': summary}
        )

        self.current_context.recent_reads.append(asdict(item))

        # Ring buffer behavior
        if len(self.current_context.recent_reads) > self.MAX_RECENT_ITEMS:
            self.current_context.recent_reads = self.current_context.recent_reads[-self.MAX_RECENT_ITEMS:]

        self._save()

    def record_output(self, command: str, output: str, success: bool = True):
        """
        Record command output.

        Args:
            command: The command/operation
            output: The output (truncated if needed)
            success: Whether it succeeded
        """
        if not self.current_context:
            return

        # Truncate large outputs
        if len(output) > 1000:
            output = output[:1000] + "\n... (truncated)"

        item = RecentItem(
            item_type='output',
            content={'command': command, 'output': output, 'success': success}
        )

        self.current_context.recent_outputs.append(asdict(item))

        if len(self.current_context.recent_outputs) > self.MAX_RECENT_ITEMS:
            self.current_context.recent_outputs = self.current_context.recent_outputs[-self.MAX_RECENT_ITEMS:]

        self._save()

    def record_error(self, error: str, context: str = None):
        """
        Record an error encountered.

        Args:
            error: The error message
            context: What we were doing when it happened
        """
        if not self.current_context:
            return

        item = RecentItem(
            item_type='error',
            content={'error': error, 'context': context}
        )

        self.current_context.recent_errors.append(asdict(item))

        if len(self.current_context.recent_errors) > self.MAX_RECENT_ITEMS:
            self.current_context.recent_errors = self.current_context.recent_errors[-self.MAX_RECENT_ITEMS:]

        self._save()

    def add_hypothesis(self, description: str, confidence: float = 0.5) -> int:
        """
        Add a hypothesis about what's happening.

        Args:
            description: The hypothesis
            confidence: Initial confidence (0-1)

        Returns:
            Index of the hypothesis
        """
        if not self.current_context:
            return -1

        hypothesis = Hypothesis(description=description, confidence=confidence)
        self.current_context.hypotheses.append(asdict(hypothesis))
        self._save()

        return len(self.current_context.hypotheses) - 1

    def update_hypothesis(
        self,
        index: int,
        evidence_for: str = None,
        evidence_against: str = None,
        new_confidence: float = None,
        status: str = None
    ):
        """
        Update a hypothesis with new evidence.

        Args:
            index: Hypothesis index
            evidence_for: Evidence supporting it
            evidence_against: Evidence against it
            new_confidence: Updated confidence
            status: New status (active, confirmed, rejected)
        """
        if not self.current_context:
            return
        if index < 0 or index >= len(self.current_context.hypotheses):
            return

        h = self.current_context.hypotheses[index]

        if evidence_for:
            h['evidence_for'].append(evidence_for)
        if evidence_against:
            h['evidence_against'].append(evidence_against)
        if new_confidence is not None:
            h['confidence'] = new_confidence
        if status:
            h['status'] = status

        self._save()

    def set_approach(self, approach: str):
        """Set the current approach being tried."""
        if not self.current_context:
            return
        self.current_context.current_approach = approach
        self._save()

    def add_blocker(self, blocker: str):
        """Add a blocker preventing progress."""
        if not self.current_context:
            return
        if blocker not in self.current_context.blockers:
            self.current_context.blockers.append(blocker)
            self._save()

    def remove_blocker(self, blocker: str):
        """Remove a blocker that's been resolved."""
        if not self.current_context:
            return
        if blocker in self.current_context.blockers:
            self.current_context.blockers.remove(blocker)
            self._save()

    def add_note(self, note: str):
        """Add a scratchpad note."""
        if not self.current_context:
            return
        self.current_context.notes.append(note)
        self._save()

    def add_dependency(self, item: str, depends_on: List[str]):
        """
        Record a dependency relationship.

        Args:
            item: The item that has dependencies
            depends_on: What it depends on
        """
        if not self.current_context:
            return
        self.current_context.dependencies[item] = depends_on
        self._save()

    def get_summary(self) -> str:
        """
        Get a summary of current working memory.

        Returns:
            Formatted summary string
        """
        if not self.current_context:
            return "No active task context."

        ctx = self.current_context
        lines = [
            f"=== Working Memory: {ctx.task_id} ===",
            f"Task: {ctx.description}",
            f"Started: {ctx.started_at}",
            ""
        ]

        if ctx.current_approach:
            lines.append(f"Current Approach: {ctx.current_approach}")
            lines.append("")

        if ctx.relevant_files:
            lines.append(f"Relevant Files ({len(ctx.relevant_files)}):")
            for f in ctx.relevant_files[:10]:
                lines.append(f"  - {f}")
            if len(ctx.relevant_files) > 10:
                lines.append(f"  ... and {len(ctx.relevant_files) - 10} more")
            lines.append("")

        if ctx.relevant_concepts:
            lines.append(f"Relevant Concepts: {', '.join(ctx.relevant_concepts)}")
            lines.append("")

        if ctx.hypotheses:
            active = [h for h in ctx.hypotheses if h.get('status') == 'active']
            if active:
                lines.append(f"Active Hypotheses ({len(active)}):")
                for h in active:
                    conf = h.get('confidence', 0.5)
                    lines.append(f"  • [{conf:.0%}] {h.get('description')}")
                lines.append("")

        if ctx.blockers:
            lines.append(f"Blockers ({len(ctx.blockers)}):")
            for b in ctx.blockers:
                lines.append(f"  ✗ {b}")
            lines.append("")

        if ctx.recent_errors:
            lines.append(f"Recent Errors ({len(ctx.recent_errors)}):")
            for e in ctx.recent_errors[-3:]:
                err = e.get('content', {}).get('error', 'Unknown')
                lines.append(f"  ! {err[:100]}")
            lines.append("")

        if ctx.notes:
            lines.append(f"Notes ({len(ctx.notes)}):")
            for n in ctx.notes[-5:]:
                lines.append(f"  • {n}")

        return "\n".join(lines)

    def complete_task(self, summary: str = None) -> Dict:
        """
        Complete the current task.

        Args:
            summary: Optional completion summary

        Returns:
            Final task state
        """
        if not self.current_context:
            return {}

        result = {
            'task_id': self.current_context.task_id,
            'description': self.current_context.description,
            'files_touched': self.current_context.relevant_files,
            'hypotheses_confirmed': [
                h for h in self.current_context.hypotheses
                if h.get('status') == 'confirmed'
            ],
            'summary': summary
        }

        # Archive the task
        archive_path = self.base_path / 'completed'
        archive_path.mkdir(exist_ok=True)
        if self._context_file and self._context_file.exists():
            self._context_file.rename(archive_path / self._context_file.name)

        self.current_context = None
        self._context_file = None

        return result

    def _save(self):
        """Save current context to disk."""
        if not self.current_context or not self._context_file:
            return

        data = asdict(self.current_context)

        if HAS_YAML:
            content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(data, indent=2)

        self._context_file.write_text(content, encoding='utf-8')
