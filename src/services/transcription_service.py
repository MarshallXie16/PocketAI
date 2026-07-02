"""Voice input (STT): transcribe a recorded audio clip to text.

Used by POST /transcribe. The browser records with MediaRecorder
(audio/webm) and uploads; the transcript is returned for review-before-send
— it lands in the message box, the user edits/sends. Uses OpenAI
gpt-4o-transcribe (lower WER than whisper-1 per current docs).
"""

import logging

from src.providers.registry import get_openai_client

logger = logging.getLogger(__name__)

STT_MODEL = 'gpt-4o-transcribe'
MAX_AUDIO_BYTES = 15 * 1024 * 1024   # generous cap; MediaRecorder clips are far smaller


def transcribe(file_storage) -> str:
    """Transcribe an uploaded audio file (werkzeug FileStorage). Returns text."""
    # the OpenAI SDK infers format from the filename; keep the original name
    result = get_openai_client().audio.transcriptions.create(
        model=STT_MODEL,
        file=(file_storage.filename or 'audio.webm', file_storage.stream),
    )
    return (result.text or '').strip()
