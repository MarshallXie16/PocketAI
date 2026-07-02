import os

from dotenv import load_dotenv

# Load .env before anything else: several components read API keys from the
# environment at import time.
load_dotenv()

import logging
import pytz
import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, current_app, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import stripe
from sqlalchemy.exc import IntegrityError

from src.components.context_analyzer import context_analyzer
from src.components.memory import long_term_memory
# from src.components.speech_to_text import speech_to_text
from src.components.ai_models import AI_model
from src.components.voice_handler import VoiceHandler

from src.models.users import User, AIModel, UserSettings, AISettings, Contacts
from src.models.google_user import GoogleUser
from src.models.message import Message

from config import select_config, MESSAGE_COST, PREMIUM_CREDITS_GRANT
from src.utils.extensions import db, migrate
from src.utils.utils import utilities
from src.utils.auth import oauth, google, init_oauth

import boto3


''' Tech Stack
# AI models: GPT-4o-mini, GPT-4o, Gemini-1.5-Flash, Gemini-1.5-Pro, Claude-3-Haiku, Claude-3.5-Sonnet
# text-to-speech: GoogleTTS, Whisper
# speech-to-text: Google, Microsoft, OpenAI, Elevenlabs
# embeddings: OpenAI
# vector database: Chroma, Pinecone
'''

# global variables
DEFAULT_WELCOME_MSG = "Hello, how can I help you today?"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
YOUR_DOMAIN = os.environ.get('YOUR_DOMAIN')

login_manager = LoginManager()

logger = logging.getLogger(__name__)


# Instantiates and configures app
def create_app(config_class=None):
    """Create the Flask app. Config is selected from APP_ENV unless a
    config class is passed explicitly (used by tests)."""
    config_class = config_class or select_config()
    app = Flask(__name__, template_folder=config_class.TEMPLATE_FOLDER, static_folder=config_class.STATIC_FOLDER)
    app.config.from_object(config_class)

    # third-party API config (after load_dotenv, unlike the old import-time reads)
    stripe.api_key = os.environ.get('STRIPE_API_KEY')
    app.config['S3_BUCKET_NAME'] = os.environ.get('S3_BUCKET_NAME')
    app.config['S3_KEY'] = os.environ.get('S3_KEY')
    app.config['S3_SECRET'] = os.environ.get('S3_SECRET')
    app.config['S3_LOCATION'] = os.environ.get('S3_LOCATION')

    # initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = app.config['LOGIN_URL']

    init_oauth(app)

    if not app.debug:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    return app


app = create_app()

# Lazily-created S3 client (avoids import-time AWS client construction).
_s3_client = None


def get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=app.config['S3_KEY'],
            aws_secret_access_key=app.config['S3_SECRET'],
        )
    return _s3_client

''' page routes '''

# homepage
@app.route('/')
def home():
    return render_template('index.html')


# login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    # User already logged in
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('chat'))

    # login request
    if request.method == 'POST':
        # obtain login info from form
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        
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
        return redirect(url_for('chat'))
            
    # visiting login page
    return render_template('login.html')


# email sign up page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # sign up request
    if request.method == 'POST':
        # extract info from sign-up form
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        confirm_password = request.form.get('confirm-password').strip()

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
            user = create_user_model(username=username, auth_type="default", password=password, email=email)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Username or email already taken', 'error')
            return render_template('signup.html')
            
        # log user in
        login_user_process(user)

        # redirect to onboarding process
        flash('Account created successfully! Now let\'s get you started! :)', 'success')
        return redirect(url_for('onboarding_user'))
    
    return render_template('signup.html')


# chat page
@app.route('/chat')
@login_required
def chat():
    # get active ai model
    ai_model = get_active_ai(current_user)
    if not ai_model:
        flash('No AI assistant found. Please select or create an AI.', 'error')
        return redirect(url_for('onboarding_ai'))
    
    # set ai session variables
    initialize_ai_session(ai_model)

    # Get chat messages
    messages = Message.query.filter_by(
        user_id=current_user.id, 
        ai_id=ai_model.id
    ).order_by(Message.timestamp.desc()).limit(
        session.get('context_length', 10)
    ).all()[::-1]

    # if no chat history, generate welcome message
    if not messages:
        welcome_message = generate_welcome_message(ai_model, current_user)
        message_obj = Message(user_id=current_user.id, ai_id=ai_model.id, sender="assistant", message=welcome_message)
        db.session.add(message_obj)
        db.session.commit()
        messages = [message_obj]
        
    print(session)  # debug

    return render_template('chat.html', ai_model=ai_model, messages=messages)


def get_ai_model(ai_id):
    return AIModel.query.filter_by(id=ai_id).first()

# user settings
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':

        # get form data
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        timezone = request.form.get('timezone').strip()
        context_length = request.form.get('context-length').strip()
        profile_image = request.files.get('profile-image')
        
        # save profile picture
        if profile_image and allowed_file(profile_image.filename):
            save_profile_picture(profile_image, current_user, "user")

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


# pricing page
@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

# privacy policy
@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy.html')

# terms of service
@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms-of-service.html')




''' functionality routes '''

# logs user out
@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')



