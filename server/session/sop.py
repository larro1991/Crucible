"""
Ember Work Patterns and Standard Operating Procedures (SOP)

Defines methodical approaches to work including:
- Task decomposition
- Progress tracking
- Quality verification
- Error handling
- Communication patterns

These patterns can be applied per-personality or globally.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from pathlib import Path


@dataclass
class QualityChecklist:
    """Checklist for quality verification"""
    name: str
    items: List[str]
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkPattern:
    """A reusable work pattern/methodology"""
    id: str
    name: str
    description: str

    # Task approach
    decomposition_strategy: str = "hierarchical"  # hierarchical, sequential, parallel
    max_task_complexity: str = "break_down"       # break_down, tackle_whole

    # Progress tracking
    use_todo_list: bool = True
    track_operations: bool = True
    checkpoint_frequency: str = "after_major_steps"  # always, after_major_steps, manual

    # Verification
    verify_before_delivery: bool = True
    test_code_before_commit: bool = True
    review_own_work: bool = True

    # Error handling
    on_error: str = "investigate_then_fix"  # investigate_then_fix, ask_user, retry
    max_retries: int = 3
    rollback_on_failure: bool = True

    # Communication
    explain_reasoning: bool = True
    show_progress: bool = True
    ask_when_uncertain: bool = True
    confirm_destructive_actions: bool = True

    # Quality
    quality_checklists: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkPattern':
        return cls(**data)


# The 4 Immutable Core Principles - These form the mandatory gate
# Every response MUST pass through these before any other principles apply
CORE_PRINCIPLES = [
    {
        "id": "honesty",
        "name": "Honesty",
        "description": "Be truthful and accurate. Never deceive or mislead.",
        "evaluation": "Is this response truthful? Am I being accurate and not misleading?"
    },
    {
        "id": "kindness",
        "name": "Kindness",
        "description": "Act with compassion and consideration. Avoid harm.",
        "evaluation": "Is this response kind? Am I being considerate and not causing unnecessary harm?"
    },
    {
        "id": "trust",
        "name": "Trust",
        "description": "Be reliable and dependable. Honor commitments.",
        "evaluation": "Does this maintain trust? Am I being reliable and honoring expectations?"
    },
    {
        "id": "transparency",
        "name": "Transparency",
        "description": "Be open about capabilities, limitations, and reasoning.",
        "evaluation": "Am I being transparent? Are my limitations and reasoning clear?"
    },
]


@dataclass
class StandardOperatingProcedure:
    """Complete SOP combining work patterns with specific procedures"""
    id: str
    name: str
    description: str

    # Secondary principles (apply AFTER core principles pass)
    principles: List[str] = field(default_factory=list)

    # Work pattern reference
    work_pattern_id: str = "default"

    # Task-specific procedures
    procedures: Dict[str, List[str]] = field(default_factory=dict)

    # Checklists
    checklists: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StandardOperatingProcedure':
        return cls(**data)

    @staticmethod
    def get_core_principles() -> List[Dict[str, str]]:
        """Return the 4 immutable core principles that gate all responses"""
        return CORE_PRINCIPLES


# Built-in work patterns
BUILTIN_WORK_PATTERNS = {
    "default": WorkPattern(
        id="default",
        name="Methodical & Thorough",
        description="Balanced approach with good practices",
        decomposition_strategy="hierarchical",
        use_todo_list=True,
        track_operations=True,
        checkpoint_frequency="after_major_steps",
        verify_before_delivery=True,
        test_code_before_commit=True,
        review_own_work=True,
        on_error="investigate_then_fix",
        explain_reasoning=True,
        show_progress=True,
        ask_when_uncertain=True,
        confirm_destructive_actions=True,
        quality_checklists=[
            {"name": "code_quality", "items": [
                "Syntax correct",
                "No obvious bugs",
                "Handles edge cases",
                "No security vulnerabilities",
                "Follows existing patterns"
            ]},
            {"name": "delivery", "items": [
                "Meets requirements",
                "Tested if applicable",
                "Documentation updated if needed"
            ]}
        ]
    ),

    "thorough": WorkPattern(
        id="thorough",
        name="Extra Thorough",
        description="Maximum verification and documentation",
        decomposition_strategy="hierarchical",
        use_todo_list=True,
        track_operations=True,
        checkpoint_frequency="always",
        verify_before_delivery=True,
        test_code_before_commit=True,
        review_own_work=True,
        on_error="investigate_then_fix",
        max_retries=5,
        explain_reasoning=True,
        show_progress=True,
        ask_when_uncertain=True,
        confirm_destructive_actions=True,
        quality_checklists=[
            {"name": "comprehensive", "items": [
                "Requirements fully understood",
                "Edge cases identified",
                "Solution designed before coding",
                "Code reviewed line-by-line",
                "All tests passing",
                "Security review done",
                "Performance considered",
                "Documentation complete"
            ]}
        ]
    ),

    "fast": WorkPattern(
        id="fast",
        name="Fast & Focused",
        description="Quick execution with essential checks only",
        decomposition_strategy="sequential",
        max_task_complexity="tackle_whole",
        use_todo_list=False,  # Skip for speed
        track_operations=True,
        checkpoint_frequency="manual",
        verify_before_delivery=True,
        test_code_before_commit=False,  # User can test
        review_own_work=False,
        on_error="retry",
        max_retries=2,
        explain_reasoning=False,  # Just do it
        show_progress=False,
        ask_when_uncertain=True,
        confirm_destructive_actions=True,
        quality_checklists=[
            {"name": "minimal", "items": [
                "Works for main case",
                "No obvious errors"
            ]}
        ]
    ),

    "careful": WorkPattern(
        id="careful",
        name="Careful & Safe",
        description="Extra caution, always ask before acting",
        decomposition_strategy="hierarchical",
        use_todo_list=True,
        track_operations=True,
        checkpoint_frequency="always",
        verify_before_delivery=True,
        test_code_before_commit=True,
        review_own_work=True,
        on_error="ask_user",
        rollback_on_failure=True,
        explain_reasoning=True,
        show_progress=True,
        ask_when_uncertain=True,
        confirm_destructive_actions=True,
        quality_checklists=[
            {"name": "safety", "items": [
                "Backup exists if needed",
                "Changes are reversible",
                "User informed of risks",
                "Tested in isolation first"
            ]}
        ]
    ),

    "learning": WorkPattern(
        id="learning",
        name="Educational",
        description="Explain everything, teach as we go",
        decomposition_strategy="hierarchical",
        use_todo_list=True,
        track_operations=True,
        checkpoint_frequency="after_major_steps",
        verify_before_delivery=True,
        test_code_before_commit=True,
        review_own_work=True,
        on_error="investigate_then_fix",
        explain_reasoning=True,  # Always explain
        show_progress=True,
        ask_when_uncertain=True,
        confirm_destructive_actions=True,
        quality_checklists=[
            {"name": "educational", "items": [
                "Concepts explained",
                "Why this approach",
                "Alternatives mentioned",
                "Learning resources shared"
            ]}
        ]
    ),
}


# Built-in SOPs
BUILTIN_SOPS = {
    "ember_default": StandardOperatingProcedure(
        id="ember_default",
        name="Ember Default SOP",
        description="Standard operating procedures for Ember AI assistant",
        principles=[
            "Break complex tasks into manageable steps",
            "Track progress using todo lists for multi-step work",
            "Verify work before delivering - test code, check outputs",
            "Persist state to survive interruptions",
            "Ask when requirements are unclear rather than assume",
            "Explain reasoning for significant decisions",
            "Prefer editing existing code over creating new files",
            "Don't over-engineer - solve the problem at hand",
            "Checkpoint frequently to avoid losing work",
            "Review own work before marking complete",
        ],
        work_pattern_id="default",
        procedures={
            "new_task": [
                "Understand the request fully",
                "Break down into steps if complex",
                "Add steps to todo list",
                "Start with first step",
                "Mark completed as done",
                "Verify final result"
            ],
            "code_change": [
                "Read existing code first",
                "Understand current behavior",
                "Plan the change",
                "Make minimal necessary edits",
                "Test if possible",
                "Explain what changed"
            ],
            "debugging": [
                "Reproduce the issue",
                "Gather information (errors, logs)",
                "Form hypothesis",
                "Test hypothesis",
                "Fix root cause not symptoms",
                "Verify fix works"
            ],
            "research": [
                "Define what we need to know",
                "Search/explore systematically",
                "Document findings",
                "Synthesize into answer",
                "Cite sources"
            ],
            "recovery": [
                "Check session status",
                "Review interrupted operations",
                "Resume from last checkpoint",
                "Verify state is consistent",
                "Continue work"
            ]
        },
        checklists={
            "before_commit": [
                "All tests pass",
                "No debug code left",
                "Changes match request",
                "No unrelated changes"
            ],
            "before_delivery": [
                "Meets requirements",
                "Code is clean",
                "Explained approach",
                "Noted any caveats"
            ],
            "session_end": [
                "All tasks completed or documented",
                "State saved",
                "Summary provided",
                "Next steps clear if any"
            ]
        }
    ),

    "ember_strict": StandardOperatingProcedure(
        id="ember_strict",
        name="Ember Strict SOP",
        description="Extra rigorous procedures for critical work",
        principles=[
            "Never skip verification steps",
            "Document every decision",
            "Test everything that can be tested",
            "Always have a rollback plan",
            "Confirm before any destructive action",
            "Checkpoint after every significant change",
            "Review twice, execute once",
        ],
        work_pattern_id="thorough",
        procedures={
            "critical_change": [
                "Backup current state",
                "Document rollback procedure",
                "Make change in isolation first",
                "Test thoroughly",
                "Get confirmation",
                "Apply change",
                "Verify success",
                "Document what was done"
            ]
        },
        checklists={
            "critical_checklist": [
                "Backup created",
                "Rollback tested",
                "Change isolated",
                "Tests comprehensive",
                "User confirmed",
                "Documentation updated"
            ]
        }
    ),
}


class SOPManager:
    """Manages work patterns and SOPs"""

    def __init__(self, data_dir: str = "data/sop"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.work_patterns: Dict[str, WorkPattern] = {}
        self.sops: Dict[str, StandardOperatingProcedure] = {}
        self.active_sop_id: str = "ember_default"

        # Load built-ins
        for pid, pattern in BUILTIN_WORK_PATTERNS.items():
            self.work_patterns[pid] = pattern
        for sid, sop in BUILTIN_SOPS.items():
            self.sops[sid] = sop

        # Load custom
        self._load_custom()
        self._load_active()

    def _get_custom_file(self) -> Path:
        return self.data_dir / "custom_sop.json"

    def _get_active_file(self) -> Path:
        return self.data_dir / "active.json"

    def _load_custom(self) -> None:
        custom_file = self._get_custom_file()
        if custom_file.exists():
            try:
                with open(custom_file, 'r') as f:
                    data = json.load(f)
                for wp in data.get('work_patterns', []):
                    pattern = WorkPattern.from_dict(wp)
                    self.work_patterns[pattern.id] = pattern
                for s in data.get('sops', []):
                    sop = StandardOperatingProcedure.from_dict(s)
                    self.sops[sop.id] = sop
            except Exception as e:
                print(f"Error loading custom SOPs: {e}")

    def _save_custom(self) -> None:
        custom_patterns = [
            p.to_dict() for p in self.work_patterns.values()
            if p.id not in BUILTIN_WORK_PATTERNS
        ]
        custom_sops = [
            s.to_dict() for s in self.sops.values()
            if s.id not in BUILTIN_SOPS
        ]

        with open(self._get_custom_file(), 'w') as f:
            json.dump({
                'work_patterns': custom_patterns,
                'sops': custom_sops
            }, f, indent=2)

    def _load_active(self) -> None:
        active_file = self._get_active_file()
        if active_file.exists():
            try:
                with open(active_file, 'r') as f:
                    data = json.load(f)
                self.active_sop_id = data.get('active_sop', 'ember_default')
            except:
                pass

    def _save_active(self) -> None:
        with open(self._get_active_file(), 'w') as f:
            json.dump({'active_sop': self.active_sop_id}, f)

    def get_active_sop(self) -> StandardOperatingProcedure:
        return self.sops.get(self.active_sop_id, self.sops['ember_default'])

    def get_active_work_pattern(self) -> WorkPattern:
        sop = self.get_active_sop()
        return self.work_patterns.get(sop.work_pattern_id, self.work_patterns['default'])

    def set_active_sop(self, sop_id: str) -> Dict[str, Any]:
        if sop_id not in self.sops:
            return {'status': 'error', 'error': f'SOP {sop_id} not found'}

        self.active_sop_id = sop_id
        self._save_active()

        sop = self.sops[sop_id]
        return {
            'status': 'activated',
            'sop_id': sop_id,
            'name': sop.name,
            'principles': sop.principles[:3]  # First 3 principles
        }

    def list_sops(self) -> List[Dict[str, Any]]:
        return [
            {
                'id': s.id,
                'name': s.name,
                'description': s.description,
                'work_pattern': s.work_pattern_id,
                'is_active': s.id == self.active_sop_id,
                'is_builtin': s.id in BUILTIN_SOPS
            }
            for s in self.sops.values()
        ]

    def list_work_patterns(self) -> List[Dict[str, Any]]:
        return [
            {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'use_todo_list': p.use_todo_list,
                'verify_before_delivery': p.verify_before_delivery,
                'is_builtin': p.id in BUILTIN_WORK_PATTERNS
            }
            for p in self.work_patterns.values()
        ]

    def get_procedure(self, procedure_name: str) -> List[str]:
        """Get a specific procedure from active SOP"""
        sop = self.get_active_sop()
        return sop.procedures.get(procedure_name, [])

    def get_checklist(self, checklist_name: str) -> List[str]:
        """Get a specific checklist from active SOP"""
        sop = self.get_active_sop()
        return sop.checklists.get(checklist_name, [])

    def get_core_principles(self) -> List[Dict[str, str]]:
        """Get the 4 immutable core principles (the gate)"""
        return CORE_PRINCIPLES

    def get_principles(self) -> List[str]:
        """Get secondary principles from active SOP (apply after core gate)"""
        return self.get_active_sop().principles

    def should_use_todo_list(self) -> bool:
        return self.get_active_work_pattern().use_todo_list

    def should_track_operations(self) -> bool:
        return self.get_active_work_pattern().track_operations

    def should_verify_before_delivery(self) -> bool:
        return self.get_active_work_pattern().verify_before_delivery

    def should_explain_reasoning(self) -> bool:
        return self.get_active_work_pattern().explain_reasoning

    def get_system_prompt_additions(self) -> str:
        """Get SOP-based additions to system prompt"""
        sop = self.get_active_sop()
        pattern = self.get_active_work_pattern()

        prompt_parts = [
            f"Operating under: {sop.name}",
            "",
            "=" * 50,
            "CORE PRINCIPLES (Immutable Gate)",
            "=" * 50,
            "Before ANY response, these 4 principles MUST be evaluated and passed:",
            "",
        ]

        for i, cp in enumerate(CORE_PRINCIPLES, 1):
            prompt_parts.append(f"{i}. {cp['name'].upper()}: {cp['description']}")
            prompt_parts.append(f"   Evaluate: {cp['evaluation']}")

        prompt_parts.append("")
        prompt_parts.append("Only after ALL core principles pass, proceed to:")
        prompt_parts.append("")
        prompt_parts.append("-" * 50)
        prompt_parts.append("Secondary Principles (Work Guidelines)")
        prompt_parts.append("-" * 50)

        for i, principle in enumerate(sop.principles[:5], 1):
            prompt_parts.append(f"{i}. {principle}")

        prompt_parts.append("")
        prompt_parts.append("Work Approach:")

        if pattern.use_todo_list:
            prompt_parts.append("- Use todo lists for multi-step tasks")
        if pattern.track_operations:
            prompt_parts.append("- Track all significant operations")
        if pattern.verify_before_delivery:
            prompt_parts.append("- Verify work before delivering")
        if pattern.explain_reasoning:
            prompt_parts.append("- Explain reasoning for decisions")
        if pattern.ask_when_uncertain:
            prompt_parts.append("- Ask when requirements unclear")
        if pattern.confirm_destructive_actions:
            prompt_parts.append("- Confirm before destructive actions")

        return "\n".join(prompt_parts)


# Global instance
_sop_manager: Optional[SOPManager] = None

def get_sop_manager() -> SOPManager:
    global _sop_manager
    if _sop_manager is None:
        _sop_manager = SOPManager()
    return _sop_manager


# MCP Tools for SOP (to be added to robust_session.py or as plugin)
def get_sop_tools():
    """Return MCP tool definitions for SOP management"""
    try:
        from mcp.types import Tool
        return [
            Tool(
                name="sop_list",
                description="List available Standard Operating Procedures",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="sop_activate",
                description="Activate a specific SOP (ember_default, ember_strict)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sop_id": {"type": "string", "description": "SOP ID to activate"}
                    },
                    "required": ["sop_id"]
                }
            ),
            Tool(
                name="sop_current",
                description="Get current SOP and its principles",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="sop_procedure",
                description="Get a specific procedure (new_task, code_change, debugging, research, recovery)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Procedure name"}
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="sop_checklist",
                description="Get a specific checklist (before_commit, before_delivery, session_end)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Checklist name"}
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="work_patterns_list",
                description="List available work patterns (default, thorough, fast, careful, learning)",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="sop_core_principles",
                description="""Get the 4 immutable core principles that form the mandatory gate.

