import base64
from typing import Union, Generator
from datetime import date, datetime
from queue import Empty, Queue
from threading import Thread, Event
from typing import Union
import functools
import signal
from . import utils, helper, message
from .. import service as service_module
from .handlers import MessageAddedHandler
from .label import Label, LabelShow, MessageShow
from .scopes import ReadonlyGmailScope
from .flood_prevention import FloodPrevention
import time
from datetime import datetime, date
from googleapiclient.errors import HttpError





class Gmail:


    def __init__(
        self,
        service: Union['service_module.GoogleService', str] = None,
        allow_modify: bool = True,
        workers: int = 4,
        save_state: bool = False,
        update_interval: int = 1
        ):
        if isinstance(service, service_module.GoogleService):
            self.service = service

        else:
            kwargs = {}
            if service:
                kwargs["session"] = service
            if not allow_modify:
                kwargs['scopes'] = [ReadonlyGmailScope()]
            self.service = service_module.GoogleService(api= "gmail", **kwargs)
        self.prevent_flood = False
        self.workers = workers
        self.save_state = save_state
        self.update_interval = update_interval
        utils.add_encoding_aliases()
        self.handlers = {}
        self.updates_queue = Queue()
        self.stop_request = Event()
        if self.service.is_authenticated:
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
        sender_name = utils.encode_if_not_english(sender_name)
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
        include_spam_and_trash: bool = False,
        metadata_only: bool = False,
        batch: bool = True,
        limit: int = None
        ) -> Generator[Union[message.Message, message.MessageMetadata], None, None]:

        query = utils.gmail_query_maker(seen, from_, to, subject, after, before, label_name)

        if label_ids:
            if isinstance(label_ids, str):
                label_ids = [utils.get_label_id(label_ids)]
            elif isinstance(label_ids, list):
                label_ids = list(map(utils.get_label_id, label_ids))

        messages_generator = helper.get_messages_generator(
            self,
            label_ids,
            query,
            include_spam_and_trash,
            metadata_only,
            batch,
            limit
            )
        return messages_generator


    def get_message_by_id(self, message_id: str, metadata_only: bool = False) -> Union[message.Message, message.MessageMetadata]:
        if metadata_only:
            message_class, message_format = message.MessageMetadata, 'metadata'
        else:
            message_class, message_format = message.Message, 'raw'
        raw_message = helper.get_message_data(self.service, message_id, message_format)
        return message_class(self, raw_message)


    def add_handler(self, handler):
        self.handlers[handler.history_type] = self.handlers.get(handler.history_type, []) + [handler]


    def update_worker(self):
        while True:
            full_update = self.updates_queue.get()
            if full_update is None:
                break
            update_type = full_update['type']
            for update in full_update['updates']:
                try:
                    message = self.get_message_by_id(update['message']['id'])
                except HttpError as e:
                    if e._get_reason().strip() == 'Requested entity was not found.':
                        # We got an update for a draft, but was deleted (sent out) or updated since.
                        continue
                    else:
                        raise e

                for handler in self.handlers[update_type]:
                    if handler.check(message):
                        handler.callback(message)


    def get_updates(self):
        ''' This is the main function which looks for updates on the
        account, and adds it to the queue.
        '''
        history_id = self.history_id
        if self.service.service_state.get('history_id') and self.save_state:
            history_id = self.service.service_state['history_id']
        history_types = list(self.handlers.keys())
        # If there's no handler's - quit.
        while history_types:
            try:
                data = helper.get_history_data(self.service, history_id, history_types)
                history_id = data['historyId']
                for history in data.get('history', []):
                    if len(history) == 3:
                        self.updates_queue.put(utils.format_update(history))
                if self.stop_request.is_set():
                    break
                time.sleep(self.update_interval)
            except Exception as e:
                self._handle_stop(history_id)
                raise e
        self._handle_stop(history_id)

        

    def _handle_stop(self, history_id):
        if not self.save_state:
            with self.updates_queue.mutex:
                self.updates_queue.queue.clear()
        else:
            queue_items = []
            while True:
                try:
                    queue_items.append(self.updates_queue.get_nowait())
                except Empty:
                    break
            if queue_items:
                oldest_history_id = queue_items[0]['history_id']
            else:
                oldest_history_id = history_id
            self.service.save_state(int(oldest_history_id) - 1)

        # Stop the workers.
        for _ in range(self.workers):
            self.updates_queue.put(None)


    def run(self):
        self.service.make_thread_safe()
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        for _ in range(self.workers):
            thread = Thread(target=self.update_worker)
            thread.start()

        self.get_updates()


    def stop(self, signum= None, frame= None):
        self.stop_request.set()


    def on_message(
        self,
        func: callable = None,
        labels: Union[list, str] = 'inbox',
        from_is: str = None,
        subject_is: str = None,
        subject_has: str = None
        ):

        @functools.wraps(func)
        def decorator(func):
            self.add_handler(MessageAddedHandler(func, labels, from_is, subject_is, subject_has))
            return func

        if func:
            return decorator(func)
        return decorator


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
        ) -> dict:
        if check_for_floods or self.prevent_flood:
            args = vars()
            if helper.check_if_sent_similar_message(self, args, check_for_floods or self.flood_prevention):
                return False
        message = utils.make_message(
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
            label_data = helper.get_label_raw_data(self.service, label_id)
            return Label(label_data, self)


    def get_lables(self):
        labels_data = helper.get_labels(self.service)
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

        body = utils.make_label_dict(name= name, message_list_visibility= message_list_visibility, label_list_visibility= label_list_visibility, 
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


    def get_auto_forwarding_settings(self) -> dict:
        return self.service.users().settings().getAutoForwarding(userId= 'me').execute()


    def get_imap_settings(self) -> dict:
        return self.service.users().settings().getImap(userId= 'me').execute()


    def get_language_settings(self) -> dict:
        return self.service.users().settings().getLanguage(userId= 'me').execute()


    def get_pop_settings(self) -> dict:
        return self.service.users().settings().getPop(userId= 'me').execute()


    def get_vacation_settings(self) -> dict:
        return self.service.users().settings().getVacation(userId= 'me').execute()


    def update_auto_forwarding_settings(
        self,
        enabled: bool,
        email_address: str,
        disposition: str
        ) -> dict:

        auto_forwarding = {
            'enabled': enabled,
            'emailAddress': email_address,
            'disposition': disposition
        }
        return self.service.users().settings().updateAutoForwarding(userId= 'me', body= auto_forwarding).execute()


    def update_imap_settings(
        self,
        enabled: bool,
        auto_expunge: bool,
        expunge_behavior: str,
        max_folder_size: int
        ) -> dict:

        imap_settings = {
            'enabled': enabled,
            'autoExpunge': auto_expunge,
            'expungeBehavior': expunge_behavior,
            'maxFolderSize': max_folder_size
        }
        return self.service.users().settings().updateImap(userId= 'me', body= imap_settings).execute()


    def update_language_settings(self, display_language: str) -> dict:
        language_settings = {
            'displayLanguage': display_language
        }
        return self.service.users().settings().updateLanguage(userId= 'me', body= language_settings).execute()


    def update_pop_settings(self, access_window: str, disposition: str) -> dict:
        pop_settings = {
            'accessWindow': access_window,
            'disposition': disposition
        }
        return self.service.users().settings().updateLanguage(userId= 'me', body= pop_settings).execute()


    def update_vacation_settings(
        self,
        enable_auto_reply: bool,
        response_subject: str,
        response_body_plain_text: str,
        response_body_html: str,
        restrict_to_contacts: bool,
        restrict_to_domain: bool,
        start_time: str, # TODO: take date object
        end_time: str
        ) -> dict:

        vacation_settings = {
            'enableAutoReply': enable_auto_reply,
            'responseSubject': response_subject,
            'responseBodyPlainText': response_body_plain_text,
            'responseBodyHtml': response_body_html,
            'restrictToContacts': restrict_to_contacts,
            'restrictToDomain': restrict_to_domain,
            'startTime': start_time,
            'endTime': end_time
        }
        return self.service.users().settings().updateVacation(userId= 'me', body= vacation_settings).execute()
