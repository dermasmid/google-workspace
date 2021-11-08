from typing import Generator, Type, Union

from typing_extensions import Literal

from . import gmail, message, utils


class Thread:
    """A message thread. This includes all messages and allows for bulk operations.

    Parameters:
        gmail_client (:obj:`~google_workspace.gmail.GmailClient`):
            The gmail_client.

        thread_data (``dict``):
            The raw thread data.

        message_format (``str``, *optional*):
            In which format to retrieve the messages. Can have one of the following values:
            ``"minimal"``, ``"full"``, ``"metadata"``. Defaults to: "full".
    """

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
        """The messages.

        Returns:
            Generator of :obj:`~google_workspace.gmail.message.Message` | :obj:`~google_workspace.gmail.message.MessageMetadata` | :obj:`~google_workspace.gmail.message.MessageMinimal`:
            A generator of the messages from this thread. Depending message_format it will return a different type of message.
        """

        message_class = utils.get_message_class(self.message_format)
        for message in self.thread_data["messages"]:
            yield message_class(self.gmail_client, message)

    def add_labels(self, label_ids: Union[list, str]) -> dict:
        """Add labels to this thread.

        Parameters:
            label_ids (``list`` | ``str``):
                The lables to add.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.add_labels_to_thread(self.thread_id, label_ids)

    def remove_labels(self, label_ids: Union[list, str]) -> dict:
        """Remove labels from this thread.

        Parameters:
            label_ids (``list`` | ``str``):
                The lables to remove.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.remove_labels_from_thread(self.thread_id, label_ids)

    def mark_read(self) -> dict:
        """Mark this thread and all of it's messages read.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.remove_labels_from_thread(self.thread_id, "unread")

    def mark_unread(self) -> dict:
        """Mark this thread and all of it's messages unread.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.add_labels_to_thread(self.thread_id, "unread")

    def delete(self) -> dict:
        """Delete this thread permanently.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.delete_thread(self.thread_id)

    def trash(self) -> dict:
        """Move this thread to the trash.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.trash_thread(self.thread_id)

    def untrash(self) -> dict:
        """Untrash this thread.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.untarsh_thread(self.thread_id)
