"""The chat turn: orchestrating an AI response.

Phase-3 shape: one hand-rolled agent loop (src/ai/agent.py) on the persona
model with native tool use — the legacy context-analyzer router and its
4–5 sequential LLM hops are gone. Short-term memory lives in the database
(ConversationState), not the session cookie, and long-term memory
consolidation runs on the background executor after the reply is returned.
"""

import datetime
import logging

import pytz
from flask import current_app, session
from flask_login import current_user

from src.ai import agent, memory
from src.ai.background import submit as submit_background
from src.extensions import db
from src.models.conversation_state import ConversationState
from src.models.message import Message
from src.models.users import AIModel
from src.services import relationship_service

logger = logging.getLogger(__name__)


def run_ai_response(ai_id, user_message, record_interaction=True):
    """Run a user message (with conversation history) through the selected AI
    model and return the response string. Ownership of ai_id is checked by
    the calling route. Pass record_interaction=False for regenerations so
    retries don't inflate relationship streak/interaction counts."""
    ai_model = AIModel.query.get(ai_id)
    if ai_model is None:
        raise ValueError(f'AI model {ai_id} not found')
    settings = ai_model.settings

    context_length = session.get('context_length', 10)
    user_timezone = session.get('user_timezone', 'UTC')
    memory_chunk_size = (settings.memory_chunk_size if settings else None) or 6
    conversation_mode = (settings.conversation_mode if settings else None) or 'conversation'

    # conversation history (most recent N, oldest first), neutral format
    rows = Message.query.filter_by(user_id=current_user.id, ai_id=ai_id).order_by(
        Message.timestamp.desc()).limit(context_length).all()[::-1]
    history = [{'role': m.sender, 'content': m.message} for m in rows]
    # the request's user_message is authoritative for this turn — replace a
    # trailing user row (it may differ after an edit/regenerate) or append
    if history and history[-1]['role'] == 'user':
        history[-1]['content'] = user_message
    else:
        history.append({'role': 'user', 'content': user_message})

    state = ConversationState.get_or_create(current_user.id, ai_id)

    turn = agent.run_turn(
        model_name=ai_model.model_name,
        persona_prompt=ai_model.prompt,
        ai_name=ai_model.name,
        username=current_user.username,
        conversation_mode=conversation_mode,
        system_info=get_system_info(user_timezone) or '',
        history=history,
        user_id=current_user.id,
        ai_id=ai_id,
        user_timezone=user_timezone,
        extra_context=state.past_context or '',
        relationship_block=relationship_service.context_block(current_user.id, ai_id, current_user.username),
    )

    if record_interaction:
        relationship_service.record_interaction(current_user.id, ai_id)

    # short-term memory cadence (DB-backed; was a session-cookie queue)
    queue = list(state.memory_queue or [])
    queue.append(f'"{current_user.username}": {user_message}, {ai_model.name}: {turn.text}')
    state.memory_queue = queue
    state.memory_queue_count = len(queue)
    # carry this turn's tool/memory context forward for follow-up questions
    state.past_context = turn.tool_context[:2000] if turn.tool_context else ''
    db.session.commit()

    if len(queue) >= memory_chunk_size:
        # Consolidate off the hot path. The queue is NOT cleared here —
        # consolidate_and_save removes exactly the lines it consumed after a
        # successful save (or an intentional gate-drop), so a failed
        # background task never silently loses memories; the next turn
        # simply retries with the queue intact.
        submit_background(
            current_app, memory.consolidate_and_save,
            current_user.id, ai_id, queue, ai_model.name, current_user.username,
        )

    return turn.text


def get_system_info(user_timezone):
    """Return the current date and time, formatted for the given timezone."""
    try:
        timezone = pytz.timezone(user_timezone or 'UTC')
        current_time = datetime.datetime.now(timezone)

        date_str = current_time.strftime('Today is %A, %b %d, %Y.')
        time_str = current_time.strftime('The current time is %I:%M%p.').lower()
        # numeric offset so the model can emit correct RFC3339 tool arguments
        raw_offset = current_time.strftime('%z')
        offset = f'{raw_offset[:3]}:{raw_offset[3:]}' if raw_offset else '+00:00'

        return (f'{date_str} {time_str} User timezone: {user_timezone or "UTC"} '
                f'(current UTC offset: {offset}).')
    except Exception:
        logger.exception('Failed to build system info')
        return None


def update_conversation_history(user_id, ai_id, sender, message, voice_url=None):
    """Add a single message to the database. Returns its id."""
    message = Message(user_id=user_id, ai_id=ai_id, sender=sender, message=message, voice_url=voice_url)
    db.session.add(message)
    db.session.commit()
    return message.id


def generate_welcome_message(ai_model, user):
    """Generate an in-character welcome message. Returns the string, or False on error."""
    try:
        turn = agent.run_turn(
            model_name=ai_model.model_name,
            persona_prompt=ai_model.prompt,
            ai_name=ai_model.name,
            username=user.username,
            conversation_mode=(ai_model.settings.conversation_mode if ai_model.settings else 'conversation'),
            system_info=get_system_info(session.get('user_timezone', 'UTC')) or '',
            history=[{'role': 'user', 'content': 'This is the first time you are chatting with the user. '
                                                 'Generate a welcome message for the user, in character.'}],
            user_id=user.id,
            ai_id=ai_model.id,
        )
        return turn.text
    except Exception:
        logger.exception('Error generating welcome message')
        return False
