"""Companion settings: proactive schedule, quiet hours, pause, and the
memory trust surface ("what your companion remembers about you").

Memory here is deliberately user-sovereign: everything is listed, editable
where sensible, and forgettable — instantly and permanently.
"""

import datetime
import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.models.conversation_state import ConversationState
from src.models.memory_entry import MemoryEntry
from src.models.relationship import KeyFact, RelationshipState
from src.services.session_service import get_active_ai
from src.utils.forms import form_get

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)

# design chips → messages/day cap
FREQUENCY_MAP = {'low': 1, 'med': 2, 'high': 4}


def _days_together(user_id, ai_id):
    state = RelationshipState.query.filter_by(user_id=user_id, ai_id=ai_id).first()
    if state is None or state.first_met_at is None:
        return 0
    return max((datetime.datetime.now(datetime.UTC).date() - state.first_met_at.date()).days, 0)


def _parse_time(value):
    """'HH:MM' → datetime.time, or None for empty/'none'."""
    value = (value or '').strip().lower()
    if not value or value == 'none':
        return None
    return datetime.datetime.strptime(value, '%H:%M').time()


@settings_bp.route('/settings', methods=['GET'])
@login_required
def settings_page():
    ai_model = get_active_ai(current_user)
    user_settings = current_user.settings
    memories, facts, days = [], [], 0
    if ai_model:
        memories = (MemoryEntry.query.filter_by(user_id=current_user.id, ai_id=ai_model.id)
                    .order_by(MemoryEntry.created_at.desc()).limit(100).all())
        facts = (KeyFact.query.filter_by(user_id=current_user.id, ai_id=ai_model.id)
                 .order_by(KeyFact.created_at.desc()).limit(100).all())
        days = _days_together(current_user.id, ai_model.id)
    return render_template('settings.html', ai_model=ai_model, user_settings=user_settings,
                           memories=memories, facts=facts, days_together=days,
                           google_linked=bool(current_user.google_id))


@settings_bp.route('/settings/proactive', methods=['POST'])
@login_required
def update_proactive():
    settings = current_user.settings
    try:
        settings.daily_checkin_time = _parse_time(form_get('daily_checkin_time'))
        settings.quiet_hours_start = _parse_time(form_get('quiet_start'))
        settings.quiet_hours_end = _parse_time(form_get('quiet_end'))
    except ValueError:
        flash('Invalid time format.', 'error')
        return redirect(url_for('settings.settings_page'))

    frequency = form_get('frequency')
    if frequency in FREQUENCY_MAP:
        settings.max_proactive_per_day = FREQUENCY_MAP[frequency]

    settings.paused = form_get('paused') == 'on'

    consent = form_get('proactive_enabled')
    if consent == 'on' and settings.proactive_consent_at is None:
        settings.proactive_consent_at = datetime.datetime.now(datetime.UTC)
        if current_user.google_id:
            settings.calendar_experiment = True
    elif consent == 'off':
        settings.proactive_consent_at = None
        settings.calendar_experiment = False

    db.session.commit()
    flash('Saved.', 'success')
    return redirect(url_for('settings.settings_page'))


@settings_bp.route('/settings/memory', methods=['POST'])
@login_required
def add_memory():
    """'Add something your companion should know' — a user-authored fact."""
    ai_model = get_active_ai(current_user)
    content = ' '.join(form_get('content').split())[:300]
    if not ai_model or not content:
        return jsonify({'error': 'Nothing to add'}), 400
    fact = KeyFact(user_id=current_user.id, ai_id=ai_model.id, fact_type='preference',
                   content=content, source='user')
    db.session.add(fact)
    db.session.commit()
    return jsonify({'success': True, 'id': fact.id, 'content': fact.content}), 200


@settings_bp.route('/settings/fact/<int:fact_id>', methods=['PUT', 'DELETE'])
@login_required
def modify_fact(fact_id):
    # scoped to the ACTIVE companion — the page presents "this companion's"
    # memory, so ids from another of the user's companions are rejected too
    ai_model = get_active_ai(current_user)
    fact = KeyFact.query.get_or_404(fact_id)
    if fact.user_id != current_user.id or not ai_model or fact.ai_id != ai_model.id:
        return jsonify({'error': 'Not found'}), 404
    if request.method == 'DELETE':
        db.session.delete(fact)
        db.session.commit()
        return jsonify({'success': True}), 200
    content = ' '.join(form_get('content').split())[:300]
    if not content:
        return jsonify({'error': 'Content required'}), 400
    fact.content = content
    db.session.commit()
    return jsonify({'success': True, 'content': fact.content}), 200


@settings_bp.route('/settings/memory/<int:memory_id>', methods=['DELETE'])
@login_required
def forget_memory(memory_id):
    ai_model = get_active_ai(current_user)
    entry = MemoryEntry.query.get_or_404(memory_id)
    if entry.user_id != current_user.id or not ai_model or entry.ai_id != ai_model.id:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'success': True}), 200


@settings_bp.route('/settings/memory/forget-all', methods=['POST'])
@login_required
def forget_everything():
    """Instant and permanent, exactly as the settings page promises."""
    ai_model = get_active_ai(current_user)
    if not ai_model:
        return jsonify({'error': 'No active companion'}), 400
    MemoryEntry.query.filter_by(user_id=current_user.id, ai_id=ai_model.id).delete()
    KeyFact.query.filter_by(user_id=current_user.id, ai_id=ai_model.id).delete()
    state = ConversationState.query.filter_by(user_id=current_user.id, ai_id=ai_model.id).first()
    if state:
        state.memory_queue = []
        state.memory_queue_count = 0
        state.past_context = ''
    db.session.commit()
    logger.info('User %s forgot all memory for ai %s', current_user.id, ai_model.id)
    return jsonify({'success': True}), 200
