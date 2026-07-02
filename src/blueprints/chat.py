"""Chat routes: the chat page and the message lifecycle (send, regenerate,
edit, paginate). All AI work is delegated to conversation_service."""

import datetime
import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from config import MESSAGE_COST
from src.components.voice_handler import VoiceHandler
from src.extensions import db
from src.models.message import Message
from src.models.users import AIModel
from src.services.ai_model_service import get_owned_ai
from src.services.conversation_service import (
    generate_welcome_message,
    run_ai_response,
    update_conversation_history,
)
from src.services.session_service import get_active_ai, initialize_ai_session
from src.services.storage_service import get_s3

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chat')
@login_required
def chat():
    # get active ai model
    ai_model = get_active_ai(current_user)
    if not ai_model:
        flash('No AI assistant found. Please select or create an AI.', 'error')
        return redirect(url_for('ai.onboarding_ai'))

    # set ai session variables
    initialize_ai_session(ai_model)

    # Get chat messages
    messages = Message.query.filter_by(
        user_id=current_user.id,
        ai_id=ai_model.id,
    ).order_by(Message.timestamp.desc()).limit(
        session.get('context_length', 10)
    ).all()[::-1]

    # if no chat history, generate welcome message
    if not messages:
        welcome_message = generate_welcome_message(ai_model, current_user)
        message_obj = Message(user_id=current_user.id, ai_id=ai_model.id, sender='assistant', message=welcome_message)
        db.session.add(message_obj)
        db.session.commit()
        messages = [message_obj]

    logger.debug(session)

    return render_template('chat.html', ai_model=ai_model, messages=messages)


@chat_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get('message')
        ai_model_id = data.get('modelId')
        if not user_message or ai_model_id is None:
            return jsonify({'error': 'Missing required fields', 'code': 'BAD_REQUEST'}), 400
        ai_model_id = int(ai_model_id)

        # Check if user has enough credits
        if current_user.free_credits + current_user.paid_credits < MESSAGE_COST:
            return jsonify({'error': 'Insufficient credits', 'code': 'INSUFFICIENT_CREDITS'}), 402

        # AI model must exist and belong to the user
        ai_model = get_owned_ai(current_user, ai_model_id)
        if not ai_model:
            return jsonify({'error': 'AI model not found', 'code': 'MODEL_NOT_FOUND'}), 404

        # add user message to the database
        update_conversation_history(current_user.id, ai_model.id, sender='user', message=user_message)

        # Get AI response
        ai_response = run_ai_response(ai_model.id, user_message)
        if not ai_response:
            raise RuntimeError('Failed to generate AI response')

        # generate voice message if enabled
        voice_url = None
        if ai_model.settings.voice_enabled:
            voice_handler = VoiceHandler(get_s3())
            voice_url = voice_handler.generate_voice(
                ai_response,
                ai_model.settings.voice_id or 'alloy',
                ai_model.settings.voice_model or 'tts-1',
            )

        # add ai message to the database
        ai_message_id = update_conversation_history(
            current_user.id, ai_model.id, sender='assistant', message=ai_response, voice_url=voice_url)

        # Deduct credits from user
        current_user.use_credits(MESSAGE_COST)
        db.session.commit()

        return jsonify({
            'response': ai_response,
            'voice_url': voice_url,
            'timestamp': datetime.datetime.now().isoformat(),
            'ai_message_id': ai_message_id,
        }), 200

    except Exception:
        db.session.rollback()
        logger.exception('Error in send_message')
        return jsonify({'error': 'An unexpected error occurred', 'code': 'SERVER_ERROR'}), 500


@chat_bp.route('/regenerate_message', methods=['POST'])
@login_required
def regenerate_message():
    """Re-run message generation with conversation history again."""
    try:
        # parse arguments
        data = request.json
        message_id = data.get('ai_message_id')
        user_message = data.get('user_message')
        ai_model_id = int(data.get('modelId'))

        logger.info(f'Regenerating message with ID: {message_id}')
        logger.info(f'User message: {user_message}')
        logger.info(f'AI model ID: {ai_model_id}')

        # Validation

        # User has enough credits to regenerate message
        if current_user.free_credits + current_user.paid_credits < MESSAGE_COST:
            return jsonify({'error': 'Insufficient credits', 'code': 'INSUFFICIENT_CREDITS'}), 402

        # Selected ai model is valid and belongs to user
        ai_model = AIModel.query.get_or_404(ai_model_id)
        if ai_model not in current_user.ai_models:
            return jsonify({'error': 'Access denied', 'code': 'ACCESS_DENIED'}), 403

        # Selected message is valid and belongs to this user/conversation
        message = Message.query.get_or_404(message_id)
        if message.sender != 'assistant' or message.user_id != current_user.id or message.ai_id != ai_model_id:
            return jsonify({'error': 'Invalid message ID'}), 400

        # Delete the regenerated message and everything after it. Selection is
        # by id (monotonic), ordered — timestamps can collide within a second
        # and previously deleted the preceding user message too.
        subsequent_messages = Message.query.filter(
            Message.user_id == current_user.id,
            Message.ai_id == ai_model_id,
            Message.id >= message.id,
        ).order_by(Message.id).all()

        deleted_ids = [msg.id for msg in subsequent_messages]
        for msg in subsequent_messages:
            db.session.delete(msg)

        # Generate new message
        if user_message == 'None':
            ai_response = generate_welcome_message(ai_model, current_user)
        else:
            ai_response = run_ai_response(ai_model_id, user_message)

        if not ai_response:
            raise Exception('Failed to generate AI response')

        new_ai_message = Message(
            user_id=current_user.id,
            ai_id=ai_model_id,
            sender='assistant',
            message=ai_response,
        )
        db.session.add(new_ai_message)
        db.session.flush()
        ai_message_id = new_ai_message.id

        current_user.use_credits(MESSAGE_COST)

        db.session.commit()

        return jsonify({
            'response': ai_response,
            'timestamp': datetime.datetime.now().isoformat(),
            'ai_message_id': ai_message_id,
            'deleted_ids': deleted_ids[1:],
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error in regenerating message: {str(e)}')
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/edit_message', methods=['PUT'])
@login_required
def edit_message():
    try:
        data = request.json
        message_id = data.get('message_id')
        new_content = data.get('new_content')

        # validate input
        if not message_id or not new_content:
            return jsonify({'error': 'Missing required fields', 'code': 'BAD_REQUEST'}), 400

        # get the message
        message = Message.query.get_or_404(message_id)

        # check msg belongs to user
        if message.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized access', 'code': 'UNAUTHORIZED'}), 403

        # verify user message
        if message.sender != 'user':
            return jsonify({'error': 'Can only edit user messages', 'code': 'BAD_REQUEST'}), 400

        # update the message
        message.message = new_content
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Message updated successfully',
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error editing message: {str(e)}')
        return jsonify({'error': 'An unexpected error occurred', 'code': 'SERVER_ERROR'}), 500


@chat_bp.route('/load-more-messages', methods=['POST'])
@login_required
def load_more_messages():
    # get the number of messages already loaded
    current_message_count = request.json.get('current_message_count', 10)
    ai_id = session.get('ai_id')

    # get the next set of messages
    messages = Message.query.filter_by(user_id=current_user.id, ai_id=ai_id).order_by(
        Message.timestamp.desc()).offset(current_message_count).limit(10).all()[::-1]
    # Format messages to be sent back
    formatted_messages = [
        {'sender': msg.sender, 'message': msg.message, 'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
        for msg in messages
    ]
    logger.info(formatted_messages)
    return jsonify(formatted_messages)
