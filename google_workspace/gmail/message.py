from typing import Union
from . import utils, gmail
from copy import copy



class BaseMessage():


    def __init__(self, gmail_client: "gmail.GmailClient", message_data: dict) -> None:
        self.gmail_client = gmail_client
        self.message_data = message_data
        self.gmail_id = message_data.get("id")
        self.thread_id = message_data.get("threadId")
        self.label_ids = message_data.get("labelIds")
        self.snippet = message_data.get('snippet')


    def add_labels(self, label_ids: Union[list, str]):
        return self.gmail_client.add_labels_to_message(self.gmail_id, label_ids)


    def remove_labels(self, label_ids: Union[list, str]):
        return self.gmail_client.remove_labels_from_message(self.gmail_id, label_ids)


    def mark_read(self):
        return self.gmail_client.mark_message_as_read(self.gmail_id)


    def mark_unread(self):
        return self.gmail_client.mark_message_as_unread(self.gmail_id)


    def delete(self):
        return self.gmail_client.delete_message(self.gmail_id)


    def trash(self):
        return self.gmail_client.trash_message()


    def untrash(self):
        return self.gmail_client.untrash_message(self.gmail_id)


    def get_header(self, header: str):
        if isinstance(self, MessageMetadata):
            return utils.invert_message_headers(self.message_data['payload']['headers']).get(header)
        elif isinstance(self, Message):
            return self.email_object.get(header) # pylint: disable=no-member




class Message(BaseMessage):


    def __init__(self, gmail_client: "gmail.GmailClient", message_data: dict):
        super().__init__(gmail_client, message_data)
        self.process_message()


    def __str__(self):
        return f"Message From: {self.from_}, Subject: {self.subject}, Date: {self.date}"


    def __contains__(self, text: str) -> bool:
        if text in self.subject or text in self.text or text in self.html_text:
            return True
        return False


    def _get_parts(self):
        text_parts = {"text/plain": "text", "text/html": "html"}
        for part in self.email_object.walk():
            if part.get_content_maintype() == "multipart":
                continue
            mimetype = part.get_content_type()
            if not part.get('Content-Disposition') and mimetype in text_parts:
                encoding = part.get_content_charset()
                if self.is_chat_message:
                    data = part.get_payload()
                else:
                    data = part.get_payload(decode= True)
                    try:
                        data = data.decode(encoding or 'utf-8', "ignore")
                    except LookupError:
                        data = data.decode('utf-8', "ignore")
                setattr(self, text_parts[mimetype], data)

            else:
                self.attachments.append(Attachment(part))


    def reply(
        self,
        text: str = None,
        html: str = None,
        attachments: list = []
        ):
        if self.is_reply:
            references = self.references + " " + self.message_id
        else:
            references = self.message_id
        text_email, html_email = utils.create_replied_message(self, text, html)
        data = self.gmail_client.send_message(
            to= self.raw_from,
            subject= f"Re: {self.subject}",
            text= text_email,
            html= html_email,
            attachments= attachments,
            references= references,
            in_reply_to= self.message_id,
            thread_id= self.thread_id
            )
        return data


    def forward(self, to: list or str):
        text_email, html_email = utils.create_forwarded_message(self)
        new_message = copy(self)
        new_message.text = text_email
        new_message.html = html_email
        new_message.subject = f'Fwd: {new_message.subject}'
        self.gmail_client.send_message_from_message_obj(new_message, to)


    def process_message(self):
        self.email_object = utils.get_email_object(self.message_data['raw'])
        self.is_seen = not "UNREAD" in self.label_ids
        self.is_chat_message = "CHAT" in self.label_ids
        self.in_reply_to = self.email_object['In-Reply-To']
        self.references = self.email_object['References']
        self.is_reply = bool(self.in_reply_to)
        self.message_id = self.email_object["Message-Id"]
        self.subject = utils.decode(self.email_object["Subject"]) or ''

        # from, to, cc, bcc
        self.raw_from = self.email_object["From"]
        self.raw_to = self.email_object["To"]
        self.raw_cc = self.email_object["Cc"]
        self.raw_bcc = self.email_object["Bcc"]
        self.to = utils.get_email_addresses(self.raw_to) or []
        self.cc = utils.get_email_addresses(self.raw_cc) or []
        self.bcc = utils.get_email_addresses(self.raw_bcc) or []
        self.raw_from, self.raw_from_name, self.from_, self.from_name = utils.get_from_info(self.raw_from)

        self.raw_date = self.email_object["Date"]
        self.date = utils.parse_date(self.raw_date)
        self.is_bulk = self.email_object['Precedence'] == 'bulk'
        self.text = ''
        self.html = ''
        self.attachments = []
        self._get_parts()
        self.html_text = utils.get_html_text(self.html)
        self.has_attachments = any(not attachment.is_inline for attachment in self.attachments) # this is if you what to know if the message has a real attachment
  



class MessageMetadata(BaseMessage):

    def __init__(self, gmail_client: "gmail.GmailClient", message_data: dict) -> None:
        super().__init__(gmail_client, message_data)
        self.process_message()


    def process_message(self):
        headers = utils.invert_message_headers(self.message_data['payload']['headers'])
        self.raw_date = headers.get('Date')
        self.date = utils.parse_date(self.raw_date)
        self.subject = headers.get('Subject')
        self.raw_reply_to = headers.get('Reply-To')
        self.message_id = headers.get('Message-Id')
        self.in_reply_to = headers.get('In-Reply-To')
        self.references = headers.get('References')
        self.is_reply = bool(self.in_reply_to)

        # from, to, cc, bcc
        self.raw_from = headers.get('From')
        self.raw_to = headers.get('To')
        self.raw_cc = headers.get('Cc')
        self.raw_bcc = headers.get('Bcc')
        self.to = utils.get_email_addresses(self.raw_to) or []
        self.cc = utils.get_email_addresses(self.raw_cc) or []
        self.bcc = utils.get_email_addresses(self.raw_bcc) or []
        self.raw_from, self.raw_from_name, self.from_, self.from_name = utils.get_from_info(self.raw_from)


    def get_full_message(self) -> Message:
        return self.gmail_client.get_message_by_id(self.gmail_id, metadata_only= False)


    def __str__(self):
        return f"Message From: {self.from_}, Subject: {self.subject}, Date: {self.date}"




class Attachment:

    def __init__(self, attachment_part):
        self._part = attachment_part
        self.is_inline = attachment_part.get('Content-Disposition', '').startswith('inline')
        self.content_id = attachment_part.get('Content-ID')


    @property
    def filename(self):
        return utils.decode(self._part.get_filename()) or ''


    @property
    def payload(self):
        data = self._part.get_payload(decode= True)
        return data


    def download(self, path: str = None):
        path = path or self.filename
        data = self.payload
        with open(path, "wb") as f:
            f.write(data)
        return path


    def __repr__(self):
        return self.filename
