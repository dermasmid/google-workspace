import json
import os
import socket
import ssl
import time
import wsgiref
from contextlib import contextmanager
from http.client import IncompleteRead
from socket import timeout
from typing import List
from urllib.parse import parse_qs, urlparse
from wsgiref import simple_server

import google_auth_httplib2
import trython
from googleapiclient import discovery, discovery_cache
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest
from httplib2 import Http
from httplib2.error import ServerNotFoundError

ERRORS_TO_CATCH = (
    BrokenPipeError,
    timeout,
    HttpError,
    ConnectionResetError,
    ServerNotFoundError,
    ssl.SSLEOFError,  # ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:1131)
    OSError,  # OSError: [Errno 101] Network is unreachable
    IncompleteRead,  # http.client.IncompleteRead: IncompleteRead(48 bytes read)
)


default_versions = {
    "drive": "v3",
    "gmail": "v1",
}  # TODO: Get latest from discovery doc.


def get_creds_file(creds):
    # check if thers more then one and throw an error
    valid_creds = []
    if os.path.exists(creds):
        return creds
    else:
        jsons = filter(
            lambda x: x[1] == ".json", iter(os.path.splitext(x) for x in os.listdir())
        )
        for j in jsons:
            json_file = "".join(j)
            with open(json_file, "r") as f:
                try:
                    json_data = json.load(f)
                except json.decoder.JSONDecodeError:
                    continue
            root_element = json_data.get(list(json_data.keys())[0])
            if isinstance(root_element, dict) and root_element.get("client_id"):
                valid_creds.append(json_file)
        if len(valid_creds) > 1:
            raise Exception(
                "I found more then one valid client secrets file, please remove one or explictly pass the path to the one you want to use"
            )
        try:
            return valid_creds[0]
        except IndexError:
            raise Exception(
                "I found no creds json file!!!! please go to the google console and download the creds file."
            )


def get_default_scopes(api: str) -> List[str]:
    from .. import drive, gmail

    default_scopes = {
        "drive": drive.scopes.FULL_ACCESS_DRIVE_SCOPE,
        "gmail": gmail.scopes.FULL_ACCESS_GMAIL_SCOPE,
    }
    return [default_scopes[api]]


@contextmanager
def modify_resource():
    try:

        def alt_init(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        original = discovery.Resource.__init__
        discovery.Resource.__init__ = alt_init

        yield None
    finally:
        # Revert.
        discovery.Resource.__init__ = original


def exception_callback(error: HttpError, _):
    if not isinstance(error, HttpError):
        return

    if error.error_details:
        if error.error_details[0]["reason"] == "rateLimitExceeded":
            # Going to sleep for a mintue
            print(
                "Got rateLimitExceeded error, sleeping for 60 seconds."
            )  # TODO: use logger.
            time.sleep(60)
            return
    if not error._get_reason().strip() in [
        "The service is currently unavailable.",
        "Bad Gateway.",
        "Internal error encountered.",
        "Unknown Error.",
        "Precondition check failed.",
    ]:
        raise error


def configure_error_handling():
    error_handled_execute = trython.wrap(
        HttpRequest.execute,
        time_to_sleep=10,
        errors_to_catch=ERRORS_TO_CATCH,
        on_exception_callback=exception_callback,
    )

    def custom_execute(self: HttpRequest, *args, **kwargs):
        is_google_workspace = getattr(
            self.http.credentials, "is_google_workspace", False
        )
        if is_google_workspace and self.http.credentials.threading:
            self.http = google_auth_httplib2.AuthorizedHttp(
                self.http.credentials, http=Http()
            )
        try:
            data = error_handled_execute(self, *args, **kwargs)
        except HttpError as e:
            # Tell the user which scopes are required
            if (
                e.reason == "Request had insufficient authentication scopes."
                and is_google_workspace
            ):
                content = json.loads(
                    discovery_cache.get_static_doc(
                        self.http.credentials.api, self.http.credentials.version
                    )
                )
                scopes = get_scopes_by_method_id(self.methodId, content)
                print(
                    f"Error: `{self.methodId}` requires one of these scopes: {scopes} , but you have {self.http.credentials.authenticated_scopes}"
                )
            raise
        finally:
            if is_google_workspace and self.http.credentials.threading:
                # close connection when using threads, because on the next
                # call we will be creating a new AuthorizedHttp anyway
                self.http.close()

        return data

    HttpRequest.execute = custom_execute


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
        respond("200 OK", [("Content-type", "text/plain")])
        request_uri = wsgiref.util.request_uri(environ).replace("http", "https", 1)
        query = parse_qs(urlparse(request_uri).query)
        if query.get("state") and query.get("code") and query.get("scope"):
            if self.fetch_token:
                self.fetch_token(
                    authorization_response=request_uri, state=query.get("state")[0]
                )
            else:
                self.authorization_response = request_uri
            self.server._BaseServer__shutdown_request = True
            return [self.message.encode("utf-8")]
        else:
            return [b"failed"]

    def start(self):
        self.server = simple_server.make_server(
            host="",
            port=self.server_port,
            app=self.wsgi_app,
            handler_class=ServerHandler,
        )
        if self.is_ssl:
            self.server.socket = ssl.wrap_socket(
                self.server.socket, keyfile=self.keyfile, certfile=self.certfile
            )
        self.server.serve_forever()
        if not self.fetch_token:
            return self.authorization_response


def port_is_available(port: int) -> bool:
    is_available = True
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
    except OSError:
        is_available = False
    return is_available


def get_available_allowed_port(client_config: dict, server_host: str) -> int:
    allowed_ports = {}
    for url in client_config["web"]["redirect_uris"]:
        parsed = urlparse(url)
        port = parsed.port
        scheme = parsed.scheme
        hostname = parsed.hostname
        if hostname:
            if not port:
                if scheme == "http":
                    port = 80
                elif scheme == "https":
                    port = 443
            if not hostname in allowed_ports:
                allowed_ports[hostname] = []
            allowed_ports[hostname].append(port)

    for port in allowed_ports[server_host]:
        if port_is_available(port):
            return port
    raise ValueError(
        """There's no availabl ports that are allowed to be used by your app, please update your
            allowed redirect URIs in the cloud console and update the client secrets json file"""
    )


def get_scopes_by_method_id(method_id: str, discovery_document: dict) -> list:
    items = method_id.split(".")
    del items[0]
    for item in items:
        if not item == items[-1]:
            discovery_document = discovery_document["resources"][item]
        else:
            method = discovery_document["methods"][item]
    return method["scopes"]
