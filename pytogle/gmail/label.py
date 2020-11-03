from .utils import make_label_dict



class Label:


    def __init__(self, raw_label: dict, mailbox: "Gmail"):
        self.mailbox = mailbox
        self.raw_label = raw_label
        self.id= raw_label.get('id')
        self.name = raw_label.get('name')
        self.message_list_visibility = _mapping[raw_label['messageListVisibility']]() if raw_label.get('messageListVisibility') else None
        self.label_list_visibility = _mapping[raw_label['labelListVisibility']]() if raw_label.get('labelListVisibility') else None
        self.type = raw_label.get('type')
        self.is_system = self.type == "system"
        self.total_messages = raw_label.get('messagesTotal')
        self.messages_unread = raw_label.get('messagesUnread')
        self.total_threads = raw_label.get('threadsTotal')
        self.threads_unread = raw_label.get('threadsUnread')
        self.color = raw_label.get('color')


    def __repr__(self):
        return str(self.raw_label)


    def get_messages(self):
        return self.mailbox.get_messages(label_ids= self.id)


    def modify(
        self,
        name: str = None,
        message_list_visibility = None,
        label_list_visibility = None,
        background_color: str = None,
        text_color: str = None
        ):
        assert not self.is_system, "Cant modify system labels"
        body = make_label_dict(name= name, message_list_visibility= message_list_visibility, label_list_visibility= label_list_visibility, 
            background_color= background_color, text_color= text_color
            )
        data = self.mailbox.service.labels_service.patch(userId= 'me',id= self.id, body= body).execute()
        return self.mailbox.get_label_by_id(data['id'])








class ListVisibility:

    def __init__(self, setting):
        self.setting = setting


    def __str__(self):
        return self.setting

class LabelShow(ListVisibility):

    def __init__(self):
        super().__init__('labelShow')


class LabelHide(ListVisibility):

    def __init__(self):
        super().__init__('labelHide')
        

class LabelShowIfUnread(ListVisibility):

    def __init__(self):
        super().__init__('labelShowIfUnread')



class MessageShow(ListVisibility):

    def __init__(self):
        super().__init__('show')


class MessageHide(ListVisibility):

    def __init__(self):
        super().__init__('hide')




_mapping = {
    'labelShow': LabelShow,
    'labelHide': LabelHide,
    'labelShowIfUnread': LabelShowIfUnread,
    'show': MessageShow,
    'hide': MessageHide
}
