import os
import json
from googleapiclient._helpers import positional
from googleapiclient import discovery
import six
from urllib.parse import urljoin, urlparse, parse_qs
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
from collections.abc import Mapping
import socket
from wsgiref import simple_server
import ssl

import __main__


logger = logging.getLogger(__name__)

try:
    import google_auth_httplib2
except ImportError:
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
            root_element = json_data.get(list(json_data.keys())[0])
            if isinstance(root_element, dict) and root_element.get('client_id'):
                valid_creds.append(json_file)
        if len(valid_creds) > 1:
            raise Exception("I found more then one valid client secrets file, please remove one or explictly pass the path to the one you want to use")
        try:
            return valid_creds[0]
        except IndexError:
            raise Exception('I found no creds json file!!!! please go to the google console and download the creds file.')




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
        if isinstance(client_options, Mapping):
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


class ServerHandler(wsgiref.simple_server.WSGIRequestHandler):
    def log_message(self, format, *args):
        pass

class OauthServer:

    def __init__(
        self,
        server_port: int,
        message: str,
        keyfile: str = None,
        certfile: str = None,
        fetch_token: callable = None,
    ) -> None:
        self.server_port = server_port
        self.fetch_token = fetch_token
        self.message = message
        self.keyfile = keyfile
        self.certfile = certfile
        self.is_ssl = keyfile and certfile

    def wsgi_app(self, environ, respond):
        respond('200 OK', [('Content-type', 'text/plain')])
        request_uri = wsgiref.util.request_uri(environ).replace('http', 'https', 1)
        query = parse_qs(urlparse(request_uri).query)
        if query.get('state') and query.get('code') and query.get('scope'):
            if self.fetch_token:
                self.fetch_token(authorization_response= request_uri, state= query.get('state')[0])
            else:
                self.authorization_response = request_uri
            self.server._BaseServer__shutdown_request = True
            return [self.message.encode('utf-8')]
        else:
            return [b'failed']

    def start(self):
        self.server = simple_server.make_server(
            host= '',
            port= self.server_port,
            app= self.wsgi_app,
            handler_class= ServerHandler,
            )
        if self.is_ssl:
            self.server.socket = ssl.wrap_socket(self.server.socket, keyfile= self.keyfile, certfile= self.certfile)
        self.server.serve_forever()
        if not self.fetch_token:
            return self.authorization_response


def port_is_available(port: int) -> bool:
    is_available = True
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        sock.close()
    except OSError:
        is_available = False
    return is_available


def get_available_allowed_port(client_config: dict, server_host: str) -> int:
    allowed_ports = {}
    for url in client_config['web']['redirect_uris']:
        parsed = urlparse(url)
        port = parsed.port
        scheme = parsed.scheme
        hostname = parsed.hostname
        if hostname:
            if not port:
                if scheme == 'http':
                    port = 80
                elif scheme == 'https':
                    port = 443
            if not hostname in allowed_ports:
                allowed_ports[hostname] = []
            allowed_ports[hostname].append(port)

    for port in allowed_ports[server_host]:
        if port_is_available(port):
            return port
    raise ValueError("""There's no availabl ports that are allowed to be used by your app, please update your
            allowed redirect URIs in the cloud console and update the client secrets json file""")
