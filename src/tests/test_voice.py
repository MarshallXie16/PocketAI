"""Tests for TTS routing (src/ai/voice.py).

Provider SDKs are mocked at the boundary: the Gemini client via
``gemini_provider._get_client`` and the S3 upload via ``voice._upload``.
OpenAI routing is verified by patching the ``OpenAIVoice`` class the
VoiceHandler references, so no OpenAI client is ever constructed.
"""

from unittest.mock import MagicMock

import pytest

from src.ai import voice
from src.providers import gemini_provider


def _gemini_response(pcm=b'\x00\x01\x02\x03'):
    """Build the nested SDK response shape GeminiVoice reads (inline PCM)."""
    resp = MagicMock()
    resp.candidates[0].content.parts[0].inline_data.data = pcm
    return resp


@pytest.fixture
def patched_upload(monkeypatch):
    monkeypatch.setattr(voice, '_upload', lambda s3, data, suffix, content_type: 'https://s3/voice.wav')


# --- Gemini path --------------------------------------------------------------

def test_gemini_model_routes_to_gemini_and_returns_url(monkeypatch, patched_upload):
    client = MagicMock()
    client.models.generate_content.return_value = _gemini_response()
    monkeypatch.setattr(gemini_provider, '_get_client', lambda: client)

    handler = voice.VoiceHandler(MagicMock())
    url = handler.generate_voice('hello', 'Kore', 'gemini-tts')

    assert url == 'https://s3/voice.wav'
    assert client.models.generate_content.called


def test_gemini_failure_falls_back_to_openai(monkeypatch):
    monkeypatch.setattr(gemini_provider, '_get_client',
                        MagicMock(side_effect=RuntimeError('boom')))
    fake_openai_cls = MagicMock()
    fake_openai_cls.return_value.generate_voice.return_value = 'https://s3/fallback.mp3'
    monkeypatch.setattr(voice, 'OpenAIVoice', fake_openai_cls)

    handler = voice.VoiceHandler(MagicMock())
    url = handler.generate_voice('hello', 'Kore', 'gemini-tts')

    assert url == 'https://s3/fallback.mp3'
    fake_openai_cls.return_value.generate_voice.assert_called_once_with('hello', 'alloy', 'tts-1')


def test_gemini_unknown_voice_falls_back_to_kore(monkeypatch, patched_upload):
    client = MagicMock()
    client.models.generate_content.return_value = _gemini_response()
    monkeypatch.setattr(gemini_provider, '_get_client', lambda: client)

    handler = voice.VoiceHandler(MagicMock())
    handler.generate_voice('hello', 'NotARealVoice', 'gemini-tts')

    config = client.models.generate_content.call_args.kwargs['config']
    voice_name = config.speech_config.voice_config.prebuilt_voice_config.voice_name
    assert voice_name == 'Kore'


# --- OpenAI path --------------------------------------------------------------

def test_openai_model_routes_directly_to_openai(monkeypatch):
    fake_openai_cls = MagicMock()
    fake_openai_cls.return_value.generate_voice.return_value = 'https://s3/openai.mp3'
    monkeypatch.setattr(voice, 'OpenAIVoice', fake_openai_cls)

    handler = voice.VoiceHandler(MagicMock())
    url = handler.generate_voice('hello', 'nova', 'tts-1')

    assert url == 'https://s3/openai.mp3'
    fake_openai_cls.return_value.generate_voice.assert_called_once_with('hello', 'nova', 'tts-1')
