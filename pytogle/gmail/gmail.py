import base64
from datetime import date, datetime
from ..service import GoogleService
from .utils import make_message, make_label_dict, get_label_id, encode_if_not_english, gmail_query_maker
from .message import Message
from .label import Label, LabelShow, MessageShow
from .scopes import ReadonlyGmailScope
from .gmail_base import GmailBase
from .flood_prevention import FloodPrevention
import os
import time
from datetime import datetime, timedelta, date
import smtplib, ssl
from email.utils import getaddresses






class Gmail(GmailBase):


    def __init__(self, service: GoogleService or str = None, allow_modify: bool = True):
        if isinstance(service, GoogleService):
            self.service = service

        else:
            kwargs = {}
            if service:
                kwargs["session"] = service
            if not allow_modify:
                kwargs['scopes'] = [ReadonlyGmailScope()]
            self.service = GoogleService(api= "gmail", **kwargs)
        self.prevent_flood = False
        self.get_user()


    def __len__(self):
        return self.user.get("messagesTotal")


    def __str__(self):
        return f"email: {self.email_address}, scopes: {self.service.authenticated_scopes}"

    def get_user(self):
        self.user = self.service.users().getProfile(userId= "me").execute()


    @property
    def sender_name(self):
        return self.user.get('sender_name')


    @sender_name.setter
    def sender_name(self, sender_name):
        sender_name = encode_if_not_english(sender_name)
        self.user['sender_name'] = sender_name


    @property
    def history_id(self):
        return self.user.get("historyId")


    @property
    def email_address(self):
        return self.user.get("emailAddress")


    def get_messages(
        self,
        label_ids: list or str = None,
        seen: bool = None,
        from_: str = None,
        to: list = None,
        subject: str = None,
        after: date = None,
        before: date = None,
        label_name: str = None
        ):

        query = gmail_query_maker(seen, from_, to, subject, after, before, label_name)

        if label_ids:
            if isinstance(label_ids, str):
                label_ids = [get_label_id(label_ids)]
            elif isinstance(label_ids, str):
                label_ids = list(map(get_label_id, label_ids))


        next_page_token = None
        messages, next_page_token = self._get_messages(next_page_token, label_ids, query)
        
        while True:
            try:
                message_id = next(messages)["id"]

            except StopIteration:
                if not next_page_token:
                    break
                messages, next_page_token = self._get_messages(next_page_token, label_ids, query)
                continue

            else:
                yield Message(self._get_message_raw_data(message_id), self)




    def get_message_by_id(self, message_id: str):
        raw_message = self._get_message_raw_data(message_id)
        return Message(raw_message, self)


    def handle_new_messages(self, func, handle_old_unread: bool = False, sleep: int = 3, mark_read: bool = False):
        history_id = self.history_id
        if handle_old_unread:
            msgs = self.get_messages('inbox', seen= False)
            for msg in msgs:
                func(msg)
                if mark_read:
                    msg.mark_read()
        while True:
            print(f"Checking for messages - {datetime.now()}")
            results = self._get_history_data(history_id, ['messageAdded'], label_id= 'INBOX')
            history_id = results['history_id']
            for message_id in results.get('messagesAdded', []):
                print("New message!")
                message = self.get_message_by_id(message_id)
                func(message)
                if mark_read:
                    message.mark_read()
            time.sleep(sleep)


    def send_message(
        self,
        to: list or str = None,
        subject: str = "", 
        text: str = None,
        html: str = None,
        attachments: list = [],
        cc: list or str = None,
        bcc: list or str = None,
        references: str = None,
        in_reply_to: str = None,
        thread_id: str = None,
        check_for_floods: FloodPrevention = None
        ):
        if check_for_floods or self.prevent_flood:
            args = vars()
            if self._check_if_sent_similar_message(args, check_for_floods or self.flood_prevention):
                return False
        message = make_message(
            self.email_address, 
            self.sender_name, 
            to, 
            cc, 
            bcc, 
            subject, 
            text, 
            html, 
            attachments, 
            references, 
            in_reply_to
            )
        b64 = base64.urlsafe_b64encode(message).decode()
        body = {'raw': b64}
        if thread_id:
            body["threadId"] = thread_id
        data = self.service.message_service.send(userId= 'me', body= body).execute()
        return data


    def send_message_from_message_obj(self, message_obj, to: list or str = None, cc: list or str = None, bcc: list or str = None):
        attachments = []
        for attachment in message_obj.attachments:
            attachments.append((attachment.payload, attachment.filename))
        self.send_message(
            to= to,
            subject= message_obj.subject,
            text= message_obj.text,
            html= message_obj.html,
            attachments= attachments,
            cc= cc,
            bcc= bcc
        )


    def get_label_by_id(self, label_id):
            label_data = self._get_label_raw_data(label_id)
            return Label(label_data, self)



    def get_lables(self):
        labels_data = self._get_labels()
        for label in labels_data['labels']:
            yield self.get_label_by_id(label['id'])



    def create_label(
        self, 
        name: str,
        message_list_visibility = MessageShow(),
        label_list_visibility = LabelShow(),
        background_color: str = None,
        text_color: str = None
        ):

        body = make_label_dict(name= name, message_list_visibility= message_list_visibility, label_list_visibility= label_list_visibility, 
            background_color= background_color, text_color= text_color
            )

        data = self.service.labels_service.create(userId= 'me', body= body).execute()
        return self.get_label_by_id(data['id'])


    def set_flood_prevention(self, similarities: list, after_date: date or datetime or int, number_of_messages: int = 1):
        self.flood_prevention = FloodPrevention(similarities, after_date, number_of_messages)
