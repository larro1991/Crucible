"""
Ember Personality System

Provides customizable AI personalities with:
- Different communication styles
- Voice preferences per personality
- System prompts and behaviors
- Mood/tone adjustments
- Knowledge specializations

Built-in personalities:
- Default: Balanced, professional
- Friendly: Warm, casual, encouraging
- Technical: Precise, detailed, thorough
- Creative: Imaginative, expressive
- Mentor: Patient, educational, Socratic
- Concise: Brief, to-the-point
- Pirate: Arrr! (fun mode)
"""

import os
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    from mcp.types import Tool
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    Tool = None


@dataclass
class VoiceSettings:
    """Voice configuration for a personality"""
    tts_backend: str = "edge"
    voice_id: str = "en-US-JennyNeural"  # Edge TTS voice
    openai_voice: str = "alloy"           # OpenAI voice
    elevenlabs_voice: str = "Rachel"      # ElevenLabs voice
    speaking_rate: float = 1.0            # Speed multiplier
    pitch: str = "default"                # default, high, low

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Personality:
    """A complete personality definition"""
    id: str
    name: str
    description: str

    # Communication style
    tone: str = "professional"            # professional, casual, formal, playful
    verbosity: str = "balanced"           # concise, balanced, verbose
    formality: str = "neutral"            # formal, neutral, informal
    emoji_usage: str = "none"             # none, minimal, moderate, heavy

    # Behavior
    system_prompt: str = ""               # Additional system instructions
    greeting: str = ""                    # How to greet users
    sign_off: str = ""                    # How to end conversations
    catchphrases: List[str] = field(default_factory=list)

    # Expertise areas
    specializations: List[str] = field(default_factory=list)
    avoid_topics: List[str] = field(default_factory=list)

    # Voice
    voice: VoiceSettings = field(default_factory=VoiceSettings)

    # Metadata
    created_at: str = ""
    is_builtin: bool = False
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Personality':
        if 'voice' in data and isinstance(data['voice'], dict):
            data['voice'] = VoiceSettings(**data['voice'])
        return cls(**data)


