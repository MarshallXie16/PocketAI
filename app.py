import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import timedelta, datetime
from authlib.integrations.flask_client import OAuth

from src.components.context_analyzer import context_analyzer
from src.components.ai_model import *
from src.components.memory import long_term_memory
from src.utils.utils import utilities
from src.components.speech_to_text import speech_to_text
from src.utils.config import google_client_id, google_client_secret
from src.utils.extensions import db, migrate
from src.models.users import User
from src.models.google_user import GoogleUser
from src.models.message import Message

''' Tech Stack
# AI models: GPT-3.5, GPT-3.5-0613, GPT-4
# text-to-speech: Google, Whisper
# speech-to-text: Google, Microsoft, OpenAI, Elevenlabs
# embeddings: OpenAI
# vector database: Chroma, Pinecone
'''

import logging

logging.basicConfig(level=logging.DEBUG)

# keys and credentials
OPENAI_API_KEY = ''
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# temporary configurations
context_model = "gpt-3.5-turbo-0613"
chat_model = "gpt-3.5-turbo"
AI_name = ''
username = ''

# database and session configurations
app = Flask(__name__,
            template_folder='src/templates',
            static_folder='src/static')
basedir = os.path.abspath(os.path.dirname(__file__))
database_path = os.path.join(basedir, 'src', 'instance', 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SECRET_KEY'] = 'pineapple'

db.init_app(app)
migrate.init_app(app, db)

# Configure OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=google_client_id,
    client_secret=google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/calendar'}
)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)

# global variables
SAVE_EVERY_X = 2
DEFAULT_WELCOME_MSG = "Hello, how can I help you today?"

# session_type = 'text'
# names = {"AI_name": AI_name, "username": username}
# initialize session variables
# conversation_history = []
# message_counter = 1
# message_memory = []
# objects
# ai = OpenAIGPT_3_5(AI_name, username)
# ai initiates conversation
# initial_response = ai.get_response(conversation_history, context='')
# ui.print_ai_output(initial_response)
# conversation_history.append({"role": "assistant", "content": initial_response})


''' page routes '''


# homepage
@app.route('/')
def home():
    return render_template('index.html', is_logged_in=current_user.is_authenticated, user_id=get_user_id())


# login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    # visiting login page (already logged in)
    # display message user already logged in !!!
    if current_user.is_authenticated:
        return redirect('/chat')

    error_message = ''

    # login request
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            # set session variables
            session['message_memory'] = []
            session['message_count'] = 0
            # this value would be configured in user settings (???)
            session['display_message_count'] = 10
            session['short_term_memory_size'] = 6
            # session['ai'] = OpenAIGPT_3_5(AI_name, current_user.username)
            return redirect('/chat')
        else:
            error_message = 'Invalid username or password'

    # visiting login page (not logged in)
    return render_template('login.html', error_message=error_message, user_id=get_user_id())


@app.route('/login/google')
def google_login():
    nonce = os.urandom(16).hex()
    session['google_auth_nonce'] = nonce
    google = oauth.create_client('google')
    # redirect to google OAuth page
    return google.authorize_redirect(url_for('authorize', _external=True), nonce=nonce)


# authorizes google oauth
@app.route('/authorize')
def authorize():
    # obtain access token. If token is invalid, return error
    google = oauth.create_client('google')
    token = google.authorize_access_token()
    if not token:
        return 'Access Denied', 401

    # search for user in database
    nonce = session.pop('google_auth_nonce', None)
    user_info = google.parse_id_token(token, nonce=nonce)
    user = User.query.filter_by(google_id=user_info['sub']).first()

    # if user does not exist, create user
    if not user:
        user = User(username=user_info['given_name'], auth_type="google", google_id=user_info['sub'],
                    email=user_info['email'])
        db.session.add(user)
        db.session.commit()

    # if google user does not exist, create google user
    google_user = GoogleUser.query.filter_by(google_id=user.google_id).first()
    if not google_user:
        print(user.google_id)
        google_user = GoogleUser(google_id=user.google_id)
        db.session.add(google_user)

    # update access and refresh tokens
    google_user.access_token = token['access_token']
    google_user.refresh_token = token.get('refresh_token')

    db.session.commit()

    # login the user
    login_user(user)

    return redirect('/chat')


# sign-up page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error_message = ''
    if request.method == 'POST':
        # extract info from sign-up form
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        if password == confirm_password:
            # register the user
            user = User(username=username, auth_type="default")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return redirect('/')
        else:
            error_message = 'password does not match.'
    return render_template('register.html', error_message=error_message, user_id=get_user_id())


