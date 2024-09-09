import unittest
from src.components.context_analyzer import ContextAnalyzer
import json

class TestContextAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = ContextAnalyzer()

    def analyze_and_print(self, conversation_history):
        result = self.analyzer.analyze_context(conversation_history)
        if result:
            function_name = result.name
            function_args = json.loads(result.arguments)
            print(f"Function: {function_name}, Arguments: {function_args}")
        else:
            print("No context retrieved")
        return result

    def test_no_context_retrieval(self):
        conversation_history = [
            {"role": "user", "content": "It's really sunny outside today."}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertFalse(result)

    def test_remember_unknown_entity(self):
        conversation_history = [
            {"role": "user", "content": "Can you remind me of what we discussed about my upcoming trip?"}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'remember')
        arguments = json.loads(result.arguments)
        self.assertIn("question", arguments)

    def test_utilities_email(self):
        conversation_history = [
            {"role": "user", "content": "Can you send an email to my manager about the project update?"}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'utilities')
        arguments = json.loads(result.arguments)
        self.assertIn("operation", arguments)
        self.assertEqual(arguments["operation"], 'email')

    def test_no_context_retrieval_personal_opinion(self):
        conversation_history = [
            {"role": "user", "content": "I'm feeling a bit tired today."}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertFalse(result)

    def test_remember_prior_knowledge(self):
        conversation_history = [
            {"role": "user", "content": "Last time, you mentioned a great book I should read. Can you remind me of the title?"}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'remember')
        arguments = json.loads(result.arguments)
        self.assertIn("question", arguments)

    def test_utilities_calendar(self):
        conversation_history = [
            {"role": "user", "content": "Add a dentist appointment to my calendar for next Friday at 10 AM."}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'utilities')
        arguments = json.loads(result.arguments)
        self.assertIn("operation", arguments)
        self.assertEqual(arguments["operation"], 'calendar')

    def test_remember_suggestion(self):
        conversation_history = [
            {"role": "user", "content": "I've been thinking about that advice you gave me regarding my job search."}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'remember')
        arguments = json.loads(result.arguments)
        self.assertIn("question", arguments)

    def test_utilities_notes(self):
        conversation_history = [
            {"role": "user", "content": "Can you make a note to call the plumber tomorrow?"}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'utilities')
        arguments = json.loads(result.arguments)
        self.assertIn("operation", arguments)
        self.assertEqual(arguments["operation"], 'notes')

    def test_remember_recipe(self):
        conversation_history = [
            {"role": "user", "content": "Can you recall the details of the recipe you gave me last week?"}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'remember')
        arguments = json.loads(result.arguments)
        self.assertIn("question", arguments)

    def test_utilities_todo_list(self):
        conversation_history = [
            {"role": "user", "content": "Add 'buy groceries' to my to-do list."}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'utilities')
        arguments = json.loads(result.arguments)
        self.assertIn("operation", arguments)
        self.assertEqual(arguments["operation"], 'notes')

    def test_unexpected_operation(self):
        conversation_history = [
            {"role": "user", "content": "Can you do something unexpected?"}
        ]
        result = self.analyze_and_print(conversation_history)
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
