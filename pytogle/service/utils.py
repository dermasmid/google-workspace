import os
import json
import requests_oauthlib
from googleapiclient._helpers import positional
from googleapiclient import discovery
import six
from six.moves.urllib.parse import urljoin
from googleapiclient.schema import Schemas
from googleapiclient import _auth
from googleapiclient.model import JsonModel
from google.auth.exceptions import MutualTLSChannelError
from googleapiclient.errors import InvalidJsonError, HttpError
from google.auth.transport import mtls
from googleapiclient.http import HttpMock, HttpMockSequence, build_http, HttpRequest
import google
from time import sleep
import traceback
import logging
from socket import timeout
from datetime import datetime
import wsgiref

import __main__


logger = logging.getLogger(__name__)

try:
    import google_auth_httplib2
except ImportError:  # pragma: NO COVER
    google_auth_httplib2 = None




default_versions = {
    "drive": "v3", 
    "gmail": "v1",
    "photoslibrary": "v1"
    }

def get_creds_file(creds):
    # check if thers more then one and throw an error
    valid_creds = []
    if os.path.exists(creds):
        return creds
    else:
        jsons = filter(lambda x: x[1] == ".json", iter(os.path.splitext(x) for x in os.listdir()))
        for j in jsons:
            json_file = "".join(j)
            with open(json_file, "r") as f:
                try:
                    json_data = json.load(f)
                except json.decoder.JSONDecodeError:
                    continue
            if json_data.get(list(json_data.keys())[0], {}).get('client_id'):
                valid_creds.append(json_file)
        if len(valid_creds) > 1:
            raise Exception("I found more then one valid client secrets file, please remove one or explictly pass the path to the one you want to use")
        try:
            return valid_creds[0]
        except IndexError:
            raise Exception('I found no creds json file!!!! please go to the google console and download the creds file.')
            





def _fix_google_ster_issues():
    def __getstate__(self):
        attri = self.__dict__
        state = {}
        for attribute in attri:
            state[attribute] = attri[attribute]
        return state

    def __setstate__(self, state):
        for attr, value in state.items():
            try:
                setattr(self, attr, value)
            except:
                pass

            
    requests_oauthlib.OAuth2Session.__getstate__ = __getstate__
    requests_oauthlib.OAuth2Session.__setstate__ = __setstate__



def get_default_scopes(api):
    from ..gmail.scopes import get_gmail_default_scope
    from ..drive.scopes import get_drive_default_scope
    default_scopes = {
        "drive": get_drive_default_scope,
        "gmail": get_gmail_default_scope,
        "photoslibrary": ['https://www.googleapis.com/auth/photoslibrary']
        }
    return [default_scopes[api]()]





