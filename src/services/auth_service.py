"""Authentication and Google OAuth helpers.

Covers local login/session bootstrapping plus the Google OAuth dance: kicking
off the redirect, refreshing access tokens, and creating user rows. OAuth
tokens are stored encrypted at rest (see src/models/google_user.py).
"""

import datetime
import logging
import os

import requests
from flask import current_app, session, url_for
from flask_login import login_user

from src.extensions import db, oauth
from src.models.google_user import GoogleUser
from src.models.users import User, UserSettings
from src.services.session_service import get_active_ai, initialize_ai_session

logger = logging.getLogger(__name__)


# ----- Login helpers -----
def login_user_process(user):
    """Log in a user and set the user + selected-AI session variables."""
    login_user(user)
    initialize_user_session(user)

    active_ai = get_active_ai(user)
    if active_ai:
        initialize_ai_session(active_ai)


def initialize_user_session(user):
    """Create user settings if missing and set the user's session variables."""
    if not user.settings:
        user.settings = UserSettings(user_id=user.id)
        db.session.add(user.settings)
        db.session.commit()

    session.update({
        'user_id': user.id,
        'context_length': user.settings.context_length or 10,
        'user_timezone': user.settings.timezone or 'UTC',
        'last_active_ai_id': user.settings.last_active_ai_id,
    })


# ----- Google OAuth helpers -----
def initiate_google_login(login_type=None):
    """Start the Google OAuth flow; returns a redirect to Google's consent page."""
    nonce = os.urandom(16).hex()
    session['google_auth_nonce'] = nonce
    google = oauth.create_client('google')

    if login_type == 'link':
        return google.authorize_redirect(url_for('auth.authorize_link', _external=True), nonce=nonce)
    return google.authorize_redirect(url_for('auth.authorize', _external=True), nonce=nonce)


def refresh_access_token(google_user):
    """Refresh a Google user's access token via the token endpoint.

    Returns True on success. (The old implementation called a method on the
    module-level ``google`` object, which was permanently None — BUG-11.)
    """
    try:
        resp = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': current_app.config['GOOGLE_CLIENT_ID'],
                'client_secret': current_app.config['GOOGLE_CLIENT_SECRET'],
                'refresh_token': google_user.refresh_token,
                'grant_type': 'refresh_token',
            },
            timeout=10,
        )
        resp.raise_for_status()
        new_token = resp.json()

        google_user.access_token = new_token['access_token']
        google_user.token_expires_at = (
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=new_token['expires_in'])
        )
        db.session.commit()
        return True
    except Exception:
        logger.exception('Failed to refresh google access token')
        return False


def get_google_user(google_id):
    """Return the GoogleUser row for a google_id, or None."""
    return GoogleUser.query.filter_by(google_id=google_id).first()


# ----- Model creation -----
def create_user_model(username, auth_type, password=None, email=None, google_id=None):
    """Create a new user and default settings row. Returns the User."""
    user = User(username=username, auth_type=auth_type, email=email, google_id=google_id)
    if password:
        user.set_password(password)
    db.session.add(user)
    db.session.commit()

    user_settings = UserSettings(user_id=user.id)
    db.session.add(user_settings)
    db.session.commit()

    return user
