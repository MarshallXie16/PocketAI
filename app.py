import os
import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, current_app, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from src.components.context_analyzer import context_analyzer
from src.components.memory import long_term_memory
# from src.components.speech_to_text import speech_to_text
from src.components.ai_models import AI_model

from src.models.users import User, AIModel, UserSettings, AISettings
from src.models.google_user import GoogleUser
from src.models.message import Message

from config import DevelopmentConfig
from src.utils.extensions import db, migrate
from src.utils.utils import utilities
from src.utils.auth import oauth, google, init_oauth

import stripe


''' Tech Stack
# AI models: GPT-3.5, GPT-3.5-0613, GPT-4
# text-to-speech: Google, Whisper
# speech-to-text: Google, Microsoft, OpenAI, Elevenlabs
# embeddings: OpenAI
# vector database: Chroma, Pinecone
'''

# global variables
SAVE_EVERY_X = 2
DEFAULT_WELCOME_MSG = "Hello, how can I help you today?"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
YOUR_DOMAIN = 'http://127.0.0.1:5000'
MESSAGE_COST = 1
stripe.api_key = os.environ.get('STRIPE_API_KEY')

load_dotenv()
login_manager = LoginManager()

# Instantiates and configures app
def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__, template_folder=config_class.TEMPLATE_FOLDER, static_folder=config_class.STATIC_FOLDER)
    app.config.from_object(config_class) # configure application variables

    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = app.config['LOGIN_URL']

    init_oauth(app)

    return app

app = create_app()

# for debugging
# import logging
# logging.basicConfig(level=logging.DEBUG)

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

        # authenticate user
        if user and user.check_password(password):
            login_user_process(user)
            return redirect(url_for('chat'))
        # user does not exist or password is incorrect
        else:
            flash('Invalid username or password.', 'error')
            return render_template('login.html')

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
        user = create_user_model(username=username, auth_type="default", password=password, email=email)

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
    # TODO: consider caching user settings when the user logs in
    user_settings = UserSettings.query.filter(UserSettings.user_id == current_user.id).first()
    session['user_timezone'] = user_settings.timezone
    session['num_msg'] = user_settings.messages_per_page

    # get the first AI model associated with the user (currently only 1 AI model per user)
    try:
        #TODO: allow users to select AI model from a dropdown
        ai_model = current_user.ai_models[0] 
    except Exception as e:
        print(f'Error: {e}')
        flash('No AI assistant found. Please select or create an AI.', 'error')
        return redirect(url_for('onboarding_ai'))
    
    # set ai-related session variables
    # TODO: we can do this when the user first logs in or when they select an AI model
    session.update({
                    'ai_name': ai_model.name,
                    'ai_id': ai_model.id,
                    'max_msg_memory': ai_model.settings.memory_chunk_size
                })

    # retrieve chat history (last 10 messages by default)
    # TODO: we might be able to cache this when the user logs in
    num_msg = session.get('num_msg', 10)
    messages = Message.query.filter_by(user_id=current_user.id, ai_id=ai_model.id).order_by(Message.timestamp.desc()).limit(num_msg).all()[::-1]

    # if no chat history, generate welcome message
    # TODO: AI generates a default welcome message?
    if not messages:
        messages = [Message(user_id=current_user.id, ai_id=ai_model.id, sender="assistant", message=DEFAULT_WELCOME_MSG)]

    return render_template('chat.html', ai_model=ai_model, messages=messages)


