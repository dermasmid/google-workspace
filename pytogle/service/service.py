import os
import pickle
from googleapiclient.discovery import build, Resource
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import dill
from ..service.utils import _fix_google_ster_issues, alt_build, default_versions, get_default_scopes, get_creds_file, _add_error_handler_for_api_client, _WsgiApp
from httplib2 import Http
from wsgiref import simple_server



class GoogleService(Resource):


    def __init__(
        self,
        api: str,
        session: str = None,
        client_secrets: str = "creds.json",
        scopes: list = [],
        version: str = None,
        auth_type = 'local',
        api_key: str = None,
        http: Http = None,
        service: Resource = None,
        creds: Credentials = None,
        redirect_uri: str = None
        ):
        self.session = session or api
        self.version = version or default_versions[api]
        self.api = api
        self.pickle_file = f"{self.session}.pickle"
        self.is_authenticated = os.path.exists(self.pickle_file)
        _add_error_handler_for_api_client()
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
                raise Exception("Invalid argument")


        else:
            if self.is_authenticated:
                self._get_service()
            else:
                self.client_secrets = get_creds_file(client_secrets)
                self.scopes = list(scope.scope_code for scope in scopes or get_default_scopes(self.api))
                self.auth_type = auth_type


                if self.auth_type == 'local':
                    self.authenticate_local()

                elif self.auth_type == 'code':
                    _fix_google_ster_issues()
                    self.flow_args = {
                        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'
                    }

                elif self.auth_type == 'redirect':
                    self.flow_args = {
                        'redirect_uri': redirect_uri
                    }

    



    def authenticate_local(self):
        self.flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets, self.scopes)
        creds = self.flow.run_local_server(port=2626)
        self._save_creds(creds)
        self._get_service()
        return self




    def get_auth_url(self):
        self.flow = Flow.from_client_secrets_file(self.client_secrets, scopes= self.scopes, **self.flow_args)
        auth_url, _ = self.flow.authorization_url(prompt='consent')



        if self.auth_type == 'url':
            def save():
                dill_file = f"{self.session}.dill"
                with open(dill_file, "wb") as f:
                    dill.dump(self.finnish_process, f)
                return dill_file
            
            self.finnish_process.save = save
        return auth_url


    def run_open_server(self, host: str, port: int, success_message: str):
        web_app = _WsgiApp(success_message)
        web_server = simple_server.make_server(host= host, port= port, app= web_app)
        web_server.handle_request()
        authorization_response = web_app.last_request_uri.replace(
            'http', 'https')
        self.finnish_process(authorization_response= authorization_response)



    def finnish_process(self, code= None, authorization_response= None):
        kwargs = {}
        if code:
            kwargs['code'] = code
        elif authorization_response:
            kwargs['authorization_response'] = authorization_response
        _fix_google_ster_issues()
        self.flow.fetch_token(**kwargs)
        creds = self.flow.credentials
        self._save_creds(creds)
        self._get_service()
        return self


    @staticmethod
    def load_finnish_process(session: str):
        dill_file = f"{session}.dill"
        with open(dill_file, "rb") as f:
            finnish_process = dill.load(f)
        return finnish_process


    
    def delete(self):
        if self.is_authenticated:
            os.remove(self.pickle_file)


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


    @alt_build
    def _get_service_args(self, creds = None, http = None, developer_key= None):
        kwargs = build(self.api, self.version, credentials=creds, http= http, developerKey= developer_key)
        return dict(kwargs)



    def _scopes_changed(self, creds):
        if not self.scopes == creds.scopes:
            self.delete()
            self.authenticate_local()
            return True
        else:
            return False


    def _add_service_methods(self, service):
        self.__dict__.update({key: service.__dict__[key] for key in service.__dict__.keys() if not key.startswith("_")})


    def _make_special_services(self):
        if self.api == "gmail":
            self.users_service = self.users()
            self.history_service = self.users_service.history()
            self.message_service = self.users_service.messages()
            self.labels_service = self.users_service.labels()
            self.attachment_service = self.message_service.attachments()
        elif self.api == "drive":
            self.files_service = self.files()



    def _save_creds(self, creds):
        with open(self.pickle_file, 'wb') as token:
            pickle.dump(creds, token)



def url_auth(
    api: str,
    session: str = None,
    client_secrets: str = "creds.json",
    scopes: list = [],
    version: str = None,
    ):
    service = GoogleService(api= api, session= session, client_secrets= client_secrets, scopes= scopes, version= version, auth_type = 'url')
    url = service.get_auth_url()
    code = input(f'{url}\nenter code: ')
    service.finnish_process(code)
    return service
