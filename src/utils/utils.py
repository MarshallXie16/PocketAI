import datetime
import pytz
import re

from src.utils.AI_model_client import openai_client

# contains useful functions
class Utilities:

    def __init__(self):
        self.utilities_model = "gpt-3.5-turbo"
        self.client = openai_client

    # TODO: update and provide documentation
    # summarize a snippet of conversation history for memory storage
    def summarize(self, messages, AI_name, username):
        prompt_template = f'''You are {AI_name} having a chat with {username}. Based on the following conversation snippet, 
        determine whether there's important information to be remembered.
        Examples of important information:
        - mention of a person, place, event, or thing
        - new information about {username} and their preferences/interests
        If there is, summarize key information in 50 words or less, from first person perspective, as {AI_name}. 
        If there's no important information, write 'false' and stop.'''



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

    # Purpose: parses date and returns a datetime object
    # Input: date (string), timezone (string)
    # Output: start_date, end_date (datetime objects)
    def parse_date(self, input_date, timezone='America/Vancouver'):

        input_date = input_date.lower().strip()

        # localize to timezone
        local_tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz=local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

        start_date = None
        end_date = None
        
        if input_date == 'today':
            start_date = now
            end_date = start_date + datetime.timedelta(days=1)
        elif input_date == 'tomorrow':
            start_date = now + datetime.timedelta(days=1)
            end_date = start_date + datetime.timedelta(days=1)
        elif input_date == 'this week':
            start_date = now - datetime.timedelta(days=now.weekday())
            end_date = start_date + datetime.timedelta(days=7)
        elif input_date == 'next week':
            start_date = now + datetime.timedelta(days=7-now.weekday())
            end_date = start_date + datetime.timedelta(days=7)
        elif input_date.startswith('c:'):
            day_of_week = input_date[2:]
            start_date, end_date = self.get_date_for_day(now, day_of_week)
        elif input_date.startswith('f:'):
            day_of_week = input_date[2:]
            start_date, end_date = self.get_date_for_day(now, day_of_week, next_week=True)
        elif input_date.startswith('s:'):
            # S:Sep 10 -> ["S", "Sep 10"]
            _, date_part = input_date.split(':')  
            # Sep 10 -> ["Sep", "10"]
            month_abbr, day = date_part.split()  
            day = int(day)

            # map month to number
            months = {
                "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                "may": 5, "jun": 6, "jul": 7, "aug": 8,
                "sep": 9, "oct": 10, "nov": 11, "dec": 12
            }
            month = months.get(month_abbr)

            # check if valid month 
            if month is None:
                raise ValueError("Invalid month abbreviation")

            year = now.year # TODO: handle different years
            start_date = datetime.datetime(year, month, day, tzinfo=local_tz)
            end_date = start_date + datetime.timedelta(days=1)
        else:
            raise ValueError("Invalid date format")
        
        # set to naive timezone
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)
        
        return start_date, end_date

    # Purpose: get a datetime object for a specific day of the week
    # Input: current_date (datetime object), day_of_week (string), next_week (boolean)
    # Output: start_date, end_date (datetime objects)
    def get_date_for_day(self, current_date, day_of_week, next_week=False):
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        # Monday is 0, Sunday is 6
        current_day_index = current_date.weekday()  
        target_day_index = day_names.index(day_of_week)

        # calculate the difference in days to target day
        days_difference = target_day_index - current_day_index

        # e.g. today is sunday, target day is monday: 0 - 6 = -6 --> move back 6 days
        # e.g. today is tuesday, target day is friday: 4 - 1 = 3 --> move forward 3 days
        start_date = current_date + datetime.timedelta(days=days_difference)

        # if looking for next week, add 7 days
        if next_week:
            start_date += datetime.timedelta(days=7)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + datetime.timedelta(days=1) # for 1 whole day

        return start_date, end_date

    # Purpose: parses time or time range and returns a timedelta object
    # Input: time_range (string)
    # Output: start_timedelta, end_timedelta (timedelta objects)
    def parse_time(self, time_range):

        '''     

        Examples:
        - 2pm -> 14:00
        - 2:30pm -> 14:30
        - 2-3pm -> 14:00-15:00
        - 2:00pm - 3:00pm -> 14:00-15:00

        '''

        # Regex to extract time from string
        time_pattern = r'(\d+:\d+|\d+)(am|pm|AM|PM)'

        # Find all occurrences of the time pattern
        matches = re.findall(time_pattern, time_range)

        # If no matches, return None
        if not matches:
            return None, None

        # Convert the start time to a datetime object
        start_time_str = matches[0][0] + matches[0][1]  # e.g., 2:30pm
        start_time = datetime.datetime.strptime(start_time_str, '%I:%M%p')

        # Calculate the timedelta for the start_time from midnight
        start_timedelta = datetime.timedelta(hours=start_time.hour, minutes=start_time.minute)

        # If end time is not provided, assume it's 1 hour from the start time
        if len(matches) == 1:
            end_timedelta = start_timedelta + datetime.timedelta(hours=1)
        else:
            # Convert the end time to a datetime object
            end_time_str = matches[1][0] + matches[1][1]  # e.g., 3:30pm
            end_time = datetime.datetime.strptime(end_time_str, '%I:%M%p')

            # Calculate the timedelta for the end_time from midnight
            end_timedelta = datetime.timedelta(hours=end_time.hour, minutes=end_time.minute)

        print(start_timedelta, end_timedelta)
        return start_timedelta, end_timedelta


utilities = Utilities()