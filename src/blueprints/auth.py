"""Authentication routes: local login/signup/logout + the Google OAuth flow.

Route paths and behavior are unchanged from the monolith; only the endpoint
names are now namespaced under ``auth.`` (e.g. ``auth.login``).
"""

import datetime
import logging

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy.exc import IntegrityError

from src.extensions import db, oauth
from src.models.google_user import GoogleUser
from src.models.users import User
from src.services.auth_service import (
    create_user_model,
    get_google_user,
    initiate_google_login,
    login_user_process,
    refresh_access_token,
)
from src.utils.forms import form_get

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # User already logged in
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('chat.chat'))

    # login request
    if request.method == 'POST':
        username = form_get('username')
        password = form_get('password')

        # form validation
        if not username or not password:
            flash('Please fill out all fields.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        # user validation
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'error')
            return render_template('login.html')

        # all clear for the user to log in
        login_user_process(user)
        return redirect(url_for('chat.chat'))

    # visiting login page
    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = form_get('username')
        email = form_get('email')
        password = form_get('password')
        confirm_password = form_get('confirm-password')

        # input validation
        if not username or not email or not password or not confirm_password:
            flash('Please fill out all fields.', 'error')
            return render_template('signup.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')

        if User.query.filter((User.username == username)).first():
            flash('Username already exists.', 'error')
            return render_template('signup.html')

        if User.query.filter((User.email == email)).first():
            flash('Email already exists.', 'error')
            return render_template('signup.html')

        # register the user
        try:
            user = create_user_model(username=username, auth_type='default', password=password, email=email)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Username or email already taken', 'error')
            return render_template('signup.html')

        # log user in
        login_user_process(user)

        # redirect to onboarding process
        flash("Account created successfully! Now let's get you started! :)", 'success')
        return redirect(url_for('profile.onboarding_user'))

    return render_template('signup.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect('/')


# ----- Google signup/login -----
@auth_bp.route('/signup/google')
def google_signup():
    return initiate_google_login()


@auth_bp.route('/login/google')
def google_login():
    # if user is logged in
    if current_user.is_authenticated:
        google_user = GoogleUser.query.filter_by(google_id=current_user.google_id).first()

        # user does not have google account
        if not google_user:
            return initiate_google_login()

        # user has google account but access token has expired
        if google_user.token_expires_at <= datetime.datetime.now(datetime.UTC):
            if google_user.refresh_token and refresh_access_token(google_user):
                login_user_process(current_user)
                return redirect('/chat')
            else:
                return initiate_google_login()

        # user has valid access token and google account
        login_user_process(current_user)
        return redirect('/chat')

    # otherwise, initiate google login
    return initiate_google_login()


@auth_bp.route('/authorize')
def authorize():
    """Authorize google login/signup, creating a user account if none exists."""
    google = oauth.create_client('google')
    try:
        # check access token
        token = google.authorize_access_token()
        if not token:
            flash('Access Denied. No access token provided.', 'error')
            return redirect('/login')

        # parse user info from token
        try:
            nonce = session.pop('google_auth_nonce', None)
            user_info = google.parse_id_token(token, nonce=nonce)
            new_user = False
        except Exception:
            flash('Failed to parse user info from Google', 'error')
            return redirect('/login')

        # if user does not exist, create user (new user)
        user = User.query.filter_by(google_id=user_info['sub']).first()
        if not user:
            user = create_user_model(
                username=user_info['given_name'], auth_type='google', password=None,
                email=user_info['email'], google_id=user_info['sub'],
            )
            new_user = True

        # if google user does not exist, create google user (linking google account)
        google_user = get_google_user(google_id=user_info['sub'])
        if not google_user:
            google_user = GoogleUser(google_id=user_info['sub'])
            db.session.add(google_user)

        # update access and refresh tokens
        google_user.access_token = token['access_token']
        google_user.refresh_token = token['refresh_token']
        google_user.token_expires_at = (
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=token['expires_in'])
        )

        db.session.commit()

        # Log user in
        login_user_process(user)

        if new_user:
            flash('Google account linked!', 'success')
            return redirect(url_for('profile.onboarding_user'))
        else:
            logger.info('redirecting to chat')
            return redirect('/chat')

    except Exception as e:
        db.session.rollback()
        logger.info(f'Google Login Error: {e}')
        flash('Failed to authenticate google account. :(', 'error')
        return redirect('/login')


@auth_bp.route('/link/google')
@login_required
def link_google():
    """Link a Google account to the current user."""
    # check if user has a linked google account
    if get_google_user(google_id=current_user.google_id):
        flash('Google account already linked.', 'error')
        return redirect(url_for('profile.onboarding_user'))
    else:
        return initiate_google_login(login_type='link')


@auth_bp.route('/authorize/link')
def authorize_link():
    """Links a google account to an existing account."""
    google = oauth.create_client('google')
    try:
        token = google.authorize_access_token()
        if not token:
            flash('Access Denied. No access token provided.', 'error')
            return redirect(url_for('profile.onboarding_user'))

        # parse user info from token
        nonce = session.pop('google_auth_nonce', None)
        user_info = google.parse_id_token(token, nonce=nonce)
        google_id = user_info['sub']

        # Check if this Google account is already linked to another user
        existing_user = User.query.filter_by(google_id=google_id).first()
        if existing_user and existing_user.id != current_user.id:
            flash('This Google account is already linked to another user.', 'error')
            return redirect(url_for('profile.onboarding_user'))

        # create google account and link to current_user
        google_user = get_google_user(google_id=user_info['sub'])
        if not google_user:
            google_user = GoogleUser(google_id=google_id)
            current_user.auth_type = 'google'
            current_user.google_id = google_id
            db.session.add(google_user)

        # update access and refresh tokens
        google_user.access_token = token['access_token']
        google_user.token_expires_at = (
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=token['expires_in'])
        )
        google_user.refresh_token = token['refresh_token']

        try:
            db.session.commit()
            flash('Google account linked!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error linking Google account: {e}')
            flash('Failed to link Google account. Please try again.', 'error')

        return redirect(url_for('profile.onboarding_user'))

    except Exception as e:
        logger.error(f'Error in authorize_link: {e}')
        flash('Failed to link Google account. Please try again.', 'error')
        return redirect(url_for('profile.onboarding_user'))
