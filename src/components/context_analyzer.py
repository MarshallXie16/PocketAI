import json

from src.utils.AI_model_client import openai_client
from src.components.memory import long_term_memory
from src.components.calendar_service import user_calendar
from src.components.email_service import user_email

''' Analyzes the context of conversations and determines the best course of action.

Available Methods
- analyze_context: Analyzes the context of the conversation and determines whether to retrieve additional context.
- parse_func: Executes the relevant function based on the provided function call.
- call_utility: Further determines which utility function to call.
- classify_calendar: Further classifies calendar operations: reading events, creating events, or editing events.
- classify_email: Further classifies email operations: reading emails, writing emails, replying to emails, etc.
- emotion_classifier: Classifies the emotion of the speaker based on the provided text.

Future updates
- Implement classifier for notes
- Add functions for editing events in calendar classifer
- Add function for replying to emails in email classifier

# Improvements to EmailClassifier
    # read_email
    # - search by subject
    # - search by keyword
    # write_email
    # - search recipient from contacts
    # - draft emails using AI
    # reply_email -- coming soon!
'''

class ContextAnalyzer:
    # TODO: move configurations to config.py
    context_model = "gpt-3.5-turbo"
    classification_model = "gpt-3.5-turbo"

    def __init__(self):
        pass

    # Purpose: Analyzes context of conversation and determines whether to:
        # 1. Retrieve additional context from memory
        # 2. Use utilities
        # 3. Continue the conversation naturally
    # Input: conversation_history (list of dict) --> context (function call) OR false
    # Output: analyzes user intention and triggers functions to retrieve additional context
    def analyze_context(self, conversation_history):

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
                # other features
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
        response = openai_client.chat.completions.create(
            model=self.context_model,
            messages=messages,
            functions=functions,
            function_call="auto",
        )

        print(f'Tokens used (analyze context): {response.usage.total_tokens}')

        # if a function call is triggered
        if response.choices[0].finish_reason == 'function_call':
            func_info = response.choices[0].message.function_call
            print(f'function call activated: {func_info.name}')
            print(f'Arguments: {func_info.arguments}')
            return func_info
        else:
            return False

    # Purpose: execute the relevant function based on provided function call
    # Input: func_info (dict), user_message (str), user_id (int)
    # Output: context (str)
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
                context = long_term_memory.search_memory(user_id, query)
            except:
                print(f'Could not extract one or more function arguments. Args: {func_args}')
            return context
        # call utilities
        elif func_name == 'utilities':
            context = self.classify_utility(user_id, func_info, user_message)
        # function does not exist
        else:
            print(f'Function call {func_name} does not exist.')

        return context

    # Purpose: further determine which utility function to call
    # Input: user_id (int), func_info (dict), user_message (str)
    # Output: context (str)
    def classify_utility(self, user_id, func_info, user_message):
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

    # Purpose: further classifies calendar operation: reading events, creating events, or editing events
    # Input: user_id (int), user_message (str)
    # Output: context (str)
    def classify_calendar(self, user_id, user_message):
        messages = [{"role": "system", "content": "You are Mira"},
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
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            functions=functions,
            function_call="auto",
        )
        print(f'Total Tokens (calendar_classifier): {response.usage.total_tokens}')

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

    # Purpose: further classifies email operations: reading emails, writing emails, replying to emails, etc.
    # Input: user_id (int), user_message (str)
    # Output: context (str)
    def classify_email(self, user_id, user_message):
        messages = [{"role": "system", "content": "You are Mira"},
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
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            functions=functions,
            function_call="auto",
        )
        print(f'Total Tokens (email_classifier): {response.usage.total_tokens}')

        # parsing function call
        context = ''
        if response.choices[0].finish_reason == 'function_call':
            func_info = response.choices[0].message.function_call
            func_name = func_info.name
            if func_name == 'read_email':
                print("read email ***")
                context = user_email.read_email(user_id, func_info.arguments)
                print("")
            elif func_name == 'write_email':
                context = user_email.write_email(user_id, func_info.arguments)

        return context

    # Purpose: classifies the emotion of the speaker based on the provided text
    # Input: text (str)
    # Output: emotion (str)
    def classify_emotion(self, text):
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
        response = openai_client.chat.completions.create(
            model=self.classification_model,
            messages=messages,
        )

        # parse response
        message = response.choices[0].message.content
        print(f'Tokens used (response): {response.usage.total_tokens}')

        return message

    
context_analyzer = ContextAnalyzer()