from typing import Generator, Literal, Type, Union

from . import gmail, utils, message


class Thread:
    def __init__(
        self,
        gmail_client: "gmail.GmailClient",
        thread_data: dict,
        message_format: Literal["minimal", "full", "metadata"] = "full",
    ) -> None:
        self.gmail_client = gmail_client
        self.thread_data = thread_data
        self.message_format = message_format
        self.thread_id = self.thread_data["id"]
        # snippet is missing https://stackoverflow.com/questions/24577265/gmail-api-thread-list-snippet
        self.snippet = self.thread_data.get("snippet")
        self.history_id = self.thread_data["historyId"]
        self.number_of_messages = len(self.thread_data["messages"])

    def __len__(self) -> int:
        return self.number_of_messages

    def __str__(self) -> str:
        return self.thread_id

    @property
    def messages(self) -> Generator[Type["message.BaseMessage"], None, None]:
        message_class = utils.get_message_class(self.message_format)
        for message in self.thread_data["messages"]:
            yield message_class(self.gmail_client, message)

    def add_labels(self, label_ids: Union[list, str]):
        return self.gmail_client.add_labels_to_thread(self.thread_id, label_ids)

    def remove_labels(self, label_ids: Union[list, str]):
        return self.gmail_client.remove_labels_from_thread(self.thread_id, label_ids)

    def mark_read(self):
        return self.gmail_client.remove_labels_from_thread(self.thread_id, "unread")

    def mark_unread(self):
        return self.gmail_client.add_labels_to_thread(self.thread_id, "unread")

    def delete(self):
        return self.gmail_client.delete_thread(self.thread_id)

    def trash(self):
        return self.gmail_client.trash_thread(self.thread_id)

    def untrash(self):
        return self.gmail_client.untarsh_thread(self.thread_id)
