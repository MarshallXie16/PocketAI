"""Voice output (TTS) — generates speech for a reply and uploads it to S3.

Primary backend: Gemini ``gemini-3.1-flash-tts-preview`` (most natural per
maintainer; supports inline expressive audio tags like ``[warmly]``). It is
a preview model, so OpenAI TTS stays wired as the automatic fallback, and
AISettings with OpenAI voice models keep working unchanged.
"""

import datetime
import io
import logging
import os
import tempfile
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

GEMINI_TTS_MODEL = 'gemini-3.1-flash-tts-preview'
GEMINI_DEFAULT_VOICE = 'Kore'
GEMINI_VOICES = {  # small curated subset of the 30 prebuilt voices
    'Kore', 'Puck', 'Charon', 'Fenrir', 'Aoede', 'Leda', 'Orus', 'Zephyr',
}
# Gemini returns raw PCM: 16-bit mono @ 24kHz — wrapped in a WAV header for playback.
PCM_SAMPLE_RATE = 24000


class VoiceHandler:
    """Routes to Gemini or OpenAI TTS based on the AI's voice_model setting."""

    def __init__(self, s3_client):
        self.s3_client = s3_client

    def generate_voice(self, text, voice_id, voice_model):
        if (voice_model or '').startswith('gemini'):
            url = GeminiVoice(self.s3_client).generate_voice(text, voice_id)
            if url:
                return url
            logger.warning('Gemini TTS failed — falling back to OpenAI')
            return OpenAIVoice(self.s3_client).generate_voice(text, 'alloy', 'tts-1')
        return OpenAIVoice(self.s3_client).generate_voice(text, voice_id, voice_model)


def _upload(s3_client, data: bytes, suffix: str, content_type: str):
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    s3_filename = f'voice_messages/voice_{timestamp}.{suffix}'
    s3_client.upload_fileobj(
        io.BytesIO(data),
        os.getenv('S3_BUCKET_NAME'),
        s3_filename,
        ExtraArgs={'ContentType': content_type, 'CacheControl': 'public, max-age=31536000'},
    )
    return f"{os.environ.get('S3_LOCATION')}{s3_filename}"


class GeminiVoice:

    def __init__(self, s3_client):
        self.s3_client = s3_client

    def generate_voice(self, text, voice_id=None):
        """Generate speech with Gemini TTS; returns an S3 URL or None."""
        try:
            from google.genai import types

            from src.providers.gemini_provider import _get_client

            voice = voice_id if voice_id in GEMINI_VOICES else GEMINI_DEFAULT_VOICE
            response = _get_client().models.generate_content(
                model=GEMINI_TTS_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=['AUDIO'],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice),
                        ),
                    ),
                ),
            )
            pcm = response.candidates[0].content.parts[0].inline_data.data

            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(PCM_SAMPLE_RATE)
                wav.writeframes(pcm)

            return _upload(self.s3_client, buffer.getvalue(), 'wav', 'audio/wav')
        except Exception:
            logger.exception('Gemini TTS generation failed')
            return None


class OpenAIVoice:

    def __init__(self, s3_client):
        from src.providers.registry import get_openai_client
        self.client = get_openai_client()
        self.s3_client = s3_client

    def generate_voice(self, text, voice_id, voice_model):
        """Generate speech with OpenAI TTS; returns an S3 URL or None."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / 'speech.mp3'
                response = self.client.audio.speech.create(
                    model=voice_model or 'tts-1', voice=voice_id or 'alloy', input=text
                )
                response.stream_to_file(temp_path)
                return _upload(self.s3_client, temp_path.read_bytes(), 'mp3', 'audio/mpeg')
        except Exception:
            logger.exception('OpenAI TTS generation failed (bucket=%s)', os.getenv('S3_BUCKET_NAME'))
            return None
