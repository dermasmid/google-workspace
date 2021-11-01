from typing import Iterable, Literal

from . import gmail, helper


class History:
    def __init__(
        self,
        gmail_client: "gmail.GmailClient",
        history_data: dict,
        history_type: Literal[
            "messageAdded", "messageDeleted", "labelAdded", "labelRemoved"
        ],
        message_format: Literal["minimal", "full", "raw", "metadata"] = "raw",
    ) -> None:
        self.gmail_client = gmail_client
        self.history_data = history_data
        self.history_type = history_type
        self.message_format = message_format
        self.label_ids = history_data["message"].get("labelIds", [])
        self.thread_id = history_data["message"]["threadId"]
        self.gmail_id = history_data["message"]["id"]
        self.modified_labels = history_data.get("labelIds", [])
        self.message_added = history_type == "messageAdded"
        self.message_deleted = history_type == "messageDeleted"
        self.label_added = history_type == "labelAdded"
        self.label_removed = history_type == "labelRemoved"
        self._message = None

    @property
    def message(self):
        if not self._message:
            self._message = self.gmail_client.get_message_by_id(
                self.gmail_id, self.message_format
            )
        return self._message

    def __str__(self) -> str:
        return f"History {self.history_type} Message ID {self.gmail_id} Labels {self.label_ids}"


class listHistoryResponse:
    def __init__(
        self,
        gmail_client: "gmail.GmailClient",
        start_history_id: int,
        history_types: Iterable[
            Literal["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"]
        ] = None,
        label_id: str = None,
        max_results: int = None,
    ) -> None:
        self.gmail_client = gmail_client
        self.start_history_id = start_history_id
        self.history_types = history_types
        self.label_id = label_id
        self.max_results = max_results
        self.next_page_token = None
        self._get_history_data()
        self.history_id = self.history_response_data["historyId"]

    def __iter__(self):
        while True:
            try:
                history = next(self.histories)
            except StopIteration:
                if self.next_page_token:
                    self._get_history_data()
                    continue
                else:
                    break
            if len(history) > 2:
                for message in history.get("messagesAdded", []):
                    yield History(self.gmail_client, message, "messageAdded")

                for message in history.get("messagesDeleted", []):
                    yield History(self.gmail_client, message, "messageDeleted")

                for message in history.get("labelsAdded", []):
                    yield History(self.gmail_client, message, "labelAdded")

                for message in history.get("labelsRemoved", []):
                    yield History(self.gmail_client, message, "labelRemoved")

    def _get_history_data(self):
        self.history_response_data = helper.get_history_data(
            self.gmail_client,
            self.start_history_id,
            self.history_types,
            self.label_id,
            self.next_page_token,
            self.max_results,
        )
        self.histories = iter(self.history_response_data.get("history", []))
        self.next_page_token = self.history_response_data.get("nextPageToken")
