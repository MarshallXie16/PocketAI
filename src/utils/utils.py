from openai import OpenAI
import datetime
import pytz
import re


# contains useful functions
class Utilities:

    def __init__(self):
        self.utilities_model = "gpt-3.5-turbo"
        self.client = OpenAI()

    # summarize a snippet of conversation history for memory storage
    def summarize(self, messages, AI_name, username):
        prompt = f'''You are {AI_name} having a chat with {username}. Based on the following conversation snippet, 
        determine whether there's important information to be remembered.
        Examples of important information:
        - mention of a person, place, event, or thing
        - new information about {username} and their preferences/interests
        If there is, summarize key information in 50 words or less, from first person perspective, as {AI_name}. 
        If there's no important information, write 'false' and stop.

            Conversation snippet: {messages}.

            Summary (if important): '''

        system_prompt = [{"role": "system", "content": prompt}]

        # make openAI API call
        response = self.client.chat.completions.create(
            model=self.utilities_model,
            messages=system_prompt,
        )

        # parse response
        message = response.choices[0].message.content
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = date + " " + message if message.lower().strip() != 'false' else 'false'

        print(f'Tokens used (summarize): {response.usage.total_tokens}')
        print(f'Summary: {message}')

        return message

    # parses ambiguous dates and return as a datetime object
    def parse_date(self, user_input):
        # parses user input
        query = user_input.lower().strip()

        # localize time: convert date to PST
        utc_now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        pst_now = utc_now.astimezone(pytz.timezone('America/Vancouver'))
        now = datetime.datetime(year=pst_now.year, month=pst_now.month, day=pst_now.day)

        if query == 'today':
            start_date = now
            # exactly 24 hours from now (!!!)
            end_date = start_date + datetime.timedelta(days=1)
        elif query == 'tomorrow':
            start_date = now + datetime.timedelta(days=1)
            end_date = start_date + datetime.timedelta(days=1)
        elif query == 'yesterday':
            start_date = now - datetime.timedelta(days=1)
            end_date = now
        elif query == 'this week':
            start_date = now
            days_until_sun = 6 - now.weekday()
            end_date = now + datetime.timedelta(days=days_until_sun)
        elif query == 'next week':
            days_until_mon = 7 - now.weekday()
            start_date = now + datetime.timedelta(days=days_until_mon)
            end_date = start_date + datetime.timedelta(days=7)
        elif query == 'last week':
            days_since_last_mon = now.weekday()
            start_date = now - datetime.timedelta(days=days_since_last_mon + 7)
            end_date = start_date + datetime.timedelta(days=6)
        # matches days of the week (this week), e.g. This Tuesday
        elif query[:2] == 'c:':
            start = self.get_date_this_week(query, now)
            start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + datetime.timedelta(days=1)
        # matches days of the week (next week), e.g. Next Tuesday
        elif query[:2] == 'f:':
            start = self.get_date_this_week(query, now) + datetime.timedelta(days=7)
            start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + datetime.timedelta(days=1)
        # matches a specific date
        elif query[:2] == 'e:':
            months = {"jan": 1,
                      "feb": 2,
                      "mar": 3,
                      "apr": 4,
                      "may": 5,
                      "jun": 6,
                      "jul": 7,
                      "aug": 8,
                      "sep": 9,
                      "oct": 10,
                      "nov": 11,
                      "dec": 12}
            month = months.get(query[2:5])
            s = query[5:7]
            day = int(''.join([char for char in s if char.isdigit()]))
            year = datetime.datetime.now().year
            start_date = datetime.datetime(year, month, day)
            end_date = start_date + datetime.timedelta(days=1)
        else:
            return None, None

        return start_date, end_date

    # day_of_the_week (e.g. Monday), today's date --> datetime object
    def get_date_this_week(self, query, now):
        target_day = query[2:5]
        days_of_the_week = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        days_until_target_day = days_of_the_week.get(target_day) - now.weekday()
        if days_until_target_day < 0:
            days_until_target_day = 7 + days_until_target_day
        start = now + datetime.timedelta(days=days_until_target_day)
        return start

    # '2:00pm - 3:00pm' --> datetime object (OR '2:00pm' --> datetime object)
    def parse_time(self, time_range):
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


# add yesterday to parse dates