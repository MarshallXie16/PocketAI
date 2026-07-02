"""Tests for agent-scheduled proactive outreach (src/services/proactive_service.py).

Every LLM call is mocked at the boundary by patching
``src.services.proactive_service.get_provider`` (the name the module imported).
Guardrails, quiet hours, daily-checkin materialization, and the nightly
planner are each exercised in isolation with ScheduledMessage rows built
directly. The tick endpoint's shared-secret auth is covered via the client.
"""

import datetime
from unittest.mock import MagicMock

import pytest

from src.extensions import db
from src.models.message import Message
from src.models.relationship import ScheduledMessage
from src.providers.base import LLMResult
from src.services import proactive_service


class _FakeProvider:
    def __init__(self, text):
        self._text = text
        self.calls = 0

    def generate(self, *, model, system, messages, max_tokens=2048, **kw):
        self.calls += 1
        return LLMResult(text=self._text)


def _patch_provider(monkeypatch, text):
    provider = _FakeProvider(text)
    monkeypatch.setattr(proactive_service, 'get_provider', lambda model: provider)
    return provider


@pytest.fixture
def consented(make_user, make_ai):
    """A user who opted into proactive outreach, with a linked AI + settings."""
    user = make_user(username='pro_user')
    ai = make_ai(owner=user, name='ProAI')
    settings = user.settings
    settings.proactive_consent_at = datetime.datetime.now(datetime.UTC)
    settings.timezone = 'UTC'
    settings.last_active_ai_id = ai.id
    db.session.commit()
    return user, ai, settings


def _future_iso(hours=3):
    return (datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=hours)).isoformat()


def _sched(user_id, ai_id, *, scheduled_for=None, trigger='commitment', status='pending'):
    row = ScheduledMessage(
        user_id=user_id, ai_id=ai_id,
        scheduled_for=scheduled_for or datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
        trigger=trigger, trigger_context='reach out',
    )
    row.status = status
    db.session.add(row)
    db.session.commit()
    return row


# --- schedule_checkin ---------------------------------------------------------

def test_schedule_checkin_stores_utc_naive(db, consented):
    user, ai, _ = consented
    # 09:00 at -07:00 == 16:00 UTC
    row = proactive_service.schedule_checkin(user.id, ai.id, '2026-07-02T09:00:00-07:00', 'good luck')

    assert row.scheduled_for == datetime.datetime(2026, 7, 2, 16, 0, 0)
    assert row.scheduled_for.tzinfo is None
    assert row.trigger == 'commitment'


# --- tick with no consented users --------------------------------------------

def test_tick_no_consent_all_zero(db, make_user):
    make_user(username='no_consent')  # settings.proactive_consent_at stays None
    stats = proactive_service.tick()
    assert stats == {'materialized': 0, 'planned': 0, 'sent': 0, 'skipped': 0, 'suppressed': 0}


# --- _deliver guardrails ------------------------------------------------------

def test_deliver_no_consent_cancels(db, make_user, make_ai, monkeypatch):
    user = make_user(username='unconsented')
    ai = make_ai(owner=user)
    row = _sched(user.id, ai.id)
    _patch_provider(monkeypatch, 'should not be used')

    outcome = proactive_service._deliver(row, datetime.datetime.now(datetime.UTC))

    assert outcome == 'suppressed'
    assert ScheduledMessage.query.get(row.id).status == 'cancelled'
    assert Message.query.count() == 0


def test_deliver_quiet_hours_stays_pending(db, consented, monkeypatch):
    user, ai, settings = consented
    settings.quiet_hours_start = datetime.time(0, 0)
    settings.quiet_hours_end = datetime.time(23, 59, 59)
    db.session.commit()
    row = _sched(user.id, ai.id)
    _patch_provider(monkeypatch, 'should not be used')

    outcome = proactive_service._deliver(row, datetime.datetime.now(datetime.UTC))

    assert outcome == 'suppressed'
    assert ScheduledMessage.query.get(row.id).status == 'pending'  # unchanged
    assert Message.query.count() == 0


