from . import utils, gmail
from copy import copy



class Message:


    def __init__(self, mailbox: "gmail.Gmail", message_data: str, is_full: bool):
        self.mailbox = mailbox
        self.is_full = is_full
        self.process_message(message_data)


    def __str__(self):
        return f"Message From: {self.from_}, Subject: {self.subject}, Date: {self.date}"


    def __contains__(self, item):
        if item in self.subject or item in self.text or item in self.html_text:
            return True
        else:
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



    def add_label(self, label_id: str):
        return self.mailbox.service.message_service.modify(userId= 'me', id= self.gmail_id, body= {'addLabelIds': [utils.get_label_id(label_id)]}).execute()


    def remove_label(self, label_id: str):
        return self.mailbox.service.message_service.modify(userId= 'me', id= self.gmail_id, body= {'removeLabelIds': [utils.get_label_id(label_id)]}).execute()


    def mark_read(self):
        return self.mailbox.mark_message_as_read(self.gmail_id)


    def mark_unread(self):
        return self.mailbox.mark_message_as_unread(self.gmail_id)


    def delete(self):
        return self.mailbox.delete_message(self.gmail_id)


    def trash(self):
        return self.mailbox.trash_message()


    def untrash(self):
        return self.mailbox.untrash_message(self.gmail_id)


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
        data = self.mailbox.send_message(
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
        self.mailbox.send_message_from_message_obj(new_message, to)


    @property
    def labels(self):
        for label in self.label_ids:
            yield self.mailbox.get_label_by_id(label)


    def process_message(self, message_data: str):
        self.message_data = message_data
        self.gmail_id = message_data["id"]
        self.thread_id = message_data["threadId"]
        self.label_ids = message_data["labelIds"]
        self.email_object = utils.get_email_object(message_data['raw'])
        self.is_seen = not "UNREAD" in self.label_ids
        self.is_chat_message = "CHAT" in self.label_ids
        self.in_reply_to = self.email_object['In-Reply-To']
        self.references = self.email_object['References']
        self.is_reply = bool(self.in_reply_to)
        self.message_id = self.email_object["Message-Id"]
        self.subject = utils.decode(self.email_object["Subject"]) or ''
        self.to = utils.get_emails_address(self.email_object["To"]) or []
        self.cc = utils.get_emails_address(self.email_object["Cc"]) or []
        self.bcc = utils.get_emails_address(self.email_object["Bcc"]) or []
        self.raw_from = self.email_object["From"]
        try:
            self.from_ = utils.get_emails_address(self.raw_from)[0]
            self.raw_from_name = utils.get_full_address_data(self.raw_from)[0]["name"] or ''
        except IndexError: # edge case where raw_from is None
            self.from_ = ''
            self.raw_from_name = ''
        if not utils.is_english_chars(self.raw_from_name):
            self.raw_from_name = utils.encode_if_not_english(self.raw_from_name)
            self.raw_from = f'{self.raw_from_name} <{self.from_}>'
        self.from_name = utils.decode(self.raw_from_name)
        self.raw_date = self.email_object["Date"]
        self.date = utils.parse_date(self.raw_date)
        self.is_bulk = self.email_object['Precedence'] == 'bulk'
        self.text = ''
        self.html = ''
        self.attachments = []
        self._get_parts()
        self.html_text = utils.get_html_text(self.html)
        self.has_attachments = any(not attachment.is_inline for attachment in self.attachments) # this is if you what to know if the message has a real attachment
  

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
