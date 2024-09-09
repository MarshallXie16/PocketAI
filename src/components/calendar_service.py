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
    # Input: user_id (int), func_args (json)
    # Output: list of events (list of string)
    def read_calendar(self, user_id, func_args):
        # extract event information
        args_data = json.loads(func_args)
        query_type = args_data.get('query_type')
        date_reference = args_data.get('date_reference')
        day_of_week = args_data.get('day_of_week', None)
        specific_date = args_data.get('specific_date', None)
        time_range = args_data.get('time_range', None)
        event_name = args_data.get('event_name', None)

        # search for event(s) on calendar
        try:
            list_of_events = self.my_calendar.read_calendar(user_id, query_type, date_reference, day_of_week, specific_date, time_range, event_name)
        except Exception as e:
            print(f"Read Calendar Error: {e}")
            return [f"Inform the user that you could not fetch calendar events. Please try again later or contact support. Error: {e}"]

        # have another model summarize the list of returned events
        if not list_of_events:
            summarized_context = "No upcoming events found."
        else:
            summarized_context = utilities.summarize_context(list_of_events)
        return [f"Summarize and do not omit any events. User's calendar has returned the following events: {summarized_context}"]

    # Purpose: parse function info for write_calendar operation
    # Input: user_id (int), func_args (json), user_timezone (string), description (string)
    # Output: success message or error (string)
    def write_calendar(self, user_id, func_args, description='This is some placeholder description.'):
        # extracts event information
        args_data = json.loads(func_args)
        event_type = args_data.get('event_type')
        event_name = args_data.get('event_name')
        date_reference = args_data.get('date_reference')
        day_of_week = args_data.get('day_of_week', None)
        specific_date = args_data.get('specific_date', None)
        time_range = args_data.get('time_range', None)
        recurrence_frequency = args_data.get('recurrence_frequency', None)
        
        # create google calendar event(s)
        try:
            link = self.my_calendar.write_calendar(
                user_id, event_type, event_name, date_reference, 
                day_of_week, specific_date, time_range, 
                recurrence_frequency, description
            )
        except Exception as e:
            print(f"Write Calendar Error: {e}")
            return f"Inform the user that you could not book the event. Error: {e}"
        return f"Inform the user that calendar event successfully created! Link to Event: {link}"


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
                calendarId='primary',               # TODO: add other calendars
                timeMin=start,
                timeMax=end,
                singleEvents=True,                  # TODO: recurring events
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

    # Purpose: return list of events in a specified time range
    # Input: service (Object), start (isoformat), end (isoformat)
    # Output: List of events (string)
    def list_events(self, service, start, end):
        # fetch events given start/end datetime
        events, status = self.fetch_events(service, start, end)
        
        # Error handing
        if isinstance(events, str):
            return f"Error: {events}", status

        # No events found
        if not events:
            return "No events found in the specified time range.", 200

        # Format list of returned events
        formatted_events = []
        for event in events:
            start_time = event['start'].get('dateTime', event['start'].get('date'))
            end_time = event['end'].get('dateTime', event['end'].get('date'))
            event_name = event['summary']
            
            formatted_event = f"Event: {event_name}\nStart: {start_time}\nEnd: {end_time}"
            if 'description' in event:
                formatted_event += f"\nDescription: {event['description']}"
            formatted_events.append(formatted_event)

        result = "Query returned the following events:\n\n" + "\n\n".join(formatted_events)
        return result, 200

    # Purpose: returns a list of available time slots in a specified time range
    # Input: service (Object), start (isoformat), end (isoformat)
    # Output: list of available time slots (string)
    def check_availability(self, service, start, end):
        # fetch list of events for specified time range 
        events, status = self.fetch_events(service, start, end)
        
        # Error handling
        if isinstance(events, str):
            return f"Error: {events}", status

        # No events found
        if not events:
            return f"User is available for the entire period from {start} to {end}.", 200

        # Identify busy periods (when events are scheduled)
        busy_periods = []
        for event in events:
            event_start = event['start'].get('dateTime', event['start'].get('date'))
            event_end = event['end'].get('dateTime', event['end'].get('date'))
            busy_periods.append((event_start, event_end))

        # Sort busy periods and merge overlapping ones
        busy_periods.sort(key=lambda x: x[0])
        merged_busy_periods = []
        for period in busy_periods:
            if not merged_busy_periods or period[0] > merged_busy_periods[-1][1]:
                merged_busy_periods.append(period)
            else:
                merged_busy_periods[-1] = (merged_busy_periods[-1][0], max(merged_busy_periods[-1][1], period[1]))

        # Find free periods
        free_periods = []
        current_time = start
        for busy_start, busy_end in merged_busy_periods:
            if current_time < busy_start:
                free_periods.append((current_time, busy_start))
            current_time = max(current_time, busy_end)
        
        if current_time < end:
            free_periods.append((current_time, end))

        # No free periods found
        if not free_periods:
            return f"You are fully booked from {start} to {end}.", 200

        result = f"Available time slots between {start} and {end}:\n\n"
        for free_start, free_end in free_periods:
            # Display free time slots
            result += f"From {free_start} to {free_end}\n"

        return result, 200

    # Purpose: searches for event in specified time range and returns start and end time
    # Input: service (Object), start (isoformat), end (isoformat), event_name (string)
    # Output: event details (string)
    def find_event(self, service, start, end, event_name):
        # Fetch all events in the specified time range
        events, status = self.fetch_events(service, start, end)
        
        # Error handling
        if isinstance(events, str):
            return f"Error: {events}", status

        # Find events matching the specified event name
        matching_events = []
        for event in events:
            if event_name.lower() in event['summary'].lower():
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                matching_events.append(f"Event: {event['summary']}\nStart: {start}\nEnd: {end}\n")

        # No matching events found
        if not matching_events:
            return f"No events matching '{event_name}' found in the specified time range.", 200

        # Matching events found
        result = f"Found the following events matching '{event_name}':\n\n" + "\n\n".join(matching_events)
                
        return result, 200

    # Purpose: fetch events from google calendar given a date and optional time
    # Input: user_id (int), query_type (string), date_reference (string), day_of_week (string), specific_date (string), time_range (string), event_name (string)
    # Output: list of events (list of string)
    def read_calendar(self, user_id, query_type, date_reference, day_of_week=None, specific_date=None, time_range=None, event_name=None):

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
        user_timezone = session.get('user_timezone')
        if not user_timezone:
            print("Error: User timezone not set.")
            raise Exception('Failed to fetch calendar events. Make sure you have set a appropriate timezone.')
        timezn = pytz.timezone(user_timezone)

        # parse the date
        try:
            start_date, end_date = utilities.parse_date(date_reference, day_of_week, specific_date, user_timezone)
        except ValueError as e:
            raise Exception(f"Date Parsing Error: {str(e)}")

        # parse the time range (if applicable)
        if time_range:
            try:
                start_time, end_time = utilities.parse_time_range(time_range)
                start_date = datetime.datetime.combine(start_date, start_time)
                end_date = datetime.datetime.combine(end_date, end_time)
            except ValueError as e:
                raise Exception(f"Time Parsing Error: {str(e)}")

        # Combine date and time
        start = timezn.localize(start_date).isoformat()
        end = timezn.localize(end_date).isoformat()

        # Fetch events
        events, status = self.fetch_events(service, start, end)

        # TODO: work this into each of the 3 functions
        # handle expired or invalid token
        if status in [401, 403]:
            # reauthenticate and rebuild service
            service = self.authenticate(user_id)
            if service:
                # try fetching events again
                events, status = self.fetch_events(service, start, end)
                if status in [401, 403]:
                    print("Failed to refresh token")
                    raise Exception('Failed to fetch calendar events. Make sure you are logged into your google account.')
            else:
                print("Failed to refresh token")
                raise Exception('Failed to fetch calendar events. Make sure you are logged into your google account.')
            
        # handle different query types
        if query_type == 'list_events':
            result, status = self.list_events(service, start, end)
        elif query_type == 'check_availability':
            result, status = self.check_availability(service, start, end)
        elif query_type == 'find_event':
            if not event_name:
                raise ValueError("Event name is required for 'find_event' query type")
            result, status = self.find_event(service, start, end, event_name)
        else:
            raise ValueError(f"Invalid query type: {query_type}")

        # handle exceptions
        if status != 200:
            raise Exception(result)
        
        return result
        
    # Purpose: add event(s) to google calendar given a date and optional time
    # Input: user_id (int), event (string), date (string), time (string)
    # Output: link to calendar event (string)
    def write_calendar(self, user_id, event_type, event_name, date_reference, day_of_week=None, specific_date=None, time_range=None, recurrence_frequency=None, description='This is some placeholder description.'):

        # Get service if cached, else authenticate
        service = self.authenticate(user_id)

        # Set timezone
        user_timezone = session.get('user_timezone')
        if not user_timezone:
            print("Error: User timezone not set.")
            raise Exception('Failed to fetch calendar events. Make sure you have set a appropriate timezone.')
        timezn = pytz.timezone(user_timezone)

        # Parse the date
        try:
            start_date, end_date = utilities.parse_date(date_reference, day_of_week, specific_date, user_timezone)
        except ValueError as e:
            raise Exception(f"Date Parsing Error: {str(e)}")

        # Parse the time range (if applicable)
        if time_range:
            try:
                start_time, end_time = utilities.parse_time_range(time_range)
                start_datetime = datetime.datetime.combine(start_date, start_time)
                end_datetime = datetime.datetime.combine(start_date, end_time)
            except ValueError as e:
                raise Exception(f"Time Parsing Error: {str(e)}")
        else:
            # If no time range is specified, use only the date
            start_datetime = start_date
            end_datetime = end_date

        # format time as date string
        start = timezn.localize(start_datetime).isoformat()
        end = timezn.localize(end_datetime).isoformat()

        # create a Google Calendar event object
        event = {
            'summary': event_name,
            'location': 'My Place',         # TODO: custom locations
            'description': description,
            'start': {
                'dateTime': start,
                'timeZone': user_timezone,
            },
            'end': {
                'dateTime': end,
                'timeZone': user_timezone,
            },
        }

        # If it's an all-day event, use 'date' instead of 'dateTime'
        if isinstance(start_datetime, datetime.date) and not isinstance(start_datetime, datetime.datetime):
            event['start'] = {'date': start_datetime.isoformat()}
            event['end'] = {'date': end_datetime.isoformat()}

        # Handle recurring events
        if event_type == 'recurring_event' and recurrence_frequency:
            if recurrence_frequency.strip().lower() == 'weekly':
                event['recurrence'] = ['RRULE:FREQ=WEEKLY']
            elif recurrence_frequency.strip().lower() == 'monthly':
                event['recurrence'] = ['RRULE:FREQ=MONTHLY']
            else:
                raise ValueError(f"Invalid recurrence frequency: {recurrence_frequency}")

        # Add the event to Google Calendar
        try:
            calendar_id = 'primary'                     # TODO: add other calendars
            created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
            link = created_event.get("htmlLink")
            
            # Prepare a formatted response
            response = f"Event successfully created!\n\n"
            response += f"Event: {event_name}\n"
            response += f"Start: {start}\n"
            response += f"End: {end}\n"
            if event_type == 'recurring_event':
                response += f"Recurrence: {recurrence_frequency}\n"
            response += f"Link: {link}"
            return response
        
        except HttpError as e:
            error_message = f"Failed to create event. Error: {str(e)}"
            print(error_message)
            raise Exception(error_message)


user_calendar = Calendar()