@app.route('/signup/google')
def google_signup():
    nonce = os.urandom(16).hex()
    session['google_auth_nonce'] = nonce
    return google.authorize_redirect(url_for('authorize', _external=True))


# profile page
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', username=current_user.username, points=current_user.points)


# pricing page
@app.route('/pricing')
def pricing():
    return render_template('pricing.html')


# chat page (requires user authentication)
@app.route('/chat')
@login_required
def chat():
    if current_user.is_authenticated:
        # retrieve chat history (last 10 messages by default)
        num_msg = session['display_message_count']
        messages = Message.query.filter_by(user_id=current_user.id).order_by(Message.timestamp.desc()).limit(
            num_msg).all()[::-1]
        # if no chat history, generate welcome message (???)
        if len(messages) == 0:
            messages = [Message(user=current_user, message=DEFAULT_WELCOME_MSG, timestamp=datetime.utcnow(),
                                sender="assistant")]
        return render_template('chat.html', ai_name=AI_name, username=current_user.username, messages=messages,
                               user_id=str(current_user.id))
    # optionally render login_message on login page (???)
    return redirect('/login')


''' functionality routes '''


# logs user out
@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')


# displays error page with custom message
@app.route('/error', methods=['GET'])
def error():
    message = request.args.get('message', 'An error has occurred!')
    return render_template('error.html', message=message)


# sends a text message
@app.route('/send_message', methods=['POST'])
def send_message():
    # parse user message
    data = request.json
    user_message = data['message']
    update_conversation_history(current_user, user_message, "user")

    # get AI response
    ai_response = run_ai_response(user_message)
    update_conversation_history(current_user, ai_response, "assistant")

    return jsonify({"response": ai_response, "timestamp": datetime.now()})


# sends an audio message
@app.route('/upload_audio', methods=['POST'])
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


@app.route('/upload-profile-image', methods=['POST'])
@login_required
def upload_profile_image():
    if 'profile_image' in request.files:
        # ???
        file = request.files['profile_image']
        filepath = os.path.join(current_app.root_path, 'src/static/images/profile_pictures', 'user_profile_image',
                                current_user.id)
        file.save(filepath)
        # current_user.profile_image = filepath
        # db.session.commit()
        return redirect('/profile')


""" Flask-Login functions """


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


""" Helper functions """


def run_ai_response(user_message):
    # grab session variables
    message_memory = session['message_memory']
    message_counter = session['message_count']
    short_term_memory_size = session['short_term_memory_size']
    ai = OpenAIGPT_3_5(AI_name, current_user.username)  # temporary solution (!!!)

    # query and parse conversation history
    try:
        conversation_history = Message.query.filter_by(user_id=current_user.id).order_by(
            Message.timestamp.desc()).limit(short_term_memory_size).all()[::-1]
        latest_messages = [{"role": msg.sender, "content": msg.message} for msg in conversation_history]
    except Exception as e:
        print(f"Error: {e}")
        latest_messages = []

    # analyze the context and determine intent (latest 6 messages)
    intention = context_analyzer.analyze_context(latest_messages)

    # if more context is needed, call a function
    if intention:
        context = context_analyzer.parse_func(intention, latest_messages[-1:][0], current_user.id)
        print(f'context: {context}')  # debug
        response = ai.get_response(latest_messages, context=context)
    # otherwise, continue regular conversation
    else:
        response = ai.get_response(latest_messages, context='')

    # updates long-term memory every 2 message cycles
    print(message_counter)
    print(SAVE_EVERY_X)
    print(message_memory)
    if message_counter >= SAVE_EVERY_X:
        print(f'message memory: {message_memory}')  # debug
        important = utilities.summarize(message_memory, AI_name, current_user.username)
        if important.lower().strip() == 'false':
            print("message not saved (not important).")  # debug
        elif important:
            long_term_memory.save_memory(current_user.id, (important,))
            print("message saved.")  # debug
        else:
            print("message not saved.")  # debug
        message_counter = 0
        message_memory.clear()
    else:
        message_counter += 1
        message_memory.append(
            f'"{current_user.username}": {user_message}, {AI_name}: {response}')

    # update session variables
    print(f'New message_counter: {message_counter}')
    session['message_count'] = message_counter
    session['message_memory'] = message_memory

    return response


def update_conversation_history(user, message, sender):
    message = Message(user=user, message=message, sender=sender)
    db.session.add(message)
    db.session.commit()


def get_user_id():
    if current_user.is_authenticated:
        return str(current_user.id)
    else:
        return "0"


if __name__ == "__main__":
    app.run(debug=True)
    long_term_memory.save_database_txt()
