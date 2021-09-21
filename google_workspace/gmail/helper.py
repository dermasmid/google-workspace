from typing import Literal, Union, Generator
from . import message, gmail
from .. import service
import trython
from googleapiclient.errors import HttpError


def get_messages(service, next_page_token, label_ids, query, include_spam_and_trash):
    kwargs = {'userId': 'me', 'pageToken': next_page_token, 'q': query, 'includeSpamTrash': include_spam_and_trash}
    if label_ids:
        kwargs['labelIds'] = label_ids
    data = service.message_service.list(**kwargs).execute()
    messages = iter(data.get("messages", []))
    next_page_token = data.get("nextPageToken", None)
    return messages, next_page_token


@trython.wrap(time_to_sleep=0, errors_to_catch=(HttpError, ), on_exception_callback=service.utils.exception_callback)
def get_message_data_batch(service, message_ids: str, format: Literal['raw', 'metadata'] = 'raw'):
    batch = service.new_batch_http_request()
    for message_id in message_ids:
        batch.add(service.message_service.get(userId = "me", id= message_id, format= format))
    batch.execute()
    messages = list(batch._requests[request_id].postproc(*batch._responses[request_id]) for request_id in batch._order)
    return messages


def get_message_data(service, message_id: str, format: Literal['raw', 'metadata'] = 'raw'):
    raw_message = service.message_service.get(userId = "me", id= message_id, format= format).execute()
    return raw_message


def get_history_data(service, start_history_id: int, history_types: list = None, label_id: str = None):
    # TODO: handle next page tokens
    params = {
        'userId': 'me',
        'startHistoryId': start_history_id,
        'historyTypes': history_types,
        'labelId': label_id
    }
    try:
        data = service.history_service.list(**params).execute()
    except HttpError as e:
        if not e.reason == 'Requested entity was not found.':
            raise
        # history_id was invalid (probably an old save_state) so getting the
        # most recent history_id. This might change.
        data = {'historyId': service.users().getProfile(userId= "me").execute().get("historyId")}
    return data


def get_labels(service):
    data = service.labels_service.list(userId= 'me').execute()
    return data


def get_label_raw_data(service, label_id: str):
    data = service.labels_service.get(userId= 'me', id= label_id).execute()
    return data


def get_messages_generator(
    gmail_client: 'gmail.GmailClient',
    label_ids: list,
    query: str,
    include_spam_and_trash: bool,
    metadata_only: bool,
    batch: bool,
    limit: Union[int, None]
    ) -> Generator[Union[message.Message, message.MessageMetadata], None, None]:

    if metadata_only:
        message_class, message_format = message.MessageMetadata, 'metadata'
    else:
        message_class, message_format = message.Message, 'raw'


    messages, next_page_token = get_messages(gmail_client.service, None, label_ids, query, include_spam_and_trash)
    counter = 0

    if batch:
        message_ids = []

        while True:
            try:
                message_ids.append(next(messages)['id'])
                if limit:
                    counter += 1
                    if counter == limit:
                        raise StopIteration

            except StopIteration:
                messages_data = get_message_data_batch(gmail_client.service, message_ids, message_format)
                for message_data in messages_data:
                    yield message_class(gmail_client, message_data)
                message_ids = []
                if not next_page_token or counter == limit:
                    break

                messages, next_page_token = get_messages(gmail_client.service, next_page_token, label_ids, query, include_spam_and_trash)
                continue

    else:
        while True:
            try:
                message_id = next(messages)['id']

            except StopIteration:
                if not next_page_token:
                    break

                messages, next_page_token = get_messages(gmail_client.service, next_page_token, label_ids, query, include_spam_and_trash)
                continue

            else:
                yield message_class(gmail_client, get_message_data(gmail_client.service, message_id, message_format))
                if limit:
                    counter += 1
                    if counter == limit:
                        break
