"""
Voice Interface Plugin for Crucible

Provides speech-to-text (STT) and text-to-speech (TTS) capabilities.

Supported backends:
- STT: OpenAI Whisper API, local Whisper, Google Speech
- TTS: OpenAI TTS, ElevenLabs, Edge TTS (free), local pyttsx3

Configuration via plugins.json:
{
  "settings": {
    "voice": {
      "stt_backend": "whisper_api",  // whisper_api, whisper_local, google
      "tts_backend": "edge",         // openai, elevenlabs, edge, local
      "openai_api_key": "...",       // Optional, uses OPENAI_API_KEY env if not set
      "elevenlabs_api_key": "...",
      "voice_id": "alloy",           // OpenAI: alloy, echo, fable, onyx, nova, shimmer
      "language": "en",
      "audio_format": "mp3"
    }
  }
}
"""

import os
import json
import asyncio
import tempfile
import subprocess
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

try:
    from mcp.types import Tool
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    Tool = None


@dataclass
class VoiceConfig:
    """Voice interface configuration"""
    stt_backend: str = "whisper_api"
    tts_backend: str = "edge"
    openai_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    voice_id: str = "alloy"
    elevenlabs_voice: str = "Rachel"
    language: str = "en"
    audio_format: str = "mp3"
    audio_dir: str = "data/voice"


class STTBackend:
    """Base class for speech-to-text backends"""

    async def transcribe(self, audio_path: str, language: str = "en") -> str:
        raise NotImplementedError


class TTSBackend:
    """Base class for text-to-speech backends"""

    async def synthesize(self, text: str, output_path: str) -> bool:
        raise NotImplementedError


