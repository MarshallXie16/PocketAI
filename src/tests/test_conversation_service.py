"""Tests for src/services/conversation_service.run_ai_response.

The agent loop is patched at ``conversation_service.agent.run_turn`` and the
background executor at ``conversation_service.submit_background`` so no provider,
SDK, or thread runs. Runs inside a Flask request context with a logged-in user.
"""

import pytest
from flask_login import login_user

from src.ai import memory
from src.ai.agent import AgentTurn
from src.models.conversation_state import ConversationState
from src.services import conversation_service as cs


@pytest.fixture
def patch_agent(monkeypatch):
    """Make agent.run_turn return a fixed AgentTurn without any provider call."""
    def _fake_run_turn(**kwargs):
        return AgentTurn(text='hi')
    monkeypatch.setattr(cs.agent, 'run_turn', _fake_run_turn)


def _login(user):
    login_user(user)


def test_returns_text_and_appends_to_queue(app, make_user, make_ai, patch_agent):
    user = make_user(username='conv_user')
    ai = make_ai(owner=user, name='Conv', memory_chunk_size=6)

    with app.test_request_context():
        _login(user)
        result = cs.run_ai_response(ai.id, 'hello there')

    assert result == 'hi'
    state = ConversationState.query.filter_by(user_id=user.id, ai_id=ai.id).first()
    assert state is not None
    assert len(state.memory_queue) == 1
    assert 'conv_user' in state.memory_queue[0]
    assert 'hi' in state.memory_queue[0]


def test_queue_full_triggers_background_and_resets(app, make_user, make_ai, patch_agent, monkeypatch):
    user = make_user(username='conv_user')
    ai = make_ai(owner=user, name='Conv', memory_chunk_size=1)  # first turn fills the chunk

    calls = []
    monkeypatch.setattr(cs, 'submit_background', lambda *a, **k: calls.append((a, k)))

    with app.test_request_context():
        _login(user)
        cs.run_ai_response(ai.id, 'remember this')

    # background consolidation submitted exactly once, with the right target + args
    assert len(calls) == 1
    args = calls[0][0]
    assert args[1] is memory.consolidate_and_save
    assert args[2] == user.id       # user_id
    assert args[3] == ai.id         # ai_id
    assert isinstance(args[4], list) and len(args[4]) == 1   # the queue snapshot
    assert args[5] == 'Conv'        # ai name
    assert args[6] == 'conv_user'   # username

    state = ConversationState.query.filter_by(user_id=user.id, ai_id=ai.id).first()
    assert state.memory_queue == []
    assert state.memory_queue_count == 0


def test_missing_ai_id_raises_value_error(app, patch_agent):
    with pytest.raises(ValueError):
        cs.run_ai_response(999999, 'hello')
