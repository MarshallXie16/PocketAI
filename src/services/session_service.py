"""Per-session AI state.

Which AI a user is currently talking to, and the session variables the chat
turn reads (memory queue, chunk size, conversation mode). Short-term memory
still lives in the Flask session cookie here — Phase 3 moves it into the DB.
"""

import logging

from flask import session

from src.services.ai_model_service import get_ai_model

logger = logging.getLogger(__name__)


def initialize_ai_session(ai_model, updated=False):
    """Initialize session variables for an AI model.

    Only updates if the AI changed or the session isn't initialized (or if the
    AI settings were just changed, via ``updated=True``).
    """
    if session.get('ai_id') != ai_model.id or updated:
        session.update({
            'ai_name': ai_model.name,
            'ai_id': ai_model.id,
            'memory_chunk_size': ai_model.settings.memory_chunk_size or 6,
            'memory_queue_count': 0,
            'memory_queue': [],
            'conversation_mode': ai_model.settings.conversation_mode or 'conversation',
        })


def get_active_ai(user):
    """Return the currently-selected AI model for a user (or None)."""
    try:
        if user.settings.last_active_ai_id:
            last_active_ai_model = get_ai_model(ai_id=user.settings.last_active_ai_id)
            return last_active_ai_model if last_active_ai_model else user.ai_models[0]
        # return the first one if no active ai model; if no models, return None
        return user.ai_models[0] if user.ai_models else None
    except Exception as e:
        logger.error(f'Error getting active AI model: {e}')
        return None