class WhisperAPIBackend(STTBackend):
    """OpenAI Whisper API for speech-to-text"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def transcribe(self, audio_path: str, language: str = "en") -> str:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(audio_path, 'rb') as f:
                    files = {'file': (Path(audio_path).name, f, 'audio/mpeg')}
                    data = {
                        'model': 'whisper-1',
                        'language': language
                    }
                    response = await client.post(
                        'https://api.openai.com/v1/audio/transcriptions',
                        headers={'Authorization': f'Bearer {self.api_key}'},
                        files=files,
                        data=data
                    )

                    if response.status_code == 200:
                        return response.json().get('text', '')
                    else:
                        return f"Error: {response.status_code} - {response.text}"
        except ImportError:
            return "Error: httpx not installed. Run: pip install httpx"
        except Exception as e:
            return f"Error: {e}"


class WhisperLocalBackend(STTBackend):
    """Local Whisper model for speech-to-text (requires whisper package)"""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None

    def _load_model(self):
        if self._model is None:
            import whisper
            self._model = whisper.load_model(self.model_size)
        return self._model

    async def transcribe(self, audio_path: str, language: str = "en") -> str:
        try:
            import whisper

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            def _transcribe():
                model = self._load_model()
                result = model.transcribe(audio_path, language=language)
                return result['text']

            return await loop.run_in_executor(None, _transcribe)
        except ImportError:
            return "Error: whisper not installed. Run: pip install openai-whisper"
        except Exception as e:
            return f"Error: {e}"


class OpenAITTSBackend(TTSBackend):
    """OpenAI TTS API for text-to-speech"""

    def __init__(self, api_key: str, voice: str = "alloy"):
        self.api_key = api_key
        self.voice = voice

    async def synthesize(self, text: str, output_path: str) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    'https://api.openai.com/v1/audio/speech',
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': 'tts-1',
                        'input': text,
                        'voice': self.voice,
                        'response_format': 'mp3'
                    }
                )

                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    return True
                return False
        except Exception as e:
            print(f"OpenAI TTS error: {e}")
            return False


class ElevenLabsTTSBackend(TTSBackend):
    """ElevenLabs API for high-quality text-to-speech"""

    VOICES = {
        "Rachel": "21m00Tcm4TlvDq8ikWAM",
        "Domi": "AZnzlk1XvdvUeBnXmlld",
        "Bella": "EXAVITQu4vr4xnSDxMaL",
        "Antoni": "ErXwobaYiN019PkySvjV",
        "Elli": "MF3mGyEYCl7XYWbV9V6O",
        "Josh": "TxGEqnHWrfWFTfGW9XjX",
        "Arnold": "VR6AewLTigWG4xSOukaG",
        "Adam": "pNInz6obpgDQGcFmaJgB",
        "Sam": "yoZ06aMxZJJ28mfd3POQ",
    }

    def __init__(self, api_key: str, voice: str = "Rachel"):
        self.api_key = api_key
        self.voice_id = self.VOICES.get(voice, voice)

    async def synthesize(self, text: str, output_path: str) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f'https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}',
                    headers={
                        'xi-api-key': self.api_key,
                        'Content-Type': 'application/json'
                    },
                    json={
                        'text': text,
                        'model_id': 'eleven_monolingual_v1',
                        'voice_settings': {
                            'stability': 0.5,
                            'similarity_boost': 0.75
                        }
                    }
                )

                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    return True
                return False
        except Exception as e:
            print(f"ElevenLabs TTS error: {e}")
            return False


class EdgeTTSBackend(TTSBackend):
    """Microsoft Edge TTS (free, no API key required)"""

    VOICES = {
        "en-US": [
            "en-US-JennyNeural",
            "en-US-GuyNeural",
            "en-US-AriaNeural",
            "en-US-DavisNeural",
        ],
        "en-GB": [
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
        ]
    }

    def __init__(self, voice: str = "en-US-JennyNeural"):
        self.voice = voice

    async def synthesize(self, text: str, output_path: str) -> bool:
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_path)
            return True
        except ImportError:
            # Fallback to subprocess if edge_tts not installed
            try:
                result = subprocess.run(
                    ['edge-tts', '--voice', self.voice, '--text', text, '--write-media', output_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.returncode == 0
            except Exception as e:
                print(f"Edge TTS error: {e}")
                return False
        except Exception as e:
            print(f"Edge TTS error: {e}")
            return False


class LocalTTSBackend(TTSBackend):
    """Local TTS using pyttsx3 (offline, no API required)"""

    def __init__(self, rate: int = 150):
        self.rate = rate

    async def synthesize(self, text: str, output_path: str) -> bool:
        try:
            import pyttsx3

            loop = asyncio.get_event_loop()

            def _synthesize():
                engine = pyttsx3.init()
                engine.setProperty('rate', self.rate)
                engine.save_to_file(text, output_path)
                engine.runAndWait()
                return True

            return await loop.run_in_executor(None, _synthesize)
        except ImportError:
            return False
        except Exception as e:
            print(f"Local TTS error: {e}")
            return False


class VoiceInterface:
    """Main voice interface manager"""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self.audio_dir = Path(config.audio_dir)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        self._stt: Optional[STTBackend] = None
        self._tts: Optional[TTSBackend] = None

        self._init_backends()

    def _init_backends(self):
        """Initialize STT and TTS backends based on config"""
        # Get API keys from config or environment
        openai_key = self.config.openai_api_key or os.environ.get('OPENAI_API_KEY')
        elevenlabs_key = self.config.elevenlabs_api_key or os.environ.get('ELEVENLABS_API_KEY')

        # Initialize STT backend
        if self.config.stt_backend == "whisper_api" and openai_key:
            self._stt = WhisperAPIBackend(openai_key)
        elif self.config.stt_backend == "whisper_local":
            self._stt = WhisperLocalBackend()

        # Initialize TTS backend
        if self.config.tts_backend == "openai" and openai_key:
            self._tts = OpenAITTSBackend(openai_key, self.config.voice_id)
        elif self.config.tts_backend == "elevenlabs" and elevenlabs_key:
            self._tts = ElevenLabsTTSBackend(elevenlabs_key, self.config.elevenlabs_voice)
        elif self.config.tts_backend == "edge":
            self._tts = EdgeTTSBackend()
        elif self.config.tts_backend == "local":
            self._tts = LocalTTSBackend()
        else:
            # Default to Edge TTS (free, works without API keys)
            self._tts = EdgeTTSBackend()

    async def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe audio file to text"""
        if not self._stt:
            return {
                'status': 'error',
                'error': 'No STT backend configured. Set OPENAI_API_KEY or use whisper_local.'
            }

        if not Path(audio_path).exists():
            return {
                'status': 'error',
                'error': f'Audio file not found: {audio_path}'
            }

        text = await self._stt.transcribe(audio_path, self.config.language)

        if text.startswith("Error:"):
            return {'status': 'error', 'error': text}

        return {
            'status': 'success',
            'text': text,
            'backend': self.config.stt_backend
        }

    async def synthesize_speech(
        self,
        text: str,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convert text to speech audio file"""
        if not self._tts:
            return {
                'status': 'error',
                'error': 'No TTS backend configured.'
            }

        if not filename:
            import uuid
            filename = f"speech_{uuid.uuid4().hex[:8]}.mp3"

        output_path = self.audio_dir / filename

        success = await self._tts.synthesize(text, str(output_path))

        if success:
            return {
                'status': 'success',
                'audio_path': str(output_path),
                'backend': self.config.tts_backend
            }

        return {
            'status': 'error',
            'error': 'Failed to synthesize speech'
        }

    async def speak_response(self, text: str) -> Dict[str, Any]:
        """Synthesize and optionally play audio response"""
        result = await self.synthesize_speech(text)

        if result['status'] == 'success':
            # Try to play the audio (optional)
            audio_path = result['audio_path']

            try:
                # Try different audio players
                for player in ['mpv', 'ffplay', 'afplay', 'aplay']:
                    try:
                        subprocess.run(
                            [player, '-nodisp', '-autoexit', audio_path] if player == 'ffplay'
                            else [player, audio_path],
                            capture_output=True,
                            timeout=60
                        )
                        result['played'] = True
                        break
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
            except:
                result['played'] = False

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get voice interface status"""
        return {
            'stt_configured': self._stt is not None,
            'stt_backend': self.config.stt_backend if self._stt else None,
            'tts_configured': self._tts is not None,
            'tts_backend': self.config.tts_backend if self._tts else None,
            'language': self.config.language,
            'audio_dir': str(self.audio_dir)
        }

    def list_audio_files(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent audio files"""
        files = sorted(
            self.audio_dir.glob("*.mp3"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]

        return [
            {
                'filename': f.name,
                'path': str(f),
                'size_bytes': f.stat().st_size,
                'modified': f.stat().st_mtime
            }
            for f in files
        ]

    def cleanup_audio(self, older_than_hours: int = 24) -> int:
        """Clean up old audio files"""
        import time

        cutoff = time.time() - (older_than_hours * 3600)
        removed = 0

        for f in self.audio_dir.glob("*.mp3"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except:
                pass

        return removed


# Global instance
_voice_interface: Optional[VoiceInterface] = None
_config: VoiceConfig = VoiceConfig()


def init(settings: Dict[str, Any]) -> None:
    """Initialize plugin with settings from plugins.json"""
    global _voice_interface, _config

    _config = VoiceConfig(
        stt_backend=settings.get('stt_backend', 'whisper_api'),
        tts_backend=settings.get('tts_backend', 'edge'),
        openai_api_key=settings.get('openai_api_key'),
        elevenlabs_api_key=settings.get('elevenlabs_api_key'),
        voice_id=settings.get('voice_id', 'alloy'),
        elevenlabs_voice=settings.get('elevenlabs_voice', 'Rachel'),
        language=settings.get('language', 'en'),
        audio_format=settings.get('audio_format', 'mp3'),
        audio_dir=settings.get('audio_dir', 'data/voice')
    )

    _voice_interface = VoiceInterface(_config)


def cleanup() -> None:
    """Cleanup on plugin unload"""
    global _voice_interface
    _voice_interface = None


def get_voice_interface() -> VoiceInterface:
    """Get the voice interface instance"""
    global _voice_interface
    if _voice_interface is None:
        _voice_interface = VoiceInterface(_config)
    return _voice_interface


# MCP Tool definitions
TOOLS = [
    Tool(
        name="voice_transcribe",
        description="""Transcribe an audio file to text using speech-to-text.

Supports various audio formats (mp3, wav, m4a, etc.).
Uses OpenAI Whisper API or local Whisper model.""",
        inputSchema={
            "type": "object",
            "properties": {
                "audio_path": {
                    "type": "string",
                    "description": "Path to the audio file to transcribe"
                }
            },
            "required": ["audio_path"]
        }
    ),
    Tool(
        name="voice_speak",
        description="""Convert text to speech and save as audio file.

Uses Edge TTS (free) by default, or OpenAI/ElevenLabs if configured.""",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech"
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename for the output audio"
                },
                "play": {
                    "type": "boolean",
                    "description": "Whether to play the audio after synthesis (default: false)"
                }
            },
            "required": ["text"]
        }
    ),
    Tool(
        name="voice_status",
        description="""Get voice interface status and configuration.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="voice_list_audio",
        description="""List recent audio files.""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum files to list (default: 20)"
                }
            }
        }
    ),
    Tool(
        name="voice_cleanup",
        description="""Clean up old audio files.""",
        inputSchema={
            "type": "object",
            "properties": {
                "older_than_hours": {
                    "type": "integer",
                    "description": "Delete files older than this many hours (default: 24)"
                }
            }
        }
    ),
] if HAS_MCP else []


# Handler functions
async def handle_transcribe(args: dict) -> str:
    vi = get_voice_interface()
    result = await vi.transcribe_audio(args['audio_path'])
    return json.dumps(result, indent=2)


async def handle_speak(args: dict) -> str:
    vi = get_voice_interface()

    if args.get('play', False):
        result = await vi.speak_response(args['text'])
    else:
        result = await vi.synthesize_speech(
            args['text'],
            args.get('filename')
        )

    return json.dumps(result, indent=2)


async def handle_status(args: dict) -> str:
    vi = get_voice_interface()
    return json.dumps(vi.get_status(), indent=2)


async def handle_list_audio(args: dict) -> str:
    vi = get_voice_interface()
    result = vi.list_audio_files(args.get('limit', 20))
    return json.dumps(result, indent=2)


async def handle_cleanup(args: dict) -> str:
    vi = get_voice_interface()
    removed = vi.cleanup_audio(args.get('older_than_hours', 24))
    return json.dumps({'removed': removed})


HANDLERS = {
    "voice_transcribe": handle_transcribe,
    "voice_speak": handle_speak,
    "voice_status": handle_status,
    "voice_list_audio": handle_list_audio,
    "voice_cleanup": handle_cleanup,
}
