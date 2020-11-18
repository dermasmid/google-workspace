import os
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from mimetypes import guess_type
from ..service import GoogleService




class Drive:

    def __init__(self, service: GoogleService = None):
        if isinstance(service, GoogleService):
            self.service = service
        
        else:
            self.connect()

    def connect(self):
        self.service = GoogleService(api= "drive")





    def upload(self, path, folder):
        mimetype = guess_type(path)
        file_metadata = {"name": path.split("/")[-1], "parents": [folder]}
        media = MediaFileUpload(filename=path, mimetype=mimetype[0], resumable=True)
        upload = self.service.files_service.create(body = file_metadata, media_body = media, fields = "id").execute()
        return upload.get("id")








    def make_folder(self, folder_name, parent = None):
        if parent:
            body = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}
        else:
            body = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        folder_id = self.service.files_service.create(fields = "id", body= body).execute().get("id")
        return folder_id



    def make_public(self, file_id):
        permission_role = {'type': 'anyone', 'role': 'reader'}
        self.service.permissions().create(fileId=file_id, body = permission_role).execute()
