from typing import Generator, Type

from typing_extensions import Literal

from . import gmail, message
from .utils import make_label_dict


class Label:
    """A gmail label.

    Parameters:
        gmail_client (:obj:`~google_workspace.gmail.GmailClient`):
            The gmail_client.

        thread_data (``dict``):
            The raw label data.
    """

    def __init__(self, gmail_client: "gmail.GmailClient", label_data: dict):
        self.gmail_client = gmail_client
        self.raw_label = label_data
        self.id = label_data.get("id")
        self.name = label_data.get("name")
        self.message_list_visibility = label_data.get("messageListVisibility")
        self.label_list_visibility = label_data.get("labelListVisibility")
        self.type = label_data.get("type")
        self.is_system = self.type == "system"
        self.total_messages = label_data.get("messagesTotal")
        self.messages_unread = label_data.get("messagesUnread")
        self.total_threads = label_data.get("threadsTotal")
        self.threads_unread = label_data.get("threadsUnread")
        self.color = label_data.get("color")

    def __repr__(self) -> str:
        return str(self.raw_label)

    def get_messages(
        self,
        message_format: Literal["minimal", "full", "raw", "metadata"] = "raw",
    ) -> Generator[Type["message.BaseMessage"], None, None]:
        """Get all messgaes with this label.

        Parameters:
            message_format (``str``, *optional*):
                In which format to retrieve the messages. Can have one of the following values:
                ``"minimal"``, ``"full"``, ``"raw"``, ``"metadata"``. Defaults to "raw".

        Returns:
            Generator of :obj:`~google_workspace.gmail.message.Message` | :obj:`~google_workspace.gmail.message.MessageMetadata` | :obj:`~google_workspace.gmail.message.MessageMinimal`:
            A generator of the messages.
        """

        return self.gmail_client.get_messages(
            label_ids=self.id, message_format=message_format
        )

    def modify(
        self,
        name: str = None,
        message_list_visibility: Literal["show", "hide"] = None,
        label_list_visibility: Literal[
            "labelShow", "labelShowIfUnread", "labelHide"
        ] = None,
        background_color: str = None,
        text_color: str = None,
    ):
        """Modfy this label.

        Parameters:
            name (``str``, *optional*):
                The name name for this label.

            message_list_visibility (``str``, *optional*):
                The visibility of messages with this label in the message list in the Gmail web interface.
                Can have one of the following values: ``"show"``, ``"hide"``
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/users.labels#messagelistvisibility>`__.

            label_list_visibility (``str``, *optional*):
                The visibility of the label in the label list in the Gmail web interface.
                Can have one of the following values: ``"labelShow"``, ``"labelShowIfUnread"``, ``"labelHide"``
                For more information visit the `Gmail API documentation <https://developers.google.com/gmail/api/reference/rest/v1/users.labels#labellistvisibility>`__.

            background_color (``str``, *optional*):
                The background color represented as hex string. Defaults to None.

            text_color (``str``, *optional*):
                The text color of the label, represented as hex string. Defaults to None.

        Returns:
            :obj:`~google_workspace.gmail.label.Label`: The created label.
        """
        assert not self.is_system, "Cant modify system labels"
        body = make_label_dict(
            name=name,
            message_list_visibility=message_list_visibility,
            label_list_visibility=label_list_visibility,
            background_color=background_color,
            text_color=text_color,
        )
        data = self.gmail_client.service.labels_service.patch(
            userId="me", id=self.id, body=body
        ).execute()
        return self.gmail_client.get_label_by_id(data["id"])
