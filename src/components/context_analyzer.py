from openai import OpenAI
import json

from .memory import long_term_memory
from .calendar_service import user_calendar
from .email_service import user_email

''' Analyzes the context of conversations and determines the best course of action.

Currently supports
- long-term memory (vectordb)
- google calendar
- gmail

Future updates
- ...
'''


client = OpenAI()

# Analyzes context of user's message and decides whether to retrieve additional context
class ContextAnalyzer:
    context_model = "gpt-3.5-turbo-0613"
    classification_model = "gpt-3.5-turbo"

    def __init__(self):
        pass

    # for main conversation
    # conversation_history (list of dict) --> function_call OR false
    # analyzes user intention and triggers functions to retrieve additional context
    def analyze_context(self, conversation_history):
        # user_id will eventually become collection_id as each user can have multiple ai models
        '''
        Given the current conversation and the user's latest message, decide whether to:
            1. retrieve additional context from memory
            2. use utilities
            3. continue the conversation naturally
        '''

        print(f'conversation history: {conversation_history}')

        system_message = [{"role": "system",
                           "content": "Analyze the following conversation history, only if they are relevant. If no functions are called, always respond with 'false'. Do NOT write anything else."}, ]
        messages = system_message + conversation_history if conversation_history else system_message

        functions = [
            {
                # long-term memory retrieval
                "name": "remember",
                "description": '''Use this function when the user's most recent message:
                1. Mentions unknown entities (e.g. person, place, thing, event, etc.).
                2. References the user's personal life (e.g. family, hobbies, identity, job, etc.)
                3. Assumes prior knowledge (e.g. users uses phrases such as 'previously', 'you told me', 'last time')
                4. When you believe additional context will make the response more personalized.
                ''',
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Write a question based on the user's most recent message and conversation history to retrieve relevant information from a database. e.g. What is the user's name?",
                        },
                    },
                    "required": ["question"],
                },
            },
            {
                # when other features are used
                "name": "utilities",
                "description": '''Use this function when the user's most recent message:
                        1. Expresses a desire to fetch or search for information (e.g. find out, search, look up)
                        2. Seeks to record or recall personal tasks or events (e.g. schedule, remind, notify).
                        3. Requires information beyond your current knowledge, but can be retrieved from external sources (e.g. latest news, current weather, upcoming events, etc.)
                        4. Is a direct command to execute a task that you normally cannot (e.g. send an email)
                        ''',
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Determine the type of operation required to retrieve relevant information. "
                                           "you must be write either: email, notes, calendar, or others. Do NOT write anything else.",
                        },
                    },
                    "required": ["operation"],
                },
            }
        ]
        # create and call openai api w/ function calling
        response = client.chat.completions.create(
            model=self.context_model,
            messages=messages,
            functions=functions,
            function_call="auto",
        )

        print(f'Tokens used (context): {response.usage.total_tokens}')

        # if a function call is triggered
        if response.choices[0].finish_reason == 'function_call':
            func_info = response.choices[0].message.function_call
            print(f'function call activated: {func_info}')
            return func_info
        else:
            return False

    # execute the relevant function based on provided function call
    def parse_func(self, func_info, user_message, user_id):
        # user id --> collection_id (???))
        func_name = func_info.name
        func_args = func_info.arguments
        context = ''
        # retrieve memory from vectordb
        if func_name == 'remember':
            arg_data = json.loads(func_args)
            try:
                # just in case LLM hallucinates; we use explicit arguments
                query = arg_data.get('question')
            except:
                print(f'Could not extract one or more function arguments. Args: {func_args}')
                return context
            context = long_term_memory.search_memory(user_id, query)
            return context
        # call utilities
        elif func_name == 'utilities':
            context = self.call_utility(user_id, func_info, user_message)
        # function does not exist
        else:
            print(f'Function call {func_name} does not exist.')

        return context

    # further determine which utility function to call
    def call_utility(self, user_id, func_info, user_message):
        func_args = json.loads(func_info.arguments)
        function_name = func_args.get("operation")
        context = ''

        if function_name == 'email':
            context = context_analyzer.classify_email(user_id, user_message)
        elif function_name == 'calendar':
            context = context_analyzer.classify_calendar(user_id, user_message)
        elif function_name == 'notes':
            print(f'Operation: notes')
        elif function_name == 'others':
            print(f'Operation: others')
        else:
            print(f"The utility {function_name} does not exist")

        return context

    # further classifies calendar operation: reading events, creating events, or editing events
    def classify_calendar(self, user_id, user_message):
        # ???
        messages = [{"role": "system", "content": "You are Mira-Chan, a cute anime girl."},
                    user_message]
        functions = [
            {
                "name": "read_calendar",
                "description": '''Use this function when the user's most recent message:
                             1. Explicitly asks to check schedule, calendar, or availability.
                             2. Asks about events on specific dates or times (e.g. today, tomorrow, this week, next week, on [specific date])
                             3. Indicates desire to be informed or reminded of upcoming events, tasks, or appointments.
                             ''',
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event": {
                            "type": "string",
                            "description": "The task, appointment, or event to read from the user's calendar. e.g. Lunch meeting with John",
                        },
                        "date": {
                            "type": "string",
                            "description": '''Extract the explicit or implicit date of the event. Output the result in one of the following formats:
                             1. Today, Tomorrow
                             2. This week, next week
                             3. If is a current day of the week, then format as: C:[day of the week] (e.g. 'this Thursday' will be formatted as C:Thursday).
                             4. If on a day of the week in the next week, then format as: F:[day of the week] (e.g. 'next Tuesday' will be formatted as F:Tuesday)
                             5. If none of the above apply, and message contains mention of a month, then format as: S:[first 3 characters of the month] [day] (e.g. 'August 3rd' will be formatted as S:Aug 3)''',
                        },
                        "time": {
                            "type": "string",
                            "description": "The time range of the event. e.g. 2:00pm - 3:00pm",
                        },
                    },
                    "required": ["date"],
                },
            },
            {
                "name": "write_calendar",
                "description": '''Use this function when the user's most recent message:
                                 1. Asks to schedule/add/book events on specific dates and times.
                                 2. Explicitly or implicitly suggest the initiation of a new task, event, or appointment.
                                 ''',
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event": {
                            "type": "string",
                            "description": "The task, appointment, or event to add to the user's calendar. e.g. Lunch meeting with John",
                        },
                        "date": {
                            "type": "string",
                            "description": '''Extract the explicit or implicit date of the event. Output the result in one of the following formats:
                             1. Today, Tomorrow
                             2. This week, next week
                             3. If is a current day of the week, then format as: C:[day of the week] (e.g. 'this Thursday' will be formatted as C:Thursday).
                             4. If on a day of the week in the next week, then format as: F:[day of the week] (e.g. 'next Tuesday' will be formatted as F:Tuesday)
                             5. If none of the above apply, and message contains mention of a month, then format as: S:[first 3 characters of the month] [day] (e.g. 'August 3rd' will be formatted as S:Aug 3)''',
                        },
                        "time": {
                            "type": "string",
                            "description": '''The time range of the event (if applicable). 
                                               If only start time is provided, return start time.
                                               If only duration is provided, don't return anything.
                                               e.g. 2:00pm - 3:00pm''',
                        },
                    },
                    # highlight parameters that are required, more likely to be generated
                    "required": ["event", "date"],
                },
            },
        ]
        # create and call function calling
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            functions=functions,
            function_call="auto",  # auto is default, but we'll be explicit
        )
        print(response)

        # parsing function call
        if response.choices[0].finish_reason == 'function_call':
            func_info = response.choices[0].message.function_call
            func_name = func_info.name
            if func_name == 'read_calendar':
                context = user_calendar.read_calendar(user_id, func_info.arguments)
            elif func_name == 'write_calendar':
                context = user_calendar.write_calendar(user_id, func_info.arguments)
            else:
                context = ''

            return context

    # further classifies email operations: reading emails, writing emails, replying to emails, etc.
    def classify_email(self, user_id, user_message):
        # test whether changing this system message matters (???)
        messages = [{"role": "system", "content": "You are Mira-Chan, a cute anime girl."},
                    user_message]
        functions = [
            {
                "name": "read_email",
                "description": '''Use this function when the user's most recent message:
                             1. Explicitly asks to check or read emails (e.g. do I have any new emails, can you check my inbox?).
                             2. Inquires about specific emails or email subjects (e.g. Is there an email from John?)
                             3. Requests summaries or updates on recent emails
                             4. Asks for information contained in an email
                             ''',
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sender_name": {
                            "type": "string",
                            "description": "The name of person whose emails the user is interested in. e.g. John",
                        },
                        "date": {
                            "type": "string",
                            "description": '''Extract the explicit or implicit date of the email. Output the result in one of the following formats:
                             1. Today, Tomorrow
                             2. This week, next week
                             3. If is a current day of the week, then format as: C:[day of the week] (e.g. 'this Thursday' will be formatted as C:Thursday).
                             4. If on a day of the week in the next week, then format as: F:[day of the week] (e.g. 'next Tuesday' will be formatted as F:Tuesday)
                             5. If none of the above apply, and message contains mention of a month, then format as: S:[first 3 characters of the month] [day] (e.g. 'August 3rd' will be formatted as S:Aug 3)''',
                        },
                    },
                    "required": ["date"],
                },
            },
            {
                "name": "write_email",
                "description": '''Use this function when the user's most recent message:
                                 1. Explicitly requests to send an email (e.g. Can you send an email to...)
                                 2. Mentions composing or drafting an email
                                 3. Includes phrases indicating the intent to communicate via email
                                 4. Provides specific details typically included in an email, such as subject, recipient's address, or message body
                                 ''',
                "parameters": {
                    "type": "object",
                    "properties": {
                        # for now, it's the recipient email (???)
                        "recipient": {
                            "type": "string",
                            "description": "The email address of the recipient. e.g. john@example.com",
                        },
                        "subject": {
                            "type": "string",
                            "description": '''The subject line of the email. e.g., Meeting Schedule Confirmation''',
                        },
                        "message_body": {
                            "type": "string",
                            "description": '''The main content of the email. e.g., Dear John, I would like to confirm our meeting...''',
                        },
                    },
                    # highlight parameters that are required, more likely to be generated
                    "required": ["recipient", "message_body"],
                },
            },
        ]
        # create and call function calling
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            functions=functions,
            function_call="auto",  # auto is default, but we'll be explicit
        )
        print(response)

        # parsing function call
        context = ''
        if response.choices[0].finish_reason == 'function_call':
            func_info = response.choices[0].message.function_call
            func_name = func_info.name
            if func_name == 'read_email':
                print("read email ***")
                context = user_email.read_email(user_id, func_info.arguments)
            elif func_name == 'write_email':
                context = user_email.write_email(user_id, func_info.arguments)

        return context

    def emotion_classifier(self, text):
        prompt = f'''You are an expert on emotion classification. Analyze the provided text. Which of the following emotions is exhibited by the speaker (CHOOSE ONE): neutral, angry, cheerful, excited, friendly, hopeful, sad, shouting, terrified, unfriendly, whispering.

        Examples
        Text: The weather today will be partly cloudy with a high of 75 degrees Fahrenheit. No rain is expected.
        Emotion: Default
        
        Text: I cannot believe this! The same error again? This is unacceptable. We need to address this issue immediately.
        Emotion: Angry

        Text: {text}
        Emotion: '''

        system_prompt = [{"role": "system", "content": prompt}]

        messages = system_prompt

        # make openAI API call
        response = client.chat.completions.create(
            model=self.classification_model,
            messages=messages,
        )

        # parse response
        message = response.choices[0].message.content
        print(f'Tokens used (response): {response.usage.total_tokens}')

        return message


context_analyzer = ContextAnalyzer()


# Improvements to EmailClassifier
# read_email
# - search by subject
# - search by keyword
# write_email
# - search recipient from contacts
# - draft emails using AI
# reply_email -- coming soon!