# profile page and settings
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':

        # get form data
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        timezone = request.form.get('timezone').strip()
        messages_per_page = request.form.get('messages').strip()
        profile_image = request.files.get('profile-image')

        # save profile picture
        if profile_image and allowed_file(profile_image.filename):
            filename = f'user_profile_image{str(current_user.id)}.png'
            UPLOAD_FOLDER = os.path.join(current_app.root_path, 'src\\static\\images\\profile_pictures')
            profile_image_path = os.path.join(UPLOAD_FOLDER, filename)
            profile_image.save(profile_image_path)
            print('profile image saved!')
    
        # update username
        user = User.query.filter(User.username == username).first()
        if user and username != current_user.username:
            # TODO: display errors for flash messages
            flash('Username already exists.', 'error')
            return redirect('/profile')
                
        current_user.username = username

        # TODO: password change validation
        if password != '*****':
            User.set_password(current_user, password)

        # update timezone and msg per page
        
        print(f'Timezone: {timezone}')
        print(f'Messages per page: {messages_per_page}')
        UserSettings.query.filter(UserSettings.user_id == current_user.id).update({'timezone': timezone, 'messages_per_page': int(messages_per_page)})

        db.session.commit()
        flash('Profile updated!', 'success')
        print(f'Updated timezone: {current_user.settings.timezone}')
        print(f'Updated messages per page: {current_user.settings.messages_per_page}')
        return redirect('/profile')
    else:
        # TODO: cache this when the user logs in
        user_settings = UserSettings.query.filter(UserSettings.user_id == current_user.id).first()
        # if for whatever reason user settings do not exist, create them
        if not user_settings:
            user_settings = UserSettings(user_id=current_user.id)
            db.session.add(user_settings)
            db.session.commit()
            print('User settings created.')
        
        # retrieve info for all ai models owned by user
        available_ais = current_user.ai_models
        return render_template('profile.html', user_settings=user_settings, available_ais=available_ais)


# pricing page
@app.route('/pricing')
def pricing():
    return render_template('pricing.html')





''' functionality routes '''

# logs user out
@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')


# sends a text message
@app.route('/send_message', methods=['POST'])
@login_required
def send_message():

    # check if user has enough credits
    if current_user.free_credits + current_user.paid_credits < MESSAGE_COST:
        flash('Insufficient credits. Please add more credits.', 'error')
        return redirect('chat')

    # TODO: allow this to work with any AI model, not just the user's first AI model
    ai_model = current_user.ai_models[0]

    # parse user message
    data = request.json
    user_message = data['message']
    update_conversation_history(current_user.id, ai_model.id, sender="user", message=user_message)

    # get AI response
    print('---- Message Start ----')
    ai_response = run_ai_response(user_message)
    print('---- Message End ----')
    update_conversation_history(current_user.id, ai_model.id, sender="assistant", message=ai_response)

    # deduct credits from user
    current_user.use_credits(MESSAGE_COST)
    db.session.commit()

    return jsonify({"response": ai_response, "timestamp": datetime.datetime.now()})


# sends an audio message
@app.route('/upload_audio', methods=['POST'])
@login_required
def upload_audio():
    if 'audio' in request.files:
        # save audio file
        audio = request.files['audio']
        audio.save('recording.wav')

        # parse user input
        user_message = speech_to_text.listen()
        update_conversation_history(current_user, user_message, "user")

        # process audio and return ai response
        ai_response = run_ai_response(user_message)
        update_conversation_history(current_user, ai_response, "assistant")

        # return response
        return jsonify({'success': True, 'user_message': user_message, 'ai_response': ai_response})
    else:
        return jsonify({'success': False, 'error_message': 'No audio file found in the request.'})


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

        # validation: check if model exists
        ai_model = AIModel.query.filter(AIModel.id == ai_id).first()
        if not ai_model:
            flash('AI model not found.', 'error')
            return redirect(url_for('profile'))
        
        # change ai profile picture (if valid)
        if profile_image and allowed_file(profile_image.filename):
            print(f'AI ID: {ai_model.id}')
            filename = f'ai_profile_image{str(ai_model.id)}.png'
            UPLOAD_FOLDER = os.path.join(current_app.root_path, 'src\\static\\images\\profile_pictures')
            profile_image_path = os.path.join(UPLOAD_FOLDER, filename)
            print(profile_image_path)
            profile_image.save(profile_image_path)
            print('profile image saved!')

        # change ai model fields
        ai_model.name = ai_name
        ai_model.model_name = ai_model_name
        ai_model.prompt = ai_prompt
        ai_model.description = ai_description

        # change ai settings fields
        ai_settings = AISettings.query.filter(AISettings.ai_model_id == ai_id).first()
        ai_settings.memory_chunk_size = int(ai_memory_chunk_size)

        # Commit changes to the database
        try:
            db.session.add(ai_model)
            db.session.add(ai_settings)
            db.session.commit()
            print('AI model and settings updated successfully.')
        except Exception as e:
            db.session.rollback()
            flash('Error updating AI model and settings.', 'error')
            return redirect(url_for('ai_settings', ai_id=ai_id))

        flash('AI model and settings updated successfully.', 'success')
        return redirect(url_for('ai_settings', ai_id=ai_id))
    else:
        # try to find ai model
        ai_model = AIModel.query.filter(AIModel.id == ai_id).first()
        if not ai_model:
            flash('AI model not found.', 'error')
            return redirect(url_for('profile'))  

        # find associated ai settings, otherwise create it
        ai_settings = AISettings.query.filter(AISettings.ai_model_id == ai_id).first()
        if not ai_settings:
            ai_settings = AISettings(ai_model_id=ai_id)
            ai_model.settings = ai_settings
            db.session.add(ai_settings)
            db.session.add(ai_model)
            db.session.commit()    

        # otherwise, display settings
        return render_template('ai_settings.html', ai_model=ai_model, ai_settings=ai_settings)


