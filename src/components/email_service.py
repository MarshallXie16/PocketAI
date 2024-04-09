import base64
import pytz
import json
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from src.utils.utils import utilities
from src.utils.extensions import db
from src.models.users import User
from src.models.google_user import GoogleUser
from src.utils.config import google_client_id, google_client_secret

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


# generic email interface
class Email:
    # set the type of email client used
    def __init__(self):
        self.my_email = Gmail()

    # func_info (json) --> list_of_emails (list of string)
    # parse function args into read_email function
    def read_email(self, user_id, func_args):
        args_data = json.loads(func_args)
        date = args_data.get('date')
        sender_name = args_data.get('sender_name')
        # return emails between date and (optionally) with sender's name
        list_of_emails = self.my_email.read_email(user_id, date, sender_name)

        return ["Please summarize, in character, the following emails: "] + list_of_emails

    # func_info (json) --> email (string)
    # parse function args into write_email function
    def write_email(self, user_id, func_args):
        args_data = json.loads(func_args)
        recipient = args_data.get('recipient')
        subject = args_data.get('subject')
        msg_body = args_data.get('message_body')
        # draft and send email
        email = self.my_email.write_email(user_id, recipient, subject, msg_body)

        return "Email success! " + email


class Gmail:
    date = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime('%Y-%m-%d')

    def __init__(self):
        pass

    # authenticates user for gmail
    def authenticate(self, user_id):
        user = User.query.get(user_id)
        google_user = GoogleUser.query.filter_by(google_id=user.google_id).first()

        if google_user and google_user.access_token:
            creds = Credentials(
                token=google_user.access_token,
                refresh_token=google_user.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=google_client_id,
                client_secret=google_client_secret)

            if creds.expired:
                try:
                    creds.refresh(Request())
                    # update stored tokens
                    google_user.access_token = creds.token
                    google_user.refresh_token = creds.token
                    db.session.commit()
                except Exception as e:
                    print(f"Error: {e}")
                    # could not update tokens
                    return None

            service = build('gmail', 'v1', credentials=creds)
            return service
        else:
            # tokens are not available
            return None

    # date (string), sender_name (string; optional) --> list of email (list of string)
    # return a list of emails corresponding to the date AND (optionally) the sender's name
    def read_email(self, user_id, date, sender_name):

        # authenticate user
        service = self.authenticate(user_id)

        ''' TO-DOS
        # Supported date formats: today, specific date
        # Future updates: yesterday, last week, last month, date range
        '''

        # parse the date
        start_date, end_date = utilities.parse_date(date)
        print(start_date, end_date)
        if start_date is None or end_date is None:
            print(f"DataError: Could not parse date.")
            return []

        # format date, considering timezone
        start_date_utc = pytz.timezone('America/Vancouver').localize(start_date).astimezone(pytz.utc)
        end_date_utc = pytz.timezone('America/Vancouver').localize(end_date).astimezone(pytz.utc)
        end_date_utc += datetime.timedelta(days=1)
        start_date_str = start_date_utc.strftime("%Y/%m/%d")
        end_date_str = end_date_utc.strftime("%Y/%m/%d")

        # construct query for gmail api -- currently limited to personal inbox (!!!)
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

    # recipient (string; email address), subject (string; optional), msg_body (string) --> email (string)
    # drafts and sends an email to a recipient with an optional subject and msg body
    def write_email(self, user_id, recipient, subject, msg_body):
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
    # payload (json) --> message_body (string)
    # extracts the message body from gmail payload
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

    # displays all emails in a given format
    def display_email_info(self, emails_info):
        for email in emails_info:
            print(f"\nSubject: {email['subject']}")
            print(f"From: {email['from']}")
            print(f"Body: {email['body']}\n")
            print("---------")




