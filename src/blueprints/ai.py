"""AI-model routes: settings, switching, deletion, and the AI-onboarding flow
(pick a template / create a new one)."""

import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.models.message import Message
from src.models.users import AIModel, AISettings
from src.services.ai_model_service import create_ai_model, get_ai_model, get_owned_ai
from src.services.session_service import initialize_ai_session
from src.services.storage_service import (
    allowed_file,
    delete_profile_image,
    delete_voice_files,
    save_profile_picture,
)
from src.utils.forms import form_get

logger = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/ai-settings/<int:ai_id>', methods=['GET', 'POST'])
@login_required
def ai_settings(ai_id: int):
    if request.method == 'POST':
        # retrieve form data
        profile_image = request.files.get('profile-image')
        ai_name = form_get('ai-name')
        ai_model_name = form_get('ai-model')
        ai_prompt = form_get('ai-prompt')
        ai_description = form_get('ai-description')
        ai_memory_chunk_size = form_get('memory-chunk-size')
        ai_conversation_mode = form_get('conversation-mode')
        voice_enabled = 'voice-enabled' in request.form
        voice_id = form_get('voice-id')
        voice_model = form_get('voice-model')

        # form validation
        if not ai_name or not ai_model_name or not ai_prompt or not ai_description or not ai_memory_chunk_size:
            flash('Please fill out all fields.', 'error')
            return redirect(url_for('ai.ai_settings', ai_id=ai_id))

        # validation: model must exist and belong to the current user
        ai_model = get_owned_ai(current_user, ai_id)
        if not ai_model:
            flash('AI model not found.', 'error')
            return redirect(url_for('profile.profile'))

        # change ai profile picture (if valid)
        if profile_image and allowed_file(profile_image.filename):
            save_profile_picture(profile_image, ai_model, 'ai')

        # change ai model fields
        ai_model.name = ai_name
        ai_model.model_name = ai_model_name
        ai_model.prompt = ai_prompt
        ai_model.description = ai_description

        # change ai settings fields
        ai_settings = ai_model.settings
        ai_settings.memory_chunk_size = int(ai_memory_chunk_size)
        ai_settings.conversation_mode = ai_conversation_mode
        ai_settings.voice_enabled = voice_enabled
        ai_settings.voice_id = voice_id
        ai_settings.voice_model = voice_model

        # Commit changes to the database
        try:
            db.session.add(ai_model)
            db.session.add(ai_settings)
            db.session.commit()
            logger.info('AI model and settings updated successfully.')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error updating AI model: {e}')
            flash('Error updating AI model and settings.', 'error')
            return redirect(url_for('ai.ai_settings', ai_id=ai_id))

        flash('AI model and settings updated successfully.', 'success')

        # update session variables
        initialize_ai_session(ai_model=ai_model, updated=True)

        return redirect(url_for('ai.ai_settings', ai_id=ai_id))
    # display ai settings for ai belonging to user
    else:
        # model must exist and belong to the current user
        ai_model = get_owned_ai(current_user, ai_id)
        if not ai_model:
            flash('AI model not found or does not belong to user', 'error')
            return redirect(url_for('profile.profile'))

        # find associated ai settings, otherwise create it
        if not ai_model.settings:
            ai_settings = AISettings(ai_model_id=ai_id)
            ai_model.settings = ai_settings
            db.session.add(ai_settings)
            db.session.commit()

        # otherwise, display settings
        return render_template('ai_settings.html', ai_model=ai_model, ai_settings=ai_model.settings)


@ai_bp.route('/change-ai/<int:ai_id>')
@login_required
def change_ai(ai_id):
    # validation - does user have access
    if not get_owned_ai(current_user, ai_id):
        flash('You do not have access to this AI model!', 'error')
        return redirect(url_for('chat.chat'))

    # Set last active_ai_id in user settings
    current_user.settings.last_active_ai_id = ai_id
    db.session.add(current_user.settings)
    db.session.commit()

    # set the session
    session['last_active_ai_id'] = ai_id
    return redirect(url_for('chat.chat'))


