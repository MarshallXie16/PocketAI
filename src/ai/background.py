"""Background task execution without a broker.

A small process-local thread pool for work that must not block the chat
turn (TTS generation, memory consolidation). Tasks re-enter the Flask app
context; pass primitives (ids, strings), never request-bound ORM objects —
they detach when the request session closes.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='pocketai-bg')


def submit(app, fn, *args, **kwargs):
    """Run fn(*args, **kwargs) on the pool inside app.app_context()."""
    real_app = app._get_current_object() if hasattr(app, '_get_current_object') else app

    def _task():
        with real_app.app_context():
            try:
                return fn(*args, **kwargs)
            except Exception:
                logger.exception('Background task %s failed', getattr(fn, '__name__', fn))

    return _executor.submit(_task)
