
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