# depreciated functions -- may be used in the future
# def read_email(service):
#     # Fetch unread emails in the primary category
#     results = service.users().messages().list(userId='me', q=f"is:unread category:primary after:{date}").execute()
#     # return a list of message objects
#     messages = results.get('messages', [])
#     print(f"Total unread messages in primary category: {len(messages)}")
#
#     # extract details from each message object
#     # for message in messages:
#     '''for now, we read only the first email (for control purposes)'''
#     message = messages[0]
#     # Extracting more details (message -> msg)
#     msg = service.users().messages().get(userId='me', id=message['id']).execute()
#     headers = msg['payload']['headers']
#     subject = next((header['value'] for header in headers if header['name'] == 'Subject'), 'No Subject')
#     from_email = next(header['value'] for header in headers if header['name'] == 'From')
#
#     # Extract body
#     parts = msg['payload'].get('parts', [])
#     body = ''
#     for part in parts:
#         if part['mimeType'] == 'text/plain':
#             encoded_body = part['body']['data']
#             body = base64.urlsafe_b64decode(encoded_body).decode('utf-8')
#
#     # Extracting attachments
#     download_attachments(service, parts, message)
#
#     print(f"\nSubject: {subject}")
#     print(f"From: {from_email}")
#     print(f"Body: {body}\n")
#     print("---------")
#
#     return {'subject': subject, 'from_email': from_email, 'id': message['id']}

#
# def write_email(service):
#     # extract information from read_email()
#     information = read_email(service)
#     subject = information['subject']
#     from_email = information['from_email']
#     message_id = information['id']
#     print('message id: ', message_id)
#     print('subject: ', subject)
#     print('from email: ', from_email)
#
#     # Get the entire message again
#     msg = service.users().messages().get(userId='me', id=message_id).execute()
#     original_headers = msg['payload']['headers']
#
#     # Craft a reply
#     subject = "Re: " + subject
#     message_text = "Thank you for your email. We have received your message and will get back to you shortly."
#
#     # Create MIME message
#     message = create_message("your_email@gmail.com", from_email, subject, message_text, original_headers)
#
#     # Send the email
#     service.users().messages().send(userId='me', body=message).execute()
#
#
# def download_attachments(service, parts, message):
#     # create an attachments folder if it does not exist
#     attachments_folder = "attachments"
#     if not os.path.exists(attachments_folder):
#         os.makedirs(attachments_folder)
#
#     # iterates through each part (chunk of a message)
#     for part in parts:
#         # it has a filename attribute and the corresponding value is not null, then an attachment exists
#         if 'filename' in part and part['filename']:
#             # fetches the attachment (JSON) based on userId, messageId, and the Id of the attachment
#             attachment = service.users().messages().attachments().get(userId='me', messageId=message['id'],
#                                                                       id=part['body']['attachmentId']).execute()
#             # extracts data from the attachment
#             file_data = attachment['data']
#             # constructs a file path based on the filename and the file path of the attachments folder
#             file_path = os.path.join(attachments_folder, part['filename'])
#             with open(file_path, 'wb') as f:
#                 f.write(file_data.encode('UTF-8'))
#
#
# def create_message(sender, to, subject, message_text, original_headers=None):
#     # convert message (str) to MIMEtext, a format that gmail api accepts
#     message = MIMEText(message_text)
#     message['to'] = to
#     message['from'] = sender
#     message['subject'] = subject
#
#     # Include the In-Reply-To and References headers to keep the same thread
#     if original_headers:
#         # extracts headers from receiving email
#         in_reply_to = next((header['value'] for header in original_headers if header['name'] == 'Message-ID'), None)
#         references = next((header['value'] for header in original_headers if header['name'] == 'References'), None)
#
#         print("Original Message-ID:", in_reply_to)  # Debug line
#         print("Original References:", references)  # Debug line
#
#         if in_reply_to:
#             # formats headers for sending email
#             message['In-Reply-To'] = in_reply_to
#             message['References'] = (references + ' ' + in_reply_to) if references else in_reply_to
#
#             print("In-Reply-To header in reply:", message['In-Reply-To'])  # Debug line
#             print("References header in reply:", message['References'])  # Debug line
#
#     # Base64-encode the message
#     raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
#     return {'raw': raw_message}


user_email = Email()