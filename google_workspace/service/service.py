import json
import os
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

        session (``str`` | ``dict``, *optional*):
            Pass a string of your choice to give a name to the client session, e.g.: "gmail".
            This name will be used to save a file on disk that stores details needed to reconnect without asking
            again for credentials. If you don't pass a value the credentials will not be writen to disk, so in order
            to preserve the credentials you can use the export_session method which will return a dict which you can
            save however you want, and then use it as the value here in order to reconnect.
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

        credentials (``Credentials``, *optional*):
            Use your own constructed ``Credentials`` object. Defaults to None.

        workdir (``str``, *optional*):
            Where to store the session files and where to look
            for the creds file. Defaults to None.

    Attributes:
        version: A string of the api version.
        api: A string of the api.
        workdir: A Path object of the working directory.
        session_file: A string of the session file if session was a string.
        session_data: A dict of the session data, including the token and addtional values set by set_value().
        is_authenticated: A boolean indicating if the service is authenticated.
    """

    def __init__(
        self,
        api: str,
        session: Union[str, dict] = None,
        client_secrets: Union[str, dict] = "creds.json",
        scopes: Union[str, list] = None,
        version: str = None,
        api_key: str = None,
        http: Http = None,
        service: Resource = None,
        credentials: Credentials = None,
        workdir: str = None,
    ):

        self.version = version or utils.default_versions.get(api)
        self.api = api
        self.workdir = Path(workdir or ".")
        self.session_file = None
        self.session_data = {}
        self.is_authenticated = False
        if isinstance(session, str):
            self.session_file = self.workdir / ((session or api) + ".session")
            self.is_authenticated = os.path.exists(self.session_file)
        elif isinstance(session, dict):
            self.is_authenticated = True
            self.session_data = session

        utils.configure_error_handling()
        if service:
            if isinstance(service, Resource):
                self._add_service_methods(service)
                self._make_special_services()

        elif api_key:
            http = http or Http()
            service = self._get_service_args(http=http, developer_key=api_key)
            super().__init__(**service)

        elif credentials:
            self.is_authenticated = True
            self.credentials = credentials
            self._init_service()

        else:
            self.credentials = None
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

    def local_oauth(self, server_port: int = 2626) -> None:
        """Run a local server to authenticate a user.

        Parameters:
            server_port (``int``, *optional*):
                The port to run the server on. Defaults to 2626.
        """

        if self.is_authenticated:
            return
        self.flow = InstalledAppFlow.from_client_config(self.client_config, self.scopes)
        self.credentials = self.flow.run_local_server(port=server_port)
        self._retrieve_session_data()
        self._save_session()
        self._init_service()

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
        self.credentials = self.flow.credentials
        self._retrieve_session_data()
        self._save_session()
        self._init_service()
        return self

    def delete(self) -> None:
        """Deletes the session file, and revokes the token."""

        if self.is_authenticated:
            data = urllib.parse.urlencode({"token": self.credentials.token}).encode(
                "ascii"
            )
            urllib.request.urlopen("https://oauth2.googleapis.com/revoke", data)
            if self.session_file:
                os.remove(self.session_file)

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

    def get_value(self, key: str) -> Any:
        """Get a value from the service set by set_value.

        Args:
            key (str): The key.

        Returns:
            Any: The value.
        """

        return self.session_data.get(self.api, {}).get(key)

    def set_value(self, key: str, value: Any) -> None:
        """Set a value for the service.

        Parameters:
            key (``str``):
                The key.

            value (``Any``):
                the value.
        """

        if not self.api in self.session_data:
            self.session_data[self.api] = {}
        self.session_data[self.api][key] = value
        self._save_session()

    def export_session(self) -> dict:
        """Export the session data, updating the token first.

        Returns:
            dict: The session data.
        """

        self._retrieve_session_data()
        return self.session_data

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

    def _get_service(self):
        service = self._get_service_args(self.credentials)
        super().__init__(**service)
        self._make_special_services()
        self.authenticated_scopes = self.credentials.scopes

    def _get_service_args(self, credentials=None, http=None, developer_key=None):
        with utils.modify_resource():
            resource = build(
                self.api,
                self.version,
                credentials=credentials,
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

    def _save_session(self):
        if self.session_file:
            with open(self.session_file, "w") as f:
                json.dump(self.session_data, f)
        self.is_authenticated = True

    def _retrieve_session_data(self):
        if self.session_file and self.is_authenticated and not self.session_data:
            with open(self.session_file, "r") as f:
                self.session_data = json.load(f)

        else:
            self.session_data["credentials"] = json.loads(self.credentials.to_json())

    def _retrieve_credentials(self):
        self.credentials = Credentials.from_authorized_user_info(
            self.session_data["credentials"]
        )
        if not self.credentials.valid:
            request = Request()
            self.credentials.refresh(request)
            request.session.close()

    def _init_service(self):
        if not self.session_data:
            self._retrieve_session_data()
        if not self.credentials:
            self._retrieve_credentials()
        self._get_service()
        self._post_auth_setup()

    def _post_auth_setup(self):
        self._http.credentials.is_google_workspace = True
        self._http.credentials.threading = False
        self._http.credentials.authenticated_scopes = self.authenticated_scopes
        self._http.credentials.api = (
            self.api
        )  # TODO: we can get this from the method_id
        self._http.credentials.version = (
            self.version
        )  # TODO: we can maybe get this from the url?
