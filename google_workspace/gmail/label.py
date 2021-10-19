from typing import Generator, Literal, Type

from . import gmail, message
from .utils import make_label_dict


class Label:
    def __init__(self, raw_label: dict, gmail_client: "gmail.GmailClient"):
        self.gmail_client = gmail_client
        self.raw_label = raw_label
        self.id = raw_label.get("id")
        self.name = raw_label.get("name")
        self.message_list_visibility = raw_label.get("messageListVisibility")
        self.label_list_visibility = raw_label.get("labelListVisibility")
        self.type = raw_label.get("type")
        self.is_system = self.type == "system"
        self.total_messages = raw_label.get("messagesTotal")
        self.messages_unread = raw_label.get("messagesUnread")
        self.total_threads = raw_label.get("threadsTotal")
        self.threads_unread = raw_label.get("threadsUnread")
        self.color = raw_label.get("color")

    def __repr__(self) -> str:
        return str(self.raw_label)

    def get_messages(self) -> Generator[Type["message.BaseMessage"], None, None]:
        return self.gmail_client.get_messages(label_ids=self.id)

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
