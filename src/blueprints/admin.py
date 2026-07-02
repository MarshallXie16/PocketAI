"""Admin routes.

NOTE: the old ``GET /add-credits/<amount>`` route was removed — it let any
logged-in user grant themselves unlimited credits. Credits are granted only by
Stripe fulfillment and admin actions.
"""

import hmac
import os

from flask import Blueprint, abort, request
from flask_login import current_user, login_required

from src.extensions import db
from src.models.users import User

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/reset_credits', methods=['POST'])
@login_required
def reset_credits():
    # requires an admin user AND the admin password (no default; unset = disabled)
    admin_password = os.getenv('ADMIN_PASSWORD')
    password = request.form.get('password') or ''
    if not current_user.is_admin or not admin_password or not hmac.compare_digest(password, admin_password):
        abort(403)

    users = User.query.all()
    for user in users:
        user.reset_free_credits()
    db.session.commit()
    return 'Credits reset successfully', 200
