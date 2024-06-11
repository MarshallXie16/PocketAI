import json
import os
import pytz
import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from flask import session

from src.models.users import User
from src.models.google_user import GoogleUser
from src.models.message import Message

from src.utils.utils import utilities
from src.utils.extensions import db
from src.utils.auth import google

'''Represents integration with google calendar API

Currently supports
- Events on a specific date: What do I have today/tomorrow/this wednesday/next thursday/on aug 3rd?
- Events within time range on a specific date: What do I have between 2:00pm - 5:00pm today/this tuesday/next friday/on dec 25th?
- Events within a default date range: this week, next week
- creating single calendar event w/ specified date and time

Future updates
- more date options: yesterday, last thursday, date range (e.g. from aug 3rd to aug 5th)
- cross date time; what do I have from Tuesday at 5:00pm to Thursday at 3:00pm?
- semantic search; what do I have in the morning?
- event -> time (sematic); when is my meeting with Bob?
- date next year, previous year, etc.
- Events within specified date range: What do I have from aug 3rd to aug 5th?
- Different locations, descriptions, and calendars for events
- Create multiple events
- Create recurring events
'''

# TODO: centralize service objects and service cache

# represents a generic calendar
class Calendar:

    def __init__(self):
        # TODO: configurable by the user in the future, currently only supports Google Calendar
        self.my_calendar = GoogleCalendar()

    # Purpose: parse function info for read_calendar operation
    # Input: user_id (int), func_args (json), user_timezone (string)
    # Output: list of events (list of string)
    def read_calendar(self, user_id, func_args):
        # extract event information
        args_data = json.loads(func_args)
        date = args_data.get('date')
        time = args_data.get('time')
        # search for event(s) on calendar
        try:
            list_of_events = self.my_calendar.read_calendar(user_id, date, time)
        except Exception as e:
            print(f"Read Calendar Error: {e}")
            return ["Could not fetch events. Please try again later or contact support."]

        return ["Summarize and do not omit any events. User's calendar has returned the following events: "] + list_of_events

    # Purpose: parse function info for write_calendar operation
    # Input: user_id (int), func_args (json), user_timezone (string), description (string)
    # Output: success message or error (string)
    def write_calendar(self, user_id, func_args, description='This is some placeholder description.'):
        # extracts event information
        args_data = json.loads(func_args)
        event = args_data.get('event')
        date = args_data.get('date')
        time = args_data.get('time')
        # create google calendar event(s)
        try:
            link = self.my_calendar.write_calendar(user_id, event, date, time, description)
        except Exception as e:
            print(f"Write Calendar Error: {e}")
            return "Could not book event. Please try again later or contact support."
        return "Calendar event successfully created! Link to Event:" + link


