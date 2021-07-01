import base64
from datetime import date, datetime
from ..service import GoogleService
from .utils import make_message, make_label_dict, get_label_id, encode_if_not_english, gmail_query_maker
from .message import Message
from .label import Label, LabelShow, MessageShow
from .scopes import ReadonlyGmailScope
from .flood_prevention import FloodPrevention
import time
from datetime import datetime, date
from email.utils import getaddresses






class Gmail:


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
        label_name: str = None,
        include_spam_and_trash: bool = False
        ):

        query = gmail_query_maker(seen, from_, to, subject, after, before, label_name)

        if label_ids:
            if isinstance(label_ids, str):
                label_ids = [get_label_id(label_ids)]
            elif isinstance(label_ids, str):
                label_ids = list(map(get_label_id, label_ids))


        next_page_token = None
        messages, next_page_token = _get_messages(self.service, next_page_token, label_ids, query, include_spam_and_trash)
        
        while True:
            try:
                message_id = next(messages)["id"]

            except StopIteration:
                if not next_page_token:
                    break
                messages, next_page_token = _get_messages(self.service, next_page_token, label_ids, query, include_spam_and_trash)
                continue

            else:
                yield Message(_get_message_raw_data(self.service, message_id), self)




    def get_message_by_id(self, message_id: str):
        raw_message = _get_message_raw_data(self.service, message_id)
        return Message(raw_message, self)


    def handle_new_messages(self, func, handle_old_unread: bool = False, sleep: int = 3, mark_read: bool = False, include_spam: bool = False):
        history_id = self.history_id
        if handle_old_unread:
            msgs = self.get_messages('inbox', seen= False, include_spam_and_trash= include_spam)
            for msg in msgs:
                func(msg)
                if mark_read:
                    msg.mark_read()
        while True:
            print(f"Checking for messages - {datetime.now()}")
            results = _get_history_data(self.service, history_id, ['messageAdded'], label_ids= ['INBOX'] if not include_spam else ['INBOX', 'SPAM'])
            history_id = results['history_id']
            for message_id in results.get('messagesAdded', []):
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
            if _check_if_sent_similar_message(self, args, check_for_floods or self.flood_prevention):
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


    def get_label_by_id(self, label_id: str):
            label_data = _get_label_raw_data(self.service, label_id)
            return Label(label_data, self)



    def get_lables(self):
        labels_data = _get_labels(self.service)
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


    def get_filters(self):
        return self.service.settings_service.filters().list(userId= 'me').execute()

    def set_flood_prevention(self, similarities: list, after_date: date or datetime or int, number_of_messages: int = 1):
        self.flood_prevention = FloodPrevention(similarities, after_date, number_of_messages)


    def delete_message(self, message_id: str):
        return self.service.message_service.delete(userId= 'me', id= message_id).execute()


    def trash_message(self, message_id: str):
        return self.service.message_service.trash(userId= 'me', id= message_id).execute()


    def untrash_message(self, message_id: str):
        return self.service.message_service.untrash(userId= 'me', id= message_id).execute()


    def mark_message_as_read(self, message_id: str):
        return self.service.message_service.modify(userId= 'me', id= message_id, body= {'removeLabelIds': ['UNREAD']}).execute()


    def mark_message_as_unread(self, message_id: str):
        return self.service.message_service.modify(userId= 'me', id= message_id, body= {'addLabelIds': ['UNREAD']}).execute()



# Helper functions
def _get_messages(service, next_page_token, label_ids, query, include_spam_and_trash):
    kwargs = {'userId': 'me', 'pageToken': next_page_token, 'q': query, 'includeSpamTrash': include_spam_and_trash}
    if label_ids:
        kwargs['labelIds'] = label_ids
    data = service.message_service.list(**kwargs).execute()
    messages = iter(data.get("messages", []))
    next_page_token = data.get("nextPageToken", None)
    return messages, next_page_token


def _get_message_raw_data(service, message_id):
    raw_message = service.message_service.get(userId = "me", id= message_id, format= "raw").execute()
    return raw_message


def _get_message_full_data(service, message_id):
    full_data = service.message_service.get(userId = "me", id= message_id).execute()
    return full_data

def _get_history_data(service, start_history_id: int, history_types: list, label_ids: list = None):
    perams = {
        'userId': 'me',
        'startHistoryId': start_history_id,
        'historyTypes': history_types
    }
    data = service.history_service.list(**perams).execute()
    results = {}
    results['history_id'] = data['historyId']
    histories = data.get("history")
    if histories:
        for history in histories:
            del history['messages']
            del history['id']
            for returned_type in history:
                if not returned_type in results:
                    results[returned_type] = []
                for message in history[returned_type]:
                    message = message['message']
                    if label_ids:
                        message_labels = message.get('labelIds', [])
                        if any(label_id in message_labels for label_id in label_ids):
                            results[returned_type].append(message['id'])
    return results


def _get_labels(service):
    data = service.labels_service.list(userId= 'me').execute()
    return data



def _get_label_raw_data(service, label_id: str):
    data = service.labels_service.get(userId= 'me', id= label_id).execute()
    return data


def _check_if_sent_similar_message(mailbox, message, flood_prevention):
    kwargs = {}
    # if raw_from is passed we have to remove the name first becuz the api wont return anything
    if 'to' in flood_prevention.similarities:
        to = message['to']
        if '<' in to:
            start = to.find('<') + 1
            end = to.find('>')
            message['to'] = to[start:end]
    kwargs['after'] = flood_prevention.after_date
    for similarity in flood_prevention.similarities:
        value = message[similarity]
        kwargs[similarity] = value
    query = gmail_query_maker(**kwargs)
    messages = _get_messages(mailbox.service, None, ['SENT'], query, False)[0]
    if type(flood_prevention.after_date) is datetime:
        final_messages = []
        for message in messages:
            message_date = Message(_get_message_raw_data(mailbox.service, message['id']), mailbox).date
            if flood_prevention.after_date < message_date:
                final_messages.append(message)
        messages = final_messages
    response = len(list(messages)) >= flood_prevention.number_of_messages
    return response