''' Chat Functionality '''
# sends a text message
@login_required
@app.route('/send_message', methods=['POST'])
def send_message():
# try:
    data = request.json
    user_message = data.get('message')
    ai_model_id = int(data.get('modelId'))

    # Check if user has enough credits
    if current_user.free_credits + current_user.paid_credits < MESSAGE_COST:
        return jsonify({'error': 'Insufficient credits', 'code': 'INSUFFICIENT_CREDITS'}), 402

    # Get the AI model associated with ID; check if it exists
    ai_model = get_ai_model(ai_id=ai_model_id)
    if not ai_model:
        return jsonify({'error': 'AI model does not exist', 'code': 'MODEL_NOT_FOUND'}), 404
    
    # Check if user has access to AI model
    if ai_model not in current_user.ai_models:
        return jsonify({'error': 'You do not have access to this AI model', 'code': 'ACCESS_DENIED'}), 403

    # add user message to the database
    # TODO: return user message id
    update_conversation_history(current_user.id, ai_model.id, sender="user", message=user_message)

    # Get AI response
    ai_response = run_ai_response(ai_model.id, user_message)
    if not ai_response:
        raise Exception("Failed to generate AI response")
    
    # generate voice message if enabled
    voice_url = None
    if ai_model.settings.voice_enabled:
        print(f'Enabled: {ai_model.settings.voice_enabled}')
        print(ai_model.settings.voice_id)
        print(ai_model.settings.voice_model)
        voice_handler = VoiceHandler(get_s3())
        voice_url = voice_handler.generate_voice(
            ai_response,
            ai_model.settings.voice_id or 'alloy',  # default
            ai_model.settings.voice_model or 'tts-1'  # default
        )
        print(voice_url)

    # add ai message to the database
    ai_message_id = update_conversation_history(current_user.id, ai_model.id, sender="assistant", message=ai_response, voice_url=voice_url)

    # Deduct credits from user
    current_user.use_credits(MESSAGE_COST)
    db.session.commit()

    return jsonify({"response": ai_response, 
                    "voice_url": voice_url,
                    "timestamp": datetime.datetime.now().isoformat(), 
                    "ai_message_id": ai_message_id
                    }), 200

    # except Exception as e:
    #     db.session.rollback()
    #     app.logger.error(f"Error in send_message: {str(e)}") # TODO: swap print statements for app logger?
    #     return jsonify({'error': 'An unexpected error occurred', 'code': 'SERVER_ERROR'}), 500


# run through message generation with conversation history again
@app.route('/regenerate_message', methods=['POST'])
@login_required
def regenerate_message():
    try: 
        # parse arguments
        data = request.json
        message_id = data.get('ai_message_id')
        user_message = data.get('user_message')
        ai_model_id = int(data.get('modelId'))
            
        print(f"Regenerating message with ID: {message_id}")
        print(f"User message: {user_message}")
        print(f"AI model ID: {ai_model_id}")
        
        # Validation
        
        # User has enough credits to regenerate message
        if current_user.free_credits + current_user.paid_credits < MESSAGE_COST:
            return jsonify({'error': 'Insufficient credits', 'code': 'INSUFFICIENT_CREDITS'}), 402

        # Selected ai model is valid and belongs to user
        ai_model = AIModel.query.get_or_404(ai_model_id)
        if ai_model not in current_user.ai_models:
            return jsonify({'error': 'Access denied', 'code': 'ACCESS_DENIED'}), 403

        # Selected message is valid
        message = Message.query.get_or_404(message_id)
        if message.sender != 'assistant':
            return jsonify({'error': 'Invalid message ID'}), 400
        
        # Find and delete all later messages in thread
        subsequent_messages = Message.query.filter(
            Message.user_id == current_user.id,
            Message.ai_id == ai_model_id,
            Message.timestamp >= message.timestamp
        ).all()
        
        deleted_ids = [msg.id for msg in subsequent_messages]
        print(deleted_ids[1:])
        for msg in subsequent_messages:
            db.session.delete(msg)

        # Generate new message
        if user_message == 'None':
            ai_response = generate_welcome_message(ai_model, current_user)
        else:
            ai_response = run_ai_response(ai_model_id, user_message)
            
        if not ai_response:
            raise Exception("Failed to generate AI response")

        new_ai_message = Message(user_id=current_user.id, 
                                 ai_id=ai_model_id, 
                                 sender="assistant", 
                                 message=ai_response
                                 )
        db.session.add(new_ai_message)
        db.session.flush()
        ai_message_id = new_ai_message.id

        current_user.use_credits(MESSAGE_COST)
        
        db.session.commit()

        return jsonify({
            "response": ai_response,
            "timestamp": datetime.datetime.now().isoformat(),
            "ai_message_id": ai_message_id,
            "deleted_ids": deleted_ids[1:]
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f'Error in regenerating message: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/edit_message', methods=['PUT'])
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

        # check msg belows to user
        if message.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized access', 'code': 'UNAUTHORIZED'}), 403

        # verify user message
        if message.sender != 'user':
            return jsonify({'error': 'Can only edit user messages', 'code': 'BAD_REQUEST'}), 400

        # update the message
        message.message = new_content
        # message.edited_at = datetime.datetime.now(datetime.UTC)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Message updated successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f'Error editing message: {str(e)}')
        return jsonify({'error': 'An unexpected error occurred', 'code': 'SERVER_ERROR'}), 500

@app.route('/load-more-messages', methods=['POST'])
@login_required
def load_more_messages():
    # get the number of messages already loaded
    current_message_count = request.json.get('current_message_count', 10)
    ai_id = session.get('ai_id')

    # get the next set of messages
    messages = Message.query.filter_by(user_id=current_user.id, ai_id=ai_id).order_by(Message.timestamp.desc()).offset(current_message_count).limit(10).all()[::-1]
    # Format messages to be sent back
    formatted_messages = [{'sender': msg.sender, 'message': msg.message, 'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')} for msg in messages]
    print(formatted_messages)
    return jsonify(formatted_messages)


