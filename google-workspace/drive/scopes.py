from ..types import Scope


class FullAccessDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive',
            usage= 'restricted',
            description= '''
            Full, permissive scope to access all of a user's files, excluding the Application Data folder.
            '''
        )



class AppdataDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.appdata',
            usage= 'recommended',
            description= '''
            Allows access to the Application Data folder.
            '''
        )



class FileDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.file',
            usage= 'recommended',
            description= '''
            Per-file access to files created or opened by the app. 
            File authorization is granted on a per-user basis and is revoked when the user deauthorizes the app.	
            '''
        )



class InstallDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.install',
            usage= 'recommended',
            description= '''
            Special scope used to let users approve installation of an app, and scope needs to be requested.
            '''
        )


class AppsReadonlyDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.apps.readonly',
            usage= 'sensitive',
            description= '''
            Allows read-only access to installed apps.
            '''
        )


class MetadataDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.metadata',
            usage= 'restricted',
            description= '''
            Allows read-write access to file metadata (excluding downloadUrl and thumbnail), 
            but does not allow any access to read, download, write or upload file content. 
            Does not support file creation, trashing or deletion. 
            Also does not allow changing folders or sharing in order to prevent access escalation.
            '''
        )


class ActivityDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.activity',
            usage= 'restricted', 
            description= '''
            Allows read and write access to the Drive Activity API.
            '''
        )


class ActivityReadonlyDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.activity.readonly',
            usage= 'restricted',
            description= '''
            Allows read-only access to the Drive Activity API.
            '''
        )


class ReadonlyDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.readonly',
            usage= 'restricted',
            description= '''
            Allows read-only access to file metadata and file content.
            '''
        )


class MetadataReadonlyDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.metadata.readonly',
            usage= 'restricted',
            description= '''
            Allows read-only access to file metadata (excluding downloadUrl and thumbnail), 
            but does not allow any access to read or download file content.
            '''
        )


class ScriptsDriveScope(Scope):

    def __init__(self):
        super().__init__(
            scope_code= 'https://www.googleapis.com/auth/drive.scripts', 
            usage= 'restricted',
            description= '''
            Allows access to Apps Script files.
            '''
        )

def get_drive_default_scope():
    return FullAccessDriveScope()
