import datetime
import pytz
import re
from bs4 import BeautifulSoup

from src.utils.AI_model_client import openai_client

# contains useful functions
class Utilities:

    def __init__(self):
        self.utilities_model = "gpt-4o-mini"
        self.client = openai_client

    # TODO: update and provide documentation
    # summarize a snippet of conversation history for memory storage
    def summarize(self, messages, AI_name, username):
        prompt_template = f'''You are {AI_name} having a chat with {username}. Analyze this conversation snippet and determine if there's important information to remember.
        Examples of important information:
        1. New details about peoples, places, events, or things
        2. New information about {username}'s preferences, interests, or experiences
        3. Changes in {username}'s life or circumstances
        4. Emotional states or reactions that provide context for future conversations
        
        If important information is found:
        - summarize it in 50 words or less from the perspective of {AI_name}
        
        If no important information is found, respond with only the world 'false'.'''

        prompt = [{"role": "system", "content": prompt_template}, 
                  {"role": "user", "content": f"Conversation snippet: {messages}. Summary (if important): "}]

        # make openAI API call
        response = self.client.chat.completions.create(
            model=self.utilities_model,
            messages=prompt,
        )

        # parse response
        message = response.choices[0].message.content
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = date + " " + message if message.lower().strip() != 'false' else 'false'

        print(f'Tokens used (summarize): {response.usage.total_tokens}')
        print(f'Summary: {message}')

        return message

    # Purpose: summarize context retrieved from the user's calendar, email, or to-do list. Reduces overall burden on primary conversation model.
    # Input: context (large string)
    # Output: summary (string)
    def summarize_context(self, context):
        prompt_template = f'''You are a useful assistant. Below is a set of context retrieved from the user's calendar, email, or to-do list.
        Summarize and reorder the context in bullet point form, making sure not to omit any information. Filter out any obvious junk mail or spam.
        
        Context: {context}

        Your summary (in bullet points):'''

        prompt = [{"role": "system", "content": prompt_template}]

        # make openAI API call
        response = self.client.chat.completions.create(
            model=self.utilities_model,
            messages=prompt,
        )

        # parse response
        summarized_context = response.choices[0].message.content

        print(f'Tokens used (summarize context): {response.usage.total_tokens}')
        print(f'Context Summary: {summarized_context}')

        return summarized_context

    # # Purpose: parses date and returns a datetime object
    # # Input: date (string), timezone (string)
    # # Output: start_date, end_date (datetime objects)
    # def parse_date(self, input_date, timezone='America/Vancouver'):

    #     input_date = input_date.lower().strip()

    #     # localize to timezone
    #     local_tz = pytz.timezone(timezone)
    #     now = datetime.datetime.now(tz=local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

    #     start_date = None
    #     end_date = None
        
    #     if input_date == 'today':
    #         start_date = now
    #         end_date = start_date + datetime.timedelta(days=1)
    #     elif input_date == 'tomorrow':
    #         start_date = now + datetime.timedelta(days=1)
    #         end_date = start_date + datetime.timedelta(days=1)
    #     elif input_date == 'this week':
    #         start_date = now - datetime.timedelta(days=now.weekday())
    #         end_date = start_date + datetime.timedelta(days=7)
    #     elif input_date == 'next week':
    #         start_date = now + datetime.timedelta(days=7-now.weekday())
    #         end_date = start_date + datetime.timedelta(days=7)
    #     elif input_date.startswith('c:'):
    #         day_of_week = input_date[2:]
    #         start_date, end_date = self.get_date_for_day(now, day_of_week)
    #     elif input_date.startswith('f:'):
    #         day_of_week = input_date[2:]
    #         start_date, end_date = self.get_date_for_day(now, day_of_week, next_week=True)
    #     elif input_date.startswith('s:'):
    #         # S:Sep 10 -> ["S", "Sep 10"]
    #         _, date_part = input_date.split(':')  
    #         # Sep 10 -> ["Sep", "10"]
    #         month_abbr, day = date_part.split()  
    #         day = int(day)

    #         # map month to number
    #         months = {
    #             "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    #             "may": 5, "jun": 6, "jul": 7, "aug": 8,
    #             "sep": 9, "oct": 10, "nov": 11, "dec": 12
    #         }
    #         month = months.get(month_abbr)

    #         # check if valid month 
    #         if month is None:
    #             raise ValueError("Invalid month abbreviation")

    #         year = now.year # TODO: handle different years
    #         start_date = datetime.datetime(year, month, day, tzinfo=local_tz)
    #         end_date = start_date + datetime.timedelta(days=1)
    #     else:
    #         raise ValueError("Invalid date format")
        
    #     # set to naive timezone
    #     if start_date.tzinfo is not None:
    #         start_date = start_date.replace(tzinfo=None)
    #     if end_date.tzinfo is not None:
    #         end_date = end_date.replace(tzinfo=None)
        
    #     return start_date, end_date

    # # Purpose: get a datetime object for a specific day of the week
    # # Input: current_date (datetime object), day_of_week (string), next_week (boolean)
    # # Output: start_date, end_date (datetime objects)
    # def get_date_for_day(self, current_date, day_of_week, next_week=False):
    #     day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    #     # Monday is 0, Sunday is 6
    #     current_day_index = current_date.weekday()  
    #     target_day_index = day_names.index(day_of_week)

    #     # calculate the difference in days to target day
    #     days_difference = target_day_index - current_day_index

    #     # e.g. today is sunday, target day is monday: 0 - 6 = -6 --> move back 6 days
    #     # e.g. today is tuesday, target day is friday: 4 - 1 = 3 --> move forward 3 days
    #     start_date = current_date + datetime.timedelta(days=days_difference)

    #     # if looking for next week, add 7 days
    #     if next_week:
    #         start_date += datetime.timedelta(days=7)

    #     start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    #     end_date = start_date + datetime.timedelta(days=1) # for 1 whole day

    #     return start_date, end_date

    # # Purpose: parses time or time range and returns a timedelta object
    # # Input: time_range (string)
    # # Output: start_timedelta, end_timedelta (timedelta objects)
    # def parse_time(self, time_range):

    #     '''     

    #     Examples:
    #     - 2pm -> 14:00
    #     - 2:30pm -> 14:30
    #     - 2-3pm -> 14:00-15:00
    #     - 2:00pm - 3:00pm -> 14:00-15:00

    #     '''

    #     # Regex to extract time from string
    #     time_pattern = r'(\d+:\d+|\d+)(am|pm|AM|PM)'

    #     # Find all occurrences of the time pattern
    #     matches = re.findall(time_pattern, time_range)

    #     # If no matches, return None
    #     if not matches:
    #         return None, None

    #     # Convert the start time to a datetime object
    #     start_time_str = matches[0][0] + matches[0][1]  # e.g., 2:30pm
    #     start_time = datetime.datetime.strptime(start_time_str, '%I:%M%p')

    #     # Calculate the timedelta for the start_time from midnight
    #     start_timedelta = datetime.timedelta(hours=start_time.hour, minutes=start_time.minute)

    #     # If end time is not provided, assume it's 1 hour from the start time
    #     if len(matches) == 1:
    #         end_timedelta = start_timedelta + datetime.timedelta(hours=1)
    #     else:
    #         # Convert the end time to a datetime object
    #         end_time_str = matches[1][0] + matches[1][1]  # e.g., 3:30pm
    #         end_time = datetime.datetime.strptime(end_time_str, '%I:%M%p')

    #         # Calculate the timedelta for the end_time from midnight
    #         end_timedelta = datetime.timedelta(hours=end_time.hour, minutes=end_time.minute)

    #     print(start_timedelta, end_timedelta)
    #     return start_timedelta, end_timedelta

    def parse_date(self, date_reference, day_of_week=None, specific_date=None, timezone='America/Vancouver'):
        local_tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz=local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

        if date_reference == 'today':
            start_date = now
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference == 'tomorrow':
            start_date = now + datetime.timedelta(days=1)
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference == 'yesterday':
            start_date = now - datetime.timedelta(days=1)
            end_date = start_date + datetime.timedelta(days=1)
        elif date_reference in ['this week', 'next week', 'last week']:
            if day_of_week:
                start_date, end_date = self.get_date_for_day(now, day_of_week, date_reference)
            else:
                week_offset = 0 if date_reference == 'this week' else (1 if date_reference == 'next week' else -1)
                start_date = now + datetime.timedelta(days=(7 * week_offset - now.weekday()))
                end_date = start_date + datetime.timedelta(days=7)
        elif date_reference == 'specific_date' and specific_date:
            start_date = self.parse_specific_date(specific_date, now.year, local_tz)
            end_date = start_date + datetime.timedelta(days=1)
        else:
            raise ValueError("Invalid date reference or missing required information")

        return start_date.replace(tzinfo=None), end_date.replace(tzinfo=None)

    def get_date_for_day(self, current_date, day_of_week, week_reference):
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_day_index = current_date.weekday()
        target_day_index = day_names.index(day_of_week.lower())

        days_difference = target_day_index - current_day_index
        if week_reference == 'next week':
            days_difference += 7
        elif week_reference == 'last week':
            days_difference -= 7

        start_date = current_date + datetime.timedelta(days=days_difference)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + datetime.timedelta(days=1)

        return start_date, end_date

    def parse_specific_date(self, specific_date, current_year, timezone):
        try:
            date_obj = datetime.datetime.strptime(f"{specific_date} {current_year}", "%b %d %Y")
            return timezone.localize(date_obj)
        except ValueError:
            raise ValueError(f"Invalid specific date format: {specific_date}. Expected format: MMM DD (e.g., Aug 3)")

    def parse_time_range(self, time_range):
        time_pattern = r'(\d+(?::\d+)?)\s*(am|pm|AM|PM)?(?:\s*-\s*(\d+(?::\d+)?)\s*(am|pm|AM|PM)?)?'
        match = re.match(time_pattern, time_range)

        if not match:
            raise ValueError(f"Invalid time range format: {time_range}")

        start_time = self.parse_time(match.group(1), match.group(2))
        
        if match.group(3):  # If end time is specified
            end_time = self.parse_time(match.group(3), match.group(4))
        else:
            end_time = (start_time + datetime.timedelta(hours=1)).time()

        return start_time, end_time

    def parse_time(self, time_str, meridiem):
        if ':' in time_str:
            hour, minute = map(int, time_str.split(':'))
        else:
            hour, minute = int(time_str), 0

        if meridiem and meridiem.lower() == 'pm' and hour != 12:
            hour += 12
        elif meridiem and meridiem.lower() == 'am' and hour == 12:
            hour = 0

        return datetime.time(hour, minute)

    def parse_html(self, html_content):
        """Helper function to parse HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        # Get text
        text = soup.get_text()
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(self.remove_repetitive_chars(chunk) for chunk in chunks if chunk)
        return text

    def remove_repetitive_chars(self, text):
        # Remove common HTML artifacts and control characters
        artifacts = [
            '\xad',    # soft hyphen
            '\u200b',  # zero-width space
            '\u200c',  # zero-width non-joiner
            '\u200d',  # zero-width joiner
            '\u2060',  # word joiner
            '\u0006',  # acknowledge
            '\u0007',  # bell
            '\u0008',  # backspace
            '\u000b',  # vertical tab
            '\u000c',  # form feed
            '\u001c',  # file separator
            '\u001d',  # group separator
            '\u001e',  # record separator
            '\u001f',  # unit separator
            '\u2002',  # en space
            '\u2003',  # em space
            '\u2004',  # three-per-em space
            '\u2005',  # four-per-em space
            '\u2006',  # six-per-em space
            '\u2007',  # figure space
            '\u2008',  # punctuation space
            '\u2009',  # thin space
            '\u200a',  # hair space
            '\u202f',  # narrow no-break space
            '\u205f',  # medium mathematical space
            '\u3000',  # ideographic space
        ]
        
        # Remove repeating artifacts
        for artifact in artifacts:
            text = re.sub(f'{re.escape(artifact)}{{2,}}', '', text)
        
        # Remove other repeating characters (more than 3 times in a row)
        text = re.sub(r'(.)\1{3,}', r'\1', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)
        
        return text

utilities = Utilities()