# (DEPRECATED) uploads profile image
@app.route('/upload-profile-image', methods=['POST'])
@login_required
def upload_profile_image():
    if 'profile-image' in request.files:
        # ???
        file = request.files['profile-image']
        filepath = os.path.join(current_app.root_path, 'src/static/images/profile_pictures', 'user_profile_image',
                                current_user.id)
        file.save(filepath)
        # current_user.profile_image = filepath
        # db.session.commit()
        return redirect('/profile')


@app.route('/ai-settings/<int:ai_id>', methods=['GET', 'POST'])
@login_required
def ai_settings(ai_id: int):
    if request.method == 'POST':
        # retrieve form data
        profile_image = request.files.get('profile-image')
        ai_name = request.form.get('ai-name').strip()
        ai_model_name = request.form.get('ai-model').strip()
        ai_prompt = request.form.get('ai-prompt').strip()
        ai_description = request.form.get('ai-description').strip()
        ai_memory_chunk_size = request.form.get('memory-chunk-size').strip()
        ai_conversation_mode = request.form.get('conversation-mode').strip()
        voice_enabled = 'voice-enabled' in request.form
        voice_id = request.form.get('voice-id').strip()
        voice_model = request.form.get('voice-model').strip()
        
        # form validation
        if not ai_name or not ai_model_name or not ai_prompt or not ai_description or not ai_memory_chunk_size:
            flash('Please fill out all fields.', 'error')
            return redirect(url_for('ai_settings', ai_id=ai_id))
        
        # validation: check if model exists
        ai_model = get_ai_model(ai_id=ai_id)
        if not ai_model:
            flash('AI model not found.', 'error')
            return redirect(url_for('profile'))
        
        # change ai profile picture (if valid)
        if profile_image and allowed_file(profile_image.filename):
            save_profile_picture(profile_image, ai_model, "ai")

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
            print('AI model and settings updated successfully.')
        except Exception as e:
            db.session.rollback()
            print(f'Error updating AI model: {e}')
            flash('Error updating AI model and settings.', 'error')
            return redirect(url_for('ai_settings', ai_id=ai_id))

        flash('AI model and settings updated successfully.', 'success')
        
        # update session variables
        initialize_ai_session(ai_model=ai_model, updated=True)
        
        return redirect(url_for('ai_settings', ai_id=ai_id))
    # display ai settings for ai belonging to user
    else:
        # try to find the ai model
        ai_model = get_ai_model(ai_id=ai_id)
        if not ai_model:
            flash('AI model not found or does not belong to user', 'error')
            return redirect(url_for('profile'))  

        # find associated ai settings, otherwise create it
        if not ai_model.settings:
            ai_settings = AISettings(ai_model_id=ai_id)
            ai_model.settings = ai_settings
            db.session.add(ai_settings)
            db.session.commit()    

        # otherwise, display settings
        return render_template('ai_settings.html', ai_model=ai_model, ai_settings=ai_model.settings)

@app.route('/change-ai/<int:ai_id>')
@login_required
def change_ai(ai_id):
    # validation - does user have access
    if not get_ai_model(ai_id) in current_user.ai_models:
        flash('You do not have access to this AI model!', 'error')
        return render_template('chat.html')
    
    # Set last active_ai_id in user settings
    current_user.settings.last_active_ai_id = ai_id
    db.session.add(current_user.settings)
    db.session.commit()
    
    # set the session
    session['last_active_ai_id'] = ai_id
    return redirect(url_for('chat'))

@app.route('/profile/delete-ai/<int:ai_id>', methods=['DELETE'])
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
                # Extract filename from URL
                profile_url_parts = ai_model.profile_image_url.split('.amazonaws.com/')
                if len(profile_url_parts) > 1:
                    profile_image_key = profile_url_parts[1].split('?')[0]
                    print(f"Deleting profile image: {profile_image_key}")
                    get_s3().delete_object(
                        Bucket=app.config["S3_BUCKET_NAME"],
                        Key=profile_image_key
                    )
            except Exception as e:
                print(f"Error deleting AI profile image from S3: {e}")
                raise e
        
        # Get and delete all associated messages and their voice files
        messages = Message.query.filter_by(ai_id=ai_id, user_id=current_user.id).all()
        voice_files_to_delete = []

        for message in messages:
            # Collect voice URLs for deletion if they exist
            if message.voice_url:
                try:
                    voice_url_parts = message.voice_url.split('.amazonaws.com/')
                    if len(voice_url_parts) > 1:
                        voice_key = voice_url_parts[1].split('?')[0]
                        voice_files_to_delete.append({'Key': voice_key})
                        print(f"Adding voice file to deletion queue: {voice_key}")
                except Exception as e:
                    print(f"Error processing voice URL for message {message.id}: {e}")
                    raise e
            
            # Delete the message from database
            db.session.delete(message)

        # Batch delete voice files from S3 if any exist
        if voice_files_to_delete:
            try:
                get_s3().delete_objects(
                    Bucket=app.config["S3_BUCKET_NAME"],
                    Delete={
                        'Objects': voice_files_to_delete,
                        'Quiet': True
                    }
                )
            except Exception as e:
                print(f"Error batch deleting voice files from S3: {e}")
                raise e

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
        print(f'Error deleting AI model: {e}')
        return jsonify({'error': 'An unexpected error occurred'}), 500  \
            

