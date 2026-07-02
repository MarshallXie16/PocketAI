"""WSGI entry point.

Production/servers import ``app`` from here (``gunicorn wsgi:app``); locally,
run ``flask --app wsgi run`` or ``python wsgi.py`` (dev-only 0.0.0.0:5000
runner below).
"""

import os

from dotenv import load_dotenv

# Load .env before importing the factory: config and components read API keys
# and secrets from the environment.
load_dotenv()

from src.app_factory import create_app  # noqa: E402  (must follow load_dotenv)

app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
