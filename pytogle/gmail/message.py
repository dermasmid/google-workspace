import email
import base64
from .utils import get_emails_address, get_full_address_data, parse_date, decode, get_label_id


class Message:


    def __init__(self, raw_message: str, mailbox):
        self.gmail_id = raw_message["id"]
        self.thread_id = raw_message["threadId"]
        self.label_ids = raw_message["labelIds"]
        self.mailbox = mailbox
        self.mail_obj = email.message_from_string(base64.urlsafe_b64decode(raw_message["raw"]).decode())
        self.is_seen = "UNREAD" in self.label_ids
        self.is_chat_message = "CHAT" in self.label_ids
        self.in_reply_to = self.mail_obj['In-Reply-To']
        self.references = self.mail_obj['References']
        self.is_reply = bool(self.in_reply_to)
        self.message_id = self.mail_obj["Message-Id"]
        self.subject = decode(self.mail_obj["Subject"])
        self.to = get_emails_address(self.mail_obj["To"])
        self.cc = get_emails_address(self.mail_obj["Cc"])
        self.bcc = get_emails_address(self.mail_obj["Bcc"])
        self.from_ = get_emails_address(self.mail_obj["From"])[0]
        self.from_name = get_full_address_data(self.mail_obj["From"])[0]["name"]
        self.raw_date = self.mail_obj["Date"]
        self.date = parse_date(self.raw_date)
        self.text = ''
        self.html = ''
        self.attachments = []
        self._get_parts()
  


    def __str__(self):
        return f"Message From: {self.from_}, Subject: {self.subject}, Date: {self.date}"


    def _get_parts(self):
        text_parts = {"text/plain": "text", "text/html": "html"}
        for part in self.mail_obj.walk():
            if part.get_content_maintype() == "multipart":
                continue
            mimetype = part.get_content_type()
            if not part.get('Content-Disposition'):
                if mimetype in text_parts.keys():
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
            references = self.references + " "  + self.message_id
        else:
            references = self.message_id
        data = self.mailbox.send_message(
            to= self.from_,
            subject= f"Re: {self.subject}",
            text= text,
            html= html,
            attachments= attachments,
            references= references,
            in_reply_to= self.message_id,
            thread_id= self.thread_id
            )
        return data
        
        

    @property
    def labels(self):
        for label in self.label_ids:
            yield self.mailbox.get_label_by_id(label)





class Attachment:

    def __init__(self, attachment_part):
        self._part = attachment_part
        

    @property
    def filename(self):
        return decode(self._part.get_filename())


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