@app.route('/profile/delete-ai/<int:ai_id>', methods=['DELETE'])
@login_required
def delete_ai(ai_id):
    # get the ai model
    ai_model = AIModel.query.get_or_404(ai_id)

    # Check if the AI model is associated with the current user
    if ai_model in current_user.ai_models:
        # Remove association with current user
        current_user.remove_ai_model(ai_model)
        db.session.commit()

        # Delete AI settings
        ai_settings = AISettings.query.filter_by(ai_model_id=ai_model.id).first()
        if ai_settings:
            db.session.delete(ai_settings)

        # Delete messages
        messages = Message.query.filter_by(ai_id=ai_id, user_id=current_user.id).all()
        for message in messages:
            db.session.delete(message)

        # Finally, delete the AI model itself
        db.session.delete(ai_model)
        db.session.commit()

        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'AI not found'}), 404


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
        # grab user settings from form
        profile_image = request.files.get('profile-image')
        username = request.form.get('username').strip()
        user_timezone = request.form.get('timezone').strip()
        messages_per_page = request.form.get('messages').strip()

        # form validation
        if not username or not user_timezone or not messages_per_page:
            flash('Please fill out all fields.', 'error')
            return redirect('/onboarding/user')

        # save profile picture
        if profile_image and allowed_file(profile_image.filename):
            filename = f'user_profile_image{str(current_user.id)}.png'
            UPLOAD_FOLDER = os.path.join(current_app.root_path, 'src\\static\\images\\profile_pictures')
            profile_image_path = os.path.join(UPLOAD_FOLDER, filename)
            profile_image.save(profile_image_path)
            print('profile image saved!')
    
        # set new username
        user = User.query.filter(User.username == username).first()
        if user and username != current_user.username:
            flash('Username already exists.', 'error')
            return redirect('/onboarding/user')     
        current_user.username = username

        # create user settings if does not exist and update user settings
        user_settings = UserSettings.query.filter(UserSettings.user_id == current_user.id).first()
        if not user_settings:
            user_settings = UserSettings(user_id=current_user.id, timezone=user_timezone, messages_per_page=messages_per_page)
            db.session.add(user_settings)
        else:
            user_settings.timezone = user_timezone
            user_settings.messages_per_page = messages_per_page
        db.session.commit()
        print('User settings updated.')

        flash('User settings updated!', 'success')
        return redirect('/onboarding/ai')
    
    return render_template('onboarding-user.html')

# onboarding AI page
@app.route('/onboarding/ai', methods=['GET', 'POST'])
@login_required
def onboarding_ai():
        return render_template('onboarding-ai.html')
    
