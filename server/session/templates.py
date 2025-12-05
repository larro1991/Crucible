"""
Session Templates and Advanced Features

Provides:
- Session templates for quick setup
- Session cloning/duplication
- Export/import for backup
- Analytics and statistics
"""

import os
import json
import uuid
import zipfile
import tempfile
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import defaultdict


@dataclass
class SessionTemplate:
    """A reusable session template"""
    template_id: str
    name: str
    description: str
    project_pattern: str = ""              # Default project name pattern
    goal_template: str = ""                # Default goal with placeholders
    tags: List[str] = field(default_factory=list)
    documents: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    github_repo: Optional[str] = None
    created_at: str = ""
    use_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionTemplate':
        return cls(**data)


# Built-in templates
BUILTIN_TEMPLATES = {
    "blank": SessionTemplate(
        template_id="blank",
        name="Blank Session",
        description="Empty session with no preset configuration",
        goal_template="",
        tags=[]
    ),

    "bugfix": SessionTemplate(
        template_id="bugfix",
        name="Bug Fix",
        description="Template for debugging and fixing issues",
        goal_template="Fix bug: {description}",
        tags=["bugfix", "debug"],
        context={
            "workflow": "investigate -> reproduce -> fix -> test -> document"
        }
    ),

    "feature": SessionTemplate(
        template_id="feature",
        name="New Feature",
        description="Template for implementing new features",
        goal_template="Implement feature: {description}",
        tags=["feature", "development"],
        context={
            "workflow": "design -> implement -> test -> document -> review"
        }
    ),

    "refactor": SessionTemplate(
        template_id="refactor",
        name="Refactoring",
        description="Template for code refactoring tasks",
        goal_template="Refactor: {description}",
        tags=["refactor", "cleanup"],
        context={
            "workflow": "analyze -> plan -> refactor -> test -> verify"
        }
    ),

    "research": SessionTemplate(
        template_id="research",
        name="Research & Learning",
        description="Template for exploring and learning new topics",
        goal_template="Research: {topic}",
        tags=["research", "learning"],
        context={
            "workflow": "explore -> document -> summarize -> apply"
        }
    ),

    "review": SessionTemplate(
        template_id="review",
        name="Code Review",
        description="Template for reviewing code changes",
        goal_template="Review: {pr_or_changes}",
        tags=["review", "quality"],
        context={
            "checklist": ["correctness", "security", "performance", "style", "tests"]
        }
    ),

    "ops": SessionTemplate(
        template_id="ops",
        name="DevOps Task",
        description="Template for infrastructure and operations tasks",
        goal_template="DevOps: {task}",
        tags=["devops", "infrastructure"],
        context={
            "checklist": ["backup", "test", "deploy", "verify", "document"]
        }
    ),
}