@positional(1)
def build_from_document(
    service,
    base=None,
    future=None,
    http=None,
    developerKey=None,
    model=None,
    requestBuilder=HttpRequest,
    credentials=None,
    client_options=None,
    adc_cert_path=None,
    adc_key_path=None,
):
    if http is not None and credentials is not None:
        raise ValueError("Arguments http and credentials are mutually exclusive.")

    if isinstance(service, six.string_types):
        service = json.loads(service)
    elif isinstance(service, six.binary_type):
        service = json.loads(service.decode("utf-8"))

    if "rootUrl" not in service and isinstance(http, (HttpMock, HttpMockSequence)):
        logger.error(
            "You are using HttpMock or HttpMockSequence without"
            + "having the service discovery doc in cache. Try calling "
            + "build() without mocking once first to populate the "
            + "cache."
        )
        raise InvalidJsonError()

    base = urljoin(service["rootUrl"], service["servicePath"])
    if client_options:
        if isinstance(client_options, six.moves.collections_abc.Mapping):
            client_options = google.api_core.client_options.from_dict(client_options)
        if client_options.api_endpoint:
            base = client_options.api_endpoint

    schema = Schemas(service)


    if http is None:
        scopes = list(
            service.get("auth", {}).get("oauth2", {}).get("scopes", {}).keys()
        )

        if scopes and not developerKey:

            if credentials is None:
                credentials = _auth.default_credentials()

            credentials = _auth.with_scopes(credentials, scopes)

        if credentials:
            http = _auth.authorized_http(credentials)

        else:
            http = build_http()

        client_cert_to_use = None
        if client_options and client_options.client_cert_source:
            raise MutualTLSChannelError(
                "ClientOptions.client_cert_source is not supported, please use ClientOptions.client_encrypted_cert_source."
            )
        if (
            client_options
            and hasattr(client_options, "client_encrypted_cert_source")
            and client_options.client_encrypted_cert_source
        ):
            client_cert_to_use = client_options.client_encrypted_cert_source
        elif adc_cert_path and adc_key_path and mtls.has_default_client_cert_source():
            client_cert_to_use = mtls.default_client_encrypted_cert_source(
                adc_cert_path, adc_key_path
            )
        if client_cert_to_use:
            cert_path, key_path, passphrase = client_cert_to_use()

            http_channel = (
                http.http
                if google_auth_httplib2
                and isinstance(http, google_auth_httplib2.AuthorizedHttp)
                else http
            )
            http_channel.add_certificate(key_path, cert_path, "", passphrase)


        if "mtlsRootUrl" in service and (
            not client_options or not client_options.api_endpoint
        ):
            mtls_endpoint = urljoin(service["mtlsRootUrl"], service["servicePath"])
            use_mtls_env = os.getenv("GOOGLE_API_USE_MTLS", "never")

            if not use_mtls_env in ("never", "auto", "always"):
                raise MutualTLSChannelError(
                    "Unsupported GOOGLE_API_USE_MTLS value. Accepted values: never, auto, always"
                )

            if use_mtls_env == "always" or (
                use_mtls_env == "auto" and client_cert_to_use
            ):
                base = mtls_endpoint

    if model is None:
        features = service.get("features", [])
        model = JsonModel("dataWrapper" in features)

    return {
        'http': http,
        'baseUrl': base,
        'model': model,
        'developerKey': developerKey,
        'requestBuilder': requestBuilder,
        'resourceDesc': service,
        'rootDesc': service,
        'schema': schema,
    }


def alt_build(func):

    def inner(*args, **kwargs):
        original = discovery.build_from_document
        discovery.build_from_document = build_from_document
        kwargs = func(*args, **kwargs)
        discovery.build_from_document = original
        return kwargs
    return inner


errors = (BrokenPipeError, timeout, HttpError, ConnectionResetError)


def _error_handling_decorator(execute_fn):
    def execute(*args, **kwargs):
        x = 0
        while True:
            try:
                data = execute_fn(*args, **kwargs)
                return data
            except Exception as e:
                x += 1
                error_str = str(e)
                trace = traceback.format_exc()
                with open('api_errors.txt', 'a') as f:
                    f.write(f'{datetime.now()}:\n{trace}file: {__main__.__file__}\n')
                    if any(isinstance(e, error) for error in errors):
                        if not isinstance(e, HttpError):
                            f.write('handled: True\n\n')
                            pass
                        else:
                            if any(error_type in error_str for error_type in (
                                'The service is currently unavailable', 
                                'Bad Gateway', 
                                'Internal error encountered',
                                'Unknown Error'
                                )):
                                f.write('handled: True\n\n')
                                pass
                            else:
                                f.write('handled: False\n\n')
                                raise e
                    else:
                        f.write('handled: False\n\n')
                        raise e
                    print(f'Sleeping for 30 secs, time: {x}')
                    sleep(30)
            if x == 5:
                raise e
    return execute


def _add_error_handler_for_api_client():
    HttpRequest.execute = _error_handling_decorator(HttpRequest.execute)



class _WsgiApp:


    def __init__(self, success_message):

        self.last_request_uri = None
        self._success_message = success_message

    def __call__(self, environ, start_response):

        start_response('200 OK', [('Content-type', 'text/plain')])
        self.last_request_uri = wsgiref.util.request_uri(environ)
        return [self._success_message.encode('utf-8')]



class _AltWsgiHandler(wsgiref.simple_server.WSGIRequestHandler):


    def log_message(self, format, *args):
        pass