# select existing ai
@app.route('/onboarding/ai/existing', methods=['GET', 'POST'])
@login_required
def onboarding_ai_existing():
    if request.method == 'POST':
        
        ai_id = request.form.get('ai-id')

        print(ai_id)
        print(type(ai_id))

        # form validation
        if not ai_id:
            flash('Please select an AI model.', 'error')
            print('no ai model selected')
            return redirect(url_for('onboarding_ai_existing'))
        
        ai_model = AIModel.query.filter(AIModel.id == ai_id).first()
        if not ai_model:
            flash('AI model not found.', 'error')
            return redirect(url_for('onboarding_ai_existing'))

        # Create a copy of the selected AI model
        new_ai_model = create_ai_model(ai_model.name, ai_model.model_name, ai_model.prompt, ai_model.description, ai_model.settings.memory_chunk_size)

        # set user-ai relationship
        current_user.assign_ai_model(new_ai_model)
        new_ai_model.assign_user(current_user)
        db.session.commit()

        # redirect to chat (to chat with selected AI model; currently only 1)
        flash('Welcome to pocketAI', 'success')
        return redirect('/chat')
    
    return render_template('onboarding-ai-existing.html')

# create new ai
@app.route('/onboarding/ai/create', methods=['GET', 'POST'])
@login_required
def onboarding_ai_create():
    if request.method == 'POST':
        # get form data
        profile_image = request.files.get('profile-image')
        ai_name = request.form.get('ai-name').strip()
        ai_model_name = request.form.get('ai-model').strip()
        ai_prompt= request.form.get('ai-prompt').strip()
        ai_description = request.form.get('ai-description').strip()
        memory_chunk_size = request.form.get('memory-chunk-size').strip()

        # form validation
        if not ai_name or not ai_model_name or not ai_prompt or not ai_description or not memory_chunk_size:
            flash('Please fill out all fields.', 'error')
            return redirect('/onboarding/ai/create')
        
        # create new AI model and settings
        ai_model = create_ai_model(ai_name, ai_model_name, ai_prompt, ai_description, memory_chunk_size)

        # set profile image
        if profile_image and allowed_file(profile_image.filename):
            filename = f'ai_profile_image{str(ai_model.id)}.png'
            UPLOAD_FOLDER = os.path.join(current_app.root_path, 'src\\static\\images\\profile_pictures')
            profile_image_path = os.path.join(UPLOAD_FOLDER, filename)
            profile_image.save(profile_image_path)
            print('profile image saved!')

        # set user and ai relationship
        current_user.assign_ai_model(ai_model)
        ai_model.assign_user(current_user)

        # commit changes
        db.session.add(ai_model)
        db.session.commit()

        # redirect to chat (to chat with selected AI model; currently only 1)
        flash('Welcome to pocketAI', 'success')
        return redirect('/chat')
    
    return render_template('onboarding-ai-create.html')


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
    endpoint_secret = 'whsec_b359014efcb8b500b61555f8029a6f87d3cc026073f7cae97b0327805721a6ed'

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
def handle_checkout_session(session):
    # retrieves user id from session
    user_id = session['client_reference_id']
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



@app.route('/add-credits', methods=['GET'])
@login_required
def add_credits():
    amount = int(request.args.get('amount'))
    user = User.query.get(current_user.id)
    user.add_paid_credits(amount)
    db.session.commit()
    return jsonify({'success': True}), 200


ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'your_admin_password')

from flask import abort

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
    return initiate_google_login(next='onboarding')


# google login
@app.route('/login/google')
def google_login():
    # if user is logged in
    if current_user.is_authenticated:
        google_user = GoogleUser.query.filter_by(google_id=current_user.google_id).first()
        if google_user:
            # google user exists and has valid access token
            if google_user.token_expires_at > datetime.datetime.now(datetime.UTC):
                login_user_process(current_user)
                return redirect('/chat')
            # google user exists but access token is expired
            elif google_user.refresh_token:
                if refresh_access_token(google_user):
                    login_user_process(current_user)
                    return redirect('/chat')
        
        # no valid google user
        return initiate_google_login()
    
    # otherwise, initiate google login
    return initiate_google_login()


