import json
import os
import pickle
import threading
import urllib
from pathlib import Path
from typing import Any, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import Resource, build
from httplib2 import Http

from . import utils


class GoogleService(Resource):


    def __init__(
        self,
        api: str,
        session: str = None,
        client_secrets: str = "creds.json",
        scopes: Union[str, list] = None,
        version: str = None,
        api_key: str = None,
        http: Http = None,
        service: Resource = None,
        creds: Credentials = None,
        workdir: str = None
        ):
        self.session = session or api
        self.version = version or utils.default_versions[api]
        self.api = api
        self.workdir = Path(workdir or '.')
        self.pickle_file = self.workdir / (self.session + '.pickle')
        self.is_authenticated = os.path.exists(self.pickle_file)
        utils.configure_error_handling()
        if service:
            if isinstance(service, Resource):
                self._add_service_methods(service)
                self._make_special_services()
            else:
                raise ValueError("Invalid argument")


        elif api_key:
            http = http or Http()
            service = self._get_service_args(http= http, developer_key= api_key)
            super().__init__(**service)


        elif creds:
            if isinstance(creds, Credentials):
                self._init_service(creds)
            else:
                raise ValueError("Invalid argument")


        else:
            if self.is_authenticated:
                self._init_service()
            else:
                client_secrets = self.workdir / utils.get_creds_file(client_secrets)
                with open(client_secrets, 'r') as f:
                    self.client_config = json.load(f)

                if isinstance(scopes, str):
                    scopes = [scopes]
                self.scopes = scopes or utils.get_default_scopes(self.api)


    def local_oauth(self, server_port: int = 2626):
        if self.is_authenticated:
            return
        self.flow = InstalledAppFlow.from_client_config(self.client_config, self.scopes)
        creds = self.flow.run_local_server(port= server_port)
        self._save_creds(creds)
        self._init_service()
        return self


    def url_oauth(
        self,
        server_host: str,
        server_port: int = None,
        success_message: str = 'success',
        keyfile: str = None,
        certfile: str = None,
        block = False
        ) -> str:

        if self.is_authenticated:
            return
        use_ssl = keyfile and certfile
        if not server_port:
            server_port = utils.get_available_allowed_port(self.client_config, server_host)
        self.redirect_uri = f'{"https" if use_ssl else "http"}://{server_host}:{server_port}/'
        self.auth_url = self.get_auth_url()
        oauthsever = utils.OauthServer(server_port, success_message, keyfile, certfile, self.fetch_token)
        thread = threading.Thread(target=oauthsever.start)
        thread.start()
        if not block:
            # TODO: We might want to add a callback for when
            # auth is done
            return self.auth_url
        else:
            print(self.auth_url)
            thread.join()


    def code_oauth(self):
        if self.is_authenticated:
            return
        self.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        return self.get_auth_url()


    def get_auth_url(self) -> str:
        self.flow = Flow.from_client_config(self.client_config, scopes= self.scopes, redirect_uri= self.redirect_uri)
        auth_url, self.state = self.flow.authorization_url(prompt='consent')
        return auth_url


    def fetch_token(self, code: str = None, authorization_response: str = None, state: str = None):
        self.flow = Flow.from_client_config(self.client_config, scopes= self.scopes, redirect_uri= self.redirect_uri, state= state)
        self.flow.fetch_token(code= code, authorization_response= authorization_response)
        creds = self.flow.credentials
        self._save_creds(creds)
        self._init_service()
        return self


    def delete(self):
        if self.is_authenticated:
            with open(self.pickle_file, 'rb') as f:
                creds = pickle.load(f)
            data = urllib.parse.urlencode({'token': creds.token}).encode('ascii')
            urllib.request.urlopen('https://oauth2.googleapis.com/revoke', data)
            os.remove(self.pickle_file)


    def get_state(self):
        if hasattr(self, 'state'):
            return self.state
        return None


    def make_thread_safe(self):
        self._http.credentials.threading = True


    def get_service_state_value(self, key: str) -> Any:
        return self.service_state.get(self.api, {}).get(key)


    def update_service_state(self, key: str, value: Any) -> None:
        if not self.api in self.service_state:
            self.service_state[self.api] = {}
        self.service_state[self.api][key] = value


    def save_service_state(self) -> None:
        with open(self.pickle_file, 'wb') as f:
            pickle.dump(self._http.credentials, f)
            pickle.dump(self.service_state, f)


    def close(self) -> None:
        if self.is_authenticated:
            self._http.close()


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.close()


    def __bool__(self) -> bool:
        return self.is_authenticated


    def _get_service(self, creds: Credentials):
        service = self._get_service_args(creds)
        super().__init__(**service)
        self._make_special_services()
        self.authenticated_scopes = creds.scopes


    def _get_service_args(self, creds = None, http = None, developer_key= None):
        with utils.modify_resource():
            resource = build(self.api, self.version, credentials=creds, http= http, developerKey= developer_key)
            kwargs = resource.kwargs # pylint: disable=no-member
        return kwargs


    def _add_service_methods(self, service):
        self.__dict__.update({key: service.__dict__[key] for key in service.__dict__.keys() if not key.startswith("_")})


    def _make_special_services(self):
        if self.api == "gmail":
            self.users_service: Resource = self.users() # pylint: disable=no-member
            self.history_service: Resource = self.users_service.history()
            self.message_service: Resource = self.users_service.messages()
            self.labels_service: Resource = self.users_service.labels()
            self.settings_service: Resource = self.users_service.settings()
            self.attachment_service: Resource = self.message_service.attachments()
        elif self.api == "drive":
            self.files_service: Resource = self.files() # pylint: disable=no-member


    def _save_creds(self, creds: Credentials):
        with open(self.pickle_file, 'wb') as token:
            pickle.dump(creds, token)
        self.is_authenticated = True


    def _get_creds(self):
        with open(self.pickle_file, 'rb') as f:
            creds = pickle.load(f)
            try:
                self.service_state = pickle.load(f)
            except EOFError:
                self.service_state = {self.api: {}}
        if not creds or not creds.valid:
            request = Request()
            creds.refresh(request)
            request.session.close()
        return creds


    def _init_service(self, creds: Credentials = None):
        if not creds:
            creds = self._get_creds()
        self._get_service(creds)
        self._post_auth_setup()


    def _post_auth_setup(self):
        self._http.credentials.is_google_workspace = True
        self._http.credentials.threading = False
        self._http.credentials.authenticated_scopes = self.authenticated_scopes
        self._http.credentials.api = self.api
        self._http.credentials.version = self.version
