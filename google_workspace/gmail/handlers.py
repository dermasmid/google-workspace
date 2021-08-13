from re import S
from typing import Union
from . import utils

class BaseHandler:

    def __init__(
        self,
        callback: callable,
        labels: Union[list, str] = None,
        from_is: str = None,
        subject_is: str = None,
        subject_has: str = None
    ) -> None:
        self.callback = callback
        self.labels = labels
        self.from_is = from_is
        self.subject_is = subject_is
        self.subject_has = subject_has

        if isinstance(labels, str):
            self.labels = [utils.get_label_id(labels)]
        elif isinstance(labels, list):
            self.labels = list(map(utils.get_label_id, labels))


    def check(self, message):
        if not self.labels is None:
            if not all(label in message.label_ids for label in self.labels):
                return False
        if not self.from_is is None:
            if not self.from_is.lower() == message.from_.lower():
                return False
        if not self.subject_is is None:
            if not self.subject_is == message.subject:
                return False
        if not self.subject_has is None:
            if not self.subject_has in message.subject:
                return False

        return True


class MessageAddedHandler(BaseHandler):


    def __init__(
        self,
        callback: callable,
        labels: list = None,
        from_is: str = None,
        subject_is: str = None,
        subject_has: str = None
    ) -> None:
        super().__init__(callback, labels, from_is, subject_is, subject_has)
        self.history_type = 'messageAdded'


class MessageDeletedHandler(BaseHandler):


    def __init__(
        self,
        callback: callable,
        labels: list = None,
        from_is: str = None,
        subject_is: str = None,
        subject_has: str = None
    ) -> None:
        super().__init__(callback, labels, from_is, subject_is, subject_has)
        self.history_type = 'messageDeleted'


class LabelAddedHandler(BaseHandler):


    def __init__(
        self,
        callback: callable,
        labels: list = None,
        from_is: str = None,
        subject_is: str = None,
        subject_has: str = None
    ) -> None:
        super().__init__(callback, labels, from_is, subject_is, subject_has)
        self.history_type = 'labelAdded'


class LabelRemovedHandler(BaseHandler):


    def __init__(
        self,
        callback: callable,
        labels: list = None,
        from_is: str = None,
        subject_is: str = None,
        subject_has: str = None
    ) -> None:
        super().__init__(callback, labels, from_is, subject_is, subject_has)
        self.history_type = 'labelRemoved'