# authorize google login/signup, create user account if does not exist
@app.route('/authorize')
def authorize():
    # obtain access token. If token is invalid, return error
    google = oauth.create_client('google')
    token = google.authorize_access_token()
    if not token:
        flash('Access Denied. No access token provided.', 'error')
        return redirect('login')

    # parse user info from token
    nonce = session.pop('google_auth_nonce', None)
    user_info = google.parse_id_token(token, nonce=nonce)
    new_user = False

    user = User.query.filter_by(google_id=user_info['sub']).first()

    # if user does not exist, create user
    if not user:
        user = create_user_model(username=user_info['given_name'], auth_type='google', password=None, email=user_info['email'], google_id=user_info['sub'])
        new_user = True

    google_user = GoogleUser.query.filter_by(google_id=user_info['sub']).first()

    # if google user does not exist, create google user
    if not google_user:
        google_user = GoogleUser(google_id=user_info['sub'])
        db.session.add(google_user)

    # update access and refresh tokens
    google_user.access_token = token['access_token']
    google_user.token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=token['expires_in'])
    google_user.refresh_token = token['refresh_token']

    db.session.commit()

    # Log user in
    login_user_process(user)

    if new_user:
        flash('Google account linked!', 'success')
        return redirect(url_for('onboarding_user'))
    else:
        print('redirecting to chat')
        return redirect('/chat')


# link google account
@app.route('/link/google')
@login_required
def link_google():
    google_user = GoogleUser.query.filter_by(google_id=current_user.google_id).first()
    # user exists but have not linked google account
    if current_user.is_authenticated and not google_user:
        return initiate_google_login(next='onboarding')
    else:
        flash('Google account already linked.', 'error')
        return redirect(url_for('onboarding_user'))


# links a google account to an existing account
@app.route('/authorize/link')
def authorize_link():
    # obtain access token. If token is invalid, return error
    google = oauth.create_client('google')
    token = google.authorize_access_token()
    if not token:
        flash('Access Denied. No access token provided.', 'error')
        return redirect(url_for('onboarding_user'))
    
    # parse user info from token
    nonce = session.pop('google_auth_nonce', None)
    user_info = google.parse_id_token(token, nonce=nonce)

    # create google account and link to current_user
    google_user = GoogleUser.query.filter_by(google_id=user_info['sub']).first()
    if not google_user:
        google_user = GoogleUser(google_id=user_info['sub'])
        current_user.auth_type = 'google'
        current_user.google_id = user_info['sub']
        db.session.add(google_user)
    
    # update access and refresh tokens
    google_user.access_token = token['access_token']
    google_user.token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=token['expires_in'])
    google_user.refresh_token = token['refresh_token']

    db.session.commit()

    flash('Google account linked!', 'success')
    return redirect(url_for('onboarding_user'))


""" Helper functions """

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Purpose: Logs in user and sets session variables
# Input: user (User)
# Output: None
def login_user_process(user):

    # login user
    login_user(user)

    # get user settings, create if does not exist
    user_settings = UserSettings.query.filter(UserSettings.user_id == user.id).first()
    # TODO: this is redundant, should remove if stable
    if not user_settings:
        user_settings = UserSettings(user_id=user.id)
        user.user_settings = user_settings
        db.session.add(user_settings)
        db.session.add(user)
        db.session.commit()
    
    # set session variables
    session.update({
                    'num_msg': user_settings.messages_per_page,
                    'msg_count_memory': 0,
                    'msg_memory': [],
                    'user_timezone': user_settings.timezone
                })

# Purpose: initiates google login process
# Input: None
# Output: redirect to google OAuth page
def initiate_google_login(next=None):
    nonce = os.urandom(16).hex()
    session['google_auth_nonce'] = nonce
    google = oauth.create_client('google')
    print(f'Next: {next}')
    if next == 'onboarding':
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
        print(f'Exception: {e}')
        return False
    