# represents a user's google calendar
class GoogleCalendar:
    # cache service objects
    _service_cache = {}

    def __init__(self):
        pass

    # Purpose: authenticates google calendar, returns service object. Refreshes access token if necessary.
    # Input: user_id (int)
    # Output: service (Object)
    def authenticate(self, user_id):
        # check if service is already cached
        if user_id in GoogleCalendar._service_cache:
            return GoogleCalendar._service_cache[user_id]
        
        # otherwise, create a new service object
        user = User.query.get(user_id)
        google_user = GoogleUser.query.filter_by(google_id=user.google_id).first()
        if google_user and google_user.access_token:
            creds = Credentials(
                token=google_user.access_token,
                refresh_token=google_user.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                )

            # refresh access token w/ refresh token if expired
            if creds.expired:
                creds.refresh(Request())
                # update access token and expiry date
                google_user.access_token = creds.token
                google_user.token_expires_at = creds.expiry
                db.session.commit()

            service = build('calendar', 'v3', credentials=creds)
            return service
        else:
            # Handle case where access token does not exist or user not logged in
            raise Exception("Access token does not exist or user not logged in.")

    # Purpose: fetches events from google calendar
    # Input: service (Object), start (string), end (string)
    # Output: events (list of string)
    def fetch_events(self, service, start, end):
        # try to fetch events at start, end dates
        try:
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy='startTime',
            ).execute()
            events = events_result.get('items', [])
            return events, 200
        # handle exceptions; token expiry
        except HttpError as e:
            if e.resp.status in [401, 403]:
                print("Token is expired or invalid")
                return "Token is expired or invalid", e.resp.status
            else:
                raise e

    # Purpose: Parses given date and time, calls API, and returns list of events
    # Input: user_id (int), date (string), time (string)
    # Output: list of events (list of string)
    def read_calendar(self, user_id, date, time=''):

        '''
        # Supported date formats: today, tomorrow, this week, next week, this thursday, next tuesday, on aug 3rd
        # future updates:
            - yesterday, last thursday, date range (e.g. from aug 3rd to aug 5th)
            - cross date time; what do I have from Tuesday at 5:00pm to Thursday at 3:00pm?
            - semantic search; what do I have in the morning?
            - event -> time (sematic); when is my meeting with Bob?
            - date next year, previous year, etc.
        '''

        # get service if cached, else authenticate and build service
        service = self.authenticate(user_id)

        # set timezone
        user_timezone = session['user_timezone']
        if not user_timezone:
            print("Error: User timezone not set.")
            return ['Failed to fetch calendar events. Make sure you have set a appropriate timezone.']
        timezn = pytz.timezone(user_timezone)

        # parse the date
        try:
            start_date, end_date = utilities.parse_date(date, user_timezone)
            # if a time is specified, only start date should be used
            if time:
                end_date = start_date
        except ValueError as e:
            print(f"DateError: Could not parse date {date}.")
            raise e

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

        # format date and time for API call
        start = timezn.localize(start_date + start_time).isoformat()
        end = timezn.localize(end_date + end_time).isoformat()
        print(f'start: {start}')
        print(f'end: {end}')

        # fetch events
        events, status = self.fetch_events(service, start, end)

        # expired or invalid token
        if status in [401, 403]:
            # reauthenticate and rebuild service
            service = self.authenticate(user_id)
            if service:
                # try fetching events again
                events, status = self.fetch_events(service, start, end)
                if status in [401, 403]:
                    print("Failed to refresh token")
                    return ['Failed to fetch calendar events. Make sure you are logged into your google account.']
            else:
                print("Failed to refresh token")
                return ['Failed to fetch calendar events. Make sure you are logged into your google account.']
            
        data = []
        # parse and print events
        if not events:
            print('No upcoming events found.')
            return ['No upcoming events found.']
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])
            data.append({"start": start, "event": event['summary']})

        return data

    # Purpose: add event(s) to google calendar given a date and optional time
    # Input: user_id (int), event (string), date (string), time (string)
    # Output: link to calendar event (string)
    def write_calendar(self, user_id, event, date, time='', description='This is some placeholder description.'):

        # get service if cached, else authenticate
        service = self.authenticate(user_id)

        # set timezone
        user_timezone = session['user_timezone']
        if not user_timezone:
            print("Error: User timezone not set.")
            return ['Failed to fetch calendar events. Make sure you have set a appropriate timezone.']
        timezn = pytz.timezone(user_timezone)

        # parse the event
        event = event.strip()

        # parse the date
        try:
            start_date, end_date = utilities.parse_date(date, user_timezone)
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

        # format time in date string
        start = timezn.localize(start_date + start_time).isoformat()
        end = timezn.localize(end_date + end_time).isoformat()

        # Create a google calendar event object
        my_event = {
            'summary': event,
            'location': 'My Place',         # custom locations coming soon!
            'description': description,     # custom descriptions coming soon!
            'start': {
                'dateTime': start,
                'timeZone': user_timezone,  # PST time zone by default!
            },
            'end': {
                'dateTime': end,
                'timeZone': user_timezone,
            },
        }

        # Add the event to google calendar
        calendar_id = 'primary'             # primary calendar by default (can be configured)
        event = service.events().insert(calendarId=calendar_id, body=my_event).execute()
        link = event.get("htmlLink")
        print(f'Event created: {link}')

        return link


user_calendar = Calendar()
