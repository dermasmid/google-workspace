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
    """GoogleService, A supercharged google service.

    Parameters:
        api (``str``):
            The service api e.g. 'gmail'.

        session (``str``, *optional*):
            A string to identify a authenticated service, when first
            authenticating a file {session}.pickle will be created which will store the credentials.
            Defaults to None.

        client_secrets (``str``, *optional*):
            A file path to the secrets file, or the secrets as a dict. you only need
            this when connecting for the first time. Defaults to "creds.json".

        scopes (``str`` | ``list``, *optional*):
            The scopes you want to authenticate
            you only need this when connecting for the first time. Defaults to None.

        version (``str``, *optional*):
            The api version, if you don't specify we will default
            to the latest one. Defaults to None.

        api_key (``str``, *optional*):
            Your api key (if you are not using oauth). Defaults to None.

        http (``Http``, *optional*):
            Optionally use diffrent http instance when using ``api_key``. Defaults to None.

        service (``Resource``, *optional*):
            Use your own constructed ``Resource`` object. Defaults to None.

        creds (``Credentials``, *optional*):
            Use your own constructed ``Credentials`` object. Defaults to None.

        workdir (``str``, *optional*):
            Where to store the session files and where to look
            for the creds file. Defaults to None.
    """

    def __init__(
        self,
        api: str,
        session: str = None,
        client_secrets: Union[str, dict] = "creds.json",
        scopes: Union[str, list] = None,
        version: str = None,
        api_key: str = None,
        http: Http = None,
        service: Resource = None,
        creds: Credentials = None,
        workdir: str = None,
    ):

        self.session = session or api
        self.version = version or utils.default_versions[api]
        self.api = api
        self.workdir = Path(workdir or ".")
        self.pickle_file = self.workdir / (self.session + ".pickle")
        self.is_authenticated = os.path.exists(self.pickle_file)
        utils.configure_error_handling()
        if service:
            if isinstance(service, Resource):
                self._add_service_methods(service)
                self._make_special_services()

        elif api_key:
            http = http or Http()
            service = self._get_service_args(http=http, developer_key=api_key)
            super().__init__(**service)

        elif creds:
            if isinstance(creds, Credentials):
                self._init_service(creds)

        else:
            if self.is_authenticated:
                self._init_service()
            else:
                if isinstance(client_secrets, str):
                    client_secrets = self.workdir / utils.get_creds_file(client_secrets)
                    with open(client_secrets, "r") as f:
                        self.client_config = json.load(f)
                else:
                    self.client_config = client_secrets

                if isinstance(scopes, str):
                    scopes = [scopes]
                self.scopes = scopes or utils.get_default_scopes(self.api)

    def local_oauth(self, server_port: int = 2626):
        """Run a local server to authenticate a user.

        Parameters:
            server_port (``int``, *optional*):
                The port to run the server on. Defaults to 2626.

        Returns:
            :obj:`~google_workspace.service.GoogleService`: Authenticated GoogleService.
        """

        if self.is_authenticated:
            return
        self.flow = InstalledAppFlow.from_client_config(self.client_config, self.scopes)
        creds = self.flow.run_local_server(port=server_port)
        self._save_creds(creds)
        self._init_service()
        return self

    def url_oauth(
        self,
        server_host: str,
        server_port: int = None,
        success_message: str = "success",
        keyfile: str = None,
        certfile: str = None,
        block=False,
    ) -> str:
        """Runs a flow to authenticate a user remotely by a url.

        Parameters:
            server_host (``str``):
                The host name of the machine (no http:// etc.).

            server_port (``int``, *optional*):
                The port to run the server on, if not provided
                we will look into the `client_secrets` file to determine which ports you have setup
                in your redirect_uris, this will only work if the file is updated after changing
                the settings in the google cloud console. Defaults to None.

            success_message (``str``, *optional*):
                A message to display to the user after they successfully
                authenticated. Defaults to "success".

            keyfile (``str``, *optional*):
                Your ssl keyfile to enable ssl for the server that
                we are going to run. Defaults to None.

            certfile (``str``, *optional*):
                Your ssl certfile to enable ssl for the server that
                we are going to run. Defaults to None.

            block (``bool``, *optional*):
                whether to have to program wait for the user
                to enter the link and finnish the signup, or move on with the execution
                of the program. Defaults to False.

        Returns:
            ``str`` | ``None``: If ``block`` is set to False (default) the function will return the url,
            otherwise we print the url.
        """

        if self.is_authenticated:
            return
        use_ssl = keyfile and certfile
        if not server_port:
            server_port = utils.get_available_allowed_port(
                self.client_config, server_host
            )
        self.redirect_uri = (
            f'{"https" if use_ssl else "http"}://{server_host}:{server_port}/'
        )
        self.auth_url = self.get_auth_url()
        oauthsever = utils.OauthServer(
            server_port, success_message, keyfile, certfile, self.fetch_token
        )
        thread = threading.Thread(target=oauthsever.start)
        thread.start()
        if not block:
            # TODO: We might want to add a callback for when
            # authentication is done
            return self.auth_url
        else:
            print(self.auth_url)
            thread.join()

    def code_oauth(self) -> str:
        """Runs a flow to authenticate a user remotely by a code.

        Returns:
            ``str``: The url for the user to authenticate.
        """

        if self.is_authenticated:
            return
        self.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        return self.get_auth_url()

    def get_auth_url(self, state: str = None) -> str:
        """Get a url with redirect_url taken from self.redirect_uri, you can
        use this if you are running the server yourself. When you get the code
        or authorization_response from the user, you can use `fetch_token` to
        complete the authentication process.

        Parameters:
            state (``str``, *optional*):
                Set the state for the authentication flow.

        Returns:
            ``str``: The url for the user to authenticate.
        """

        self.flow = Flow.from_client_config(
            self.client_config, scopes=self.scopes, redirect_uri=self.redirect_uri
        )
        auth_url, self.state = self.flow.authorization_url(
            prompt="consent", state=state
        )
        return auth_url

    def fetch_token(
        self, code: str = None, authorization_response: str = None, state: str = None
    ):
        """Complete the authentiction process.

        Parameters:
            code (``str``, *optional*):
                The code that the user got from google
                when they authorized your app. Defaults to None.

            authorization_response (``str``, *optional*):
                The reponse that the client sent
                to your server after the user authorized your app. Defaults to None.

            state (``str``, *optional*):
                The state used when you started the flow. Defaults to None.

        Returns:
            :obj:`~google_workspace.service.GoogleService`: Authenticated GoogleService.
        """

        self.flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri,
            state=state,
        )
        self.flow.fetch_token(code=code, authorization_response=authorization_response)
        creds = self.flow.credentials
        self._save_creds(creds)
        self._init_service()
        return self

    def delete(self) -> None:
        """Deletes the session file, and revokes the token."""

        if self.is_authenticated:
            with open(self.pickle_file, "rb") as f:
                creds = pickle.load(f)
            data = urllib.parse.urlencode({"token": creds.token}).encode("ascii")
            urllib.request.urlopen("https://oauth2.googleapis.com/revoke", data)
            os.remove(self.pickle_file)

    def get_state(self):
        """Get the state for the current flow.

        Returns:
            str: If you started a flow it will return the state,
            otherwise it will return None.
        """

        if hasattr(self, "state"):
            return self.state
        return None

    def make_thread_safe(self) -> None:
        """Set's this service to be thread safe. Used internally."""

        self._http.credentials.threading = True

    def get_service_state_value(self, key: str) -> Any:
        """Get a value from the service state. Used internally.

        Args:
            key (str): The key.

        Returns:
            Any: The value.
        """

        return self.service_state.get(self.api, {}).get(key)

    def update_service_state(self, key: str, value: Any) -> None:
        """Set's a value for the service state

        Parameters:
            key (``str``):
                The key.

            value (``Any``):
                the value.
        """

        if not self.api in self.service_state:
            self.service_state[self.api] = {}
        self.service_state[self.api][key] = value

    def save_service_state(self) -> None:
        """Saves the service state to the session file."""

        with open(self.pickle_file, "wb") as f:
            pickle.dump(self._http.credentials, f)
            pickle.dump(self.service_state, f)

    def close(self) -> None:
        """Closes the open http connection."""

        if self.is_authenticated:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.close()

    def __bool__(self) -> bool:
        """Whether the service is authenticated

        Returns:
            ``bool``: Returns True if the session file exists.
        """

        return self.is_authenticated

    def _get_service(self, creds: Credentials):
        service = self._get_service_args(creds)
        super().__init__(**service)
        self._make_special_services()
        self.authenticated_scopes = creds.scopes

    def _get_service_args(self, creds=None, http=None, developer_key=None):
        with utils.modify_resource():
            resource = build(
                self.api,
                self.version,
                credentials=creds,
                http=http,
                developerKey=developer_key,
            )
            kwargs = resource.kwargs  # pylint: disable=no-member
        return kwargs

    def _add_service_methods(self, service):
        self.__dict__.update(
            {
                key: service.__dict__[key]
                for key in service.__dict__.keys()
                if not key.startswith("_")
            }
        )

    def _make_special_services(self):
        if self.api == "gmail":
            self.users_service: Resource = self.users()  # pylint: disable=no-member
            self.history_service: Resource = self.users_service.history()
            self.messages_service: Resource = self.users_service.messages()
            self.threads_service: Resource = self.users_service.threads()
            self.labels_service: Resource = self.users_service.labels()
            self.settings_service: Resource = self.users_service.settings()
            self.attachments_service: Resource = self.messages_service.attachments()
        elif self.api == "drive":
            self.files_service: Resource = self.files()  # pylint: disable=no-member

    def _save_creds(self, creds: Credentials):
        with open(self.pickle_file, "wb") as token:
            pickle.dump(creds, token)
        self.is_authenticated = True

    def _get_creds(self):
        with open(self.pickle_file, "rb") as f:
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