@ai_bp.route('/profile/delete-ai/<int:ai_id>', methods=['DELETE'])
@login_required
def delete_ai(ai_id):
    try:
        # get the ai model
        ai_model = AIModel.query.get_or_404(ai_id)

        # Check if the AI model is associated with the current user
        if ai_model not in current_user.ai_models:
            return jsonify({'error': 'AI not found'}), 404

        # Delete AI profile image from S3 if it exists
        if ai_model.profile_image_url:
            try:
                delete_profile_image(ai_model.profile_image_url)
            except Exception as e:
                logger.error(f'Error deleting AI profile image from S3: {e}')
                raise e

        # Get all associated messages and their voice files
        messages = Message.query.filter_by(ai_id=ai_id, user_id=current_user.id).all()

        # Batch delete voice files from S3 if any exist
        try:
            delete_voice_files(messages)
        except Exception as e:
            logger.error(f'Error batch deleting voice files from S3: {e}')
            raise e

        # Delete the messages from the database
        for message in messages:
            db.session.delete(message)

        # Remove association with current user
        current_user.remove_ai_model(ai_model)

        # Delete AI settings
        ai_settings = AISettings.query.filter_by(ai_model_id=ai_model.id).first()
        if ai_settings:
            db.session.delete(ai_settings)

        # Delete the AI model itself
        db.session.delete(ai_model)

        # Update user's last active AI
        if current_user.ai_models:
            current_user.settings.last_active_ai_id = current_user.ai_models[0].id
        else:
            current_user.settings.last_active_ai_id = None

        session['last_active_ai_id'] = current_user.settings.last_active_ai_id

        # Commit all database changes
        db.session.commit()

        return jsonify({'success': True}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting AI model: {e}')
        return jsonify({'error': 'An unexpected error occurred'}), 500


@ai_bp.route('/onboarding/ai', methods=['GET'])
@login_required
def onboarding_ai():
    return render_template('onboarding-ai.html')


@ai_bp.route('/onboarding/ai/existing', methods=['GET', 'POST'])
@login_required
def onboarding_ai_existing():
    """Select an existing (template) AI, cloning a copy for the user.

    Templates are stored at specific id values; only prebuilt templates may be
    cloned — never another user's private AI (is_template gate, Phase-1 fix).
    """
    if request.method == 'POST':
        ai_id = request.form.get('ai-id')

        logger.debug(f'Onboarding/ai/existing: {ai_id}')

        # form validation
        if not ai_id:
            flash('Please select an AI model.', 'error')
            return redirect(url_for('ai.onboarding_ai_existing'))

        ai_model = get_ai_model(ai_id=ai_id)
        # only prebuilt templates may be cloned — never another user's AI
        if not ai_model or not ai_model.is_template:
            flash('AI model not found.', 'error')
            return redirect(url_for('ai.onboarding_ai_existing'))

        # Create a copy of the selected AI model
        new_ai_model = create_ai_model(
            ai_model.name, ai_model.model_name, ai_model.prompt, ai_model.description,
            ai_model.settings.memory_chunk_size, ai_model.profile_image_url,
        )

        # set user-ai relationship
        current_user.assign_ai_model(new_ai_model)
        new_ai_model.assign_user(current_user)

        db.session.add(new_ai_model)
        db.session.commit()

        # redirect to chat
        flash('Welcome to pocketAI', 'success')
        return redirect('/chat')

    return render_template('onboarding-ai-existing.html')


@ai_bp.route('/onboarding/ai/create', methods=['GET', 'POST'])
@login_required
def onboarding_ai_create():
    if request.method == 'POST':
        try:
            # get form data
            profile_image = request.files.get('profile-image')
            ai_name = form_get('ai-name')
            ai_model_name = form_get('ai-model')
            ai_prompt = form_get('ai-prompt')
            ai_description = form_get('ai-description')
            memory_chunk_size = form_get('memory-chunk-size')
            conversation_mode = form_get('conversation-mode')
            voice_enabled = 'voice-enabled' in request.form
            voice_id = form_get('voice-id')
            voice_model = form_get('voice-model')

            # form validation
            if not ai_name or not ai_model_name or not ai_prompt or not ai_description or not memory_chunk_size:
                flash('Please fill out all fields.', 'error')
                return redirect(url_for('ai.onboarding_ai_create'))

            # create new AI model and settings
            ai_model = create_ai_model(ai_name, ai_model_name, ai_prompt, ai_description, memory_chunk_size)

            # set profile image
            if profile_image and allowed_file(profile_image.filename):
                save_profile_picture(profile_image, ai_model, 'ai')

            # change ai settings fields
            ai_settings = ai_model.settings
            ai_settings.memory_chunk_size = int(memory_chunk_size) or 6
            ai_settings.conversation_mode = conversation_mode or 'conversation'
            ai_settings.voice_enabled = voice_enabled or False
            ai_settings.voice_id = voice_id or 'alloy'
            ai_settings.voice_model = voice_model or 'tts-1'

            # set user and ai relationship
            current_user.assign_ai_model(ai_model)
            ai_model.assign_user(current_user)

            # commit changes
            db.session.add(ai_model)
            db.session.commit()

            # redirect to chat
            flash('Welcome to pocketAI', 'success')
            return redirect('/chat')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error creating new AI model: {e}')
            flash('Error creating new AI model.', 'error')
            return redirect(url_for('ai.onboarding_ai_create'))

    return render_template('onboarding-ai-create.html')
