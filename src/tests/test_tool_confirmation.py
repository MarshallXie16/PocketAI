"""The consequential-action confirmation gate (review finding: prompt-injected
content must not be able to send email / create events within a single turn).
"""

from unittest.mock import patch

from src.ai import tools
from src.extensions import db
from src.models.conversation_state import ConversationState
from src.models.message import Message


def _add_message(user, ai, sender, text):
    msg = Message(user_id=user.id, ai_id=ai.id, sender=sender, message=text)
    db.session.add(msg)
    db.session.commit()
    return msg


def test_consequential_tool_stores_draft_without_executing(app, make_user, make_ai):
    user = make_user()
    ai = make_ai(owner=user)
    _add_message(user, ai, 'user', 'email bob for me')

    with patch.object(tools, '_execute') as execute:
        result = tools.dispatch('email_send',
                                {'recipient_name': 'Bob', 'subject': 'hi', 'body': 'hello'},
                                user_id=user.id, ai_id=ai.id)

    execute.assert_not_called()
    assert 'NOT executed' in result
    state = ConversationState.query.filter_by(user_id=user.id, ai_id=ai.id).first()
    assert state.pending_action['tool'] == 'email_send'
    assert state.pending_action['args']['recipient_name'] == 'Bob'


def test_confirm_blocked_within_same_turn(app, make_user, make_ai):
    """No user message after the draft → confirmation refused (injection guard)."""
    user = make_user()
    ai = make_ai(owner=user)
    _add_message(user, ai, 'user', 'email bob for me')
    tools.dispatch('email_send', {'recipient_name': 'Bob', 'subject': 'hi', 'body': 'x'},
                   user_id=user.id, ai_id=ai.id)

    with patch.object(tools, '_execute') as execute:
        result = tools.dispatch('confirm_action', {}, user_id=user.id, ai_id=ai.id)

    execute.assert_not_called()
    assert 'Cannot execute yet' in result
    # the draft survives for a later, genuine confirmation
    state = ConversationState.query.filter_by(user_id=user.id, ai_id=ai.id).first()
    assert state.pending_action is not None


def test_confirm_allowed_after_new_user_message(app, make_user, make_ai):
    user = make_user()
    ai = make_ai(owner=user)
    _add_message(user, ai, 'user', 'email bob for me')
    tools.dispatch('email_send', {'recipient_name': 'Bob', 'subject': 'hi', 'body': 'x'},
                   user_id=user.id, ai_id=ai.id)
    _add_message(user, ai, 'user', 'yes, send it')  # genuine reply after the draft

    with patch.object(tools, '_execute', return_value='Email sent.') as execute:
        result = tools.dispatch('confirm_action', {}, user_id=user.id, ai_id=ai.id)

    execute.assert_called_once()
    assert result == 'Email sent.'
    state = ConversationState.query.filter_by(user_id=user.id, ai_id=ai.id).first()
    assert state.pending_action is None


def test_confirm_with_no_pending_action(app, make_user, make_ai):
    user = make_user()
    ai = make_ai(owner=user)
    result = tools.dispatch('confirm_action', {}, user_id=user.id, ai_id=ai.id)
    assert 'no pending action' in result.lower()


def test_dispatch_errors_are_generic(app, make_user, make_ai):
    """Tool failures must not leak exception internals to the model."""
    user = make_user()
    ai = make_ai(owner=user)
    with patch.object(tools.memory, 'search_memory', side_effect=RuntimeError('AKIA-secret-internals')):
        result = tools.dispatch('memory_search', {'query': 'x'}, user_id=user.id, ai_id=ai.id)
    assert 'AKIA-secret-internals' not in result
    assert 'memory_search' in result


def test_consume_queue_lines_only_removes_consumed(app, make_user, make_ai):
    """Background consolidation removes exactly what it consumed — lines
    appended meanwhile survive; on failure nothing is removed."""
    from src.ai.memory import _consume_queue_lines

    user = make_user()
    ai = make_ai(owner=user)
    state = ConversationState.get_or_create(user.id, ai.id)
    state.memory_queue = ['a', 'b', 'c-new']
    state.memory_queue_count = 3
    db.session.commit()

    _consume_queue_lines(user.id, ai.id, ['a', 'b'])
    state = ConversationState.query.filter_by(user_id=user.id, ai_id=ai.id).first()
    assert state.memory_queue == ['c-new']
    assert state.memory_queue_count == 1
