from openai import OpenAI
import json

client = OpenAI()
name = "hilbert"

messages = [{"role": "system", "content": "You are Mira-Chan, a cute anime girl."},
            {"role": "user", "content": f"I have a meeting with {name} tomorrow. Can you book that for me?"}]

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

response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            functions=functions,
            function_call="auto",
)

print(response.choices[0].finish_reason)
print(response.choices[0].message.function_call)
print(response.choices[0].message.tool_calls)
print(json.loads(response.choices[0].message.function_call.arguments).get('event'))


# print(response.choices[0].finish_reason) -- determine whether function call or regular conversation
# print(response.choices[0].message.function_call) -- for custom functions
# print(response.choices[0].message.tool_calls) -- for openAI tools  (?)



# first choice
# response.choices[0]
# Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content="Hello! It's nice to meet you! How can I help you today, dear user?", role='assistant', function_call=None, tool_calls=None))

# finish_reason
# response.choices[0].finish_reason

# function call/tool calls
# response.choices[0].message.function_call
# response.choices[0].message.tool_calls

# content
# response.choices[0].message.content