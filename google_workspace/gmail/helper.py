from . import message as msg
from . import utils
from datetime import datetime


def get_messages(service, next_page_token, label_ids, query, include_spam_and_trash):
    kwargs = {'userId': 'me', 'pageToken': next_page_token, 'q': query, 'includeSpamTrash': include_spam_and_trash}
    if label_ids:
        kwargs['labelIds'] = label_ids
    data = service.message_service.list(**kwargs).execute()
    messages = iter(data.get("messages", []))
    next_page_token = data.get("nextPageToken", None)
    return messages, next_page_token


def get_message_raw_data(service, message_id: str, download_full: bool):
    raw_message = service.message_service.get(userId = "me", id= message_id, format= 'raw' if download_full else 'minimal').execute()
    return raw_message


def get_history_data(service, start_history_id: int, history_types: list = None, label_id: str = None):
    params = {
        'userId': 'me',
        'startHistoryId': start_history_id,
        'historyTypes': history_types,
        'labelId': label_id
    }
    data = service.history_service.list(**params).execute()
    return data


def get_labels(service):
    data = service.labels_service.list(userId= 'me').execute()
    return data


def get_label_raw_data(service, label_id: str):
    data = service.labels_service.get(userId= 'me', id= label_id).execute()
    return data


def check_if_sent_similar_message(mailbox, message, flood_prevention):
    kwargs = {}
    # if raw_from is passed we have to remove the name first becuz the api wont return anything
    if 'to' in flood_prevention.similarities:
        to = message['to']
        if '<' in to:
            start = to.find('<') + 1
            end = to.find('>')
            message['to'] = to[start:end]
    kwargs['after'] = flood_prevention.after_date
    for similarity in flood_prevention.similarities:
        value = message[similarity]
        kwargs[similarity] = value
    query = utils.gmail_query_maker(**kwargs)
    messages = get_messages(mailbox.service, None, ['SENT'], query, False)[0]
    if type(flood_prevention.after_date) is datetime:
        final_messages = []
        for message in messages:
            message_date = msg.Message(mailbox, get_message_raw_data(mailbox.service, message['id'], True), True).date
            if flood_prevention.after_date < message_date:
                final_messages.append(message)
        messages = final_messages
    response = len(list(messages)) >= flood_prevention.number_of_messages
    return response
