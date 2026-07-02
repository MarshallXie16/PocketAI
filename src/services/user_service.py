"""User settings persistence."""

import logging

from src.extensions import db
from src.models.users import UserSettings

logger = logging.getLogger(__name__)


def update_user_settings(user, user_timezone, context_length, last_active_ai_id=None):
    """Update a user's settings, creating the row if it doesn't exist."""
    if not user.settings:
        user_settings = UserSettings(user_id=user.id, timezone=user_timezone, context_length=context_length)
        db.session.add(user_settings)
    else:
        user.settings.timezone = user_timezone
        user.settings.context_length = context_length
        user.settings.last_active_ai_id = last_active_ai_id if last_active_ai_id else user.settings.last_active_ai_id
    db.session.commit()
    logger.info(f'User settings for user {user.id} has been updated.')
    logger.info(f'Timezone: {user.settings.timezone}')
    logger.info(f'Context length: {user.settings.context_length}')