# (DEPRECATED) displays error page with custom message
@app.route('/error', methods=['GET'])
def error():
    message = request.args.get('message', 'An error has occurred!')
    return render_template('error.html', message=message)


""" Onboarding process """
# Onboarding page
# TODO: currently redundant with profile page
@app.route('/onboarding/user', methods=['GET', 'POST'])
@login_required
def onboarding_user():
    if request.method == 'POST':
        # grab user settings info from form
        profile_image = request.files.get('profile-image')
        username = request.form.get('username').strip()
        user_timezone = request.form.get('timezone').strip()
        context_length = request.form.get('messages').strip()

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
            save_profile_picture(profile_image, current_user, "user")

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


#  Purpose: Update user settings, create if does not exist
def update_user_settings(user, user_timezone, context_length, last_active_ai_id=None):
    # create user settings if does not exist
    if not user.settings:
        user_settings = UserSettings(user_id=user.id, timezone=user_timezone, context_length=context_length)
        db.session.add(user_settings)
    else:
        user.settings.timezone = user_timezone
        user.settings.context_length = context_length
        user.settings.last_active_ai_id = last_active_ai_id if last_active_ai_id else user.settings.last_active_ai_id
    db.session.commit()
    print(f'User settings for user {user.id} has been updated.')
    print(f'Timezone: {user.settings.timezone}')
    print(f'Context length: {user.settings.context_length}')


# onboarding AI page
@app.route('/onboarding/ai', methods=['GET'])
@login_required
def onboarding_ai():
        return render_template('onboarding-ai.html')
    

# Purpose: Save profile picture to S3 and commit changes to db
# Input: profile_image (data), model (User or AIModel), model_type (str)
# Output: status (bool)
def save_profile_picture(profile_image, model, model_type):
    try:
        timestamp = datetime.datetime.now(datetime.UTC).timestamp()
        filename = f'{model_type}_profile_image{str(model.id)}{timestamp}.png'
        # upload to s3
        get_s3().upload_fileobj(
            profile_image,
            app.config["S3_BUCKET_NAME"],
            filename,
            ExtraArgs={"CacheControl": "max-age=31536000, public"}
        )
        # Generate a versioned URL to force browser to load the new image
        versioned_url = f'{app.config["S3_LOCATION"]}{filename}'
        print(f'Profile image for {model.id} has been saved to S3! ImageURL: {versioned_url}')  # debug
        model.profile_image_url = versioned_url
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f'Error saving profile picture for {model_type} {model.id}: {e}')
        return False
    
    
# select existing ai
# currently creates a copy of the existing ai model for each user
# templates are stored at specific id values
@app.route('/onboarding/ai/existing', methods=['GET', 'POST'])
@login_required
def onboarding_ai_existing():
    if request.method == 'POST':
        
        ai_id = request.form.get('ai-id')

        print(f'Onboarding/ai/existing: {ai_id}') # debug

        # form validation
        if not ai_id:
            flash('Please select an AI model.', 'error')
            return redirect(url_for('onboarding_ai_existing'))
        
        ai_model = get_ai_model(ai_id=ai_id)
        if not ai_model:
            flash('AI model not found.', 'error')
            return redirect(url_for('onboarding_ai_existing'))

        # Create a copy of the selected AI model
        new_ai_model = create_ai_model(ai_model.name, ai_model.model_name, ai_model.prompt, ai_model.description, ai_model.settings.memory_chunk_size, ai_model.profile_image_url)

        # set user-ai relationship
        current_user.assign_ai_model(new_ai_model)
        new_ai_model.assign_user(current_user)
        
        db.session.add(new_ai_model)
        db.session.commit()

        # redirect to chat
        flash('Welcome to pocketAI', 'success')
        return redirect('/chat')
    
    return render_template('onboarding-ai-existing.html')

# create new ai
@app.route('/onboarding/ai/create', methods=['GET', 'POST'])
@login_required
def onboarding_ai_create():
    if request.method == 'POST':
        try:
            # get form data
            profile_image = request.files.get('profile-image')
            ai_name = request.form.get('ai-name').strip()
            ai_model_name = request.form.get('ai-model').strip()
            ai_prompt= request.form.get('ai-prompt').strip()
            ai_description = request.form.get('ai-description').strip()
            memory_chunk_size = request.form.get('memory-chunk-size').strip()
            conversation_mode = request.form.get('conversation-mode').strip()
            voice_enabled = 'voice-enabled' in request.form
            voice_id = request.form.get('voice-id').strip()
            voice_model = request.form.get('voice-model').strip()
            
            # form validation
            if not ai_name or not ai_model_name or not ai_prompt or not ai_description or not memory_chunk_size:
                flash('Please fill out all fields.', 'error')
                return redirect(url_for('onboarding_ai_create'))
            
            # create new AI model and settings
            ai_model = create_ai_model(ai_name, ai_model_name, ai_prompt, ai_description, memory_chunk_size)
            
            # set profile image
            if profile_image and allowed_file(profile_image.filename):
                save_profile_picture(profile_image, ai_model, "ai")

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
            print(f'Error creating new AI model: {e}')
            flash('Error creating new AI model.', 'error')
            return redirect(url_for('onboarding_ai_create'))
    
    return render_template('onboarding-ai-create.html')



