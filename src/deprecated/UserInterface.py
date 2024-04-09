from flask import Flask, render_template, request, jsonify
from abc import ABC, abstractmethod

from src.components.speech_to_text import speech_to_text
from src.components.text_to_speech import text_to_speech


class AbstractInterface(ABC):
    @abstractmethod
    def get_user_input(self, conversation_history):
        pass

    @abstractmethod
    def print_ai_output(self, response):
        pass


class UserInterface(AbstractInterface):

    def __init__(self, session_type, AI_name, username):
        self.session_type = session_type
        self.AI_name = AI_name
        self.username = username
        self.app = Flask(__name__)
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def home():
            return render_template('chat.html', ai_name=self.AI_name, user_name=self.username)

        @self.app.route('/send_message', methods=['POST'])
        def send_message():
            data = request.json
            user_message = data['message']
            response = self.handle_message(user_message)
            return jsonify({"response": response})

    def handle_message(self, message):
        # Here you will integrate the logic to handle the message and return the AI's response
        # For example, you can call ai.get_response() method and return its output
        return "AI Response to: " + message

    def run(self):
        self.app.run(debug=True)


# represents terminal-based user interface
class TextInterface(AbstractInterface):

    def __init__(self, session_type, AI_name, username):
        self.session_type = session_type
        self.AI_name = AI_name
        self.username = username

    # get the user input through text or speech
    def get_user_input(self, conversation_history):
        user_input = ''
        if self.session_type == 'text':
            user_input = input(f'{self.username}: ')
        elif self.session_type == 'speech':
            user_input = speech_to_text.listen()
            print(f'{self.username}: {user_input}')

        # special commands
        if user_input == 'end':
            # exits the loop (and saves messages -- did not config that yet)
            exit()
        elif user_input == 'print convo':
            print(conversation_history)
        elif user_input == 'E1' or user_input == 'E2':
            user_input = 'System message: The user is having some errors with audio. Please inform the user.'

        return user_input

    # format and print AI output
    def print_ai_output(self, response):
        print(f'{self.AI_name}: {response}')
        if self.session_type == 'speech':
            text_to_speech.speak(response)

