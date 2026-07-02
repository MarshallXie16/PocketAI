"""Background task endpoints, hit by external cron (no user session).

POST /tasks/proactive-tick — runs one proactive outreach pass. Authenticated
by a shared secret header (X-Tick-Secret == PROACTIVE_TICK_SECRET); disabled
entirely when the env var is unset. Platform cron should call this every
~15 minutes.
"""

import hmac
import logging
import os

from flask import Blueprint, abort, jsonify, request

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks/proactive-tick', methods=['POST'])
def proactive_tick():
    secret = os.environ.get('PROACTIVE_TICK_SECRET')
    provided = request.headers.get('X-Tick-Secret') or ''
    if not secret or not hmac.compare_digest(provided, secret):
        abort(403)

    from src.services.proactive_service import tick

    stats = tick()
    logger.info('Proactive tick: %s', stats)
    return jsonify(stats)