''' Contacts CRUD routes '''

@app.route('/user-settings/contacts', methods=['GET'])
@login_required
def user_contacts():
    return render_template('user-contacts.html', contacts=current_user.contacts)    

@app.route('/add-contact', methods=['POST'])
@login_required
def add_contacts():
    try:
        # extract form information
        name = request.form.get('name')
        email = request.form.get('email')
        relationship = request.form.get('relationship', None)
        phone = request.form.get('phone', None)
        notes = request.form.get('notes', None)
        
        # add user contacts
        new_contact = create_user_contact(current_user.id, name, email, relationship, phone, notes)
        current_user.add_contact(new_contact)
        
        print(new_contact)
        
        # check status and return response
        if not new_contact:
            return jsonify({'success': False, 'error': 'Failed to add contact'}), 400
        
        return jsonify({'success': True, 'contact': new_contact.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': f'An unexpected error has occurred: {e}'}), 500

@app.route('/edit-contact/<int:contact_id>', methods=['PUT'])
@login_required
def edit_contact(contact_id):
    # retrieve contacts if they belong to the user
    contact = Contacts.query.get_or_404(contact_id)
    if contact.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # extract data from form and change the fields
    data = request.form
    contact.name = data['name']
    contact.email = data['email']
    contact.relationship = data.get('relationship', '')
    contact.phone = data.get('phone', '')
    contact.notes = data.get('notes', '')
    
    db.session.commit()
    
    return jsonify({'success': True, 'contact': contact.to_dict()})


@app.route('/delete-contact/<int:contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    # delete the contact only if it belongs to the user
    contact = Contacts.query.get_or_404(contact_id)
    if contact.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    db.session.delete(contact)
    db.session.commit()
    
    return jsonify({'success': True})


''' Subscription routes '''

# creates stripe checkout session
@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        user_id = current_user.id
        # try to find price based on lookup key
        prices = stripe.Price.list(
            lookup_keys=[request.form['lookup_key']],
            expand=['data.product']
        )

        # create checkout session
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': prices.data[0].id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            client_reference_id=user_id,
            success_url=YOUR_DOMAIN +
            '/payment-success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=YOUR_DOMAIN + '/payment-canceled',
        )
        # redirect to stripe hosted checkout page
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        print(f'Subscription Purchase Error: {e}')
        return redirect('/error?message=Error creating subscription session.')

# webhook endpoint for stripe
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    # raw data from stripe servers
    payload = request.data
    # signature to verify that it came from stripe servers
    sig_header = request.headers.get('STRIPE_SIGNATURE')
    # used to verify stripe signature
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        # try to reconstruct event
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        raise e
    except stripe.error.SignatureVerificationError as e:
        raise e

    event_type = event['type']
    print(f'Event: {event}')
    # user has successfully paid
    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)
    elif event_type == 'customer.subscription.updated':
        print('Subscription created %s', event.id)
    elif event_type == 'customer.subscription.deleted':
        print('Subscription canceled: %s', event.id)

    return jsonify({'status': 'success'})

# handles successful payment session
@login_required
def handle_checkout_session(session):
    # retrieves user id from session and save strip customer id
    user_id = session.client_reference_id
    stripe_customer_id = session.customer
    current_user.stripe_customer_id = stripe_customer_id
    db.session.commit()
    print(f'Suceessful payment for user: {user_id}')

    # retrieve subscription id
    session_with_line_item = stripe.checkout.Session.retrieve(
        session['id'],
        expand=['line_items']
    )
    # Get the price ID from the single line item
    line_item = session_with_line_item['line_items']['data'][0]
    price_id = line_item['price']['id']

    # Retrieve the price object to get the lookup key
    price = stripe.Price.retrieve(price_id)
    lookup_key = price['lookup_key']

    print(f'User purchased product: {lookup_key}')
        
    # Update the user's subscription status or credits
    update_user_subscription(user_id, lookup_key)

# updates user subscription plan
def update_user_subscription(user_id, subscription_plan):
    # set user subscription plan and credits
    user = User.query.get(user_id)
    user.plan = subscription_plan
    if subscription_plan == 'premium':
        print("User has purchased Premium subscription plan.")
        user.credits += 100
    else:
        print("Not valid subscription plan.")

    db.session.commit()

    print(f'User {user_id} has been updated to subscription plan {subscription_plan}.')

@app.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    try:
        # Get the customer's Stripe ID
        customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
        
        # Get the customer's active subscriptions
        subscriptions = stripe.Subscription.list(customer=customer.id, status='active')
        
        if not subscriptions.data:
            return jsonify({'error': 'User does not have any active subscriptions'}), 404

        # Cancel the first active subscription
        subscription = subscriptions.data[0]
        canceled_subscription = stripe.Subscription.delete(subscription.id)

        # Update your database to reflect the cancellation
        # This depends on how you're storing subscription info in your database
        # For example:
        # current_user.has_active_subscription = False
        # db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Subscription canceled successfully!',
            'subscription_id': canceled_subscription.id
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500

# displays payment success page
@app.route('/payment-success')
def success():
    session_id = request.args.get('session_id')
    session = stripe.checkout.Session.retrieve(session_id)
    return render_template('payment-success.html', session=session)

# displays payment canceled page
@app.route('/payment-canceled')
def cancel():
    return render_template('payment-canceled.html')


''' Credits and Admin Routes '''

# testing implementation
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'your_admin_password')
from flask import abort

