"""Chat message-lifecycle tests: regenerate, edit, and pagination.

AI generation (conversation_service.run_ai_response) is patched at the point
where the chat blueprint imported it, so no provider is contacted.
"""

import datetime
from unittest.mock import patch

from src.extensions import db
from src.models.message import Message


def _seed_message(user, ai, sender, text, ts):
    msg = Message(user_id=user.id, ai_id=ai.id, sender=sender, message=text)
    msg.timestamp = ts
    db.session.add(msg)
    db.session.commit()
    return msg


def test_regenerate_deletes_only_target_and_after(client, make_user, make_ai, login):
    user = make_user(username='u', password='pw')
    ai = make_ai(owner=user)
    base = datetime.datetime(2024, 1, 1, 12, 0, 0)

    m1 = _seed_message(user, ai, 'user', 'hi', base)
    m2 = _seed_message(user, ai, 'assistant', 'hello', base + datetime.timedelta(seconds=1))
    m3 = _seed_message(user, ai, 'assistant', 'second reply', base + datetime.timedelta(seconds=2))
    m4 = _seed_message(user, ai, 'user', 'bye', base + datetime.timedelta(seconds=3))

    login('u', 'pw')
    with patch('src.blueprints.chat.run_ai_response', return_value='REGENERATED'):
        resp = client.post('/regenerate_message', json={
            'ai_message_id': m3.id,
            'user_message': 'hello again',
            'modelId': ai.id,
        })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['response'] == 'REGENERATED'
    # deleted_ids excludes the regenerated message itself -> only m4
    assert body['deleted_ids'] == [m4.id]

    # earlier two survive; target + subsequent are gone; a fresh assistant exists
    assert Message.query.get(m1.id) is not None
    assert Message.query.get(m2.id) is not None
    assert Message.query.get(m3.id) is None
    assert Message.query.get(m4.id) is None
    remaining = Message.query.filter_by(user_id=user.id, ai_id=ai.id).order_by(Message.id).all()
    assert [m.message for m in remaining] == ['hi', 'hello', 'REGENERATED']


def test_edit_message_rejects_other_users_message(client, make_user, make_ai, login):
    owner = make_user(username='owner', password='pw')
    make_user(username='intruder', password='pw2')
    ai = make_ai(owner=owner)
    msg = _seed_message(owner, ai, 'user', 'private text', datetime.datetime(2024, 1, 1))

    login('intruder', 'pw2')
    resp = client.put('/edit_message', json={'message_id': msg.id, 'new_content': 'hacked'})
    assert resp.status_code == 403
    assert Message.query.get(msg.id).message == 'private text'


def test_load_more_messages_shape(client, make_user, make_ai, login):
    user = make_user(username='u', password='pw')
    ai = make_ai(owner=user)
    base = datetime.datetime(2024, 1, 1, 12, 0, 0)
    for i in range(12):
        _seed_message(user, ai, 'user' if i % 2 == 0 else 'assistant',
                      f'msg {i}', base + datetime.timedelta(seconds=i))

    login('u', 'pw')
    resp = client.post('/load-more-messages', json={'current_message_count': 10})
    assert resp.status_code == 200
    data = resp.get_json()
    # 12 total, offset 10 -> 2 remaining, returned oldest-first
    assert len(data) == 2
    for item in data:
        assert set(item.keys()) == {'sender', 'message', 'timestamp'}
    assert [d['message'] for d in data] == ['msg 0', 'msg 1']