# Purpose: Runs user_message w/ conversation history through selected AI model to get response
# Input: user_message (str)
# Output: response (str)
def run_ai_response(user_message: str) -> str:
    
    # load session variables
    message_memory = session.get('msg_memory')
    message_count = session.get('msg_count_memory')
    short_term_memory_size = session.get('max_msg_memory')
    ai_name = session.get('ai_name')
    ai_id = session.get('ai_id')

    print(f'message count: {message_count}')  # debug
    print(f'message memory: {message_memory}')  # debug
    print(f'short-term memory size: {short_term_memory_size}')  # debug

    try: 
        ai = AI_model(ai_id, current_user.username)
    except Exception as e:
        print(f"Error: {e}")
        return "Error loading AI model."

    # query and parse conversation history
    # TODO: keep track of conversation history in cache/session
    # TODO: limit conversation history based on token size as well (currently number of messages)
    try:
        conversation_history = Message.query.filter_by(user_id=current_user.id, ai_id=ai_id).order_by(
            Message.timestamp.desc()).limit(short_term_memory_size).all()[::-1]
        latest_messages = [{"role": msg.sender, "content": msg.message} for msg in conversation_history]
    except Exception as e:
        print(f"Error: {e}")
        latest_messages = []

    # analyze the context and determine intent (latest 6 messages)
    print_conversation_history(latest_messages)
    intention = context_analyzer.analyze_context(latest_messages)

    # if more context is needed, call a function
    if intention:
        context = context_analyzer.parse_func(intention, latest_messages[-1:][0], current_user.id)
        print(f'Context: {context}')  # debug
        response = ai.get_response(latest_messages, context=context)
    # otherwise, continue regular conversation
    else:
        response = ai.get_response(latest_messages, context='')


    print(f'AI response: {response}')  # debug
    print(f'Message count: {message_count}/{SAVE_EVERY_X}')  # debug
    
    # saves short-term memory to long-term memory every 2 message cycles
    # TODO: make this customizable
    if message_count >= SAVE_EVERY_X:
        print(f'Short-term memory: {message_memory}') # debug
        # determine if message is important
        memory = utilities.summarize(message_memory, ai_name, current_user.username)
        if memory.lower().strip() == 'false':
            print("message not saved (not important).")
        elif memory:
            long_term_memory.save_memory(current_user.id, memory)
            print("message saved.")
        else:
            print("message not saved (error).")
        message_count = 0
        message_memory.clear()
    else:
        message_count += 1
        message_memory.append(
            f'"{current_user.username}": {user_message}, {ai_name}: {response}')

    # update session variables
    session['msg_count_memory'] = message_count
    session['msg_memory'] = message_memory

    return response

# Purpose: adds a single message to msg database
# Input: user_id (int), ai_id (int), sender (str), message (str)
# Output: None
def update_conversation_history(user_id, ai_id, sender, message):
    message = Message(user_id=user_id, ai_id=ai_id, sender=sender, message=message)
    db.session.add(message)
    db.session.commit()

# Purpose: prints conversation history for debugging
def print_conversation_history(conversation_history: list):
    for msg in conversation_history:
        print(f"{msg['role']}: {msg['content']}")

# Purpose: checks if file is allowed to be uploaded
# Input: filename (str)
# Output: allowed (bool)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Purpose: creates a new AI model and settings
# Input: ai_name (str), ai_model_name (str), ai_prompt (str), ai_description (str), memory_chunk_size (int)
# Output: ai_model (AIModel)
def create_ai_model(ai_name, ai_model_name, ai_prompt, ai_description, memory_chunk_size):
    # create AI model
    ai_model = AIModel(name=ai_name, 
                       model_name=ai_model_name, 
                       prompt=ai_prompt, 
                       description=ai_description 
                       )
    db.session.add(ai_model)
    db.session.commit()
    
    # create AI settings with default settings
    ai_settings = AISettings(ai_model_id=ai_model.id, memory_chunk_size=memory_chunk_size)
    db.session.add(ai_settings)
    db.session.commit()

    return ai_model

# Purpose: creates a new user model and settings
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

import re
def preprocess_message(message):
    # Convert newlines to <br>
    formatted_message = message.replace('\n', '<br>')

    # Convert **bold** to <strong>bold</strong>
    formatted_message = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted_message)

    # Convert _italic_ to <em>italic</em>
    formatted_message = re.sub(r'_(.*?)_', r'<em>\1</em>', formatted_message)

    # Convert ordered lists
    formatted_message = re.sub(r'\d+\.\s+(.*?)(?=<br>|$)', r'<li>\1</li>', formatted_message)
    formatted_message = re.sub(r'(<li>.*<\/li>)+', r'<ol>\1</ol>', formatted_message)

    return formatted_message
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))





# session variables
# current_user -> username, points, email, etc.
# num_msg -> number of messages to display
# max_msg_memory -> maximum number of messages to store in short-term memory
# msg_count_memory -> number of messages to store in short-term memory
# msg_memory -> short-term memory of messages
# ai_name -> name of the AI
# model_name -> name of the model
# model_prompt -> prompt for the model