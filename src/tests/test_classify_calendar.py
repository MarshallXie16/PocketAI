import unittest
import json
from src.components.context_analyzer import ContextAnalyzer
from src.utils.AI_model_client import openai_client
class TestContextAnalyzerCalendar(unittest.TestCase):

    def setUp(self):
        self.analyzer = ContextAnalyzer()

    def classify_and_print(self, user_message):
        result = self.classify_calendar(user_message)
        if result:
            function_name = result.name
            function_args = json.loads(result.arguments)
            print(f"Function: {function_name}, Arguments: {function_args}")
        else:
            print("No context retrieved")
        return result

    def classify_calendar(self, user_message):
        messages = [{"role": "system", "content": "Classify the user's intention."},
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

        if response.choices[0].finish_reason == 'function_call':
            func_info = response.choices[0].message.function_call
            return func_info
        else:
            return False

    # Test cases for read calendar function
    def test_read_calendar_today(self):
        user_message = {"role": "user", "content": "What's on my schedule today?"}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'read_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["date"], "Today")

    def test_read_calendar_tomorrow(self):
        user_message = {"role": "user", "content": "Do I have anything scheduled for tomorrow?"}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'read_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["date"], "Tomorrow")

    def test_read_calendar_this_week(self):
        user_message = {"role": "user", "content": "What's on my calendar for this week?"}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'read_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["date"], "This week")

    def test_read_calendar_next_week(self):
        user_message = {"role": "user", "content": "What do I have on my schedule next week?"}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'read_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["date"], "Next week")

    def test_read_calendar_next_thursday(self):
        user_message = {"role": "user", "content": "What do I have for next Thursday?"}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'read_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["date"], "F:Thursday")

    def test_read_calendar_specific_date(self):
        user_message = {"role": "user", "content": "What's scheduled for the 3rd of august?"}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'read_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["date"], "S:Aug 3")

    # Test cases for write calendar function
    def test_write_calendar_specific_time(self):
        user_message = {"role": "user", "content": "I have a meeting with John on August 3rd at 2pm."}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'write_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["event"], "meeting with John")
        self.assertEqual(arguments["date"], "S:Aug 3")
        self.assertEqual(arguments["time"], "2:00pm")

    def test_write_calendar_no_time(self):
        user_message = {"role": "user", "content": "Add a reminder to go shopping this Saturday."}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'write_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["event"], "reminder to go shopping")
        self.assertEqual(arguments["date"], "C:Saturday")
        self.assertNotIn("time", arguments)

    def test_write_calendar_with_duration(self):
        user_message = {"role": "user", "content": "Schedule a 2-hour appointment with my tutor on Friday."}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'write_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["event"], "2-hour appointment with my tutor")
        self.assertEqual(arguments["date"], "C:Friday")
        self.assertNotIn("time", arguments)

    def test_write_calendar_generic_event(self):
        user_message = {"role": "user", "content": "Can you mark down our block party for September 5th?"}
        result = self.classify_and_print(user_message)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'write_calendar')
        arguments = json.loads(result.arguments)
        self.assertEqual(arguments["event"], "Block Party")
        self.assertEqual(arguments["date"], "S:Sep 5")
        self.assertNotIn("time", arguments)

if __name__ == '__main__':
    unittest.main()