@app.route('/add-credits/<int:amount>', methods=['GET'])
@login_required
def add_credits(amount):
    current_user.add_paid_credits(amount)
    db.session.commit()
    return jsonify({'success': True}), 200

@app.route('/admin/reset_credits', methods=['POST'])
def reset_credits():
    password = request.form.get('password')
    if password != ADMIN_PASSWORD:
        abort(403)  # Forbidden

    users = User.query.all()
    for user in users:
        user.reset_free_credits()
    db.session.commit()
    return 'Credits reset successfully', 200


'''Google signup/login routes'''

# google sign-up
@app.route('/signup/google')
def google_signup():
    return initiate_google_login()


# google login
@app.route('/login/google')
def google_login():
    # if user is logged in
    if current_user.is_authenticated:
        # (??)
        google_user = GoogleUser.query.filter_by(google_id=current_user.google_id).first()
        
        # user does not have google account
        if not google_user:
            return initiate_google_login()
        
        # user has google account but access token has expired
        if google_user.token_expires_at <= datetime.datetime.now(datetime.UTC):
            if google_user.refresh_token and refresh_access_token(google_user):
                # (??) - refresh google token?
                login_user_process(current_user)
                return redirect('/chat')
            else:
                return initiate_google_login()
        
        # user has valid access token and google account
        login_user_process(current_user)
        return redirect('/chat')
    
    # otherwise, initiate google login
    return initiate_google_login()


# authorize google login/signup, create user account if does not exist
@app.route('/authorize')
def authorize():
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
        except Exception as e:
            flash('Failed to parse user info from Google', 'error')
            return redirect('/login')
        
        # if user does not exist, create user (new user)
        user = User.query.filter_by(google_id=user_info['sub']).first()
        if not user:
            user = create_user_model(username=user_info['given_name'], auth_type='google', password=None, email=user_info['email'], google_id=user_info['sub'])
            new_user = True

        # if google user does not exist, create google user (linking google account)
        google_user = get_google_user(google_id=user_info['sub'])
        if not google_user:
            google_user = GoogleUser(google_id=user_info['sub']) # (??)
            db.session.add(google_user)

        # update access and refresh tokens
        google_user.access_token = token['access_token']
        google_user.refresh_token = token['refresh_token']
        google_user.token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=token['expires_in'])

        db.session.commit()

        # Log user in
        login_user_process(user)

        if new_user:
            flash('Google account linked!', 'success')
            return redirect(url_for('onboarding_user'))
        else:
            print('redirecting to chat')
            return redirect('/chat')
        
    except Exception as e:
        db.session.rollback()
        print(f'Google Login Error: {e}')
        flash('Failed to authenticate google account. :(', 'error')
        return redirect('/login')
    

# link google account
@app.route('/link/google')
@login_required
def link_google():
    # check if user has a linked google account
    if get_google_user(google_id=current_user.google_id):
        flash('Google account already linked.', 'error')
        return redirect(url_for('onboarding_user'))
    else:
        return initiate_google_login(login_type='link')
    

# links a google account to an existing account
@app.route('/authorize/link')
def authorize_link():
    # obtain access token. If token is invalid, return error
    google = oauth.create_client('google')
    try:
        token = google.authorize_access_token()
        if not token:
            flash('Access Denied. No access token provided.', 'error')
            return redirect(url_for('onboarding_user'))
        
        # parse user info from token
        nonce = session.pop('google_auth_nonce', None)
        user_info = google.parse_id_token(token, nonce=nonce)
        google_id = user_info['sub']

        # Check if this Google account is already linked to another user
        existing_user = User.query.filter_by(google_id=google_id).first()
        if existing_user and existing_user.id != current_user.id:
            flash('This Google account is already linked to another user.', 'error')
            return redirect(url_for('onboarding_user'))

        # create google account and link to current_user
        google_user = get_google_user(google_id=user_info['sub'])
        if not google_user:
            google_user = GoogleUser(google_id=google_id)
            current_user.auth_type = 'google'
            current_user.google_id = google_id
            db.session.add(google_user)
        
        # update access and refresh tokens
        google_user.access_token = token['access_token']
        google_user.token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=token['expires_in'])
        google_user.refresh_token = token['refresh_token']

        try:
            db.session.commit()
            flash('Google account linked!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error linking Google account: {e}")  # Basic logging
            flash('Failed to link Google account. Please try again.', 'error')

        return redirect(url_for('onboarding_user'))
    
    except Exception as e:
        print(f"Error in authorize_link: {e}")  # Basic logging
        flash('Failed to link Google account. Please try again.', 'error')
        return redirect(url_for('onboarding_user'))


""" Helper functions """


# ----- Login Helpers -----
# Purpose: initiates google login process
# Input: None
# Output: redirect to google OAuth page
def initiate_google_login(login_type=None):
    # generate nonce for verification
    nonce = os.urandom(16).hex()
    session['google_auth_nonce'] = nonce
    google = oauth.create_client('google')

    if login_type == 'link':
        return google.authorize_redirect(url_for('authorize_link', _external=True), nonce=nonce)
    else:
        # redirect to google OAuth page
        return google.authorize_redirect(url_for('authorize', _external=True), nonce=nonce)

# Purpose: refreshes access token for google user
# Input: google_user (GoogleUser)
# Output: status (boolean)
def refresh_access_token(google_user):
    # try to refresh access token
    try:
        # refresh token
        new_token = google.refresh_token(
            refresh_url='https://oauth2.googleapis.com/token',
            refresh_token=google_user.refresh_token
        )

        # update access token and expiration time
        google_user.access_token = new_token['access_token']
        google_user.token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=new_token['expires_in'])
        db.session.commit()
        return True
    # handle exception; return false
    except Exception as e:
        print(f'Failed to refresh google access token: {e}')
        return False
    
