"""Application factory.

``create_app`` builds and configures the Flask app: it selects a config,
wires the shared extensions (SQLAlchemy, Migrate, Flask-Login, Authlib OAuth),
registers the Google OAuth client and the user loader, and mounts every
blueprint. Nothing here runs at import time — the app is created only when a
caller (``wsgi.py`` or the test fixtures) calls ``create_app``.
"""

import logging
import os

import stripe
from flask import Flask

from config import select_config
from src.extensions import db, login_manager, migrate, oauth
from src.models.users import User

logger = logging.getLogger(__name__)

# Project root — app_factory.py lives in src/, but templates/static are addressed
# relative to the repo root ('src/templates', 'src/static'), exactly as they were
# when app.py sat at the root. Pinning root_path keeps those paths (and
# current_app.root_path) resolving identically.
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def create_app(config_class=None):
    """Create the Flask app.

    Config is selected from APP_ENV unless a config class is passed explicitly
    (used by tests).
    """
    config_class = config_class or select_config()
    app = Flask(
        __name__,
        root_path=BASE_DIR,
        template_folder=config_class.TEMPLATE_FOLDER,
        static_folder=config_class.STATIC_FOLDER,
    )
    app.config.from_object(config_class)

    # third-party API config (after config load, unlike the old import-time reads)
    stripe.api_key = os.environ.get('STRIPE_API_KEY')
    app.config['S3_BUCKET_NAME'] = os.environ.get('S3_BUCKET_NAME')
    app.config['S3_KEY'] = os.environ.get('S3_KEY')
    app.config['S3_SECRET'] = os.environ.get('S3_SECRET')
    app.config['S3_LOCATION'] = os.environ.get('S3_LOCATION')

    # initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    _register_oauth(app)
    _register_blueprints(app)

    if not app.debug:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    return app


def _register_oauth(app):
    """Register the Google OAuth client on the shared OAuth extension.

    Use ``oauth.create_client('google')`` to get the client — the old
    module-level ``google`` global was permanently None for importers (BUG-11).
    Idempotent so repeated ``create_app`` calls (tests) don't double-register.
    """
    oauth.init_app(app)
    if oauth._registry.get('google') is None:
        oauth.register(
            name='google',
            client_id=app.config['GOOGLE_CLIENT_ID'],
            client_secret=app.config['GOOGLE_CLIENT_SECRET'],
            server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
            client_kwargs={
                'scope': 'openid email profile '
                         'https://www.googleapis.com/auth/gmail.modify '
                         'https://www.googleapis.com/auth/calendar'
            },
        )


def _register_blueprints(app):
    """Mount every blueprint. Route PATHS are unchanged from the monolith."""
    from src.blueprints.admin import admin_bp
    from src.blueprints.ai import ai_bp
    from src.blueprints.auth import auth_bp
    from src.blueprints.billing import billing_bp
    from src.blueprints.chat import chat_bp
    from src.blueprints.contacts import contacts_bp
    from src.blueprints.pages import pages_bp
    from src.blueprints.profile import profile_bp

    for bp in (pages_bp, auth_bp, chat_bp, ai_bp, profile_bp, contacts_bp, billing_bp, admin_bp):
        app.register_blueprint(bp)


# Flask-Login user loader — registered on the shared login_manager at import.
@login_manager.user_loader
def load_user(user_id):
    return User.query.filter(User.id == user_id).first()
