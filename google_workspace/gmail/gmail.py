import base64
import functools
import json
import signal
import time
from datetime import date
from queue import Queue
from threading import Event, Thread
from typing import Any, Callable, Generator, Iterable, Tuple, Type, Union

from googleapiclient.errors import HttpError
from typing_extensions import Literal

from .. import service as service_module
from . import helper, histories, message, thread, utils
from .handlers import BaseHandler, MessageAddedHandler
from .label import Label


class GmailClient:
    """Create a Gmail client to interact with the Gmail API.

    Parameters:
        service (:obj:`~google_workspace.service.GoogleService` | ``str``, *optional*):
            Pass either a GoogleService instance or the GoogleService session name.
            If left empty will use "gmail" for session name. If the service is not authenticated,
            we'll run local_oauth. Defaults to None.

        workers (``int``, *optional*):
            Number of threads to use when handling updates. Defaults to 4.

        save_state (``bool``, *optional*):
            whether or not to save the state when the application
            stops, if set to True and the application is then restarted and save_state is still set to True,
            the app will go back in time to handle the updated that happend while the app was offline.
            See the limitations here: https://developers.google.com/gmail/api/guides/sync#limitations. Defaults to False.

        update_interval (``int``, *optional*):
            How long to sleep before checking for updates again. Defaults to 1.

        email_address(``str``, *optional*):
            If you dont have enough scopes for getting the user's info, you have to specify the user's
            email address which will be used when sending messages.

        sender_name(``str``, *optional*):
            If you dont have enough scopes for getting the user's info, you can set the senders name here,
            and will be used when sending emails.

    Attributes:
        workers: Number of workers.
        save_state: whether to save the history_id.
        update_interval: How often to check for updates.
        sender_name: The user's name.
        email_address: The user's email address.
    """

    def __init__(
        self,
        service: Union["service_module.GoogleService", str] = None,
        workers: int = 4,
        save_state: bool = False,
        update_interval: int = 1,
        email_address: str = None,
        sender_name: str = None,
    ):

        if isinstance(service, service_module.GoogleService):
            self.service = service

        else:
            self.service = service_module.GoogleService(
                api="gmail", session=service or "gmail"
            )
            self.service.local_oauth()
        self.workers = workers
        self.save_state = save_state
        self.update_interval = update_interval
        utils.add_encoding_aliases()
        self.handlers = {}
        self._handlers_config = {"labels": [], "labels_per_type": {}}
        self.updates_queue = Queue()
        self.stop_request = Event()
        self._sender_name = sender_name
        self._email_address = email_address
        self._history_id = None
        self._user = None

    def __len__(self) -> int:
        return self.user.get("messagesTotal")

    def __str__(self) -> str:
        return f"email: {self.email_address or 'Not known'}, scopes: {self.service.authenticated_scopes}"

    @property
    def sender_name(self) -> str:
        if self._sender_name is None:
            self._sender_name = self.user.get("sender_name")
        return self._sender_name

    @sender_name.setter
    def sender_name(self, sender_name: str):
        self._sender_name = utils.encode_if_not_english(sender_name)

    @property
    def email_address(self) -> str:
        if self._email_address is None:
            self._email_address = self.user.get("emailAddress")
        return self._email_address

    @email_address.setter
    def email_address(self, email_address: str):
        self._email_address = email_address

    @property
    def history_id(self):
        if self._history_id is None:
            self._history_id = self.user.get("historyId")
        return self._history_id

    @history_id.setter
    def history_id(self, history_id: str):
        self._history_id = history_id

    @property
    def user(self) -> dict:
        if self._user is None:
            self._get_user()
        return self._user

    def get_messages(
        self,
        label_ids: Union[list, str] = None,
        seen: bool = None,
        from_: str = None,
        to: list = None,
        subject: str = None,
        after: date = None,
        before: date = None,
        label_name: str = None,
        include_spam_and_trash: bool = False,
        message_format: Literal["minimal", "full", "raw", "metadata"] = "raw",
        batch: bool = True,
        limit: int = None,
    ) -> Generator[Type["message.BaseMessage"], None, None]:
        """Search and get messages

        Parameters:
            label_ids (``list`` | ``str``, *optional*):
                Get only messages that have all these labels. Defaults to None.

            seen (``bool``, *optional*):
                Get only seen or unseen messages. Defaults to None.

            from_ (``str``, *optional*):
                Get only messages from this sender. Defaults to None.

            to (``list``, *optional*):
                Get only messages that where sent to this list of recipients. Defaults to None.

            subject (``str``, *optional*):
                Get only messages that have this subject. Defaults to None.

            after (:obj:`date`, *optional*):
                Get only messages that where send after this date. Defaults to None.

            before (:obj:`date`, *optional*):
                Get only messages that where sent before this date. Defaults to None.

            label_name (``str``, *optional*):
                Get only messages that have this label. differs from ``label_ids`` that this
                take the lable name, not the id. Defaults to None.

            include_spam_and_trash (``bool``, *optional*):
                Whether to include spam and trash in the results. Defaults to False.

            message_format (``str``, *optional*):
                In which format to retrieve the messages. Can have one of the following values:
                ``"minimal"``, ``"full"``, ``"raw"``, ``"metadata"``. Defaults to "raw".

            batch (``bool``, *optional*):
                Whether to use batch requests when fetching the messages. recommended when fetching
                a lot of messages. Defaults to True.

            limit (``int``, *optional*):
                Limit the number of messages to retrieve. especially useful when ``batch`` is ``True``
                to avoid downloading more messages then you need. Defaults to None.

        Returns:
            Generator of :obj:`~google_workspace.gmail.message.Message` | :obj:`~google_workspace.gmail.message.MessageMetadata` | :obj:`~google_workspace.gmail.message.MessageMinimal`:
            Depending message_format it will return a differenttype of message.
        """

        query = utils.gmail_query_maker(
            seen, from_, to, subject, after, before, label_name
        )
        label_ids = utils.get_proper_label_ids(label_ids)

        messages_generator = helper.get_messages_generator(
            self, label_ids, query, include_spam_and_trash, message_format, batch, limit
        )
        return messages_generator

    def get_message_by_id(
        self,
        message_id: str,
        message_format: Literal["minimal", "full", "raw", "metadata"] = "raw",
    ) -> Type["message.BaseMessage"]:
        """Get a message by it's id

        Parameters:
            message_id (``str``):
                The message id. (The ``gmail_id`` property)

            message_format (``str``, *optional*):
                In which format to retrieve the messages. Can have one of the following values:
                ``"minimal"``, ``"full"``, ``"raw"``, ``"metadata"``. Defaults to "raw".

        Returns:
            :obj:`~google_workspace.gmail.message.Message` | :obj:`~google_workspace.gmail.message.MessageMetadata` | :obj:`~google_workspace.gmail.message.MessageMinimal`:
            Depending message_format it will return a differenttype of message.
        """

        message_class = utils.get_message_class(message_format)
        raw_message = helper.get_message_data(self.service, message_id, message_format)
        return message_class(self, raw_message)

    def get_threads(
        self,
        label_ids: Union[list, str] = None,
        seen: bool = None,
        from_: str = None,
        to: list = None,
        subject: str = None,
        after: date = None,
        before: date = None,
        label_name: str = None,
        include_spam_and_trash: bool = False,
        message_format: Literal["minimal", "full", "metadata"] = "full",
        batch: bool = True,
        limit: int = None,
    ) -> Generator["thread.Thread", None, None]:
        """Search and get threads

        Parameters:
            label_ids (``list`` | ``str``, *optional*):
                Get only threads that have all these labels. Defaults to None.

            seen (``bool``, *optional*):
                Get only seen or unseen threads. Defaults to None.

            from_ (``str``, *optional*):
                Get only threads from this sender. Defaults to None.

            to (``list``, *optional*):
                Get only threads that where sent to this list of recipients. Defaults to None.

            subject (``str``, *optional*):
                Get only threads that have this subject. Defaults to None.

            after (:obj:`date`, *optional*):
                Get only threads that where send after this date. Defaults to None.

            before (:obj:`date`, *optional*):
                Get only threads that where sent before this date. Defaults to None.

            label_name (``str``, *optional*):
                Get only threads that have this label. differs from ``label_ids`` that this
                take the lable name, not the id. Defaults to None.

            include_spam_and_trash (``bool``, *optional*):
                Whether to include spam and trash in the results. Defaults to False.

            message_format (``str``, *optional*):
                In which format to retrieve the messages. Can have one of the following values:
                ``"minimal"``, ``"full"``, ``"metadata"``. Defaults to "full".

            batch (``bool``, *optional*):
                Whether to use batch requests when fetching the threads. recommended when fetching
                a lot of threads. Defaults to True.

            limit (``int``, *optional*):
                Limit the number of threads to retrieve. especially useful when ``batch`` is ``True``
                to avoid downloading more threads then you need. Defaults to None.

        Returns:
            Generator of :obj:`~google_workspace.gmail.thread.Thread`: A generator of all the threads the matched you query.
        """

        query = utils.gmail_query_maker(
            seen, from_, to, subject, after, before, label_name
        )
        label_ids = utils.get_proper_label_ids(label_ids)

        threads_generator = helper.get_messages_generator(
            self,
            label_ids,
            query,
            include_spam_and_trash,
            message_format,
            batch,
            limit,
            True,
        )
        return threads_generator

    def get_thread_by_id(
        self,
        thread_id: str,
        message_format: Literal["minimal", "full", "metadata"] = "full",
    ) -> "thread.Thread":
        """Get a thread by it's id

        Parameters:
            thread_id (``str``):
                The thread id.

            message_format (``str``, *optional*):
                In which format to retrieve the messages. Can have one of the following values:
                ``"minimal"``, ``"full"``, ``"metadata"``.  Defaults to "full".

        Returns:
            :obj:`~google_workspace.gmail.thread.Thread`: The full thread with all it's messages.
        """

        raw_thread = helper.get_message_data(
            self.service, thread_id, message_format, True
        )
        return thread.Thread(self, raw_thread, message_format)

    def add_handler(self, handler: Type[BaseHandler]) -> None:
        """Add a handler.

        Parameters:
            handler (:obj:`~google_workspace.gmail.handlers.BaseHandler`):
                The handler you would like to add.
        """

        for history_type in handler.history_types:
            self.handlers[history_type] = self.handlers.get(history_type, []) + [
                handler
            ]
            self._handlers_config["labels_per_type"][
                history_type
            ] = self._handlers_config["labels_per_type"].get(history_type, [])
            self._handlers_config["labels_per_type"][
                history_type
            ] = utils.add_labels_to_handler_config(
                handler.labels, self._handlers_config["labels_per_type"][history_type]
            )

        self._handlers_config["labels"] = utils.add_labels_to_handler_config(
            handler.labels, self._handlers_config["labels"]
        )

    def update_worker(self) -> None:
        while True:
            history = self.updates_queue.get()
            if history is None:
                break

            utils.handle_update(self, history)

    def get_updates(self) -> None:
        """This is the main function which looks for updates on the
        account, and adds it to the queue.
        """

        if self.save_state:
            self.history_id = self.service.get_value("history_id") or self.history_id
        history_types = list(self.handlers.keys())
        # Determine which labels are to be handled, and if it's just
        # one, we can ask to api to only send us updates which matches
        # that label
        labels_to_handle = self._handlers_config["labels"]
        label_id = (
            labels_to_handle[0]
            if (not labels_to_handle is None and len(labels_to_handle) == 1)
            else None
        )
        # If there's no handler's - quit.
        while history_types:
            histories = self.get_history(self.history_id, label_id, history_types)
            self.history_id = histories.history_id
            for history in histories:
                self.updates_queue.put(history)
            if self.stop_request.is_set():
                break
            time.sleep(self.update_interval)

    def _handle_stop(self) -> None:
        if not self.save_state:
            with self.updates_queue.mutex:
                self.updates_queue.queue.clear()
        else:
            if not self.history_id is None:
                self.service.set_value("history_id", int(self.history_id) - 1)
                self.service.save_service_state()

        # Stop the workers.
        for _ in range(self.workers):
            self.updates_queue.put(None)

    def run(self) -> None:
        """Check for updates and have the handers handle it."""

        self.service.make_thread_safe()
        signal.signal(signal.SIGINT, self.quit)
        signal.signal(signal.SIGTERM, self.quit)
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

    def quit(self, signum=None, frame=None) -> None:
        self.stop_request.set()

    def on_message(
        self,
        func: Callable[["histories.History"], Any] = None,
        labels: Union[list, str] = "inbox",
        filters: Iterable[Callable[["histories.History"], bool]] = None,
    ):
        """Helper decorator to add a :obj:`~google_workspace.gmail.handlers.MessageAddedHandler` handler.

        Parameters:
            labels: (``list`` | ``str``, *optional*):
                Filter for messages that that have these lables. Defaults to ``"inbox"``.

            filters (``list``, *optional*):
                A list of filters. A filter is a function that takes in a message as an argument
                and returns ``True`` or ``False``. Defaults to False.
        """

        @functools.wraps(func)
        def decorator(func):
            self.add_handler(MessageAddedHandler(func, labels, filters))
            return func

        if func:
            return decorator(func)
        return decorator

    def get_history(
        self,
        start_history_id: int,
        label_id: str = None,
        history_types: Iterable[
            Literal["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"]
        ] = None,
        max_results: int = None,
    ) -> "histories.ListHistoryResponse":
        """Get everything that happened in the account since start_history_id.

        Parameters:
            start_history_id(``int``):
                Where to start the results from.

            label_id(``str``, *optional*):
                Only return histories which have the label in thier message.

            history_types(``str``, *optional*):
                Only return histories of this types.

            max_results(``int``, *optional*):
                Maximum number of history records to return. The maximum allowed value for this field is 500.

        Returns:
            :obj:`~google_workspace.gmail.histories.listHistoryResponse`: A iterable of histories.
        """

        return histories.ListHistoryResponse(
            self,
            start_history_id,
            history_types,
            label_id,
            max_results,
        )

    @staticmethod
    def decode_pub_sub_message(message: Union[str, bytes]) -> dict:
        """Decodes an incoming pub/sub message.

        Parameters:
            message(``str`` | ``bytes``):
                The message recived from Google, as text or bytes.

        Returns:
            ``dict``: The actual message like this: {"emailAddress": "user@example.com", "historyId": "9876543210"}
        """
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        message_dict = json.loads(message)
        return json.loads(
            base64.b64decode(message_dict["message"]["data"]).decode("utf-8")
        )

    def send_message(
        self,
        to: Union[list, str] = None,
        subject: str = "",
        text: str = None,
        html: str = None,
        attachments: Union[Iterable[str], Iterable[Tuple[bytes, str]]] = [],
        cc: Union[list, str] = None,
        bcc: Union[list, str] = None,
        references: str = None,
        in_reply_to: str = None,
        thread_id: str = None,
        headers: dict = None,
    ) -> dict:
        """Send a message.

        Parameters:
            to (``list`` | ``str``, *optional*):
                Who to send the message to. Can be either a string or a list of strings. Defaults to None.

            subject (``str``, *optional*):
                The message subject. Defaults to "".

            text (``str``, *optional*):
                The plain text of the message. if you only specify ``html`` the text will be automaticly
                generated. Defaults to None.

            html (``str``, *optional*):
                The html of the message. Defaults to None.

            attachments (``list``, *optional*):
                A List of attachments. Can be a list of file paths like this ["image.png", "doc.pdf"],
                or it can be a list of lists where every list consists of the attachment data and a name
                for the attachment like this [[b"some binary here", "image.png"]].
                Defaults to [].

            cc (``list`` | ``str``, *optional*):
                The cc recipients. Defaults to None.

            bcc (``list`` | ``str``, *optional*):
                The bcc recipients. Defaults to None.

            references (``str``, *optional*):
                Message references, used for replies. Defaults to None.

            in_reply_to (``str``, *optional*):
                The message this replies to. Defaults to None.

            thread_id (``str``, *optional*):
                The thread id of the message you are replying to. Defaults to None.

            headers (``dict``, *optional*):
                Additional headers to add to the message. Defaults to None.

        Returns:
            ``dict``: The API response.
        """

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
            headers,
        )
        b64 = base64.urlsafe_b64encode(message).decode()
        body = {"raw": b64}
        if thread_id:
            body["threadId"] = thread_id
        data = self.service.messages_service.send(userId="me", body=body).execute()
        return data

    def watch(
        self,
        topic_name: str,
        label_filter_action: Literal["include", "exclude"] = None,
        label_ids: Union[list, str] = None,
    ) -> dict:
        """Set up or update a push notification watch on the given user mailbox.

        Parameters:
            topic_name (``str``):
                A fully qualified Google Cloud Pub/Sub API topic name to publish the events to.

            label_filter_action (``str``, *optional*):
                Filtering behavior of labelIds list specified.
                Can have one of the following values: ``"include"``, ``"exclude"``. Defaults to: None.

            label_ids (``list`` | ``str``, *optional*):
                List of labelIds to restrict notifications about. By default, if unspecified, all changes are pushed out.
                If specified then dictates which labels are required for a push notification to be generated.
                Defaults to: None.

        Returns:
            ``dict``: The API response.
        """

        return self.service.users_service.watch(
            userId="me",
            body={
                "labelIds": utils.get_proper_label_ids(label_ids),
                "labelFilterAction": label_filter_action,
                "topicName": topic_name,
            },
        ).execute()

    def stop(self) -> dict:
        """Stop receiving push notifications for the given user mailbox.

        Returns:
            ``dict``: The API response.
        """

        return self.service.users_service.stop(userId="me").execute()

    def get_label_by_id(self, label_id: str) -> Label:
        """Get a label by it's id.

        Parameters:
            label_id (``str``):
                The label id.

        Returns:
            :obj:`~google_workspace.gmail.label.Label`: The label.
        """

        label_data = helper.get_label_raw_data(self.service, label_id)
        return Label(self, label_data)

    def get_lables(self) -> Generator[Label, None, None]:
        """Get all Labels.

        Returns:
            Generator of :obj:`~google_workspace.gmail.label.Label`: A generator of all the labels.
        """
        labels_data = helper.get_labels(self.service)
        for label in labels_data["labels"]:
            yield self.get_label_by_id(label["id"])

    def create_label(
        self,
        name: str,
        message_list_visibility: Literal["show", "hide"] = "show",
        label_list_visibility: Literal[
            "labelShow", "labelShowIfUnread", "labelHide"
        ] = "labelShow",
        background_color: str = None,
        text_color: str = None,
    ) -> Label:
        """Create a label

        Parameters:
            name (``str``):
                The display name of the label.

            message_list_visibility (``str``, *optional*):
                The visibility of messages with this label in the message list in the Gmail web interface.
                Can have one of the following values: ``"show"``, ``"hide"``
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/users.labels#messagelistvisibility>`__.
                Defaults to: "show".

            label_list_visibility (``str``, *optional*):
                The visibility of the label in the label list in the Gmail web interface.
                Can have one of the following values: ``"labelShow"``, ``"labelShowIfUnread"``, ``"labelHide"``
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/users.labels#labellistvisibility>`__.
                Defaults to: "labelShow".

            background_color (``str``, *optional*):
                The background color represented as hex string. Defaults to None.

            text_color (``str``, *optional*):
                The text color of the label, represented as hex string. Defaults to None.

        Returns:
            :obj:`~google_workspace.gmail.label.Label`: The created label.
        """

        body = utils.make_label_dict(
            name=name,
            message_list_visibility=message_list_visibility,
            label_list_visibility=label_list_visibility,
            background_color=background_color,
            text_color=text_color,
        )

        data = self.service.labels_service.create(userId="me", body=body).execute()
        return self.get_label_by_id(data["id"])

    def get_filters(self) -> dict:
        """Get filters.

        Returns:
            ``dict``: The API response.
        """

        return self.service.settings_service.filters().list(userId="me").execute()

    def delete_thread(self, thread_id: str) -> dict:
        """Delete an entire thread.

        Parameters:
            thread_id (``str``):
                The thread id.

        Returns:
            ``dict``: The API response.
        """

        return self.service.threads_service.delete(userId="me", id=thread_id).execute()

    def trash_thread(self, thread_id: str) -> dict:
        """Trash an entire thread.

        Parameters:
            thread_id (``str``):
                The thread id.

        Returns:
            ``dict``: The API response.
        """

        return self.service.threads_service.trash(userId="me", id=thread_id).execute()

    def untarsh_thread(self, thread_id: str) -> dict:
        """Untrash a thread.

        Parameters:
            thread_id (``str``):
                The thread id.

        Returns:
            ``dict``: The API response.
        """

        return self.service.threads_service.untrash(userId="me", id=thread_id).execute()

    def add_labels_to_thread(self, thread_id: str, label_ids: Union[list, str]) -> dict:
        """Add labels to all messages in a thread.

        Parameters:
            thread_id (``str``):
                The thread id.

            label_ids (``list`` | ``str``):
                The labels to add.

        Returns:
            ``dict``: The API response.
        """

        return self.service.threads_service.modify(
            userId="me",
            id=thread_id,
            body={"addLabelIds": utils.get_proper_label_ids(label_ids)},
        ).execute()

    def remove_labels_from_thread(
        self, thread_id: str, label_ids: Union[list, str]
    ) -> dict:
        """Remove labels from all messages in thread.

        Parameters:
            thread_id (``str``):
                The thread id.

            label_ids (``list`` | ``str``):
                The labels to remove.

        Returns:
            ``dict``: The API response.
        """

        return self.service.threads_service.modify(
            userId="me",
            id=thread_id,
            body={"removeLabelIds": utils.get_proper_label_ids(label_ids)},
        ).execute()

    def delete_message(self, message_id: str) -> dict:
        """Delete a message.

        Parameters:
            message_id (``str``):
                The message id.

        Returns:
            ``dict``: The API response.
        """

        return self.service.messages_service.delete(
            userId="me", id=message_id
        ).execute()

    def trash_message(self, message_id: str) -> dict:
        """Trash a message.

        Parameters:
            message_id (``str``):
                The message id.

        Returns:
            ``dict``: The API response.
        """

        return self.service.messages_service.trash(userId="me", id=message_id).execute()

    def untrash_message(self, message_id: str) -> dict:
        """Untrash a message.

        Parameters:
            message_id (``str``):
                The message id.

        Returns:
            ``dict``: The API response.
        """

        return self.service.messages_service.untrash(
            userId="me", id=message_id
        ).execute()

    def add_labels_to_message(
        self, message_id: str, label_ids: Union[list, str]
    ) -> dict:
        """Add labels to a message

        Parameters:
            message_id (``str``):
                The message id.

            label_ids (``list`` | ``str``):
                The labels to add.

        Returns:
            ``dict``: The API response.
        """

        return self.service.messages_service.modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": utils.get_proper_label_ids(label_ids)},
        ).execute()

    def remove_labels_from_message(
        self, message_id: str, label_ids: Union[list, str]
    ) -> dict:
        """Remove labels from a message.

        Parameters:
            message_id (``str``):
                The message id.

            label_ids (``list`` | ``str``):
                The labels to remove.

        Returns:
            ``dict``: The API response.
        """

        return self.service.messages_service.modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": utils.get_proper_label_ids(label_ids)},
        ).execute()

    def mark_message_as_read(self, message_id: str) -> dict:
        """Mark a message as read.

        Parameters:
            message_id (``str``):
                The message id.

        Returns:
            ``dict``: The API response.
        """

        return self.remove_labels_from_message(message_id, ["UNREAD"])

    def mark_message_as_unread(self, message_id: str) -> dict:
        """Mark a message as unread.

        Parameters:
            message_id (``str``):
                The message id.

        Returns:
            ``dict``: The API response.
        """

        return self.add_labels_to_message(message_id, ["UNREAD"])

    def get_auto_forwarding_settings(self) -> dict:
        """Get auto forwarding settings.

        Returns:
            ``dict``: The API response.
        """
        return self.service.settings_service.getAutoForwarding(userId="me").execute()

    def get_imap_settings(self) -> dict:
        """Get imap settings.

        Returns:
            ``dict``: The API response.
        """
        return self.service.settings_service.getImap(userId="me").execute()

    def get_language_settings(self) -> dict:
        """Get language settings.

        Returns:
            ``dict``: The API response.
        """
        return self.service.settings_service.getLanguage(userId="me").execute()

    def get_pop_settings(self) -> dict:
        """Get pop settings.

        Returns:
            ``dict``: The API response.
        """
        return self.service.settings_service.getPop(userId="me").execute()

    def get_vacation_settings(self) -> dict:
        """Get vacation settings.

        Returns:
            ``dict``: The API response.
        """
        return self.service.settings_service.getVacation(userId="me").execute()

    def update_auto_forwarding_settings(
        self,
        enabled: bool,
        email_address: str,
        disposition: Literal[
            "dispositionUnspecified", "leaveInInbox", "archive", "trash", "markRead"
        ],
    ) -> dict:
        """Update auto forwarding settings.
        This method is only available to service account clients that have been delegated domain-wide authority.

        Parameters:
            enabled (``bool``):
                Whether all incoming mail is automatically forwarded to another address.

            email_address (``str``):
                Email address to which all incoming messages are forwarded.
                This email address must be a verified member of the forwarding addresses.

            disposition (``str``):
                The state that a message should be left in after it has been forwarded.
                Can have one of the following values: ``"dispositionUnspecified"``,
                ``"leaveInInbox"``, ``"archive"``, ``"trash"``, ``"markRead"``.
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/AutoForwarding#disposition>`__.

        Returns:
            ``dict``: The API response.
        """

        auto_forwarding = {
            "enabled": enabled,
            "emailAddress": email_address,
            "disposition": disposition,
        }
        return self.service.settings_service.updateAutoForwarding(
            userId="me", body=auto_forwarding
        ).execute()

    def update_imap_settings(
        self,
        enabled: bool,
        auto_expunge: bool,
        expunge_behavior: Literal[
            "expungeBehaviorUnspecified", "archive", "trash", "deleteForever"
        ],
        max_folder_size: int,
    ) -> dict:
        """Update IMAP settings.

        Parameters:
            enabled (``bool``):
                Whether IMAP is enabled for the account.

            auto_expunge (``bool``):
                If this value is true, Gmail will immediately expunge a message when it is marked as deleted in IMAP.
                Otherwise, Gmail will wait for an update from the client before expunging messages marked as deleted.

            expunge_behavior (``str``):
                The action that will be executed on a message when it is marked
                as deleted and expunged from the last visible IMAP folder.
                Can have one of the following values: ``"expungeBehaviorUnspecified"``, ``"archive"``,
                ``"trash"``, ``"deleteForever"``
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/ImapSettings#expungebehavior>`__.

            max_folder_size (``int``):
                An optional limit on the number of messages that an IMAP folder may contain.
                Legal values are 0, 1000, 2000, 5000 or 10000.
                A value of zero is interpreted to mean that there is no limit.

        Returns:
            ``dict``: The API response.
        """

        imap_settings = {
            "enabled": enabled,
            "autoExpunge": auto_expunge,
            "expungeBehavior": expunge_behavior,
            "maxFolderSize": max_folder_size,
        }
        return self.service.settings_service.updateImap(
            userId="me", body=imap_settings
        ).execute()

    def update_language_settings(self, display_language: str) -> dict:
        """Updates language settings.

        Parameters:
            display_language (``str``):
                The language to display Gmail in, formatted as an RFC 3066 Language Tag
                (for example en-GB, fr or ja for British English, French, or Japanese respectively).

        Returns:
            ``dict``: The API response.
        """

        language_settings = {"displayLanguage": display_language}
        return self.service.settings_service.updateLanguage(
            userId="me", body=language_settings
        ).execute()

    def update_pop_settings(
        self,
        access_window: Literal[
            "accessWindowUnspecified", "disabled", "fromNowOn", "allMail"
        ],
        disposition: Literal[
            "dispositionUnspecified", "leaveInInbox", "archive", "trash", "markRead"
        ],
    ) -> dict:
        """Updates POP settings.

        Parameters:
            access_window (``str``):
                The range of messages which are accessible via POP.
                Can have one of the following values: ``"accessWindowUnspecified"``, ``"disabled"``, ``"fromNowOn"``, ``"allMail"``
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/PopSettings#accesswindow>`__.

            disposition (``str``):
                The action that will be executed on a message after it has been fetched via POP.
                Can have one of the following values: ``"dispositionUnspecified"``, ``"leaveInInbox"``, ``"archive"``, ``"trash"``, ``"markRead"``
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/PopSettings#disposition>`__.

        Returns:
            ``dict``: The API response.
        """

        pop_settings = {"accessWindow": access_window, "disposition": disposition}
        return self.service.settings_service.updateLanguage(
            userId="me", body=pop_settings
        ).execute()

    def update_vacation_settings(
        self,
        enable_auto_reply: bool,
        response_subject: str,
        response_body_plain_text: str,
        response_body_html: str,
        restrict_to_contacts: bool,
        restrict_to_domain: bool,
        start_time: int,  # TODO: take date object
        end_time: int,
    ) -> dict:
        """Updates vacation responder settings.

        Parameters:
            enable_auto_reply (``bool``):
                Flag that controls whether Gmail automatically replies to messages.

            response_subject (``str``):
                Optional text to prepend to the subject line in vacation responses.
                In order to enable auto-replies, either the response subject
                or the response body must be nonempty.

            response_body_plain_text (``str``):
                Response body in plain text format.
                If both ``response_body_plain_text`` and ``response_body_html`` are specified,
                ``response_body_html`` will be used.

            response_body_html (``str``):
                Response body in HTML format. Gmail will sanitize the HTML before storing it.
                If both ``response_body_plain_text`` and ``response_body_html`` are specified,
                ``response_body_html`` will be used.

            restrict_to_contacts (``bool``):
                Flag that determines whether responses are sent to recipients
                who are not in the user's list of contacts.

            restrict_to_domain (``bool``):
                Flag that determines whether responses are sent to recipients who are
                outside of the user's domain. This feature is only available for G Suite users.

            start_time (``int``):
                An optional start time for sending auto-replies (epoch ms). When this is specified,
                Gmail will automatically reply only to messages that it receives after the start time.
                If both startTime and endTime are specified, startTime must precede endTime.

            end_time (``int``):
                An optional end time for sending auto-replies (epoch ms). When this is specified,
                Gmail will automatically reply only to messages that it receives before the end time.
                If both startTime and endTime are specified, startTime must precede endTime.

        Returns:
            ``dict``: The API response.
        """

        vacation_settings = {
            "enableAutoReply": enable_auto_reply,
            "responseSubject": response_subject,
            "responseBodyPlainText": response_body_plain_text,
            "responseBodyHtml": response_body_html,
            "restrictToContacts": restrict_to_contacts,
            "restrictToDomain": restrict_to_domain,
            "startTime": start_time,
            "endTime": end_time,
        }
        return self.service.settings_service.updateVacation(
            userId="me", body=vacation_settings
        ).execute()

    def _get_user(self):
        try:
            self._user = self.service.users_service.getProfile(userId="me").execute()
        except HttpError as e:
            if e.reason == "Request had insufficient authentication scopes.":
                # Not sufficient permissions.
                self._user = {}
            else:
                raise