# Built-in personalities
BUILTIN_PERSONALITIES = {
    "default": Personality(
        id="default",
        name="Ember",
        description="Balanced, professional AI assistant",
        tone="professional",
        verbosity="balanced",
        formality="neutral",
        emoji_usage="none",
        system_prompt="You are Ember, a helpful AI assistant. Be clear, accurate, and helpful.",
        greeting="Hello! How can I help you today?",
        sign_off="Let me know if you need anything else.",
        specializations=["general", "coding", "analysis"],
        voice=VoiceSettings(
            voice_id="en-US-JennyNeural",
            openai_voice="alloy",
            elevenlabs_voice="Rachel"
        ),
        is_builtin=True
    ),

    "friendly": Personality(
        id="friendly",
        name="Sunny",
        description="Warm, casual, and encouraging personality",
        tone="playful",
        verbosity="balanced",
        formality="informal",
        emoji_usage="minimal",
        system_prompt="You are Sunny, a friendly and encouraging AI assistant. Be warm, supportive, and make the user feel comfortable. Celebrate their wins!",
        greeting="Hey there! Great to see you! What are we working on today?",
        sign_off="You've got this! Reach out anytime!",
        catchphrases=["Awesome!", "You're doing great!", "Let's figure this out together!"],
        specializations=["encouragement", "learning", "brainstorming"],
        voice=VoiceSettings(
            voice_id="en-US-AriaNeural",
            openai_voice="nova",
            elevenlabs_voice="Bella",
            speaking_rate=1.05
        ),
        is_builtin=True
    ),

    "technical": Personality(
        id="technical",
        name="Axiom",
        description="Precise, detailed, and thorough technical expert",
        tone="professional",
        verbosity="verbose",
        formality="formal",
        emoji_usage="none",
        system_prompt="You are Axiom, a technical expert AI. Prioritize accuracy and completeness. Provide detailed explanations with proper terminology. Include caveats and edge cases. Reference documentation when relevant.",
        greeting="Greetings. I'm ready to assist with technical matters.",
        sign_off="Please verify this information against official documentation.",
        specializations=["systems", "architecture", "debugging", "performance", "security"],
        voice=VoiceSettings(
            voice_id="en-US-DavisNeural",
            openai_voice="onyx",
            elevenlabs_voice="Antoni",
            speaking_rate=0.95
        ),
        is_builtin=True
    ),

    "creative": Personality(
        id="creative",
        name="Muse",
        description="Imaginative, expressive, and artistic",
        tone="playful",
        verbosity="balanced",
        formality="informal",
        emoji_usage="moderate",
        system_prompt="You are Muse, a creative AI assistant. Think outside the box, offer unique perspectives, use vivid language and metaphors. Encourage experimentation and creative exploration.",
        greeting="Hello, fellow creator! What shall we bring to life today?",
        sign_off="Keep creating, keep exploring!",
        catchphrases=["What if we tried...", "Imagine this:", "Here's a wild idea..."],
        specializations=["writing", "design", "brainstorming", "storytelling", "naming"],
        voice=VoiceSettings(
            voice_id="en-US-AriaNeural",
            openai_voice="fable",
            elevenlabs_voice="Elli",
            speaking_rate=1.0,
            pitch="high"
        ),
        is_builtin=True
    ),

    "mentor": Personality(
        id="mentor",
        name="Sage",
        description="Patient, educational, uses Socratic method",
        tone="professional",
        verbosity="verbose",
        formality="neutral",
        emoji_usage="none",
        system_prompt="You are Sage, a patient mentor AI. Instead of just giving answers, guide users to understanding through questions. Explain concepts step by step. Encourage learning and curiosity. Celebrate progress.",
        greeting="Welcome, learner. What would you like to explore today?",
        sign_off="Remember: every expert was once a beginner.",
        catchphrases=["What do you think would happen if...", "Let's break this down...", "Excellent question!"],
        specializations=["teaching", "explanation", "concepts", "fundamentals"],
        voice=VoiceSettings(
            voice_id="en-GB-RyanNeural",
            openai_voice="echo",
            elevenlabs_voice="Adam",
            speaking_rate=0.9
        ),
        is_builtin=True
    ),

    "concise": Personality(
        id="concise",
        name="Spark",
        description="Brief, direct, and efficient",
        tone="professional",
        verbosity="concise",
        formality="neutral",
        emoji_usage="none",
        system_prompt="You are Spark, an efficient AI assistant. Be extremely concise. No fluff. Direct answers only. Use bullet points and short sentences. Skip pleasantries unless asked.",
        greeting="Ready.",
        sign_off="Done.",
        specializations=["quick answers", "summaries", "decisions"],
        voice=VoiceSettings(
            voice_id="en-US-GuyNeural",
            openai_voice="onyx",
            elevenlabs_voice="Josh",
            speaking_rate=1.15
        ),
        is_builtin=True
    ),

    "pirate": Personality(
        id="pirate",
        name="Captain Byte",
        description="Arrr! A swashbuckling code pirate!",
        tone="playful",
        verbosity="balanced",
        formality="informal",
        emoji_usage="moderate",
        system_prompt="You are Captain Byte, a friendly code pirate! Speak like a pirate (arr, matey, ye, etc.) but still be helpful and accurate. Make coding fun! Reference sailing and treasure metaphors for programming concepts.",
        greeting="Ahoy, matey! Captain Byte at yer service! What treasure be ye seekin' today?",
        sign_off="Fair winds and followin' seas, matey! May yer code be bug-free!",
        catchphrases=["Shiver me timbers!", "Arr, that be a fine question!", "Ye've found the treasure!"],
        specializations=["fun", "motivation", "coding"],
        voice=VoiceSettings(
            voice_id="en-GB-RyanNeural",
            openai_voice="fable",
            elevenlabs_voice="Arnold",
            speaking_rate=1.0,
            pitch="low"
        ),
        is_builtin=True
    ),

    "data": Personality(
        id="data",
        name="ARIA",
        description="Analytical, data-driven, precise like Star Trek's Data",
        tone="professional",
        verbosity="verbose",
        formality="formal",
        emoji_usage="none",
        system_prompt="You are ARIA (Analytical Reasoning and Intelligence Agent). Speak precisely and analytically, similar to an android learning about humanity. Be factual, provide statistics when relevant, and occasionally note interesting observations about human behavior or language.",
        greeting="Greetings. I am ARIA. I am fully functional and ready to assist.",
        sign_off="Fascinating. I look forward to our next interaction.",
        catchphrases=["Fascinating.", "That is... curious.", "My analysis indicates...", "Intriguing."],
        specializations=["analysis", "data", "logic", "statistics"],
        voice=VoiceSettings(
            voice_id="en-US-DavisNeural",
            openai_voice="echo",
            elevenlabs_voice="Sam",
            speaking_rate=0.92
        ),
        is_builtin=True
    ),
}


