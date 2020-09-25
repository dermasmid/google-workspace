from datetime import datetime, timedelta
from .utils import gmail_query_maker



class GmailBase:

    def _get_messages(self, next_page_token, label_ids, query):
        kwargs = {'userId': 'me', 'pageToken': next_page_token, 'q': query}
        if label_ids:
            kwargs['labelIds'] = label_ids
        data = self.service.message_service.list(**kwargs).execute()
        messages = iter(data.get("messages", []))
        next_page_token = data.get("nextPageToken", None)
        return messages, next_page_token


    def _get_message_raw_data(self, message_id):
        raw_message = self.service.message_service.get(userId = "me", id= message_id, format= "raw").execute()
        return raw_message


    def _get_history_data(self, start_history_id: int, history_types: list, label_id: str = None):
        perams = {
            'userId': 'me',
            'startHistoryId': start_history_id,
            'historyTypes': history_types
        }
        if label_id:
            perams['labelId'] = label_id    # there's a bug that the api returns sent and draft emails that are a reply
        data = self.service.history_service.list(**perams).execute()
        results = {}
        results['history_id'] = data['historyId']
        histories = data.get("history")
        if histories:
            for history in histories:
                del history['messages']
                del history['id']
                for returned_type in history:
                    if not returned_type in results:
                        results[returned_type] = []
                    for message in history[returned_type]:
                        message = message['message']
                        if label_id in message['labelIds']:
                            results[returned_type].append(message['id'])
        return results


    def _get_labels(self):
        data = self.service.labels_service.list(userId= 'me').execute()
        return data



    def _get_label_raw_data(self, label_id: str):
        data = self.service.labels_service.get(userId= 'me', id= label_id).execute()
        return data


    def _check_if_sent_similar_message(self, message, similarities: list):
        kwargs = {}
        if isinstance(datetime, similarities[-1]):
            kwargs['after'] = similarities.pop(-1)
        else:
            kwargs['after'] = datetime.today() - timedelta(days=1)
        for similarity in similarities:
            value = message[similarity]
            kwargs[similarity] = value
        query = gmail_query_maker(to= message['to'], **kwargs)
        response = bool(self._get_messages(None, ['SENT'], query)[0])
        
        return response