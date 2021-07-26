import json
import os
import pickle
from googleapiclient.discovery import build, Resource
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import threading
from ..service import utils
from httplib2 import Http
import urllib



class GoogleService(Resource):


    def __init__(
        self,
        api: str,
        session: str = None,
        client_secrets: str = "creds.json",
        scopes: list = [],
        version: str = None,
        api_key: str = None,
        http: Http = None,
        service: Resource = None,
        creds: Credentials = None,
        ):
        self.session = session or api
        self.version = version or utils.default_versions[api]
        self.api = api
        self.pickle_file = f"{self.session}.pickle"
        self.is_authenticated = os.path.exists(self.pickle_file)
        utils._add_error_handler_for_api_client()
        if service:
            if isinstance(service, Resource):
                self._add_service_methods(service)
                self._make_special_services()
            else:
                raise Exception("Invalid argument")


        elif api_key:
            http = http or Http()
            service = self._get_service_args(http= http, developer_key= api_key)
            super().__init__(**service)


        elif creds:
            if isinstance(creds, Credentials):
                service = self._get_service_args(creds= creds)
                super().__init__(**service)
                self._make_special_services()
                self.authenticated_scopes = creds.scopes
            else:
                raise ValueError("Invalid argument")


        else:
            if self.is_authenticated:
                self._get_service()
            else:
                client_secrets = utils.get_creds_file(client_secrets)
                with open(client_secrets, 'r') as f:
                    self.client_config = json.load(f)
                self.scopes = list(scope.scope_code for scope in scopes or utils.get_default_scopes(self.api))


    def local_oauth(self, server_port: int = 2626):
        if self.is_authenticated:
            return
        self.flow = InstalledAppFlow.from_client_config(self.client_config, self.scopes)
        creds = self.flow.run_local_server(port= server_port)
        self._save_creds(creds)
        self._get_service()
        return self


    def url_oauth(self, server_host: str, server_port: int = None, success_message: str = 'success', keyfile: str = None, certfile: str = None) -> str:
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
        return self.auth_url


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
        self._get_service()
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


    def __bool__(self):
        return self.is_authenticated


    def _get_service(self):
        with open(self.pickle_file, 'rb') as f:
            creds = pickle.load(f)
        if not creds or not creds.valid:
            creds.refresh(Request())
        service = self._get_service_args(creds)
        super().__init__(**service)
        self._make_special_services()
        self.authenticated_scopes = creds.scopes


    @utils.alt_build
    def _get_service_args(self, creds = None, http = None, developer_key= None):
        kwargs = build(self.api, self.version, credentials=creds, http= http, developerKey= developer_key)
        return dict(kwargs)


    def _add_service_methods(self, service):
        self.__dict__.update({key: service.__dict__[key] for key in service.__dict__.keys() if not key.startswith("_")})


    def _make_special_services(self):
        if self.api == "gmail":
            self.users_service = self.users() # pylint: disable=no-member
            self.history_service = self.users_service.history()
            self.message_service = self.users_service.messages()
            self.labels_service = self.users_service.labels()
            self.settings_service = self.users_service.settings()
            self.attachment_service = self.message_service.attachments()
        elif self.api == "drive":
            self.files_service = self.files() # pylint: disable=no-member


    def _save_creds(self, creds):
        with open(self.pickle_file, 'wb') as token:
            pickle.dump(creds, token)
        self.is_authenticated = True
