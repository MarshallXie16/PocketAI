import json

from src.utils.AI_model_client import openai_client
from src.components.memory import long_term_memory
from src.components.calendar_service import user_calendar
from src.components.email_service import user_email

""" Analyzes the context of conversations and determines the best course of action.

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
"""


class ContextAnalyzer:
    # TODO: move configurations to config.py
    context_model = "gpt-4o-mini"
    classification_model = "gpt-4o-mini"
    context_analyzer_model = "gpt-3.5-turbo"  # keep at 3.5 turbo for consistency

    def __init__(self):
        pass

    # Purpose: Analyzes context of conversation and determines whether to:
    # 1. Retrieve additional context from memory
    # 2. Use utilities
    # 3. Continue the conversation naturally
    # Input: conversation_history (list of dict) --> context (function call) OR false
    # Output: analyzes user intention and triggers functions to retrieve additional context
    def analyze_context(self, conversation_history):

        system_message = [
            {
                "role": "system",
                "content": "You are a helpful assistant with access to a variety of tools to retrieve more information. Analyze the following conversation and determine which functions to call, if any. If the user's intentions are not clear, ask to confirm (but not explicitly). If you're not sure about anything, ask the user. If no functions are called AND no clarification is needed, always respond with 'false'. Do NOT write anything else.",
            }
        ]
        messages = (
            system_message + conversation_history
            if conversation_history
            else system_message
        )

        functions = [
            {
                "name": "remember",
                "description": """Use this function to retrieve relevant memories to provide more personalized responses. 
                You should call this function when the user's messages: 
                    1. Mentions unknown people, places, events, or things 
                    2. Refers to the user's personal life (e.g. family, hobbies, preferences, habits, experiences) 
                    3. Assumes prior knowledge (e.g. user uses phrases such as 'we discussed previously', 'remember when', 'last time') 
                    4. Additional context from past conversations would enable a personalized response. 
                    
                Do NOT use for: 
                    1. Information that can be retrieved from the calendar 
                    2. General knowledge unrelated to the user 
                    3. Current events or real-time data 
                    4. Sensitive personal data (e.g., passwords, financial details)""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Create a specific, context-aware question based on the user's messages and conversation history. This will be run against the database to retrieve relevant memories.",
                        }
                    },
                    "required": ["question"],
                },
            },
            {
                # other features
                "name": "utilities",
                "description": """Use this function when the user's most recent message:
                        1. Expresses a desire to fetch or search for information (e.g. find out, search, look up)
                        2. Seeks to record or recall personal tasks or events (e.g. schedule, remind, notify).
                        3. Requires information beyond your current knowledge, but can be retrieved from external sources (e.g. latest news, current weather, upcoming events, etc.)
                        4. Is a direct command to execute a task that you normally cannot (e.g. send an email)
                        """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["email", "notes", "calendar", "others"],
                            "description": "Determine the type of operation required to retrieve relevant information. "
                            "you must be write either: email, notes, calendar, or others.",
                        },
                    },
                    "required": ["operation"],
                },
            },
        ]
        # create and call openai api w/ function calling
        response = openai_client.chat.completions.create(
            model=self.context_analyzer_model,
            messages=messages,
            functions=functions,
            function_call="auto",
        )

        print(f"Tokens used (analyze context): {response.usage.total_tokens}")

        # if a function call is triggered
        if response.choices[0].finish_reason == "function_call":
            func_info = response.choices[0].message.function_call
            print("---------------------------------")
            print(f"Function call: {func_info.name}")
            print(f"Operation: {func_info.arguments}")
            print("---------------------------------")
            return func_info, True
        else:
            print("---------------------------------")
            print("No Functions Called")
            print("---------------------------------")
            message = response.choices[0].message.content

            # no clarification is needed, continue conversation
            if message.strip().lower() == "false":
                return False, False
            # clarification is needed
            else:
                return message, False

    # Purpose: execute the relevant function based on provided function call
    # Input: func_info (dict), latest_messages (list of dict), user_id (int)
    # Output: context (str)
    def parse_func(self, func_info, latest_messages, user_id, ai_id, system_info):
        func_name = func_info.name
        func_args = func_info.arguments
        context = ""

        # retrieve memory from vectordb
        if func_name == "remember":
            arg_data = json.loads(func_args)
            try:
                # just in case LLM hallucinates; we use explicit arguments
                query = arg_data.get("question")
                context = long_term_memory.search_memory(user_id, ai_id, query)
            except:
                print(f"Could not retrieve memory for query: {query}")
            return context, [func_name]
        # call utilities
        elif func_name == "utilities":
            context, function_log = self.classify_utility(
                user_id, func_info, latest_messages, system_info
            )
        # function does not exist
        else:
            print(f"Function call {func_name} does not exist.")

        # update function log
        function_log.append(func_name)

        return context, function_log

    # Purpose: further determine which utility function to call
    # Input: user_id (int), func_info (dict), latest_messages (list of dict)
    # Output: context (str)
    def classify_utility(self, user_id, func_info, lastest_messages, system_info):
        func_args = json.loads(func_info.arguments)
        function_name = func_args.get("operation")
        context = ""
        function_log = None

        if function_name == "email":
            context, function_log = context_analyzer.classify_email(
                user_id, lastest_messages, system_info
            )
        elif function_name == "calendar":
            context, function_log = context_analyzer.classify_calendar(
                user_id, lastest_messages, system_info
            )
        elif function_name == "notes":
            pass
        elif function_name == "others":
            pass
        else:
            print(f"The utility {function_name} does not exist")

        # update function log
        function_log.append(function_name)

        return context, function_log

    # Purpose: further classifies calendar operation: reading events, creating events, or editing events
    # Input: user_id (int), latest_messages (list of dict)
    # Output: context (str)
    # TODO: add system info
    def classify_calendar(
        self, user_id, latest_messages, system_info="Nothing to report"
    ):
        messages = [
            {
                "role": "system",
                "content": f"Analyze the user's messages and determine the user's intentions. System info: {system_info}",
            }
        ] + latest_messages
        functions = [
            {
                "name": "read_calendar",
                "description": "Use this function when the user's messages indicates a need to retrieve calendar information, such as: 1. Explicitly asking to check schedule, calendar, or availability. 2. Asks about events on specific dates or times (e.g. today, tomorrow, this week, next week, on specific date) 3. Requesting information about upcoming events, tasks, or appointments. 4. Asking about free time or busy periods.",
                "parameters": {
                    "type": "object",
                    "required": ["query_type", "date_reference"],
                    "properties": {
                        "query_type": {
                            "enum": ["list_events", "check_availability", "find_event"],
                            "type": "string",
                            "description": "The type of calendar query. list_events: Lists all calendar events for a specified date and/or time range. find_event: Searches calendar for events matching a keyword or phrase. check_availability: returns a list of available times within a specified date and/or time range.",
                        },
                        "date_reference": {
                            "enum": [
                                "today",
                                "tomorrow",
                                "yesterday",
                                "this week",
                                "next week",
                                "last week",
                                "specific_date",
                            ],
                            "type": "string",
                            "description": "The reference point for the date query. Choose from only available options.",
                        },
                        "day_of_week": {
                            "enum": [
                                "monday",
                                "tuesday",
                                "wednesday",
                                "thursday",
                                "friday",
                                "saturday",
                                "sunday",
                            ],
                            "type": "string",
                            "description": "If the query refers to a specific day of the week, specify it here. Use only when date_reference is either: this week, next week, or last week. Do NOT use otherwise.",
                        },
                        "specific_date": {
                            "type": "string",
                            "description": "If date_reference is a specific_date, provide it here in the format MMM DD (e.g. Aug 3).",
                        },
                        "time_range": {
                            "type": "string",
                            "description": "The time range of the event. If no time is specified, do NOT provide a time range. If only start time is provided, assume the event ends in 1 hour. Write in the format of 0:00xx - 0:00xx (e.g. 2:00pm - 3:00pm)",
                        },
                        "event_name": {
                            "type": "string",
                            "description": "If user is looking for a specific event, extract out the name of the event. e.g. meeting with John",
                        },
                    },
                },
            },
            {
                "name": "write_calendar",
                "description": "Use this function when the user's messages indicates a need to create new calendar events, such as: 1. Explicitly asking to schedule/book new events or appointments. 2. Setting up recurring events.",
                "parameters": {
                    "type": "object",
                    "required": ["event_type", "event_name", "date_reference"],
                    "properties": {
                        "event_type": {
                            "enum": ["single_event", "recurring_event"],
                            "type": "string",
                            "description": "Determine whether the event is one-time or recurring. If it isn't clear, set as single_event.",
                        },
                        "event_name": {
                            "type": "string",
                            "description": "The name of the event. If it isn't clear assign it a specific name based on the context of the conversation. e.g. Lunch meeting with John",
                        },
                        "date_reference": {
                            "enum": [
                                "today",
                                "tomorrow",
                                "this week",
                                "next week",
                                "specific_date",
                            ],
                            "type": "string",
                            "description": "The reference point for the date query.",
                        },
                        "day_of_week": {
                            "enum": [
                                "monday",
                                "tuesday",
                                "wednesday",
                                "thursday",
                                "friday",
                                "saturday",
                                "sunday",
                            ],
                            "type": "string",
                            "description": "If the query refers to a specific day of the week, specify it here. Use only when date_reference is either: this week, next week, or last week. Do NOT use otherwise.",
                        },
                        "specific_date": {
                            "type": "string",
                            "description": "If date_reference is specific_date, provide it here in the format MMM DD (e.g. Aug 3).",
                        },
                        "time_range": {
                            "type": "string",
                            "description": "The time range of the event, if applicable. If only start time is provided, assume the event ends in 1 hour. e.g. 2:00pm - 3:00pm",
                        },
                        "recurrence_frequency": {
                            "type": "string",
                            "enum": ["weekly", "monthly"],
                            "description": "The frequency of recurring events. Use only from available options. Use only if event_type is recurring_event.",
                        },
                    },
                },
            },
        ]
        # create and call function calling
        response = openai_client.chat.completions.create(
            model=self.context_model,
            messages=messages,
            functions=functions,
            function_call="auto",
        )

        # parsing function call
        if response.choices[0].finish_reason == "function_call":

            # print function call info
            print(f"Operation: {response.choices[0].message.function_call.name}")
            print(f"Arguments: {response.choices[0].message.function_call.arguments}")
            print(f"Total Tokens (calendar_classifier): {response.usage.total_tokens}")

            # parse function call
            func_info = response.choices[0].message.function_call
            func_name = func_info.name

            # TODO: temporary solution for gpt-4o-mini hallucinating function names
            if func_name in [
                "read_calendar",
                "find_event",
                "list_events",
                "check_availability",
            ]:
                context = user_calendar.read_calendar(user_id, func_info.arguments)
            elif func_name == "write_calendar":
                context = user_calendar.write_calendar(user_id, func_info.arguments)
            else:
                context = ""

            return context, [func_name]

        print(f"Question posed: {response.choices[0].message.content}")
        return response.choices[0].message.content, []

    # Purpose: further classifies email operations: reading emails, writing emails, replying to emails, etc.
    # Input: user_id (int), latest_messages (list of dict)
    # Output: context (str)
    def classify_email(self, user_id, latest_messages, system_info="Nothing to report"):
        messages = [
            {
                "role": "system",
                "content": "Identify the user's intention based on the conversation history.",
            }
        ] + latest_messages

        functions = [
            {
                "name": "read_email",
                "description": "Use this function when the user wants to read emails or search for specific emails in their inbox.",
                "parameters": {
                    "type": "object",
                    "required": ["operation_type", "date_reference"],
                    "properties": {
                        "operation_type": {
                            "enum": ["list_emails", "search_inbox"],
                            "type": "string",
                            "description": "The type of read email operation. list_emails: Returns a list of emails for a specified time range. search_inbox: Search all inboxes for specific emails based on date/time range, subject, and/or sender name.",
                        },
                        "date_reference": {
                            "enum": [
                                "today",
                                "yesterday",
                                "this week",
                                "last week",
                                "last month",
                                "this month",
                                "specific_date",
                            ],
                            "type": "string",
                            "description": "The reference point for the date query. If not clear, use this week as default.",
                        },
                        "day_of_week": {
                            "enum": [
                                "monday",
                                "tuesday",
                                "wednesday",
                                "thursday",
                                "friday",
                                "saturday",
                                "sunday",
                            ],
                            "type": "string",
                            "description": "If the query refers to a specific date o fthe week, specify it here. Use only when date_reference is this week or last week.",
                        },
                        "specific_date": {
                            "type": "string",
                            "description": "If date_reference is specific_date, provide it here in the format MMM DD (e.g. Aug 3).",
                        },
                        "time_range": {
                            "type": "string",
                            "description": "The time range for the query. If no time range is specified, do NOT provide a time range. If only start time is provided, assume 1 hour in duration. Format: HH:MMam/pm - HH:MMam/pm",
                        },
                        "sender_name": {
                            "type": "string",
                            "description": "The name of the sender to search for, if applicable.",
                        },
                        "subject": {
                            "type": "string",
                            "description": "The subject to search for, if applicable.",
                        },
                    },
                },
            },
            {
                "name": "write_email",
                "description": "Use this function when the user wants to draft a new email or reply to an existing email. ALWAYS call this function before you call send_email.",
                "parameters": {
                    "type": "object",
                    "required": ["operation_type", "recipient_name", "content"],
                    "properties": {
                        "operation_type": {
                            "enum": ["draft_email", "reply_email"],
                            "type": "string",
                            "description": "The type of write email operation. draft_email: Create a new email draft. reply: Reply to an existing email thread; use if an email_thread_id is present in chat history.",
                        },
                        "recipient_name": {
                            "type": "string",
                            "description": "The name of the email recipient.",
                        },
                        "recipient_email": {
                            "type": "string",
                            "description": "The email address of the recipient. Use only when provided.",
                        },
                        "subject": {
                            "type": "string",
                            "description": "The subject of the email, if applicable.",
                        },
                        "body": {
                            "type": "string",
                            "description": "The body content of the email.",
                        },
                        "email_thread_id": {
                            "type": "string",
                            "description": "The ID of the email thread being replied to, if applicable. Use only when operation_type is reply_email.",
                        },
                    },
                },
            },
            {
                "name": "send_email",
                "description": "Use this function ONLY when the user confirms to send a drafted email, or explicitly instructs to send an email. If any of the required arguments are not clear, do NOT use this function.",
                "parameters": {
                    "type": "object",
                    "required": ["operation_type", "recipient_name", "content"],
                    "properties": {
                        "operation_type": {
                            "enum": ["draft_email", "reply_email"],
                            "type": "string",
                            "description": "The type of write email operation. draft_email: Create a new email draft. reply: Reply to an existing email thread; use if an email_thread_id is present in chat history.",
                        },
                        "recipient_name": {
                            "type": "string",
                            "description": "The name of the email recipient.",
                        },
                        "recipient_email": {
                            "type": "string",
                            "description": "The email address of the recipient. Use only when the email is clearly provided. Do NOT try to guess the email.",
                        },
                        "subject": {
                            "type": "string",
                            "description": "The subject of the email, if applicable.",
                        },
                        "body": {
                            "type": "string",
                            "description": "The body content of the email.",
                        },
                        "email_thread_id": {
                            "type": "string",
                            "description": "The ID of the email thread being replied to, if applicable. Use only when operation_type is reply_email.",
                        },
                    },
                },
            },
        ]

        # create and call function calling
        response = openai_client.chat.completions.create(
            model=self.context_model,
            messages=messages,
            functions=functions,
            function_call="auto",  # TODO: only allow 1 function call at a time
        )

        # parsing function call
        context = ""
        if response.choices[0].finish_reason == "function_call":

            # print function call info
            print(f"Operation: {response.choices[0].message.function_call.name}")
            print(f"Arguments: {response.choices[0].message.function_call.arguments}")
            print(f"Total Tokens (email_classifier): {response.usage.total_tokens}")

            func_info = response.choices[0].message.function_call
            func_name = func_info.name
            # TODO: temporary solution for gpt-4o-mini hallucinating function names
            if func_name in ["read_email", "list_emails", "search_inbox"]:
                print("Operation: read_email")
                context = user_email.read_email(user_id, func_info.arguments)
            elif func_name in ["write_email", "draft_email", "reply_email"]:
                print("Operation: write_email")
                context = user_email.write_email(user_id, func_info.arguments)
            elif func_name in ["send_email"]:
                context = user_email.send_email(user_id, func_info.arguments)
            else:
                print(f"Not a valid function. Function name: {func_name}")

            return context, [func_name]

        return context, []

    # Purpose: classifies the emotion of the speaker based on the provided text
    # Input: text (str)
    # Output: emotion (str)
    def classify_emotion(self, text):
        prompt = f"""You are an expert on emotion classification. Analyze the provided text. Which of the following emotions is exhibited by the speaker (CHOOSE ONE): neutral, angry, cheerful, excited, friendly, hopeful, sad, shouting, terrified, unfriendly, whispering.

        Examples
        Text: The weather today will be partly cloudy with a high of 75 degrees Fahrenheit. No rain is expected.
        Emotion: Default
        
        Text: I cannot believe this! The same error again? This is unacceptable. We need to address this issue immediately.
        Emotion: Angry

        Text: {text}
        Emotion: """

        system_prompt = [{"role": "system", "content": prompt}]

        messages = system_prompt

        # make openAI API call
        response = openai_client.chat.completions.create(
            model=self.classification_model,
            messages=messages,
        )

        # parse response
        message = response.choices[0].message.content
        print(f"Tokens used (response): {response.usage.total_tokens}")

        return message


context_analyzer = ContextAnalyzer()
