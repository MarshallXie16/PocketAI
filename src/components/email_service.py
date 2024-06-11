import base64
import pytz
import json
import datetime
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import session

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from src.models.users import User
from src.models.google_user import GoogleUser
from src.models.message import Message

from src.utils.utils import utilities
from src.utils.extensions import db

'''
We can:
- read emails given date and optionally sender's name
- write email with optional subject, given email address and message body
- generates email based on provided message body

Future updates:
- search emails sent yesterday
- search emails sent last week
- search emails sent last month
- reply to emails
- able to read latest message in a message thread
- more advanced filters; by category, read/unread, date filters
- improved email generation
- map senders to email addresses
- draft emails before sending (safety mechanism)
'''


# wrapper class for email service
class Email:
    # set the type of email client used
    def __init__(self):
        self.my_email = Gmail()

    # Purpose: parse function args into read_email function
    # Input: user_id (int), func_args (json)
    # Output: list of emails (list of string)
    def read_email(self, user_id, func_args):
        # parse args
        args_data = json.loads(func_args)
        date = args_data.get('date')
        sender_name = args_data.get('sender_name')
        # return emails between date and (optionally) with sender's name
        try:
            list_of_emails = self.my_email.read_email(user_id, date, sender_name)
        except Exception as e:
            return [f"Inform the user there has been an error in reading their emails. Error: {str(e)}"]

        return ["Summarize, in character, the following emails: "] + list_of_emails

    # Purpose: parse function args into write_email function
    # Input: user_id (int), func_args (json)
    # Output: email body and output (string)
    def write_email(self, user_id, func_args):
        # parse args
        args_data = json.loads(func_args)
        recipient = args_data.get('recipient')
        subject = args_data.get('subject')
        msg_body = args_data.get('message_body')
        # draft and send email
        # TODO: enable users to check emails before sending
        email = self.my_email.write_email(user_id, recipient, subject, msg_body)
        return "Inform user of the result of send email operation: " + email

# represents a user's gmail calendar
class Gmail:

    _service_cache = {}

    def __init__(self):
        pass

    # Purpose: authenticates gmail, returns service object. Refreshes access token if necessary.
    # Input: user_id (int)
    # Output: service (Object)
    def authenticate(self, user_id):
        # check if service is already cached
        if user_id in Gmail._service_cache:
            return Gmail._service_cache[user_id]
        
        # otherwise, create a new service object
        user = User.query.get(user_id)
        google_user = GoogleUser.query.filter_by(google_id=user.google_id).first()
        print(f'Google user: {google_user}')
        print(google_user.access_token, google_user.refresh_token, google_user.token_expire_at)
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

            service = build('gmail', 'v1', credentials=creds)
            return service
        else:
            # Handle case where access token does not exist or user not logged in
            raise Exception("Access token does not exist or user not logged in.")
    
    # Purpose: return list of emails corresponding to the date and (optionally) the sender's name
    # Input: user_id (int), date (string), sender_name (string)
    # Output: list of emails (list of string)
    def read_email(self, user_id, date, sender_name):

        '''
        # Supported date formats: today, this week, this day_of_week, specific date
        # Future updates: yesterday, last week, last month, last day_of_week, date range, time range (for more precision)
        # Suupport multiple categories (currently only primary)
        # Display and store attachements
        # Read emails from specific contacts or email addresses
        '''

        # get service if cached, else authenticate
        service = self.authenticate(user_id)
        
        # set timezone
        user_timezone = session.get('user_timezone', 'UTC')
        timezn = pytz.timezone(user_timezone)

        # parse the date
        start_date, end_date = utilities.parse_date(date, user_timezone)
        print(start_date, end_date)
        if start_date is None or end_date is None:
            print(f"DataError: Could not parse date.")
            return []

        # format date, considering timezone
        start_date_utc = timezn.localize(start_date).astimezone(pytz.utc)
        end_date_utc = timezn.localize(end_date).astimezone(pytz.utc)
        end_date_utc += datetime.timedelta(days=1)
        start_date_str = start_date_utc.strftime("%Y/%m/%d")
        end_date_str = end_date_utc.strftime("%Y/%m/%d")

        # construct query for gmail api
        # TODO: expand beyond primary category
        query = f'category:primary after:{start_date_str} before:{end_date_str}'
        if sender_name:
            query += f' from:{sender_name}'

        # calls gmail API, returns list of message ids
        try:
            response = service.users().messages().list(userId='me', q=query).execute()
            messages = response.get('messages', [])
        except Exception as e:
            print(e)
            return []

        # parse and display each email
        emails = []
        for message_id in [message['id'] for message in messages]:
            # fetch email content by id
            email_data = service.users().messages().get(userId='me', id=message_id).execute()

            # extract headers
            headers = email_data['payload']['headers']
            subject = next((header['value'] for header in headers if header['name'] == 'Subject'), 'No Subject')
            from_email = next(header['value'] for header in headers if header['name'] == 'From')

            # extract body
            body = self.get_message_body(email_data['payload'])

            # Optionally, extract attachments
            # download_attachments(self.service, email_data['payload'].get('parts', []), email_data)

            emails.append({
                'subject': subject,
                'from': from_email,
                'body': body
            })

        self.display_email_info(emails)

        return emails

    # Purpose: drafts and sends email to recipient with optional subject and message body
    # Input: user_id (int), recipient (string), subject (string), msg_body (string)
    # Output: msg status (string)
    def write_email(self, user_id, recipient, subject, msg_body):
        
        '''
            Current Capabilities:
            - Send email to recipient with optional subject and message body
            - recipient must be a valid email address
            - msg_body is automatically generated based on AI; can be limited since no memory is accessed besides conversation context
            - Email is sent immediately without approval

            Future Updates:
            - Allow user to draft and approve email before sending
            - Allow user to reply to emails (email threads)
            - Allow user to send emails to multiple recipients
            - Allow user to send emails to contacts (instead of email address)
        '''

        # get service if cached, else authenticate
        service = self.authenticate(user_id)

        # Create a MIME message
        message = MIMEMultipart()
        message['to'] = recipient
        message['subject'] = subject if subject else 'No Subject'

        # Add the body to the message
        msg = MIMEText(msg_body)
        message.attach(msg)

        # Encode the message in base64
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

        # Use the Gmail API to send the message
        try:
            sent_message = service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
            return f"Email sent successfully to {recipient}. Message ID: {sent_message['id']}"
        except Exception as e:
            return f"Failed to send email. Error: {str(e)}"

    ''' Helper functions '''

    # Purpose: extract message body from gmail payload
    # Input: payload (json)
    # Output: message body (string)
    def get_message_body(self, payload):
        if payload.get('parts'):
            # multipart message
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    encoded_body = part['body']['data']
                    return base64.urlsafe_b64decode(encoded_body).decode('utf-8')
        elif payload['mimeType'] == 'text/plain':
            # single part message
            encoded_body = payload['body']['data']
            return base64.urlsafe_b64decode(encoded_body).decode('utf-8')
        return ''

    # Purpose: display email information for debugging
    # Input: emails_info (list of json)
    def display_email_info(self, emails_info):
        for email in emails_info:
            print(f"\nSubject: {email['subject']}")
            print(f"From: {email['from']}")
            print(f"Body: {email['body']}\n")
            print("---------")


user_email = Email()