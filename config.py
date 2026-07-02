import os

"""App configuration.

Select a config with the APP_ENV environment variable ("development",
"testing", or "production") via select_config(). Development is the default
since the app is not currently deployed; production must be opted into
explicitly and fails closed if required secrets are missing.
"""

basedir = os.path.abspath(os.path.dirname(__file__))


# ---- Product constants (single source of truth) ----
# Credits: one credit = one message (MESSAGE_COST). Free users get
# FREE_CREDITS_DEFAULT on signup and at each monthly reset (matches the
# pricing page's "900 messages/month"). Premium grants are effectively
# unlimited pending a real metering policy.
MESSAGE_COST = 1
FREE_CREDITS_DEFAULT = 900
PREMIUM_CREDITS_GRANT = 10000

# Memory: summarize short-term conversation into long-term memory every
# N message pairs. (Historic defaults disagreed: 6 vs 256 — 6 is the
# intended cadence; 256 would effectively disable memory.)
MEMORY_CHUNK_SIZE_DEFAULT = 6


class Config:
    SECRET_KEY = os.environ.get('DB_SECRET_KEY')
    PERMANENT_SESSION_LIFETIME = 604800
    TEMPLATE_FOLDER = 'src/templates'
    STATIC_FOLDER = 'src/static'
    LOGIN_URL = '/login'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

    MESSAGE_COST = MESSAGE_COST
    FREE_CREDITS_DEFAULT = FREE_CREDITS_DEFAULT
    PREMIUM_CREDITS_GRANT = PREMIUM_CREDITS_GRANT
    MEMORY_CHUNK_SIZE_DEFAULT = MEMORY_CHUNK_SIZE_DEFAULT


class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'src', 'instance', 'users.db')
    DEBUG = True
    # Dev-only fallback so a bare checkout boots; production fails closed.
    SECRET_KEY = os.environ.get('DB_SECRET_KEY') or 'dev-secret-key-do-not-use-in-prod'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Set lazily by select_config() so importing this module never crashes.
    SQLALCHEMY_DATABASE_URI = None


def select_config(env: str | None = None):
    """Return the config class for APP_ENV (or the given env name).

    Production validates its required secrets here — at selection, not at
    import — and raises with an actionable message if any are missing.
    """
    env = (env or os.environ.get('APP_ENV') or os.environ.get('FLASK_CONFIG') or 'development').lower()

    if env in ('development', 'dev'):
        return DevelopmentConfig
    if env in ('testing', 'test'):
        return TestingConfig
    if env in ('production', 'prod'):
        secret = os.environ.get('DB_SECRET_KEY')
        if not secret:
            raise RuntimeError('DB_SECRET_KEY must be set in production.')
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError('DATABASE_URL must be set in production.')
        # Heroku-style URLs use the deprecated postgres:// scheme.
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        ProductionConfig.SECRET_KEY = secret
        ProductionConfig.SQLALCHEMY_DATABASE_URI = db_url
        return ProductionConfig

    raise RuntimeError(f"Unknown APP_ENV: {env!r} (expected development, testing, or production)")
