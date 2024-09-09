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

from src.models.users import User, Contacts
from src.models.google_user import GoogleUser
from src.models.message import Message

from src.utils.utils import utilities
from src.utils.extensions import db

import email.utils
from sqlalchemy.orm.exc import NoResultFound

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
        # parse function arguments
        args_data = json.loads(func_args)
        operation_type = args_data.get('operation_type')
        date_reference = args_data.get('date_reference', None)
        day_of_week = args_data.get('day_of_week', None)
        specific_date = args_data.get('specific_date', None)
        time_range = args_data.get('time_range', None)
        sender_name = args_data.get('search_sender_name', None)
        subject = args_data.get('search_subject', None)
        
        # return list of emails for a specified date OR return summary of retrieved emails from search results
        try:
            list_of_emails = self.my_email.read_email(user_id, operation_type, date_reference, day_of_week, specific_date, time_range, sender_name, subject)
        except Exception as e:
            print(f'Read Email Error: {e}')
            return [f"Inform the user there has been an error in reading their emails. Error: {str(e)}"]

        # summarize returned list of emails
        if not list_of_emails:
            summarized_context = "No emails found."
        else:
            try:
                summarized_context = utilities.summarize_context(list_of_emails)
            except Exception as e:
                print(f"Error extracting email body: {e}")
                return ["No readable content found. Likely due to trouble parising HTML emails."]
        return ["Summarize, in character, the following emails. If there are no emails, tell the user. Emails: "] + list_of_emails

    # Purpose: parse function args into write_email function
    # Input: user_id (int), func_args (json)
    # Output: email body and output (string)
    def write_email(self, user_id, func_args):
        # parse function arguments
        args_data = json.loads(func_args)
        operation = args_data.get('operation_type')
        recipient_name = args_data.get('recipient_name')
        body = args_data.get('body')
        recipient_email = args_data.get('recipient_email', None)
        subject = args_data.get('subject', None)
        email_thread_id = args_data.get('email_thread_id', None)

        try: 
            draft = self.my_email.write_email(user_id, operation, recipient_name, body, recipient_email, subject, email_thread_id)
        except Exception as e:
            return [f"Inform the user that there has been an error in drafting their email. Error: {str(e)}"]
    
        return f"Show user the full email draft, do not omit anything: {draft}"

    # Purpose: parse function args into send_email function
    # Input: user_id (int), func_args (json)
    # Output: email body and output (string)
    def send_email(self, user_id, func_args):
        # parse function arguments
        args_data = json.loads(func_args)
        operation = args_data.get('operation_type')
        recipient_name = args_data.get('recipient_name')
        body = args_data.get('body')
        recipient_email = args_data.get('recipient_email', None)
        subject = args_data.get('subject', None)
        email_thread_id = args_data.get('email_thread_id', None)

        try: 
            email = self.my_email.send_email(user_id, operation, recipient_name, body, recipient_email, subject, email_thread_id)
        except Exception as e:
            return [f"Inform the user there has been an error in sending their email. Error: {str(e)}"]
    
        return f"Tell user that email has been successfully sent: {email}"

        
    

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


    # Purpose: returns list of emails for a specified time range OR searches emails based on sender's name and/or subject
    # Input: user_id (int), operation (string), date_reference (string), day_of_week (string), specific_date (string), time_range (string), sender_name (string), subject (string)
    # Output: summary of emails (formatted string)
    def read_email(self, user_id, operation, date_reference=None, day_of_week=None, specific_date=None, time_range=None, sender_name=None, subject=None):

        # Get service if cached, else authenticate
        service = self.authenticate(user_id)

        # Set timezone
        user_timezone = session.get('user_timezone', 'UTC')
        timezn = pytz.timezone(user_timezone)

        # Parse the date
        if not date_reference:
            date_reference = 'this week'
        try:
            start_date, end_date = utilities.parse_date(date_reference, day_of_week, specific_date, user_timezone)
        except ValueError as e:
            raise Exception(f"Date Parsing Error: {str(e)}")

        # Parse the time range (if applicable)
        if time_range:
            try:
                start_time, end_time = utilities.parse_time_range(time_range)
                start_date = datetime.datetime.combine(start_date, start_time)
                end_date = datetime.datetime.combine(end_date, end_time)
            except ValueError as e:
                raise Exception(f"Time Parsing Error: {str(e)}")

        # Combine date and time
        start = timezn.localize(start_date).astimezone(pytz.utc)
        end = timezn.localize(end_date).astimezone(pytz.utc)

        # Handle different operations
        if operation == 'list_emails':
            result = self.list_emails(service, start, end)
        elif operation == 'search_inbox':
            result = self.search_inbox(service, start, end, sender_name, subject)
        else:
            raise ValueError(f"Invalid operation type: {operation}")

        return result


    # Purpose: Organizes function call args into a readable email draft, returns to base model
    # Input: user_id (int), operation (string), recipient_name (string), body (string), subject (string), email_thread_id (string)
    # Output: formatted email draft (formatted string)
    def write_email(self, user_id, operation, recipient_name, body, recipient_email=None, subject=None, email_thread_id=None):
        # parse subject line and recipient email
        subject = subject if subject else 'No Subject'
        # search for recipient email in contacts
        # TODO: handle cases where multiple recipients might share the same first name
        recipient = Contacts.query.filter(user_id == user_id, Contacts.name.ilike(f'%{recipient_name}%')).first()
        recipient_email = recipient.email if recipient else recipient_email
        
        formatted_email = f'Email Draft\n'
        formatted_email += f'Operation Type: {operation}\n'
        formatted_email += f'Recipient: {recipient_name} <{recipient_email}>\n'
        formatted_email += f'Subject: {subject}\n'
        formatted_email += f'Body: {body}\n'
        formatted_email += f'Attachments: None\n' # TODO: add attachment support
        
        if operation == 'reply_email':
            formatted_email += f'Replying to Thread: {email_thread_id}\n'
            
        return formatted_email
    
    
    # Purpose: drafts and sends email to recipient with optional subject and message body
    # Input: user_id (int), recipient (string), subject (string), msg_body (string)
    # Output: msg status (string)
    def send_email(self, user_id, operation, recipient_name, body, recipient_email=None, subject=None, email_thread_id=None):
        
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

        # Get service if cached, else authenticate
        service = self.authenticate(user_id)

        try:
            # Fetch the user
            user = User.query.get(user_id)
            if not user:
                return "Error: User not found."

            # Search for the contact if recipient_email is not provided
            if not recipient_email:
                try:
                    contact = Contacts.query.filter_by(user_id=user_id, name=recipient_name).first()
                    recipient_email = contact.email
                except NoResultFound:
                    raise Exception(f"Contact '{recipient_name}' not found in your contacts. Please add this contact first or check the spelling of the name.")

            # Create the email message
            message = MIMEMultipart()
            message['to'] = recipient_email
            message['subject'] = subject
            msg = MIMEText(body)
            message.attach(msg)

            # Check if the operation is a reply
            if operation == 'reply':
                # Fetch the original email
                original_email = service.users().messages().get(userId='me', id=email_thread_id).execute()
                headers = original_email['payload']['headers']
                from_header = next((header for header in headers if header['name'] == 'From'), None)
                if from_header:
                    original_sender = from_header['value']
                    if original_sender != recipient_email:
                        raise Exception(f"Warning: The original sender ({original_sender}) doesn't match the recipient email ({recipient_email}). Please confirm if you want to proceed.") 
                
                message['In-Reply-To'] = email_thread_id
                message['References'] = email_thread_id

            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            raw_body = {'raw': raw_message}

            if operation == 'reply':
                raw_body['threadId'] = email_thread_id

            # Send the message
            sent_message = service.users().messages().send(userId='me', body=raw_body).execute()

            # Format the sent email for context
            formatted_email = f"Email sent successfully. Details:\n"
            formatted_email += f"Recipient: {recipient_name} <{recipient_email}>\n"
            formatted_email += f"Subject: {subject}\n"
            formatted_email += f"Body: {body}\n"
            if operation == 'reply':
                formatted_email += f"In reply to email ID: {email_thread_id}\n"
            formatted_email += f"Sent message ID: {sent_message['id']}"

            return formatted_email

        except Exception as e:
            raise Exception(f"An error occurred while sending the email: {str(e)}")


    ''' Helper functions '''
    
    # Purpose: returns list of emails for a specified time range
    # Input: service (Object), start_date (datetime), end_date (datetime)
    # Output: list of emails (list of string)
    def list_emails(self, service, start_date, end_date):
        query = f'after:{start_date.strftime("%Y/%m/%d")} before:{end_date.strftime("%Y/%m/%d")}'
        
        print(f'List Emails Query: {query}')
        
        try:
            response = service.users().messages().list(userId='me', q=query).execute()
            messages = response.get('messages', [])
        except Exception as e:
            print(f"Error fetching email list: {e}")
            raise Exception(f"Error fetching emails: {e}")

        print('listed emails')
        return self.process_emails(service, messages)

    # Purpose: searches emails based on sender's name and/or subject
    # Input: service (Object), start_date (datetime), end_date (datetime), sender_name (string), subject (string)
    # Output: list of emails (list of string)
    def search_inbox(self, service, start_date, end_date, sender_name=None, subject=None):
        query = f'after:{start_date.strftime("%Y/%m/%d")} before:{end_date.strftime("%Y/%m/%d")}'
        
        print(f'Search Inbox Query: {query}')
        
        if sender_name:
            query += f' from:{sender_name}'
        if subject:
            query += f' subject:{subject}'

        try:
            response = service.users().messages().list(userId='me', q=query).execute()
            messages = response.get('messages', [])
        except Exception as e:
            print(f"Error searching inbox: {e}")
            return []

        return self.process_emails(service, messages)

    # Purpose: processes emails and returns formatted results
    # Input: service (Object), messages (list of json)
    # Output: summary of emails (formatted string)
    def process_emails(self, service, messages):
        print('processing emails...')
        print(f'Messages: {messages}')
        threads = {}
        for message in messages:
            try:
                email_data = service.users().messages().get(userId='me', id=message['id']).execute()
                thread_id = email_data['threadId']
                
                if thread_id not in threads:
                    threads[thread_id] = []
                
                headers = email_data['payload']['headers']
                subject = next((header['value'] for header in headers if header['name'] == 'Subject'), 'No Subject')
                from_email = next(header['value'] for header in headers if header['name'] == 'From')
                date = next((header['value'] for header in headers if header['name'] == 'Date'), '')
                body = self.get_message_body(email_data['payload'])

                threads[thread_id].append({
                    'id': message['id'],
                    'subject': subject,
                    'from': from_email,
                    'date': date,
                    'body': body
                })
            except Exception as e:
                print(f"Error processing email {message['id']}: {e}")
                raise Exception(f"Error processing email {message['id']}: {e}")

        print('before threads')
        
        # # Sort messages within each thread by date
        # for thread_id in threads:
        #     threads[thread_id].sort(key=lambda x: email.utils.parsedate_to_datetime(x['date']))

        print('after threads')
        
        # Format email threads for output
        formatted_emails = []
        for thread_id, messages in threads.items():
            if len(messages) == 1:
                # Single email
                email = messages[0]
                email_summary = f"Single Email: {email['subject']}\n"
                email_summary += f"From: {email['from']}\n"
                email_summary += f"Date: {email['date']}\n"
                email_summary += f"Content: {email['body']}\n"
                formatted_emails.append(email_summary)
            else:
                # Email thread
                thread_summary = f"Email Thread: {messages[0]['subject']} ({len(messages)} messages)\n"
                for i, message in enumerate(messages, 1):
                    thread_summary += f"\nMessage {i}:\n"
                    thread_summary += f"From: {message['from']}\n"
                    thread_summary += f"Date: {message['date']}\n"
                    thread_summary += f"Content: {message['body']}\n"
                formatted_emails.append(thread_summary)

        print('formatted emails')
        
        return formatted_emails

    # Purpose: extract message body from gmail payload
    # Input: payload (json)
    # Output: message body (string)
    def get_message_body(self, payload):
        """Extract the message body from the payload"""
        if 'body' in payload:
            body = payload['body'].get('data')
            if body:
                decoded = base64.urlsafe_b64decode(body.encode('ASCII')).decode('utf-8')
                if payload.get('mimeType') == 'text/html':
                    print(f'Decoded Message Body: {utilities.parse_html(decoded)}')
                    return utilities.parse_html(decoded)
                return decoded
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        return base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    data = part['body'].get('data')
                    if data:
                        html_content = base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8')
                        print(utilities.parse_html(html_content))
                        return utilities.parse_html(html_content)
                elif 'parts' in part:
                    return self.get_message_body(part)
        
        return "No readable content found."

    # DEPRECATED
    # Purpose: display email information for debugging
    # Input: emails_info (list of json)
    def display_email_info(self, emails_info):
        for email in emails_info:
            print(f"\nSubject: {email['subject']}")
            print(f"From: {email['from']}")
            print(f"Body: {email['body']}\n")
            print("---------")
            
    # DEPRECATED 
    # Purpose: return list of emails corresponding to the date and (optionally) the sender's name
    # Input: user_id (int), date (string), sender_name (string)
    # Output: list of emails (list of string)
    def read_email_old(self, user_id, date, sender_name):

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
        print(f'Start Date: {start_date}')
        print(f'End Date: {end_date}')

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

            print(f'Raw Email Data: {email_data}')

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



user_email = Email()