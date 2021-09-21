from typing import Type, Union, Callable, Literal, List, Any
from . import utils, message


HISTORY_TYPE_LITERAL = Literal['messageAdded', 'messageDeleted', 'labelAdded', 'labelRemoved']

class BaseHandler:


    def __init__(
        self,
        callback: Callable[[Type['message.BaseMessage']], Any],
        labels: Union[list, str] = None,
        filters: List[Callable[[Type['message.BaseMessage']], bool]] = None,
        history_types: List[HISTORY_TYPE_LITERAL] = None
    ) -> None:

        self.callback = callback
        self.labels = utils.get_proper_label_ids(labels)
        self.filters = filters
        self.history_types = history_types if history_types else ['messageAdded', 'messageDeleted', 'labelAdded', 'labelRemoved']


    def check(self, message: 'message.BaseMessage') -> bool:
        if not self.labels is None:
            if not all(label in message.label_ids for label in self.labels):
                return False

        if not self.filters is None:
            for filter in self.filters:
                if not filter(message):
                    return False

        return True


class MessageAddedHandler(BaseHandler):


    def __init__(
        self,
        callback: Callable[[Type['message.BaseMessage']], Any],
        labels: Union[list, str] = None,
        filters: List[Callable[[Type['message.BaseMessage']], bool]] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ['messageAdded'])


class MessageDeletedHandler(BaseHandler):


    def __init__(
        self,
        callback: Callable[[Type['message.BaseMessage']], Any],
        labels: Union[list, str] = None,
        filters: List[Callable[[Type['message.BaseMessage']], bool]] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ['messageDeleted'])


class LabelAddedHandler(BaseHandler):


    def __init__(
        self,
        callback: Callable[[Type['message.BaseMessage']], Any],
        labels: Union[list, str] = None,
        filters: List[Callable[[Type['message.BaseMessage']], bool]] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ['labelAdded'])


class LabelRemovedHandler(BaseHandler):


    def __init__(
        self,
        callback: Callable[[Type['message.BaseMessage']], Any],
        labels: Union[list, str] = None,
        filters: List[Callable[[Type['message.BaseMessage']], bool]] = None,
    ) -> None:
        super().__init__(callback, labels, filters, ['labelRemoved'])


def simple_filter(
    is_from: str = None,
    is_not_from: Union[str, List[str]] = None,
    is_to: Union[str, List[str]] = None,
    subject_is: str = None,
    subject_has: str = None,
    contains: str = None,
    not_contains: str = None
) -> Callable[['message.BaseMessage'], bool]:

    if isinstance(is_not_from, str):
        is_not_from = [is_not_from]
    if isinstance(is_to, str):
        is_to = [is_to]

    def message_filter(message: Type['message.BaseMessage']) -> bool:
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