def test_deliver_daily_cap_skips(db, consented, monkeypatch):
    user, ai, settings = consented
    settings.max_proactive_per_day = 2
    db.session.commit()
    # cap accounting counts delivered initiated Messages, not sent rows
    db.session.add(Message(user_id=user.id, ai_id=ai.id, sender='assistant', message='m1', initiated=True))
    db.session.add(Message(user_id=user.id, ai_id=ai.id, sender='assistant', message='m2', initiated=True))
    db.session.commit()
    row = _sched(user.id, ai.id)
    _patch_provider(monkeypatch, 'should not be used')

    outcome = proactive_service._deliver(row, datetime.datetime.now(datetime.UTC))

    assert outcome == 'suppressed'
    assert ScheduledMessage.query.get(row.id).status == 'skipped'
    assert Message.query.count() == 2  # only the seeded ones — nothing new sent


def test_deliver_model_skip_creates_no_message(db, consented, monkeypatch):
    user, ai, _ = consented
    row = _sched(user.id, ai.id)
    _patch_provider(monkeypatch, 'SKIP')

    outcome = proactive_service._deliver(row, datetime.datetime.now(datetime.UTC))

    assert outcome == 'skipped'
    assert ScheduledMessage.query.get(row.id).status == 'skipped'
    assert Message.query.count() == 0


def test_deliver_model_text_creates_initiated_message(db, consented, monkeypatch):
    user, ai, _ = consented
    row = _sched(user.id, ai.id)
    _patch_provider(monkeypatch, 'Hey, thinking of you today.')

    outcome = proactive_service._deliver(row, datetime.datetime.now(datetime.UTC))

    assert outcome == 'sent'
    msg = Message.query.one()
    assert msg.initiated is True
    assert msg.sender == 'assistant'
    assert msg.message == 'Hey, thinking of you today.'
    updated = ScheduledMessage.query.get(row.id)
    assert updated.status == 'sent'
    assert updated.delivered_message_id == msg.id


# --- quiet-hours helper -------------------------------------------------------

def _settings_with_quiet(start, end, tz='UTC'):
    s = MagicMock()
    s.quiet_hours_start = start
    s.quiet_hours_end = end
    s.timezone = tz
    return s


def test_quiet_hours_normal_range():
    s = _settings_with_quiet(datetime.time(9, 0), datetime.time(17, 0))
    noon = datetime.datetime(2026, 7, 1, 12, 0, tzinfo=datetime.UTC)
    evening = datetime.datetime(2026, 7, 1, 20, 0, tzinfo=datetime.UTC)
    assert proactive_service._in_quiet_hours(s, noon) is True
    assert proactive_service._in_quiet_hours(s, evening) is False


def test_quiet_hours_midnight_wrap():
    s = _settings_with_quiet(datetime.time(22, 0), datetime.time(6, 0))
    late = datetime.datetime(2026, 7, 1, 23, 0, tzinfo=datetime.UTC)
    early = datetime.datetime(2026, 7, 1, 3, 0, tzinfo=datetime.UTC)
    midday = datetime.datetime(2026, 7, 1, 12, 0, tzinfo=datetime.UTC)
    assert proactive_service._in_quiet_hours(s, late) is True
    assert proactive_service._in_quiet_hours(s, early) is True
    assert proactive_service._in_quiet_hours(s, midday) is False


def test_quiet_hours_unset_is_false():
    s = _settings_with_quiet(None, None)
    now = datetime.datetime(2026, 7, 1, 3, 0, tzinfo=datetime.UTC)
    assert proactive_service._in_quiet_hours(s, now) is False


# --- _materialize_daily_checkin ----------------------------------------------

def test_materialize_creates_one_row_after_local_time(db, consented):
    user, ai, settings = consented
    settings.daily_checkin_time = datetime.time(9, 0)
    db.session.commit()
    now = datetime.datetime(2026, 7, 1, 15, 0, tzinfo=datetime.UTC)

    assert proactive_service._materialize_daily_checkin(settings, now) == 1
    rows = ScheduledMessage.query.filter_by(user_id=user.id, trigger='daily_checkin').all()
    assert len(rows) == 1


