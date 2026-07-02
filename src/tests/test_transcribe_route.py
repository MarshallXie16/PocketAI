"""Tests for POST /transcribe (src/blueprints/chat.py).

transcription_service.transcribe is patched at the module the route imports it
from, so no OpenAI client is constructed.
"""

import io

from src.services import transcription_service


def _audio(data=b'fake-audio-bytes', name='clip.webm'):
    return {'audio': (io.BytesIO(data), name)}


def test_transcribe_anonymous_redirects(client):
    resp = client.post('/transcribe')
    assert resp.status_code == 302  # login_required -> redirect to login


def test_transcribe_logged_in_without_file_bad_request(client, make_user, login):
    make_user(username='u', password='pw')
    login('u', 'pw')
    resp = client.post('/transcribe')
    assert resp.status_code == 400
    assert resp.get_json()['code'] == 'BAD_REQUEST'


def test_transcribe_returns_text(client, make_user, login, monkeypatch):
    make_user(username='u', password='pw')
    login('u', 'pw')
    monkeypatch.setattr(transcription_service, 'transcribe', lambda audio: 'hello')

    resp = client.post('/transcribe', data=_audio(), content_type='multipart/form-data')

    assert resp.status_code == 200
    assert resp.get_json() == {'text': 'hello'}


def test_transcribe_error_returns_500(client, make_user, login, monkeypatch):
    make_user(username='u', password='pw')
    login('u', 'pw')

    def _boom(audio):
        raise RuntimeError('stt exploded')

    monkeypatch.setattr(transcription_service, 'transcribe', _boom)

    resp = client.post('/transcribe', data=_audio(), content_type='multipart/form-data')

    assert resp.status_code == 500
    body = resp.get_json()
    assert body['code'] == 'SERVER_ERROR'
    assert 'stt exploded' not in body['error']  # generic message, no internals leaked
