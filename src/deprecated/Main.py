import os

from src.deprecated.UserInterface import TextInterface
from src.components.context_analyzer import context_analyzer
from src.components.ai_model import *
from src.components.memory import long_term_memory
from src.utils.utils import utilities

''' Tech Stack
# text-to-speech: Google, Whisper
# AI models: GPT-3.5, GPT-3.5-0613, GPT-4
# speech-to-text: Google, Microsoft, Elevenlabs
# embeddings: OpenAI
# vector database: Chroma
'''

# keys and credentials
OPENAI_API_KEY = ''
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# settings
context_model = "gpt-3.5-turbo-0613"
chat_model = "gpt-3.5-turbo"
AI_name = 'Mira'
username = 'Average'

# global variables
SAVE_EVERY_X = 2
session_type = 'text'
names = {"AI_name": AI_name, "username": username}

def main():

    # initialize session variables
    conversation_history = []
    message_counter = 1
    message_memory = []

    # objects
    ui = TextInterface(session_type, AI_name, username)
    ai = OpenAIGPT_3_5(AI_name, username)

    # ai initiates conversation
    initial_response = ai.get_response(conversation_history, context='')
    ui.print_ai_output(initial_response)
    conversation_history.append({"role": "assistant", "content": initial_response})

    while True:

        # get user message, update conversation
        user_message = ui.get_user_input(conversation_history)
        conversation_history.append({"role": "user", "content": user_message})

        # analyze the context and determine intent (latest 6 messages)
        conversation_snippet = conversation_history[-6:] if len(conversation_history) >= 6 else conversation_history
        intention = context_analyzer.analyze_context(conversation_snippet)

        # if more context is needed, call a function
        if intention:
            context = context_analyzer.parse_func(intention, conversation_history[-1:][0])
            print(f'context: {context}') # debug
            response = ai.get_response(conversation_history[-6:], context=context)
        # otherwise, continue regular conversation
        else:
            response = ai.get_response(conversation_history[-6:], context='')

        # print ai response, update conversation
        ui.print_ai_output(response)
        conversation_history.append({"role": "assistant", "content": response})

        # updates long-term memory every 2 message cycles
        if message_counter >= SAVE_EVERY_X:
            print(f'message memory: {message_memory}') # debug
            important = utilities.summarize(message_memory, AI_name, username)
            if important.lower().strip() == 'false':
                print("message not saved (not important).") # debug
            elif important:
                long_term_memory.save_memory((important,))
                print("message saved.") # debug
            else:
                print("message not saved.") # debug
            message_counter = 0
            message_memory.clear()
        else:
            message_counter += 1
            message_memory.append(
                f'{AI_name}: {response}, "{username}": {user_message}')



if __name__ == '__main__':
    main()
    long_term_memory.save_database_txt()
