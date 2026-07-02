"""User contact-list persistence."""

import logging

from src.extensions import db
from src.models.users import Contacts

logger = logging.getLogger(__name__)


def create_user_contact(user_id, name, email, relationship='', phone='', notes=''):
    """Create a new contact for a user. Returns the Contacts row, or False on error."""
    try:
        new_contact = Contacts(
            name=name, email=email, user_id=user_id,
            relationship=relationship, phone=phone, notes=notes,
        )
        db.session.add(new_contact)
        db.session.commit()
        return new_contact
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error: {e}')
        return False