# Purpose: Logs in user and set user and selected ai session variables
# Input: user (User)
# Output: None
def login_user_process(user):
    login_user(user)
    initialize_user_session(user)
    
    active_ai = get_active_ai(user)
    if active_ai:
        initialize_ai_session(active_ai)

# Purpose: Creates user setting if does not exist and sets session variables for user
# Input: user
# Output: None
def initialize_user_session(user):
    # create user settings if it does not exist
    if not user.settings:
        user.settings = UserSettings(user_id=user.id)
        db.session.add(user.settings)
        db.session.commit()
        
    # load the session variables for user
    session.update({
        'user_id': user.id,
        'context_length': user.settings.context_length or 10,
        'user_timezone': user.settings.timezone or "UTC",
        'last_active_ai_id': user.settings.last_active_ai_id
    })

# Purpose: Initializes session variables for AI model
# Input: ai_model (AIModel)
# Output: None
def initialize_ai_session(ai_model, updated=False):
    # Only update if AI changed or session not initialized (or if ai-settings have been changed)
    if session.get('ai_id') != ai_model.id or updated:
        session.update({
            'ai_name': ai_model.name,
            'ai_id': ai_model.id,
            'memory_chunk_size': ai_model.settings.memory_chunk_size or 6,
            'memory_queue_count': 0,
            'memory_queue': [],
            'conversation_mode': ai_model.settings.conversation_mode or 'conversation'
        })

# Purpose: Return the selected ai model for user
def get_active_ai(user):
    try:
        if user.settings.last_active_ai_id:
            # return the active ai model
            last_active_ai_model = get_ai_model(ai_id=user.settings.last_active_ai_id)
            return last_active_ai_model if last_active_ai_model else user.ai_models[0]
        # return the first one if no active ai model, if no models, return none
        return user.ai_models[0] if user.ai_models else None
    except Exception as e:
        print(f'Error getting active AI model: {e}')
        return None






# ----- Conversation Helpers -----
# Purpose: Runs user_message w/ conversation history through selected AI model to get response
# Input: user_message (str)
# Output: response (str)
def run_ai_response(ai_id, user_message):
    
    # load session variables
    # TODO: rename these session variables
    memory_queue = session.get('memory_queue', [])
    memory_queue_count = session.get('memory_queue_count', 0)
    context_length = session.get('context_length', 6)
    memory_chunk_size = session.get('memory_chunk_size', 2)
    ai_name = session.get('ai_name', 'Assistant')

    # Settings for debugging
    print(f'---- Settings ----')
    print(f'Memory Queue Count: {memory_queue_count}')  # debug
    print(f'Memory Queue:       {memory_queue}')        # debug
    print(f'Context length:     {context_length}')      # debug
    print(f'------------------')

    # Instantiate AI model
    try: 
        ai = AI_model(ai_id, current_user.username)
    except Exception as e:
        print(f"Error: {e}")
        raise Exception("Failed to instantiate AI model.") 

    # query and parse conversation history
    # TODO: keep track of conversation history in cache/session
    # TODO: limit conversation history based on token size as well (currently number of messages)
    try:
        conversation_history = Message.query.filter_by(user_id=current_user.id, ai_id=ai_id).order_by(
            Message.timestamp.desc()).limit(context_length).all()[::-1]
        latest_messages = [{"role": msg.sender, "content": msg.message} for msg in conversation_history]
    except Exception as e:
        print(f"Error: {e}")
        latest_messages = []
        
    # get system info
    system_info = get_system_info(session.get('user_timezone'))

    # analyze the context and determine intent (latest 6 messages)
    print_conversation_history(latest_messages)
    intention, is_function_call = context_analyzer.analyze_context(latest_messages)

    # if more context is needed, call a function
    if intention and is_function_call:
        # format system info
        context, function_log = context_analyzer.parse_func(intention, latest_messages, current_user.id, ai_id, system_info)
        print(f'Context: {context}')  # debug
        print(f'Function log: {function_log}')  # debug
        print("---------------------------------")
    # clarification is needed but no functions were called
    elif intention:
        context = f'Seek clarification: {intention}'
        function_log = None
    # otherwise, no additional context is needed
    else:
        context = ''
        function_log = None
    
    # run ai response with the provided context (if any) 
    response = ai.get_response(latest_messages, context=context, function_log=function_log, system_info=system_info)

    print(f'AI response: {response}')  # debug
    print(f'Message count: {memory_queue_count}/{memory_chunk_size}')  # debug
    print("---------------------------------")

    # saves short-term memory to long-term memory every x message cycles
    if memory_queue_count >= memory_chunk_size:
        print(f'Short-term memory: {memory_queue}') # debug
        # determine if message is important
        memory = utilities.summarize(memory_queue, ai_name, current_user.username)
        if memory.lower().strip() == 'false':
            print("message not saved (not important).")
        elif memory:
            long_term_memory.save_memory(current_user.id, ai_id, memory)
            print("message saved.")
        else:
            print("message not saved (error).")
        memory_queue_count = 0
        memory_queue.clear()
    else:
        memory_queue_count += 1
        memory_queue.append(
            f'"{current_user.username}": {user_message}, {ai_name}: {response}')

    # update session variables
    session['memory_queue_count'] = memory_queue_count
    session['memory_queue'] = memory_queue
    session['past_context'] = context

    return response

