"""User profile routes: settings page, (deprecated) image upload, and the
user-onboarding step."""

import logging
import os

import pytz
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
)
from flask_login import current_user, login_required

from src.extensions import db
from src.models.users import User
from src.services.storage_service import allowed_file, save_profile_picture
from src.services.user_service import update_user_settings
from src.utils.forms import form_get

logger = logging.getLogger(__name__)

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # get form data
        username = form_get('username')
        password = form_get('password')
        timezone = form_get('timezone')
        context_length = form_get('context-length')
        profile_image = request.files.get('profile-image')

        # save profile picture
        if profile_image and allowed_file(profile_image.filename):
            save_profile_picture(profile_image, current_user, 'user')

        # update username
        user = User.query.filter(User.username == username).first()
        if user and username != current_user.username:
            # TODO: display errors for flash messages
            flash('Username already exists.', 'error')
            return redirect('/profile')
        current_user.username = username
        db.session.commit()

        # TODO: password change validation
        if password != '*****':
            User.set_password(current_user, password)

        # update timezone and context length
        update_user_settings(current_user, timezone, context_length)

        flash('Profile updated!', 'success')
        return redirect('/profile')
    else:
        # retrieve info for all ai models owned by user
        return render_template('profile.html', user_settings=current_user.settings, available_ais=current_user.ai_models)


# (DEPRECATED) uploads profile image
@profile_bp.route('/upload-profile-image', methods=['POST'])
@login_required
def upload_profile_image():
    if 'profile-image' in request.files:
        file = request.files['profile-image']
        filepath = os.path.join(
            current_app.root_path, 'src/static/images/profile_pictures', 'user_profile_image',
            current_user.id,
        )
        file.save(filepath)
        return redirect('/profile')


@profile_bp.route('/onboarding/user', methods=['GET', 'POST'])
@login_required
def onboarding_user():
    # TODO: currently redundant with profile page
    if request.method == 'POST':
        # grab user settings info from form
        profile_image = request.files.get('profile-image')
        username = form_get('username')
        user_timezone = form_get('timezone')
        context_length = form_get('messages')

        # form validation
        if not username or not user_timezone or not context_length:
            flash('Please fill out all fields.', 'error')
            return redirect('/onboarding/user')

        # additional input validation
        if not pytz.timezone(user_timezone):
            flash('Invalid timezone.', 'error')
            return redirect('/onboarding/user')

        # save profile picture
        if profile_image and allowed_file(profile_image.filename):
            save_profile_picture(profile_image, current_user, 'user')

        # set new username
        user = User.query.filter(User.username == username).first()
        if user and username != current_user.username:
            flash('Username already exists.', 'error')
            return redirect('/onboarding/user')
        current_user.username = username

        # create user settings if does not exist and update user settings
        update_user_settings(current_user, user_timezone, context_length)

        flash('User settings updated!', 'success')
        return redirect('/onboarding/ai')

    return render_template('onboarding-user.html')
