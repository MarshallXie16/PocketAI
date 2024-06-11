# import os

# from src.deprecated.UserInterface import TextInterface
# from src.components.context_analyzer import context_analyzer
# from components.ai_models import *
# from src.components.memory import long_term_memory
# from src.utils.utils import utilities

# ''' Tech Stack
# # text-to-speech: Google, Whisper
# # AI models: GPT-3.5, GPT-3.5-0613, GPT-4
# # speech-to-text: Google, Microsoft, Elevenlabs
# # embeddings: OpenAI
# # vector database: Chroma
# '''

# # keys and credentials
# OPENAI_API_KEY = ''
# os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# # settings
# context_model = "gpt-3.5-turbo-0613"
# chat_model = "gpt-3.5-turbo"
# AI_name = 'Mira'
# username = 'Average'

# # global variables
# SAVE_EVERY_X = 2
# session_type = 'text'
# names = {"AI_name": AI_name, "username": username}

# def main():

#     # initialize session variables
#     conversation_history = []
#     message_counter = 1
#     message_memory = []

#     # objects
#     ui = TextInterface(session_type, AI_name, username)
#     ai = OpenAIGPT_3_5(AI_name, username)

#     # ai initiates conversation
#     initial_response = ai.get_response(conversation_history, context='')
#     ui.print_ai_output(initial_response)
#     conversation_history.append({"role": "assistant", "content": initial_response})

#     while True:

#         # get user message, update conversation
#         user_message = ui.get_user_input(conversation_history)
#         conversation_history.append({"role": "user", "content": user_message})

#         # analyze the context and determine intent (latest 6 messages)
#         conversation_snippet = conversation_history[-6:] if len(conversation_history) >= 6 else conversation_history
#         intention = context_analyzer.analyze_context(conversation_snippet)

#         # if more context is needed, call a function
#         if intention:
#             context = context_analyzer.parse_func(intention, conversation_history[-1:][0])
#             print(f'context: {context}') # debug
#             response = ai.get_response(conversation_history[-6:], context=context)
#         # otherwise, continue regular conversation
#         else:
#             response = ai.get_response(conversation_history[-6:], context='')

#         # print ai response, update conversation
#         ui.print_ai_output(response)
#         conversation_history.append({"role": "assistant", "content": response})

#         # updates long-term memory every 2 message cycles
#         if message_counter >= SAVE_EVERY_X:
#             print(f'message memory: {message_memory}') # debug
#             important = utilities.summarize(message_memory, AI_name, username)
#             if important.lower().strip() == 'false':
#                 print("message not saved (not important).") # debug
#             elif important:
#                 long_term_memory.save_memory((important,))
#                 print("message saved.") # debug
#             else:
#                 print("message not saved.") # debug
#             message_counter = 0
#             message_memory.clear()
#         else:
#             message_counter += 1
#             message_memory.append(
#                 f'{AI_name}: {response}, "{username}": {user_message}')



# if __name__ == '__main__':
#     main()
#     long_term_memory.save_database_txt()


# session = {'user_timezone': 'America/Vancouver'}

# from datetime import datetime, timezone
# import pytz

# # Step 1: Get the current time in UTC
# current_time_utc = datetime.now(timezone.utc)

# # Assuming user_timezone is retrieved from the session
# user_timezone = session.get('user_timezone')

# # Step 2: Convert the current time to the user's timezone
# if user_timezone:
#     user_timezn = pytz.timezone(user_timezone)
#     current_time_user = current_time_utc.astimezone(user_timezn)
#     formatted_time = current_time_user.strftime("%Y-%m-%d %H:%M:%S")
#     print(f"Current time in user's timezone: {current_time_user}")
# else:
#     print("Error: User timezone not set.")

# conversation_history = [{'role': 'system', 'content': 'You are a helpful assistantYou have the ability to interact with the user\'s calendar and email. Provided context for this conversation: ["Summarize and do not omit any events. User\'s calendar has returned the following events: ", {\'start\': \'2024-05-16\', \'event\': \'Simplify Subscripton\'}, {\'start\': \'2024-05-16T09:00:00-07:00\', \'event\': \'COMM 335 921\'}, {\'start\': \'2024-05-16T13:00:00-07:00\', \'event\': \'COMM 204 922\'}]. \n        Your response: '}, {'role': 'assistant', 'content': 'I currently see the following event on your calendar for today:\n\n1. Event: COMM 204 922\n   - Start Time: Today at 13:00 (1:00 PM)\n\nIf you have any more questions or need further assistance, feel free to let me know!'}, {'role': 'user', 'content': "What's on my calendar for tomorrow?"}, {'role': 'assistant', 'content': 'I currently see the following event on your calendar for tomorrow:\n\n1. Event: COMM 335 - Class Exercise\n   - Date: Tomorrow\n\nIf you have any more questions or need further assistance, feel free to let me know!'}, {'role': 'user', 'content': "What's on my Calendar for August 30?"}, {'role': 'assistant', 'content': 'I am currently seeing the following event on your calendar for August 30:\n\n1. Event: COMM 335 - Group Presentation\n   - Date: August 30\n\nIf you have any more questions or need further assistance, feel free to let me know!'}, {'role': 'user', 'content': 'Check my calendar for tomorrow?'}]
# item = conversation_history[-1]['content']
# context = "You have 3 new emails"
# new_item = item + f" Provided context for this conversation: {context}."
# print(new_item)

import openai
from pinecone import Pinecone
import os
import uuid

client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))

class PineconeMemory:
    def __init__(self):
        self.db = self.setup_memory()

    # Purpose: initializes Pinecone client w/ user index
    # Input: None
    # Output: index (pinecone index object)
    def setup_memory(self):
        
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

        # if index_name not in pinecone.list_indexes():
        #     pinecone.create_index(name=index_name, metric="cosine", dimension=1536)

        index_name = "user-pool"
        index = pc.Index(index_name)

        return index

    # Purpose: return embeddings of the given text
    # Input: text (str)
    # Output: response (dict)
    def get_embedding(self, text):
        response = client.embeddings.create(input=text, model="text-embedding-3-small")
        print(f"Total Tokens (embeddings): {response.usage.total_tokens}")
        return response.data[0].embedding

    # Purpose: searches vectordb for similar text to the query and returns it
    # Input: collection_id (str), query (str)
    # Output: context (list)
    def search_memory(self, namespace, query):
        # vectorize the query
        query_vector = self.get_embedding(query)
        with open("save.txt", "w") as f:
            f.write(str(query_vector))
        # query vectordb
        results = self.db.query(
            namespace=str(namespace),
            vector=query_vector,
            top_k=3,
            include_values=False,
            include_metadata=True,
        )
        
        context = [match['metadata']['text'] for match in results['matches']]
        return context

    # Purpose: saves memory to vectordb
    # Input: namespace, memory (list)
    # Output: status (boolean)
    def save_memory(self, namespace, memory):
        try:
            vectors = [{"id": str(uuid.uuid4()), "values": self.get_embedding(memory), "metadata": {"text": memory}}]
            self.db.upsert(vectors=vectors, 
                           namespace=str(namespace))
            return True
        except Exception as e:
            print(f'MemoryError: {e}')
            return False

pinecone_client = PineconeMemory()

context = pinecone_client.search_memory("2", "what does Marshall have to do at 12:00pm?")

print(f'Context: {context}')