def test_materialize_no_duplicate_same_day(db, consented):
    user, ai, settings = consented
    settings.daily_checkin_time = datetime.time(9, 0)
    db.session.commit()
    now = datetime.datetime(2026, 7, 1, 15, 0, tzinfo=datetime.UTC)

    assert proactive_service._materialize_daily_checkin(settings, now) == 1
    assert proactive_service._materialize_daily_checkin(settings, now) == 0
    assert ScheduledMessage.query.filter_by(trigger='daily_checkin').count() == 1


def test_materialize_before_local_time_creates_none(db, consented):
    user, ai, settings = consented
    settings.daily_checkin_time = datetime.time(23, 0)
    db.session.commit()
    now = datetime.datetime(2026, 7, 1, 15, 0, tzinfo=datetime.UTC)

    assert proactive_service._materialize_daily_checkin(settings, now) == 0
    assert ScheduledMessage.query.filter_by(trigger='daily_checkin').count() == 0


# --- _run_planner_if_due ------------------------------------------------------

def test_planner_creates_rows_capped_at_two(db, consented, monkeypatch):
    user, ai, settings = consented
    now = datetime.datetime(2026, 7, 1, 2, 0, tzinfo=datetime.UTC)
    plan = ('{"messages": ['
            f'{{"send_at": "{_future_iso(hours=3)}", "reason": "interview"}},'
            f'{{"send_at": "{_future_iso(hours=6)}", "reason": "follow up"}},'
            f'{{"send_at": "{_future_iso(hours=9)}", "reason": "third — dropped"}}]}}')
    _patch_provider(monkeypatch, plan)

    created = proactive_service._run_planner_if_due(settings, now)

    assert created == 2
    rows = ScheduledMessage.query.filter_by(user_id=user.id, trigger='planner').all()
    assert len(rows) == 2


def test_planner_empty_plan_records_skipped_row(db, consented, monkeypatch):
    user, ai, settings = consented
    now = datetime.datetime(2026, 7, 1, 2, 0, tzinfo=datetime.UTC)
    _patch_provider(monkeypatch, '{"messages": []}')

    created = proactive_service._run_planner_if_due(settings, now)

    assert created == 0
    rows = ScheduledMessage.query.filter_by(user_id=user.id, trigger='planner').all()
    assert len(rows) == 1
    assert rows[0].status == 'skipped'


def test_planner_runs_once_per_interval(db, consented, monkeypatch):
    user, ai, settings = consented
    now = datetime.datetime(2026, 7, 1, 2, 0, tzinfo=datetime.UTC)
    provider = _patch_provider(monkeypatch, f'{{"messages": [{{"send_at": "{_future_iso(hours=3)}", "reason": "x"}}]}}')

    first = proactive_service._run_planner_if_due(settings, now)
    second = proactive_service._run_planner_if_due(settings, now)

    assert first == 1
    assert second == 0            # inside PLANNER_MIN_INTERVAL_HOURS -> no-op
    assert provider.calls == 1    # provider only consulted on the first run


def test_planner_not_run_when_calendar_experiment_off(db, consented, monkeypatch):
    user, ai, settings = consented
    settings.calendar_experiment = False
    db.session.commit()
    provider_factory = MagicMock()
    monkeypatch.setattr(proactive_service, 'get_provider', provider_factory)

    stats = proactive_service.tick()

    assert stats['planned'] == 0
    provider_factory.assert_not_called()


# --- tick endpoint auth -------------------------------------------------------

def test_tick_endpoint_no_secret_forbidden(client, monkeypatch):
    monkeypatch.delenv('PROACTIVE_TICK_SECRET', raising=False)
    resp = client.post('/tasks/proactive-tick')
    assert resp.status_code == 403


def test_tick_endpoint_wrong_secret_forbidden(client, monkeypatch):
    monkeypatch.setenv('PROACTIVE_TICK_SECRET', 'topsecret')
    resp = client.post('/tasks/proactive-tick', headers={'X-Tick-Secret': 'wrong'})
    assert resp.status_code == 403


def test_tick_endpoint_correct_secret_ok(client, monkeypatch):
    monkeypatch.setenv('PROACTIVE_TICK_SECRET', 'topsecret')
    resp = client.post('/tasks/proactive-tick', headers={'X-Tick-Secret': 'topsecret'})
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {'materialized', 'planned', 'sent', 'skipped', 'suppressed'}