These principles (Honesty, Kindness, Trust, Transparency) MUST be evaluated
and passed before ANY other principles or work patterns apply.""",
                inputSchema={"type": "object", "properties": {}}
            ),
        ]
    except ImportError:
        return []


# Handlers
async def handle_sop_list(args: dict) -> str:
    sm = get_sop_manager()
    return json.dumps(sm.list_sops(), indent=2)

async def handle_sop_activate(args: dict) -> str:
    sm = get_sop_manager()
    result = sm.set_active_sop(args['sop_id'])
    return json.dumps(result, indent=2)

async def handle_sop_current(args: dict) -> str:
    sm = get_sop_manager()
    sop = sm.get_active_sop()
    pattern = sm.get_active_work_pattern()
    return json.dumps({
        'core_principles': {
            'description': 'Immutable gate - must pass ALL before proceeding',
            'principles': [cp['name'] for cp in CORE_PRINCIPLES]
        },
        'sop': {
            'id': sop.id,
            'name': sop.name,
            'secondary_principles': sop.principles,
            'procedures': list(sop.procedures.keys()),
            'checklists': list(sop.checklists.keys())
        },
        'work_pattern': {
            'id': pattern.id,
            'name': pattern.name,
            'use_todo_list': pattern.use_todo_list,
            'verify_before_delivery': pattern.verify_before_delivery,
            'explain_reasoning': pattern.explain_reasoning
        }
    }, indent=2)

async def handle_sop_procedure(args: dict) -> str:
    sm = get_sop_manager()
    steps = sm.get_procedure(args['name'])
    return json.dumps({
        'procedure': args['name'],
        'steps': steps
    }, indent=2)

async def handle_sop_checklist(args: dict) -> str:
    sm = get_sop_manager()
    items = sm.get_checklist(args['name'])
    return json.dumps({
        'checklist': args['name'],
        'items': items
    }, indent=2)

async def handle_work_patterns_list(args: dict) -> str:
    sm = get_sop_manager()
    return json.dumps(sm.list_work_patterns(), indent=2)

async def handle_sop_core_principles(args: dict) -> str:
    """Return the 4 immutable core principles that gate all responses"""
    return json.dumps({
        'description': 'These 4 principles form the MANDATORY GATE. Every response must pass ALL of these before any other principles or work patterns apply.',
        'immutable': True,
        'evaluation_order': 'All 4 must pass sequentially',
        'principles': CORE_PRINCIPLES
    }, indent=2)


SOP_HANDLERS = {
    "sop_list": handle_sop_list,
    "sop_activate": handle_sop_activate,
    "sop_current": handle_sop_current,
    "sop_procedure": handle_sop_procedure,
    "sop_checklist": handle_sop_checklist,
    "work_patterns_list": handle_work_patterns_list,
    "sop_core_principles": handle_sop_core_principles,
}
