"""Shared pytest fixtures for the PocketAI test suite.

The suite runs with ZERO required env vars / API keys: the app is built with
``TestingConfig`` (in-memory SQLite) and every external provider
(openai / stripe / boto3 / pinecone) is mocked at the service boundary inside
individual tests. Nothing here contacts the network.
"""

import os
import sys

import pytest

# --- make the repo root importable ('import src.*') ---------------------------
# pytest prepends the test file's directory (src/tests) to sys.path, not the
# repo root, so 'import src' fails without this. Compute the repo root from this
# file's location (src/tests/conftest.py -> repo root is two levels up).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from config import TestingConfig  # noqa: E402
from src.app_factory import create_app  # noqa: E402
from src.extensions import db as _db  # noqa: E402
from src.models.users import AIModel, AISettings, User, UserSettings  # noqa: E402


@pytest.fixture
def app():
    """A fresh app bound to an in-memory DB, one per test (full isolation)."""
    application = create_app(TestingConfig)
    ctx = application.app_context()
    ctx.push()
    _db.create_all()
    try:
        yield application
    finally:
        _db.session.remove()
        _db.drop_all()
        ctx.pop()


@pytest.fixture
def db(app):
    """Expose the SQLAlchemy handle inside an active app context."""
    return _db


@pytest.fixture
def client(app):
    """Flask test client (persists the session cookie across requests)."""
    return app.test_client()


@pytest.fixture
def make_user(db):
    """Factory: create + persist a User with a password and default settings.

    Extra keyword args (is_admin, plan, free_credits, paid_credits,
    stripe_customer_id, ...) are set as attributes after construction.
    """

    def _make_user(username='user', password='password', email=None, **attrs):
        user = User(username=username, auth_type='default', email=email or f'{username}@example.com')
        user.set_password(password)
        for key, value in attrs.items():
            setattr(user, key, value)
        db.session.add(user)
        db.session.commit()

        if not user.settings:
            settings = UserSettings(user_id=user.id)
            db.session.add(settings)
            db.session.commit()
        return user

    return _make_user


@pytest.fixture
def login(client):
    """Helper: log a created user in via POST /login. Returns the response."""

    def _login(username='user', password='password'):
        return client.post(
            '/login',
            data={'username': username, 'password': password},
            follow_redirects=False,
        )

    return _login


@pytest.fixture
def make_ai(db):
    """Factory: create an AIModel + linked AISettings, optionally owned by a user.

    Pass ``owner=<User>`` to establish the user<->AI relationship (the ownership
    gate every id-taking route checks). Pass ``is_template=True`` for a
    prebuilt roster entry (clonable during onboarding).
    """

    def _make_ai(owner=None, name='TestAI', model_name='gpt-4o', prompt='You are {ai_name}.',
                 description='desc', is_template=False, memory_chunk_size=6, **attrs):
        ai = AIModel(name=name, model_name=model_name, prompt=prompt, description=description)
        ai.is_template = is_template
        for key, value in attrs.items():
            setattr(ai, key, value)
        db.session.add(ai)
        db.session.commit()

        settings = AISettings(ai_model_id=ai.id, memory_chunk_size=memory_chunk_size)
        db.session.add(settings)
        db.session.commit()

        if owner is not None:
            owner.assign_ai_model(ai)
            ai.assign_user(owner)
            db.session.commit()
        return ai

    return _make_ai
