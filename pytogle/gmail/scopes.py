from ..types import Scope


__all__ = [
    'FullAccessGmailScope',
    'LabelsGmailScope',
    'SendGmailScope',
    'ReadonlyGmailScope',
    'ComposeGmailScope',
    'InsertGmailScope',
    'ModifyGmailScope',
    'MetadataGmailScope',
    'SettingsBasicGmailScope',
    'SettingsSharingGmailScope'
]

class FullAccessGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://mail.google.com/',
            usage= 'restricted',
            description= '''
            Full access to the account’s mailboxes,
            including permanent deletion of threads and messages This scope should only be requested if your application needs 
            to immediately and permanently delete threads and messages, bypassing Trash; all other actions can be performed with less permissive scopes.
            '''
        )



class LabelsGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.labels',
            usage= 'recommended',
            description= '''
            Create, read, update, and delete labels only.
            '''
        )


class SendGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.send',
            usage= 'sensitive',
            description= '''
            Send messages only. No read or modify privileges on mailbox.
            '''
        )



class ReadonlyGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.readonly',
            usage= 'restricted',
            description= '''
            Read all resources and their metadata—no write operations.
            '''
        )



class ComposeGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.compose',
            usage= 'restricted',
            description= '''
            Create, read, update, and delete drafts. Send messages and drafts.
            '''
        )



class InsertGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.insert',
            usage= 'restricted',
            description= '''
            Insert and import messages only.
            '''
        )



class ModifyGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.modify',
            usage= 'restricted',
            description= '''
            All read/write operations except immediate, permanent deletion of threads and messages, bypassing Trash.
            '''
        )


class MetadataGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.metadata',
            usage= 'restricted',
            description= '''
            Read resources metadata including labels, history records, and email message headers, but not the message body or attachments.
            '''
        )


class SettingsBasicGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.settings.basic',
            usage= 'restricted',
            description= '''
            Manage basic mail settings.
            '''
        )


class SettingsSharingGmailScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/gmail.settings.sharing',
            usage= 'restricted',
            description= '''
            Manage sensitive mail settings, including forwarding rules and aliases.
            Note: Operations guarded by this scope are restricted to administrative use only. 
            They are only available to G Suite customers using a service account with domain-wide delegation
            '''
        )


def get_gmail_default_scope():
    return FullAccessGmailScope()
