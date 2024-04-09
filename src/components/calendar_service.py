import json
import os
import datetime
import pytz
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.utils.utils import utilities
from ..models.users import User
from ..models.google_user import GoogleUser
from ..models.message import Message
from ..utils.config import google_client_id, google_client_secret

'''Represents integration with google calendar API

Currently supports (???)
- reading calendar events
- creating calendar events

Future updates
- semantic event search
- more accurate time parsing
'''

# credentials
google_credentials_path = "C:/Users/Lyric/Downloads/basic-strata-382418-6f8ce922e875.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path
email_address = 'marshallxie16@gmail.com'

# represents a generic calendar
class Calendar:

    def __init__(self):
        self.my_calendar = GoogleCalendar()

    # parse function info for read_calendar operation
    def read_calendar(self, user_id, func_args):
        # extract event information
        args_data = json.loads(func_args)
        date = args_data.get('date')
        time = args_data.get('time')
        # search for event(s) on calendar
        list_of_events = self.my_calendar.read_calendar(user_id, date, time)

        return ["Please summarize the following events in character, focusing on most important events: "] + list_of_events

    # parse function info for write_calendar operation
    def write_calendar(self, user_id, func_args):
        args_data = json.loads(func_args)
        event = args_data.get('event')
        date = args_data.get('date')
        time = args_data.get('time')
        # create google calendar event(s)
        try:
            link = self.my_calendar.write_calendar(user_id, event, date, time)
        except Exception as e:
            print(f"Error {e}")
            return "Could not book event. Please try again later or contact support."
        return "Booking success! " + link


# represents a user's google calendar
class GoogleCalendar:

    # authenticate google calendar upon instantiation
    def __init__(self):
        pass

    # authenticates google calendar
    def authenticate(self, user_id):
        print(user_id)
        user = User.query.get(user_id)
        print(user)
        print(user.google_id)
        google_user = GoogleUser.query.filter_by(google_id=user.google_id).first()
        print(f'google user: {google_user}')
        print(f'google access token: {google_user.access_token}')
        if google_user and google_user.access_token:
            creds = Credentials(
                token=google_user.access_token,
                refresh_token=google_user.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=google_client_id,
                client_secret=google_client_secret)

            if creds.expired:
                print("request here")
                creds.refresh(Request())

            service = build('calendar', 'v3', credentials=creds)
            print(f'debug: {service}')
            return service
        else:
            # Handle case where tokens are not available
            return None



    # date (required), time (optional) --> list of events
    def read_calendar(self, user_id, date, time=''):

        ''' TO-DOs
        # Supported date formats: today, tomorrow, this week, next week, this thursday, next tuesday, on aug 3rd
        # future updates: add ability to return time given event name (semantic search; not direct match)
        # more potential update: support even more accurate search; down to the hour
        '''

        # authenticate user
        service = self.authenticate(user_id)

        # parse the date
        try:
            start_date, end_date = utilities.parse_date(date)
            # if a time is specified, only start date should be used
            if time:
                end_date = start_date
        except:
            print(f"DateError: Could not parse date {date}.")
            return []

        # parse the time (if applicable)
        if time:
            # convert time range to datetime object
            start_time, end_time = utilities.parse_time(time)
            if not start_time and not end_time:
                print(f'Could not parse time range.')
                start_time = end_time = datetime.timedelta(hours=0, minutes=0)
        else:
            # default time (00:00)
            start_time = end_time = datetime.timedelta(hours=0, minutes=0)

        vancouver = pytz.timezone('America/Vancouver')
        # format time in date string
        temp1 = start_date + start_time
        start = vancouver.localize(temp1).isoformat()
        temp2 = end_date + end_time
        end = vancouver.localize(temp2).isoformat()
        print(start, end)
        print(start_date)
        print(start_time)
        print(end_time)

        # fetch events
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime',
        ).execute()
        events = events_result.get('items', [])

        data = []
        # parse and print events
        if not events:
            print('No upcoming events found.')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])
            data.append({"start": start, "event": event['summary']})

        return data

    # event (required), date (required), time (optional) --> link to calendar event
    def write_calendar(self, user_id, event, date, time=''):

        service = self.authenticate(user_id)

        # defaults
        description = 'This is some placeholder description.'
        timeZone = 'America/Vancouver'

        # parse the event
        event = event.strip()

        # parse the date
        try:
            start_date, end_date = utilities.parse_date(date)
            if time:
                end_date = start_date
        except:
            print(f"DateError: Could not parse date {date}.")
            return ''

        # for testing purposes
        print(f'Event: {event}')
        print(f'Date: {start_date}, {end_date}')
        print(f'Time: {time}')

        # parse the time (if applicable)
        if time:
            # convert time range to datetime object
            start_time, end_time = utilities.parse_time(time)
            if not start_time and not end_time:
                print(f'Could not parse time range.')
                start_time = end_time = datetime.timedelta(hours=0, minutes=0)
        else:
            # create a manual datetime object
            start_time = end_time = datetime.timedelta(hours=0, minutes=0)

        vancouver = pytz.timezone('America/Vancouver')
        # format time in date string
        temp1 = start_date + start_time
        start = vancouver.localize(temp1).isoformat()
        temp2 = end_date + end_time
        end = vancouver.localize(temp2).isoformat()

        # Create a google calendar event object
        my_event = {
            'summary': event,
            'location': 'My Place',
            'description': description,  # custom descriptions coming soon!
            'start': {
                'dateTime': start,
                'timeZone': timeZone,  # PST time zone by default!
            },
            'end': {
                'dateTime': end,
                'timeZone': timeZone,
            },
        }

        # Add the event to google calendar
        calendar_id = 'primary'  # primary calendar by default (can be configured)
        print(f'debug: {service}')
        event = service.events().insert(calendarId=calendar_id, body=my_event).execute()
        link = event.get("htmlLink")
        print(f'Event created: {link}')

        return link


user_calendar = Calendar()
