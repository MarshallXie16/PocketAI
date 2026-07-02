"""Voice output (TTS) — generates speech for a reply and uploads it to S3.

Phase 4c replaces the OpenAI backend with Gemini TTS
(gemini-3.1-flash-tts-preview) behind this same interface, keeping OpenAI
as the fallback.
"""

import datetime
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# Wrapper class for text to speech
class VoiceHandler:

    def __init__(self, s3_client):
        self.client = OpenAIVoice(s3_client)

    def generate_voice(self, text, voice_id, voice_model):
        return self.client.generate_voice(text, voice_id, voice_model)


class OpenAIVoice:

    def __init__(self, s3_client):
        from src.providers.registry import get_openai_client
        self.client = get_openai_client()
        self.s3_client = s3_client

    def generate_voice(self, text, voice_id, voice_model):
        """Generate speech for `text`, upload to S3, return the URL (or None)."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "speech.mp3"

                response = self.client.audio.speech.create(
                    model=voice_model, voice=voice_id, input=text
                )
                response.stream_to_file(temp_path)

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                s3_filename = f"voice_messages/voice_{timestamp}.mp3"

                with open(temp_path, "rb") as audio_file:
                    self.s3_client.upload_fileobj(
                        audio_file,
                        os.getenv("S3_BUCKET_NAME"),
                        s3_filename,
                        ExtraArgs={
                            "ContentType": "audio/mpeg",
                            "CacheControl": "public, max-age=31536000",
                        },
                    )

                return f"{os.environ.get('S3_LOCATION')}{s3_filename}"

        except Exception:
            logger.exception("Error generating voice (bucket=%s)", os.getenv("S3_BUCKET_NAME"))
            return None