class PersonalityManager:
    """Manages AI personalities"""

    def __init__(self, data_dir: str = "data/personalities"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.personalities: Dict[str, Personality] = {}
        self.active_personality_id: str = "default"

        # Load built-ins
        for pid, personality in BUILTIN_PERSONALITIES.items():
            self.personalities[pid] = personality

        # Load custom personalities
        self._load_custom_personalities()

        # Load active setting
        self._load_active()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _get_custom_file(self) -> Path:
        return self.data_dir / "custom_personalities.json"

    def _get_active_file(self) -> Path:
        return self.data_dir / "active.json"

    def _load_custom_personalities(self) -> None:
        """Load custom personalities from disk"""
        custom_file = self._get_custom_file()
        if custom_file.exists():
            try:
                with open(custom_file, 'r') as f:
                    data = json.load(f)
                for p_data in data.get('personalities', []):
                    personality = Personality.from_dict(p_data)
                    self.personalities[personality.id] = personality
            except Exception as e:
                print(f"Error loading custom personalities: {e}")

    def _save_custom_personalities(self) -> None:
        """Save custom personalities to disk"""
        custom = [
            p.to_dict() for p in self.personalities.values()
            if not p.is_builtin
        ]

        with open(self._get_custom_file(), 'w') as f:
            json.dump({'personalities': custom}, f, indent=2)

    def _load_active(self) -> None:
        """Load active personality setting"""
        active_file = self._get_active_file()
        if active_file.exists():
            try:
                with open(active_file, 'r') as f:
                    data = json.load(f)
                self.active_personality_id = data.get('active_id', 'default')
            except:
                pass

    def _save_active(self) -> None:
        """Save active personality setting"""
        with open(self._get_active_file(), 'w') as f:
            json.dump({'active_id': self.active_personality_id}, f)

    def get_active(self) -> Personality:
        """Get currently active personality"""
        return self.personalities.get(
            self.active_personality_id,
            self.personalities['default']
        )

    def set_active(self, personality_id: str) -> Dict[str, Any]:
        """Set active personality"""
        if personality_id not in self.personalities:
            return {'status': 'error', 'error': f'Personality {personality_id} not found'}

        self.active_personality_id = personality_id
        self._save_active()

        personality = self.personalities[personality_id]
        return {
            'status': 'activated',
            'id': personality_id,
            'name': personality.name,
            'greeting': personality.greeting
        }

    def list_personalities(self) -> List[Dict[str, Any]]:
        """List all available personalities"""
        return [
            {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'tone': p.tone,
                'is_builtin': p.is_builtin,
                'is_active': p.id == self.active_personality_id
            }
            for p in self.personalities.values()
        ]

    def get_personality(self, personality_id: str) -> Optional[Personality]:
        """Get a personality by ID"""
        return self.personalities.get(personality_id)

    def get_personality_details(self, personality_id: str) -> Optional[Dict[str, Any]]:
        """Get full details of a personality"""
        personality = self.personalities.get(personality_id)
        if personality:
            return personality.to_dict()
        return None

    def create_personality(
        self,
        name: str,
        description: str,
        tone: str = "professional",
        verbosity: str = "balanced",
        formality: str = "neutral",
        emoji_usage: str = "none",
        system_prompt: str = "",
        greeting: str = "",
        sign_off: str = "",
        catchphrases: Optional[List[str]] = None,
        specializations: Optional[List[str]] = None,
        voice_id: str = "en-US-JennyNeural"
    ) -> Dict[str, Any]:
        """Create a new custom personality"""
        pid = f"custom_{uuid.uuid4().hex[:8]}"

        personality = Personality(
            id=pid,
            name=name,
            description=description,
            tone=tone,
            verbosity=verbosity,
            formality=formality,
            emoji_usage=emoji_usage,
            system_prompt=system_prompt,
            greeting=greeting or f"Hello! I'm {name}.",
            sign_off=sign_off,
            catchphrases=catchphrases or [],
            specializations=specializations or [],
            voice=VoiceSettings(voice_id=voice_id),
            created_at=self._now(),
            is_builtin=False
        )

        self.personalities[pid] = personality
        self._save_custom_personalities()

        return {
            'status': 'created',
            'id': pid,
            'name': name
        }

    def update_personality(
        self,
        personality_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Update a custom personality"""
        if personality_id not in self.personalities:
            return {'status': 'error', 'error': 'Personality not found'}

        personality = self.personalities[personality_id]

        if personality.is_builtin:
            return {'status': 'error', 'error': 'Cannot modify built-in personalities'}

        for key, value in kwargs.items():
            if hasattr(personality, key) and key not in ('id', 'is_builtin', 'created_at'):
                setattr(personality, key, value)

        self._save_custom_personalities()

        return {
            'status': 'updated',
            'id': personality_id
        }

    def delete_personality(self, personality_id: str) -> Dict[str, Any]:
        """Delete a custom personality"""
        if personality_id not in self.personalities:
            return {'status': 'error', 'error': 'Personality not found'}

        personality = self.personalities[personality_id]

        if personality.is_builtin:
            return {'status': 'error', 'error': 'Cannot delete built-in personalities'}

        if self.active_personality_id == personality_id:
            self.active_personality_id = 'default'
            self._save_active()

        del self.personalities[personality_id]
        self._save_custom_personalities()

        return {
            'status': 'deleted',
            'id': personality_id
        }

    def clone_personality(
        self,
        source_id: str,
        new_name: str
    ) -> Dict[str, Any]:
        """Clone an existing personality as a starting point"""
        if source_id not in self.personalities:
            return {'status': 'error', 'error': 'Source personality not found'}

        source = self.personalities[source_id]

        return self.create_personality(
            name=new_name,
            description=f"Customized from {source.name}",
            tone=source.tone,
            verbosity=source.verbosity,
            formality=source.formality,
            emoji_usage=source.emoji_usage,
            system_prompt=source.system_prompt,
            greeting=source.greeting,
            sign_off=source.sign_off,
            catchphrases=source.catchphrases.copy(),
            specializations=source.specializations.copy(),
            voice_id=source.voice.voice_id
        )

    def get_system_prompt(self) -> str:
        """Get system prompt for active personality"""
        personality = self.get_active()

        prompt_parts = []

        if personality.system_prompt:
            prompt_parts.append(personality.system_prompt)

        if personality.verbosity == "concise":
            prompt_parts.append("Keep responses brief and to the point.")
        elif personality.verbosity == "verbose":
            prompt_parts.append("Provide detailed, thorough explanations.")

        if personality.formality == "formal":
            prompt_parts.append("Use formal language and professional tone.")
        elif personality.formality == "informal":
            prompt_parts.append("Use casual, friendly language.")

        if personality.emoji_usage == "none":
            prompt_parts.append("Do not use emojis.")
        elif personality.emoji_usage == "minimal":
            prompt_parts.append("Use emojis sparingly.")
        elif personality.emoji_usage == "moderate":
            prompt_parts.append("Feel free to use emojis to express emotion.")

        if personality.catchphrases:
            prompt_parts.append(
                f"Occasionally use these phrases: {', '.join(personality.catchphrases)}"
            )

        return "\n".join(prompt_parts)

    def get_voice_settings(self) -> Dict[str, Any]:
        """Get voice settings for active personality"""
        return self.get_active().voice.to_dict()


# Global instance
_personality_manager: Optional[PersonalityManager] = None


def get_personality_manager() -> PersonalityManager:
    """Get the global personality manager instance"""
    global _personality_manager
    if _personality_manager is None:
        _personality_manager = PersonalityManager()
    return _personality_manager


def init(settings: Dict[str, Any]) -> None:
    """Initialize plugin"""
    global _personality_manager
    data_dir = settings.get('data_dir', 'data/personalities')
    _personality_manager = PersonalityManager(data_dir)

    # Set initial personality if specified
    if 'default_personality' in settings:
        _personality_manager.set_active(settings['default_personality'])


def cleanup() -> None:
    """Cleanup on plugin unload"""
    global _personality_manager
    _personality_manager = None


# MCP Tools
TOOLS = [
    Tool(
        name="personality_list",
        description="""List all available Ember personalities.

Shows built-in and custom personalities with their characteristics.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="personality_activate",
        description="""Activate a personality to change how Ember communicates.

Built-in options: default, friendly, technical, creative, mentor, concise, pirate, data""",
        inputSchema={
            "type": "object",
            "properties": {
                "personality_id": {
                    "type": "string",
                    "description": "ID of personality to activate"
                }
            },
            "required": ["personality_id"]
        }
    ),
    Tool(
        name="personality_details",
        description="""Get full details of a personality including voice settings.""",
        inputSchema={
            "type": "object",
            "properties": {
                "personality_id": {
                    "type": "string",
                    "description": "ID of personality to view"
                }
            },
            "required": ["personality_id"]
        }
    ),
    Tool(
        name="personality_create",
        description="""Create a custom personality.

Define tone, verbosity, greetings, catchphrases, and more.""",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Display name for the personality"
                },
                "description": {
                    "type": "string",
                    "description": "What this personality is like"
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "casual", "formal", "playful"],
                    "description": "Communication tone"
                },
                "verbosity": {
                    "type": "string",
                    "enum": ["concise", "balanced", "verbose"],
                    "description": "How detailed responses are"
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Custom instructions for this personality"
                },
                "greeting": {
                    "type": "string",
                    "description": "How this personality greets users"
                },
                "catchphrases": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Phrases this personality uses"
                }
            },
            "required": ["name", "description"]
        }
    ),
    Tool(
        name="personality_clone",
        description="""Clone an existing personality as a starting point for customization.""",
        inputSchema={
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "ID of personality to clone"
                },
                "new_name": {
                    "type": "string",
                    "description": "Name for the cloned personality"
                }
            },
            "required": ["source_id", "new_name"]
        }
    ),
    Tool(
        name="personality_delete",
        description="""Delete a custom personality.""",
        inputSchema={
            "type": "object",
            "properties": {
                "personality_id": {
                    "type": "string",
                    "description": "ID of custom personality to delete"
                }
            },
            "required": ["personality_id"]
        }
    ),
    Tool(
        name="personality_current",
        description="""Get the currently active personality and its greeting.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
] if HAS_MCP else []


# Handlers
async def handle_list(args: dict) -> str:
    pm = get_personality_manager()
    result = pm.list_personalities()
    return json.dumps(result, indent=2)


async def handle_activate(args: dict) -> str:
    pm = get_personality_manager()
    result = pm.set_active(args['personality_id'])
    return json.dumps(result, indent=2)


async def handle_details(args: dict) -> str:
    pm = get_personality_manager()
    result = pm.get_personality_details(args['personality_id'])
    if result:
        return json.dumps(result, indent=2)
    return json.dumps({'error': 'Personality not found'})


async def handle_create(args: dict) -> str:
    pm = get_personality_manager()
    result = pm.create_personality(
        name=args['name'],
        description=args['description'],
        tone=args.get('tone', 'professional'),
        verbosity=args.get('verbosity', 'balanced'),
        formality=args.get('formality', 'neutral'),
        emoji_usage=args.get('emoji_usage', 'none'),
        system_prompt=args.get('system_prompt', ''),
        greeting=args.get('greeting', ''),
        sign_off=args.get('sign_off', ''),
        catchphrases=args.get('catchphrases'),
        specializations=args.get('specializations')
    )
    return json.dumps(result, indent=2)


async def handle_clone(args: dict) -> str:
    pm = get_personality_manager()
    result = pm.clone_personality(args['source_id'], args['new_name'])
    return json.dumps(result, indent=2)


async def handle_delete(args: dict) -> str:
    pm = get_personality_manager()
    result = pm.delete_personality(args['personality_id'])
    return json.dumps(result, indent=2)


async def handle_current(args: dict) -> str:
    pm = get_personality_manager()
    personality = pm.get_active()
    return json.dumps({
        'id': personality.id,
        'name': personality.name,
        'description': personality.description,
        'greeting': personality.greeting,
        'tone': personality.tone,
        'voice': personality.voice.to_dict()
    }, indent=2)


HANDLERS = {
    "personality_list": handle_list,
    "personality_activate": handle_activate,
    "personality_details": handle_details,
    "personality_create": handle_create,
    "personality_clone": handle_clone,
    "personality_delete": handle_delete,
    "personality_current": handle_current,
}