class TemplateManager:
    """Manages session templates"""

    def __init__(self, data_dir: str = "data/session/templates"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.templates: Dict[str, SessionTemplate] = {}

        # Load built-ins
        for tid, template in BUILTIN_TEMPLATES.items():
            self.templates[tid] = template

        # Load custom templates
        self._load_templates()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _get_templates_file(self) -> Path:
        return self.data_dir / "custom_templates.json"

    def _load_templates(self) -> None:
        """Load custom templates from disk"""
        templates_file = self._get_templates_file()
        if templates_file.exists():
            try:
                with open(templates_file, 'r') as f:
                    data = json.load(f)
                for t_data in data.get('templates', []):
                    template = SessionTemplate.from_dict(t_data)
                    self.templates[template.template_id] = template
            except Exception as e:
                print(f"Error loading templates: {e}")

    def _save_templates(self) -> None:
        """Save custom templates to disk"""
        custom = [
            t.to_dict() for t in self.templates.values()
            if t.template_id not in BUILTIN_TEMPLATES
        ]

        with open(self._get_templates_file(), 'w') as f:
            json.dump({'templates': custom}, f, indent=2)

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates"""
        return [
            {
                'template_id': t.template_id,
                'name': t.name,
                'description': t.description,
                'tags': t.tags,
                'use_count': t.use_count,
                'is_builtin': t.template_id in BUILTIN_TEMPLATES
            }
            for t in self.templates.values()
        ]

    def get_template(self, template_id: str) -> Optional[SessionTemplate]:
        """Get a template by ID"""
        return self.templates.get(template_id)

    def create_template(
        self,
        name: str,
        description: str,
        goal_template: str = "",
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        github_repo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new custom template"""
        template_id = f"tmpl_{uuid.uuid4().hex[:8]}"

        template = SessionTemplate(
            template_id=template_id,
            name=name,
            description=description,
            goal_template=goal_template,
            tags=tags or [],
            context=context or {},
            github_repo=github_repo,
            created_at=self._now()
        )

        self.templates[template_id] = template
        self._save_templates()

        return {
            'status': 'created',
            'template_id': template_id,
            'name': name
        }

    def create_template_from_session(
        self,
        session_data: Dict[str, Any],
        name: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """Create a template from an existing session"""
        template_id = f"tmpl_{uuid.uuid4().hex[:8]}"

        template = SessionTemplate(
            template_id=template_id,
            name=name,
            description=description or f"Created from session {session_data.get('session_id', 'unknown')}",
            project_pattern=session_data.get('project', ''),
            goal_template=session_data.get('goal', ''),
            tags=session_data.get('tags', []),
            documents=session_data.get('documents', []),
            context=session_data.get('context', {}),
            github_repo=session_data.get('github', {}).get('repo_url') if session_data.get('github') else None,
            created_at=self._now()
        )

        self.templates[template_id] = template
        self._save_templates()

        return {
            'status': 'created',
            'template_id': template_id,
            'name': name
        }

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """Delete a custom template"""
        if template_id in BUILTIN_TEMPLATES:
            return {'status': 'error', 'error': 'Cannot delete built-in templates'}

        if template_id not in self.templates:
            return {'status': 'error', 'error': 'Template not found'}

        del self.templates[template_id]
        self._save_templates()

        return {'status': 'deleted', 'template_id': template_id}

    def record_use(self, template_id: str) -> None:
        """Record that a template was used"""
        if template_id in self.templates:
            self.templates[template_id].use_count += 1
            if template_id not in BUILTIN_TEMPLATES:
                self._save_templates()


class SessionExporter:
    """Handles session export and import"""

    def __init__(self, session_dir: str = "data/session"):
        self.session_dir = Path(session_dir)

    def export_session(
        self,
        session_id: str,
        output_path: Optional[str] = None,
        include_checkpoints: bool = True,
        include_wal: bool = False
    ) -> Dict[str, Any]:
        """Export a session to a JSON file or zip archive"""
        session_file = self.session_dir / f"robust_{session_id}.json"

        if not session_file.exists():
            return {'status': 'error', 'error': f'Session {session_id} not found'}

        with open(session_file, 'r') as f:
            session_data = json.load(f)

        export_data = {
            'version': '1.0',
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'session': session_data
        }

        if include_checkpoints:
            checkpoint_dir = self.session_dir / "checkpoints"
            checkpoints = []
            for cp_file in checkpoint_dir.glob(f"ckpt_{session_id}*.json"):
                try:
                    with open(cp_file, 'r') as f:
                        checkpoints.append(json.load(f))
                except:
                    pass
            export_data['checkpoints'] = checkpoints

        if include_wal:
            wal_dir = self.session_dir / "wal"
            wal_entries = []
            for wal_file in wal_dir.glob(f"wal_{session_id}*.log"):
                try:
                    with open(wal_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                wal_entries.append(json.loads(line))
                except:
                    pass
            export_data['wal'] = wal_entries

        if not output_path:
            output_path = f"session_export_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        return {
            'status': 'exported',
            'session_id': session_id,
            'output_path': output_path,
            'size_bytes': os.path.getsize(output_path)
        }

    def import_session(
        self,
        input_path: str,
        new_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import a session from an exported file"""
        if not Path(input_path).exists():
            return {'status': 'error', 'error': f'File not found: {input_path}'}

        with open(input_path, 'r') as f:
            import_data = json.load(f)

        session_data = import_data.get('session', {})

        if not session_data:
            return {'status': 'error', 'error': 'No session data in export file'}

        # Generate new session ID if not provided
        if new_session_id:
            session_data['session_id'] = new_session_id
        else:
            old_id = session_data.get('session_id', '')
            session_data['session_id'] = f"imported_{old_id}_{uuid.uuid4().hex[:4]}"

        # Update timestamps
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        session_data['imported_at'] = now
        session_data['updated_at'] = now
        session_data['status'] = 'imported'

        # Save session
        session_file = self.session_dir / f"robust_{session_data['session_id']}.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)

        return {
            'status': 'imported',
            'session_id': session_data['session_id'],
            'original_id': import_data.get('session', {}).get('session_id'),
            'imported_from': input_path
        }

    def export_all_sessions(self, output_dir: str) -> Dict[str, Any]:
        """Export all sessions to a directory"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        exported = []
        for session_file in self.session_dir.glob("robust_*.json"):
            session_id = session_file.stem.replace('robust_', '')
            result = self.export_session(
                session_id,
                str(output_path / f"{session_id}.json"),
                include_checkpoints=False,
                include_wal=False
            )
            if result['status'] == 'exported':
                exported.append(session_id)

        return {
            'status': 'exported',
            'count': len(exported),
            'session_ids': exported,
            'output_dir': str(output_path)
        }


class SessionAnalytics:
    """Session analytics and statistics"""

    def __init__(self, session_dir: str = "data/session"):
        self.session_dir = Path(session_dir)

    def _load_all_sessions(self) -> List[Dict[str, Any]]:
        """Load all session data"""
        sessions = []
        for session_file in self.session_dir.glob("robust_*.json"):
            try:
                with open(session_file, 'r') as f:
                    sessions.append(json.load(f))
            except:
                pass
        return sessions

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get overall summary statistics"""
        sessions = self._load_all_sessions()

        if not sessions:
            return {'total_sessions': 0}

        # Basic counts
        total = len(sessions)
        by_status = defaultdict(int)
        by_project = defaultdict(int)
        total_recoveries = 0
        total_drops = 0

        for s in sessions:
            by_status[s.get('status', 'unknown')] += 1
            by_project[s.get('project', 'unknown')] += 1
            total_recoveries += s.get('recoveries', 0)
            total_drops += s.get('connection_drops', 0)

        # Time analysis
        durations = []
        for s in sessions:
            try:
                start = datetime.fromisoformat(s['started_at'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(s['updated_at'].replace('Z', '+00:00'))
                durations.append((end - start).total_seconds() / 60)  # minutes
            except:
                pass

        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            'total_sessions': total,
            'by_status': dict(by_status),
            'by_project': dict(by_project),
            'total_recoveries': total_recoveries,
            'total_connection_drops': total_drops,
            'recovery_rate': total_recoveries / total if total > 0 else 0,
            'avg_session_duration_minutes': round(avg_duration, 1),
            'sessions_with_github': sum(1 for s in sessions if s.get('github')),
            'sessions_with_docs': sum(1 for s in sessions if s.get('documents')),
            'total_documents': sum(len(s.get('documents', [])) for s in sessions)
        }

    def get_project_stats(self, project: str) -> Dict[str, Any]:
        """Get statistics for a specific project"""
        sessions = [
            s for s in self._load_all_sessions()
            if s.get('project') == project
        ]

        if not sessions:
            return {'project': project, 'session_count': 0}

        goals = [s.get('goal', '') for s in sessions]
        tags = []
        for s in sessions:
            tags.extend(s.get('tags', []))

        return {
            'project': project,
            'session_count': len(sessions),
            'recent_goals': goals[-5:],
            'common_tags': list(set(tags)),
            'total_recoveries': sum(s.get('recoveries', 0) for s in sessions),
            'has_github': any(s.get('github') for s in sessions)
        }

    def get_activity_timeline(self, days: int = 30) -> Dict[str, Any]:
        """Get session activity over time"""
        sessions = self._load_all_sessions()

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        by_day = defaultdict(int)

        for s in sessions:
            try:
                start = datetime.fromisoformat(s['started_at'].replace('Z', '+00:00'))
                if start >= cutoff:
                    day = start.strftime('%Y-%m-%d')
                    by_day[day] += 1
            except:
                pass

        # Fill in missing days
        timeline = {}
        current = cutoff
        while current <= datetime.now(timezone.utc):
            day = current.strftime('%Y-%m-%d')
            timeline[day] = by_day.get(day, 0)
            current += timedelta(days=1)

        return {
            'period_days': days,
            'total_sessions': sum(timeline.values()),
            'avg_per_day': round(sum(timeline.values()) / days, 2),
            'timeline': timeline
        }

    def get_tag_analysis(self) -> Dict[str, Any]:
        """Analyze tag usage across sessions"""
        sessions = self._load_all_sessions()

        tag_counts = defaultdict(int)
        tag_projects = defaultdict(set)

        for s in sessions:
            project = s.get('project', 'unknown')
            for tag in s.get('tags', []):
                tag_counts[tag] += 1
                tag_projects[tag].add(project)

        tag_analysis = [
            {
                'tag': tag,
                'count': count,
                'projects': list(tag_projects[tag])
            }
            for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])
        ]

        return {
            'total_unique_tags': len(tag_counts),
            'tags': tag_analysis[:20]  # Top 20
        }


# Global instances
_template_manager: Optional[TemplateManager] = None
_exporter: Optional[SessionExporter] = None
_analytics: Optional[SessionAnalytics] = None


def get_template_manager() -> TemplateManager:
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager


def get_exporter() -> SessionExporter:
    global _exporter
    if _exporter is None:
        _exporter = SessionExporter()
    return _exporter


def get_analytics() -> SessionAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = SessionAnalytics()
    return _analytics
