from typing import Generator, Iterable, Type, Union

import trython
from googleapiclient.errors import HttpError
from typing_extensions import Literal

from .. import service
from . import gmail, message, thread, utils


def get_messages(
    service,
    next_page_token,
    label_ids,
    query,
    include_spam_and_trash,
    threads: bool = False,
):
    if not threads:
        endpoint = service.messages_service.list
        items_key = "messages"
    else:
        endpoint = service.threads_service.list
        items_key = "threads"
    kwargs = {
        "userId": "me",
        "pageToken": next_page_token,
        "q": query,
        "includeSpamTrash": include_spam_and_trash,
    }
    if label_ids:
        kwargs["labelIds"] = label_ids
    data = endpoint(**kwargs).execute()
    messages = iter(data.get(items_key, []))
    next_page_token = data.get("nextPageToken", None)
    return messages, next_page_token


@trython.wrap(
    time_to_sleep=0,
    errors_to_catch=(HttpError,),
    on_exception_callback=service.utils.exception_callback,
)
def get_messages_data_batch(
    service,
    message_ids: str,
    message_format: Literal["minimal", "full", "raw", "metadata"] = "raw",
    threads: bool = False,
):
    if not threads:
        endpoint = service.messages_service.get
    else:
        endpoint = service.threads_service.get
    batch = service.new_batch_http_request()
    for message_id in message_ids:
        batch.add(endpoint(userId="me", id=message_id, format=message_format))
    batch.execute()
    messages = list(
        batch._requests[request_id].postproc(*batch._responses[request_id])
        for request_id in batch._order
    )
    return messages


def get_message_data(
    service,
    message_id: str,
    message_format: Literal["minimal", "full", "raw", "metadata"] = "raw",
    threads: bool = False,
):
    if not threads:
        endpoint = service.messages_service.get
    else:
        endpoint = service.threads_service.get
    raw_message = endpoint(userId="me", id=message_id, format=message_format).execute()
    return raw_message


def get_history_data(
    gmail_client,
    start_history_id: int,
    history_types: Iterable[
        Literal["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"]
    ] = None,
    label_id: str = None,
    page_token: str = None,
    max_results: int = None,
):
    params = {
        "userId": "me",
        "startHistoryId": start_history_id,
        "historyTypes": history_types,
        "labelId": label_id,
        "pageToken": page_token,
        "maxResults": max_results,
    }

    return gmail_client.service.history_service.list(**params).execute()


def get_labels(service):
    data = service.labels_service.list(userId="me").execute()
    return data


def get_label_raw_data(service, label_id: str):
    data = service.labels_service.get(userId="me", id=label_id).execute()
    return data


def get_messages_generator(
    gmail_client: "gmail.GmailClient",
    label_ids: list,
    query: str,
    include_spam_and_trash: bool,
    message_format: Literal["minimal", "full", "raw", "metadata"],
    batch: bool,
    limit: Union[int, None],
    threads: bool = False,
) -> Generator[Type["message.BaseMessage"], None, None]:

    message_class = utils.get_message_class(message_format)
    message_kwargs = {}

    if threads:
        message_class = thread.Thread
        message_kwargs["message_format"] = message_format

    messages, next_page_token = get_messages(
        gmail_client.service,
        None,
        label_ids,
        query,
        include_spam_and_trash,
        threads=threads,
    )
    counter = 0

    if batch:
        message_ids = []

        while True:
            try:
                message_ids.append(next(messages)["id"])
                if limit:
                    counter += 1
                    if counter == limit:
                        raise StopIteration

            except StopIteration:
                messages_data = get_messages_data_batch(
                    gmail_client.service, message_ids, message_format, threads=threads
                )
                for message_data in messages_data:
                    yield message_class(gmail_client, message_data)
                message_ids = []
                if not next_page_token or counter == limit:
                    break

                messages, next_page_token = get_messages(
                    gmail_client.service,
                    next_page_token,
                    label_ids,
                    query,
                    include_spam_and_trash,
                    threads=threads,
                )
                continue

    else:
        while True:
            try:
                message_id = next(messages)["id"]

            except StopIteration:
                if not next_page_token:
                    break

                messages, next_page_token = get_messages(
                    gmail_client.service,
                    next_page_token,
                    label_ids,
                    query,
                    include_spam_and_trash,
                    threads=threads,
                )
                continue

            else:
                yield message_class(
                    gmail_client,
                    get_message_data(
                        gmail_client.service,
                        message_id,
                        message_format,
                        threads=threads,
                    ),
                    **message_kwargs
                )
                if limit:
                    counter += 1
                    if counter == limit:
                        break
