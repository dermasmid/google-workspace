import email
import base64
from .utils import get_emails_address, get_full_address_data, parse_date, decode, get_label_id, get_html_text, is_english_chars, encode_if_not_english
import chardet
from copy import copy

class Message:


    def __init__(self, raw_message: str, mailbox):
        self.gmail_id = raw_message["id"]
        self.thread_id = raw_message["threadId"]
        self.label_ids = raw_message["labelIds"]
        self.mailbox = mailbox
        try:
            self.mail_obj = email.message_from_string(base64.urlsafe_b64decode(raw_message["raw"]).decode())
        except UnicodeDecodeError: # i can do this every time but the detection takes 0.1 secs - which i think is long
            data = base64.urlsafe_b64decode(raw_message["raw"])
            encoding = chardet.detect(data)['encoding']
            self.mail_obj = email.message_from_string(data.decode(encoding)) if encoding else email.message_from_string('')
        self.is_seen = not "UNREAD" in self.label_ids
        self.is_chat_message = "CHAT" in self.label_ids
        self.in_reply_to = self.mail_obj['In-Reply-To']
        self.references = self.mail_obj['References']
        self.is_reply = bool(self.in_reply_to)
        self.message_id = self.mail_obj["Message-Id"]
        self.subject = decode(self.mail_obj["Subject"]) or ''
        self.to = get_emails_address(self.mail_obj["To"]) or []
        self.cc = get_emails_address(self.mail_obj["Cc"]) or []
        self.bcc = get_emails_address(self.mail_obj["Bcc"]) or []
        self.raw_from = self.mail_obj["From"]
        try:
            self.from_ = get_emails_address(self.raw_from)[0]
            self.raw_from_name = get_full_address_data(self.raw_from)[0]["name"] or ''
        except IndexError: # edge case where raw_from is None
            self.from_ = ''
            self.raw_from_name = ''
        if not is_english_chars(self.raw_from_name):
            self.raw_from_name = encode_if_not_english(self.raw_from_name)
            self.raw_from = f'{self.raw_from_name} <{self.from_}>'
        self.from_name = decode(self.raw_from_name)
        self.raw_date = self.mail_obj["Date"]
        self.date = parse_date(self.raw_date)
        self.is_bulk = self.mail_obj['Precedence'] == 'bulk'
        self.text = ''
        self.html = ''
        self.attachments = []
        self._get_parts()
        self.html_text = get_html_text(self.html)
        self.has_attachments = any(not attachment.is_inline for attachment in self.attachments) # this is if you what to know if the message has a real attachment
  


    def __str__(self):
        return f"Message From: {self.from_}, Subject: {self.subject}, Date: {self.date}"


    def __contains__(self, item):
        if item in self.subject or item in self.text or item in self.html_text:
            return True
        else:
            return False

    def _get_parts(self):
        text_parts = {"text/plain": "text", "text/html": "html"}
        for part in self.mail_obj.walk():
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



    def add_label(self, label_id: str):
        message = self.mailbox.service.message_service.modify(userId= 'me', id= self.gmail_id, body= {'addLabelIds': [get_label_id(label_id)]}).execute()
        return message


    def remove_label(self, label_id: str):
        message = self.mailbox.service.message_service.modify(userId= 'me', id= self.gmail_id, body= {'removeLabelIds': [get_label_id(label_id)]}).execute()
        return message

    def mark_read(self):
        message = self.mailbox.service.message_service.modify(userId= 'me', id= self.gmail_id, body= {'removeLabelIds': ['UNREAD']}).execute()
        return message

    def mark_unread(self):
        message = self.mailbox.service.message_service.modify(userId= 'me', id= self.gmail_id, body= {'addLabelIds': ['UNREAD']}).execute()
        return message

    def delete(self):
        self.mailbox.service.message_service.delete(userId= 'me', id= self.gmail_id).execute()


    def trash(self):
        message = self.mailbox.service.message_service.trash(userId= 'me', id= self.gmail_id).execute()
        return message


    def untrash(self):
        message = self.mailbox.service.message_service.untrash(userId= 'me', id= self.gmail_id).execute()
        return message


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
        data = self.mailbox.send_message(
            to= self.raw_from,
            subject= f"Re: {self.subject}",
            text= text,
            html= html,
            attachments= attachments,
            references= references,
            in_reply_to= self.message_id,
            thread_id= self.thread_id
            )
        return data
        
        

    def forward(self, to: list or str):
        new_message = copy(self)
        if new_message.text:
            new_message.text = f'Original message from: {new_message.from_}\r\n' + new_message.text
        if new_message.html_text:
            new_message.html = f'<h3>Original message from: {new_message.from_}</h3>' + new_message.html
        new_message.subject = f'Fwd: {new_message.subject}'
        self.mailbox.send_message_from_message_obj(new_message, to)

    @property
    def labels(self):
        for label in self.label_ids:
            yield self.mailbox.get_label_by_id(label)





class Attachment:

    def __init__(self, attachment_part):
        self._part = attachment_part
        self.is_inline = attachment_part.get('Content-Disposition', '').startswith('inline')
        self.content_id = attachment_part.get('Content-ID')
        

    @property
    def filename(self):
        return decode(self._part.get_filename()) or ''


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