# Purpose: get the current date and time, formatted
# Input: user_timezone (str)
# Output: formatted system info message (str)
def get_system_info(user_timezone):
    try:
        # get current datetime object
        timezone = pytz.timezone(user_timezone)
        current_time = datetime.datetime.now(timezone)
        
        # format string
        date_str = current_time.strftime('Today is %A, %b %d, %Y.')
        time_str = current_time.strftime('The current time is %I:%M%p.').lower()
        
        # # Capitalize the first letter of AM/PM
        # time_str = time_str[:-2] + time_str[-2:].upper()
        
        return f"{date_str} {time_str}"
    except Exception as e:
        print(f"Error: {e}")
        return None

# Purpose: adds a single message to msg database
# Input: user_id (int), ai_id (int), sender (str), message (str)
# Output: message_id (int)
def update_conversation_history(user_id, ai_id, sender, message, voice_url=None):
    message = Message(user_id=user_id, ai_id=ai_id, sender=sender, message=message, voice_url=voice_url)
    db.session.add(message)
    db.session.commit()
    return message.id

# Purpose: prints conversation history for debugging
def print_conversation_history(conversation_history: list):
    print("---- Conversation History ----")
    for msg in conversation_history:
        print(f"{msg['role']}: {msg['content']}")
    print ("-------------------------------")

# Purpose: checks if file is allowed to be uploaded
# Input: filename (str)
# Output: allowed (bool)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



# ----- Model Helpers -----
# Purpose: return User obj given user id
# Input: user_id (int)
# Output: User (obj)
@login_manager.user_loader
def get_user(user_id):
    return User.query.filter(User.id == user_id).first()
    
def get_google_user(google_id):
    return GoogleUser.query.filter_by(google_id=google_id).first()

# Purpose: creates a new AI model and settings
# Input: ai_name (str), ai_model_name (str), ai_prompt (str), ai_description (str), memory_chunk_size (int)
# Output: ai_model (AIModel)
def create_ai_model(ai_name, ai_model_name, ai_prompt, ai_description, memory_chunk_size, profile_image_url=""):
    # create AI model
    ai_model = AIModel(name=ai_name, 
                       model_name=ai_model_name, 
                       prompt=ai_prompt, 
                       description=ai_description,
                       profile_image_url=profile_image_url
                       )
    db.session.add(ai_model)
    db.session.commit()
    
    # create AI settings with default settings
    ai_settings = AISettings(ai_model_id=ai_model.id, memory_chunk_size=memory_chunk_size)
    db.session.add(ai_settings)
    db.session.commit()

    return ai_model

# Purpose: creates a new user model and default settings
# Input: username (str), email (str), password (str), auth_type (str)
# Output: user (User)
def create_user_model(username, auth_type, password=None, email=None, google_id=None):
    # create user
    user = User(username=username, 
                auth_type=auth_type, 
                email=email, 
                google_id=google_id)
    if password:
        user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # create user settings with default settings
    user_settings = UserSettings(user_id=user.id)
    db.session.add(user_settings)
    db.session.commit()

    return user

# Purpose: add a new contact to the user's contact list
# Input: user_id (int), contact_id (int)
# Output: None
def create_user_contact(user_id, name, email, relationship="", phone="", notes=""):
    try: 
        new_contact = Contacts(name=name, email=email, user_id=user_id, relationship=relationship, phone=phone, notes=notes)
        db.session.add(new_contact)
        db.session.commit()
        return new_contact
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        return False    

# Purpose: Generates a welcome message and saves it to db
# Input: ai_model (AIModel), user (User)
# Output: True if successful, False otherwise
def generate_welcome_message(ai_model, user):
    WELCOME_PROMPT = 'This is the first time you are chatting with the user. Generate a welcome message for the user, in character.'
    try:
        tmp_model = AI_model(ai_model.id, user.username)
        welcome_message = tmp_model.get_response(False, WELCOME_PROMPT)
        return welcome_message
    except Exception as e:
        print(f'Error generating welcome message: {e}')
        return False
    

    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))