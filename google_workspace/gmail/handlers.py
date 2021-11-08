from typing import Any, Callable, Iterable, List, Union

from typing_extensions import Literal

from . import histories, utils

HISTORY_TYPE_LITERAL = Literal[
    "messageAdded", "messageDeleted", "labelAdded", "labelRemoved"
]


class BaseHandler:
    """A handler class with no history type filter.

    Parameters:
        callback (``callable``):
            A callback function to execute when there's a new update. The function should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History`.

        labels (``list`` | ``str``, *optional*):
            Handle only updates to messages that have all of these labels.
            Defaults to None.

        filters (``list``, *optional*):
            A list of functions. The functions should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History` and should return a bool if the message should be handled or not.
            Defaults to None.

        history_types (``str``, *optional*):
            Which history types to handle. Can have one of the following values: ``"messageAdded"``,
            ``"messageDeleted"``, ``"labelAdded"``, ``"labelRemoved"``.
            Defaults to None.

        modified_labels (``list`` | ``str``, *optional*):
            For labelAdded and labelRemoved history types, only handle message that have all of these
            labels modified.
    """

    def __init__(
        self,
        callback: Callable[["histories.History"], Any],
        labels: Union[list, str] = None,
        filters: Iterable[Callable[["histories.History"], bool]] = None,
        history_types: List[HISTORY_TYPE_LITERAL] = None,
        modified_labels: Union[list, str] = None,
    ) -> None:

        self.callback = callback
        self.labels = utils.get_proper_label_ids(labels)
        self.filters = filters
        self.history_types = (
            history_types
            if history_types
            else ["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"]
        )
        self.modified_labels = modified_labels

    def check(self, history: "histories.History") -> bool:
        if not self.labels is None:
            if not all(label in history.label_ids for label in self.labels):
                return False

        if not self.modified_labels is None:
            if history.modified_labels:
                if not all(
                    label in history.modified_labels for label in self.modified_labels
                ):
                    return False

        if not self.filters is None:
            for filter in self.filters:
                if not filter(history):
                    return False

        return True


class MessageAddedHandler(BaseHandler):
    """A handler class with the messageAdded history type filter.

    Parameters:
        callback (``callable``):
            A callback function to execute when there's a new update. The function should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History`.

        labels (``list`` | ``str``, *optional*):
            Handle only updates to messages that have all of these labels.
            Defaults to None.

        filters (``list``, *optional*):
            A list of functions. The functions should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History` and should return a bool if the message should be handled or not.
            Defaults to None.
    """

    def __init__(
        self,
        callback: Callable[["histories.History"], Any],
        labels: Union[list, str] = None,
        filters: Iterable[Callable[["histories.History"], bool]] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ["messageAdded"])


class MessageDeletedHandler(BaseHandler):
    """A handler class with the messageDeleted history type filter.

    Parameters:
        callback (``callable``):
            A callback function to execute when there's a new update. The function should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History`.

        labels (``list`` | ``str``, *optional*):
            Handle only updates to messages that have all of these labels.
            Defaults to None.

        filters (``list``, *optional*):
            A list of functions. The functions should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History` and should return a bool if the message should be handled or not.
            Defaults to None.
    """

    def __init__(
        self,
        callback: Callable[["histories.History"], Any],
        labels: Union[list, str] = None,
        filters: Iterable[Callable[["histories.History"], bool]] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ["messageDeleted"])


class LabelAddedHandler(BaseHandler):
    """A handler class with the labelAdded history type filter.

    Parameters:
        callback (``callable``):
            A callback function to execute when there's a new update. The function should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History`.

        labels (``list`` | ``str``, *optional*):
            Handle only updates to messages that have all of these labels.
            Defaults to None.

        filters (``list``, *optional*):
            A list of functions. The functions should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History` and should return a bool if the message should be handled or not.
            Defaults to None.

        modified_labels (``list`` | ``str``, *optional*):
            Only handle message that have all of these labels modified.
    """

    def __init__(
        self,
        callback: Callable[["histories.History"], Any],
        labels: Union[list, str] = None,
        filters: Iterable[Callable[["histories.History"], bool]] = None,
        modified_labels: Union[list, str] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ["labelAdded"], modified_labels)


class LabelRemovedHandler(BaseHandler):
    """A handler class with the labelRemoved history type filter.

    Parameters:
        callback (``callable``):
            A callback function to execute when there's a new update. The function should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History`.

        labels (``list`` | ``str``, *optional*):
            Handle only updates to messages that have all of these labels.
            Defaults to None.

        filters (``list``, *optional*):
            A list of functions. The functions should take one agrument which will be the
            :obj:`~google_workspace.gmail.histories.History` and should return a bool if the message should be handled or not.
            Defaults to None.

        modified_labels (``list`` | ``str``, *optional*):
            Only handle message that have all of these labels modified.
    """

    def __init__(
        self,
        callback: Callable[["histories.History"], Any],
        labels: Union[list, str] = None,
        filters: Iterable[Callable[["histories.History"], bool]] = None,
        modified_labels: Union[list, str] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ["labelRemoved"], modified_labels)


def simple_filter(
    is_from: str = None,
    is_not_from: Union[str, Iterable[str]] = None,
    is_to: Union[str, Iterable[str]] = None,
    subject_is: str = None,
    subject_has: str = None,
    contains: str = None,
    not_contains: str = None,
) -> Callable[["histories.History"], bool]:

    if isinstance(is_not_from, str):
        is_not_from = [is_not_from]
    if isinstance(is_to, str):
        is_to = [is_to]

    def message_filter(history: "histories.History") -> bool:
        message = history.message
        if not is_from is None:
            if not is_from == message.from_:
                return False

        if not is_not_from is None:
            if message.from_ in is_not_from:
                return False

        if not subject_is is None:
            if not subject_is == message.subject:
                return False

        if not subject_has is None:
            if not subject_has in message.subject:
                return False

        if not contains is None:
            if not contains in message:
                return False

        if not not_contains is None:
            if not_contains in message:
                return False

        return True

    return message_filter
