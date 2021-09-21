import base64
import time
from typing import Union, Generator, Callable, Type, List, Any
from datetime import date, datetime
from queue import Empty, Queue
from threading import Thread, Event
import functools
import signal
from . import utils, helper, message
from .. import service as service_module
from .handlers import MessageAddedHandler, BaseHandler
from .label import Label, LabelShow, MessageShow
from .flood_prevention import FloodPrevention




class GmailClient:


    def __init__(
        self,
        service: Union['service_module.GoogleService', str] = None,
        workers: int = 4,
        save_state: bool = False,
        update_interval: int = 1
        ):
        """Create a mailbox to interact with the Gmail API.

        Args:
            service (Union['service_module.GoogleService', str], optional): Pass either a GoogleService 
        instance or the GoogleService session name. Defaults to None.
            workers (int, optional): Number of threads to use when handling updates. Defaults to 4.
            save_state (bool, optional): whether or not to save the sate when the application 
        stops, if set to True and the application is then restarted and save_state is still set to True,
        the app will go back in time to handle the updated that happend while the app was offline.
        See the limitations here: https://developers.google.com/gmail/api/guides/sync#limitations. Defaults to False.
            update_interval (int, optional): How long to sleep before checking for updates again. Defaults to 1.
        """
        if isinstance(service, service_module.GoogleService):
            self.service = service

        else:
            if service:
                self.service = service_module.GoogleService(api= "gmail", session= service)
        self.workers = workers
        self.save_state = save_state
        self.update_interval = update_interval
        utils.add_encoding_aliases()
        self.handlers = {}
        self._handlers_config = {'labels': [], 'labels_per_type': {}}
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
        self.history_id = self.user.get("historyId")


    @property
    def sender_name(self):
        return self.user.get('sender_name')


    @sender_name.setter
    def sender_name(self, sender_name):
        sender_name = utils.encode_if_not_english(sender_name)
        self.user['sender_name'] = sender_name


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

        label_ids = utils.get_proper_label_ids(label_ids)

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


    def add_handler(self, handler: Type[BaseHandler]):
        for history_type in handler.history_types:
            self.handlers[history_type] = self.handlers.get(history_type, []) + [handler]
            self._handlers_config['labels_per_type'][history_type] = self._handlers_config['labels_per_type'].get(history_type, [])
            self._handlers_config['labels_per_type'][history_type] = utils.add_labels_to_handler_config(
                handler.labels, self._handlers_config['labels_per_type'][history_type])

        self._handlers_config['labels'] = utils.add_labels_to_handler_config(handler.labels, self._handlers_config['labels'])


    def update_worker(self):
        while True:
            full_update = self.updates_queue.get()
            if full_update is None:
                break

            utils.handle_update(self, full_update)


    def get_updates(self):
        ''' This is the main function which looks for updates on the
        account, and adds it to the queue.
        '''
        if self.service.service_state.get('history_id') and self.save_state:
            self.history_id = self.service.service_state['history_id']
        history_types = list(self.handlers.keys())
        # Determine which labels are to be handled, and if it's just
        # one, we can ask to api to only send us updates which matches
        # that label
        labels_to_handle = self._handlers_config['labels']
        label_id = labels_to_handle[0] if (not labels_to_handle is None and len(labels_to_handle) == 1) else None
        # If there's no handler's - quit.
        while history_types:
            data = helper.get_history_data(self.service, self.history_id, history_types, label_id)
            self.history_id = data['historyId']
            for history in data.get('history', []):
                if len(history) == 3:
                    self.updates_queue.put(utils.format_update(history))
            if self.stop_request.is_set():
                break
            time.sleep(self.update_interval)


    def _handle_stop(self):
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
                oldest_history_id = self.history_id
            self.service.save_state(int(oldest_history_id) - 1)

        # Stop the workers.
        for _ in range(self.workers):
            self.updates_queue.put(None)


    def run(self):
        self.service.make_thread_safe()
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        threads = []
        for _ in range(self.workers):
            thread = Thread(target=self.update_worker)
            thread.start()
            threads.append(thread)
        try:
            self.get_updates()
        except:
            raise
        finally:
            self._handle_stop()


    def stop(self, signum= None, frame= None):
        self.stop_request.set()


    def on_message(
        self,
        func: Callable[[Type['message.BaseMessage']], Any] = None,
        labels: Union[list, str] = 'inbox',
        filters: List[Callable[[Type['message.BaseMessage']], bool]] = None
        ):

        @functools.wraps(func)
        def decorator(func):
            self.add_handler(MessageAddedHandler(func, labels, filters))
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
        headers: dict = None
        ) -> dict:

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
            in_reply_to,
            headers
            )
        b64 = base64.urlsafe_b64encode(message).decode()
        body = {'raw': b64}
        if thread_id:
            body["threadId"] = thread_id
        data = self.service.message_service.send(userId= 'me', body= body).execute()
        return data


    def send_message_from_message_obj(
        self,
        message_obj: 'message.BaseMessage',
        to: Union[list, str] = None,
        cc: Union[list, str] = None,
        bcc: Union[list, str] = None
        ) -> None:
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


    def add_labels_to_message(self, message_id: str, label_ids: Union[list, str]) -> dict:
        return self.service.message_service.modify(userId= 'me', id= message_id, body= {'addLabelIds': utils.get_proper_label_ids(label_ids)}).execute()


    def remove_labels_from_message(self, message_id: str, label_ids: Union[list, str]) -> dict:
        return self.service.message_service.modify(userId= 'me', id= message_id, body= {'removeLabelIds': utils.get_proper_label_ids(label_ids)}).execute()


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
