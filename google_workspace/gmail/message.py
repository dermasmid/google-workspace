from typing import Iterable, Tuple, Union

from typing_extensions import Literal

from . import gmail, thread, utils


class BaseMessage:
    """Common methods available on all message types.

    Parameters:
        gmail_client (:obj:`~google_workspace.gmail.GmailClient`):
            The gmail_client.

        message_data (``dict``):
            The raw message data.

    Attributes:
        gmail_client: The gmail client.
        message_data: The raw message data from the API.
        gmail_id: The message id used for the API.
        thread_id: The messgae thread ID.
        label_ids: A list of labels.
        snippet: A short snippet from the message.
        is_seen: Whether the message is marked as read or not.
        is_chat_message: If this message is a chat message.
    """

    def __init__(self, gmail_client: "gmail.GmailClient", message_data: dict) -> None:
        self.gmail_client = gmail_client
        self.message_data = message_data
        self.gmail_id = message_data.get("id")
        self.thread_id = message_data.get("threadId")
        self.label_ids = message_data.get("labelIds")
        self.snippet = message_data.get("snippet")
        self.is_seen = not "UNREAD" in self.label_ids
        self.is_chat_message = "CHAT" in self.label_ids

    def add_labels(self, label_ids: Union[list, str]) -> dict:
        """Add labels to this message.

        Parameters:
            label_ids (``list`` | ``str``):
                The lables to add.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.add_labels_to_message(self.gmail_id, label_ids)

    def remove_labels(self, label_ids: Union[list, str]) -> dict:
        """Remove labels from this message.

        Parameters:
            label_ids (``list`` | ``str``):
                The lables to remove.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.remove_labels_from_message(self.gmail_id, label_ids)

    def mark_read(self) -> dict:
        """Mark this message as read.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.mark_message_as_read(self.gmail_id)

    def mark_unread(self) -> dict:
        """Mark this message as unread.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.mark_message_as_unread(self.gmail_id)

    def delete(self) -> dict:
        """Delete this message permanently.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.delete_message(self.gmail_id)

    def trash(self) -> dict:
        """Move this message to the trash.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.trash_message(self.gmail_id)

    def untrash(self) -> dict:
        """Untrash this message.

        Returns:
            ``dict``: The API response.
        """

        return self.gmail_client.untrash_message(self.gmail_id)

    def get_header(self, header: str) -> Union[str, None]:
        """Get a header from this message.

        Parameters:
            header (``str``):
                The header name.

        Returns:
            ``str`` | None: If the header was found this will return the header value, otherwise
            it will return None.
        """

        if isinstance(self, MessageMetadata):
            return utils.invert_message_headers(
                self.message_data["payload"]["headers"]
            ).get(header)
        elif isinstance(self, Message):
            return self.email_object.get(header)  # pylint: disable=no-member

    def get_thread(
        self, message_format: Literal["minimal", "full", "metadata"] = None
    ) -> "thread.Thread":
        """Get the message's full thread.

        Parameters:
            message_format (``str``, *optional*):
                In which format to retrieve the messages. Can have one of the following values:
                ``"minimal"``, ``"full"``, ``"metadata"``. If this is not set we default to the
                format of the current message. Defaults to None.

        Returns:
            :obj:`~google_workspace.gmail.thread.Thread`: The full thread.
        """

        if not message_format:
            message_format = utils.get_message_format_from_message(
                self, allow_raw=False
            )
        return self.gmail_client.get_thread_by_id(self.thread_id, message_format)


class Message(BaseMessage):
    """A full message. This message is returned for "raw" and "full" message formats.

    Parameters:
        gmail_client (:obj:`~google_workspace.gmail.GmailClient`):
            The gmail_client.

        message_data (``dict``):
            The raw message data.
    Attributes:
        in_reply_to: The message id of the message this message replies to.
        references: The message ids of the messages this message is a reply to.
        is_reply: Whether the message is a reply or not.
        message_id: A string of the the message id.
        subject: A string of the message subject.
        raw_from: A string of the message's From header which can be used when sending messages
            to include the name.
        raw_to: A list of the message's To header in it's original form.
        raw_cc: A list of the message's Cc header in it's original form.
        raw_bcc: A list of the message's Bcc header in it's original form.
        to: A list of the message's To header with the email addresses only.
        cc: A list of the message's Cc header with the email addresses only.
        bcc: A list of the message's Bcc header with the email addresses only.
        raw_from_name: A string of the from name, potentially encoded.
        from_: A string of the email address of the sender.
        from_name: A string with the senders name decoded.
        raw_date: A string of the message date in it's original form.
        date: A Datetime object with the message's date.
        is_bulk: A boolean set to True when the message has the Precedence header set to bulk.
        text: A string with the message's plain text body.
        html: A string with the message's html body.
        attachments: A list of :obj:`~google_workspace.gmail.message.Attachment` objects.
        html_text: A string of the text extracted from the html body.
        has_attachments: A boolean indicating if the message has real attachments.

        gmail_client: The gmail client.
        message_data: The raw message data from the API.
        gmail_id: The message id used for the API.
        thread_id: The messgae thread ID.
        label_ids: A list of labels.
        snippet: A short snippet from the message.
        is_seen: Whether the message is marked as read or not.
        is_chat_message: If this message is a chat message.
    """

    def __init__(self, gmail_client: "gmail.GmailClient", message_data: dict):
        super().__init__(gmail_client, message_data)
        if message_data.get("raw"):
            self.message_format = "raw"
            self.email_object = utils.get_email_object(self.message_data["raw"])
            self._process_message()

    def __str__(self) -> str:
        return f"Message From: {self.from_}, Subject: {self.subject}, Date: {self.date}"

    def __contains__(self, text: str) -> bool:
        if text in self.subject or text in self.text or text in self.html_text:
            return True
        return False

    def _get_parts(self):
        text_parts = {"text/plain": "text", "text/html": "html"}
        for part in self.email_object.walk():
            if part.get_content_maintype() == "multipart":
                continue
            mimetype = part.get_content_type()
            if not part.get("Content-Disposition") and mimetype in text_parts:
                encoding = part.get_content_charset()
                if self.is_chat_message:
                    data = part.get_payload()
                else:
                    data = part.get_payload(decode=self.message_format == "raw")
                    # If format is full then the payload is the ready text.
                    if self.message_format == "raw":
                        try:
                            data = data.decode(encoding or "utf-8", "ignore")
                        except LookupError:
                            data = data.decode("utf-8", "ignore")
                setattr(self, text_parts[mimetype], data)

            else:
                self.attachments.append(Attachment(part))

    def reply(
        self,
        text: str = None,
        html: str = None,
        attachments: Union[Iterable[str], Iterable[Tuple[bytes, str]]] = [],
        headers: dict = None,
    ) -> dict:
        """Reply to this message.

        Parameters:
            text (``str``, *optional*):
                The plain text of the message. if you only specify ``html`` the text will be automaticly
                generated. Defaults to None.

            html (``str``, *optional*):
                The html of the message. Defaults to None.

            attachments (``list``, *optional*):
                A List of attachments. Can be a list of file paths like this ["image.png", "doc.pdf"],
                or it can be a list of lists where every list consists of the attachment data and a name
                for the attachment like this [[b"some binary here", "image.png"]].
                Defaults to [].

            headers (``dict``, *optional*):
                Additional headers to add to the message. Defaults to None.

        Returns:
            ``dict``: The API response.
        """

        if self.is_reply:
            references = self.references + " " + self.message_id
        else:
            references = self.message_id
        text_email, html_email = utils.create_replied_message(self, text, html)
        return self.gmail_client.send_message(
            to=self.raw_from,
            subject=f"Re: {self.subject}",
            text=text_email,
            html=html_email,
            attachments=attachments,
            references=references,
            in_reply_to=self.message_id,
            thread_id=self.thread_id,
            headers=headers,
        )

    def forward(
        self,
        to: Union[list, str] = None,
        cc: Union[list, str] = None,
        bcc: Union[list, str] = None,
        headers: dict = None,
    ) -> dict:
        """Forward this message.

        Parameters:
            to (``list`` | ``str``, *optional*):
                Who to send the message to. Can be either a string or a list of strings. Defaults to None.

            cc (``list`` | ``str``, *optional*):
                The cc recipients. Defaults to None.

            bcc (``list`` | ``str``, *optional*):
                The bcc recipients. Defaults to None.

            headers (``dict``, *optional*):
                Additional headers to add to the message. Defaults to None.

        Returns:
            ``dict``: The API response.
        """

        text_email, html_email = utils.create_forwarded_message(self)
        attachments = list(
            (attachment.payload, attachment.filename) for attachment in self.attachments
        )
        return self.gmail_client.send_message(
            to,
            f"Fwd: {self.subject}",
            text_email,
            html_email,
            attachments,
            cc,
            bcc,
            headers,
        )

    @classmethod
    def from_full_format(cls, gmail_client: "gmail.GmailClient", message_data: dict):
        """Create a message from the "full" format.

        Parameters:
            gmail_client (:obj:`~google_workspace.gmail.GmailClient`):
                The gmail_client.

            message_data (``dict``):
                The raw message data in "full" format.
        """

        self = cls(gmail_client, message_data)
        self.message_format = "full"
        self.email_object = utils.full_format_to_message_object(message_data["payload"])
        self._process_message()
        return self

    def _process_message(self):
        self.in_reply_to = self.email_object["In-Reply-To"]
        self.references = self.email_object["References"]
        self.is_reply = bool(self.in_reply_to)
        self.message_id = self.email_object["Message-Id"]
        self.subject = utils.decode(self.email_object["Subject"]) or ""

        # from, to, cc, bcc
        self.raw_from = self.email_object["From"]
        self.raw_to = self.email_object["To"]
        self.raw_cc = self.email_object["Cc"]
        self.raw_bcc = self.email_object["Bcc"]
        self.to = utils.get_email_addresses(self.raw_to) or []
        self.cc = utils.get_email_addresses(self.raw_cc) or []
        self.bcc = utils.get_email_addresses(self.raw_bcc) or []
        (
            self.raw_from,
            self.raw_from_name,
            self.from_,
            self.from_name,
        ) = utils.get_from_info(self.raw_from)

        self.raw_date = self.email_object["Date"]
        self.date = utils.parse_date(self.raw_date)
        self.is_bulk = self.email_object["Precedence"] == "bulk"
        self.text = ""
        self.html = ""
        self.attachments = []
        self._get_parts()
        self.html_text = utils.get_html_text(self.html)
        # This is if you what to know if the message has a real attachment
        self.has_attachments = any(
            not attachment.is_inline for attachment in self.attachments
        )


class MessageMetadata(BaseMessage):
    """A message that includes only email message ID, labels, and email headers.
    This message is returned for the "metadata" message format.

    Parameters:
        gmail_client (:obj:`~google_workspace.gmail.GmailClient`):
            The gmail_client.

        message_data (``dict``):
            The raw message data.
    Attributes:
        in_reply_to: The message id of the message this message replies to.
        references: The message ids of the messages this message is a reply to.
        is_reply: Whether the message is a reply or not.
        message_id: A string of the the message id.
        subject: A string of the message subject.
        raw_from: A string of the message's From header which can be used when sending messages
            to include the name.
        raw_to: A list of the message's To header in it's original form.
        raw_cc: A list of the message's Cc header in it's original form.
        raw_bcc: A list of the message's Bcc header in it's original form.
        to: A list of the message's To header with the email addresses only.
        cc: A list of the message's Cc header with the email addresses only.
        bcc: A list of the message's Bcc header with the email addresses only.
        raw_from_name: A string of the from name, potentially encoded.
        from_: A string of the email address of the sender.
        from_name: A string with the senders name decoded.
        raw_date: A string of the message date in it's original form.
        date: A Datetime object with the message's date.
        is_bulk: A boolean set to True when the message has the Precedence header set to bulk.

        gmail_client: The gmail client.
        message_data: The raw message data from the API.
        gmail_id: The message id used for the API.
        thread_id: The messgae thread ID.
        label_ids: A list of labels.
        snippet: A short snippet from the message.
        is_seen: Whether the message is marked as read or not.
        is_chat_message: If this message is a chat message.
    """

    def __init__(self, gmail_client: "gmail.GmailClient", message_data: dict) -> None:
        super().__init__(gmail_client, message_data)
        self._process_message()

    def _process_message(self):
        headers = utils.invert_message_headers(self.message_data["payload"]["headers"])
        self.raw_date = headers.get("Date")
        self.date = utils.parse_date(self.raw_date)
        self.subject = headers.get("Subject")
        self.raw_reply_to = headers.get("Reply-To")
        self.message_id = headers.get("Message-Id")
        self.in_reply_to = headers.get("In-Reply-To")
        self.references = headers.get("References")
        self.is_reply = bool(self.in_reply_to)
        self.is_bulk = self.headers.get["Precedence"] == "bulk"

        # from, to, cc, bcc
        self.raw_from = headers.get("From")
        self.raw_to = headers.get("To")
        self.raw_cc = headers.get("Cc")
        self.raw_bcc = headers.get("Bcc")
        self.to = utils.get_email_addresses(self.raw_to) or []
        self.cc = utils.get_email_addresses(self.raw_cc) or []
        self.bcc = utils.get_email_addresses(self.raw_bcc) or []
        (
            self.raw_from,
            self.raw_from_name,
            self.from_,
            self.from_name,
        ) = utils.get_from_info(self.raw_from)

    def get_full_message(self) -> Message:
        """Download the full message. Downloads the message using the "raw" format.

        Returns:
            :obj:`~google_workspace.gmail.message.Message`: The full message.
        """

        return self.gmail_client.get_message_by_id(self.gmail_id, message_format="raw")

    def __str__(self) -> str:
        return f"Message From: {self.from_}, Subject: {self.subject}, Date: {self.date}"


class MessageMinimal(BaseMessage):
    """A message that includes only email message ID and labels.
    This message is returned for the "minimal" message format.

    Parameters:
        gmail_client (:obj:`~google_workspace.gmail.GmailClient`):
            The gmail_client.

        message_data (``dict``):
            The raw message data.

    Attributes:
        gmail_client: The gmail client.
        message_data: The raw message data from the API.
        gmail_id: The message id used for the API.
        thread_id: The messgae thread ID.
        label_ids: A list of labels.
        is_seen: Whether the message is marked as read or not.
        is_chat_message: If this message is a chat message.
    """

    def __init__(self, gmail_client: "gmail.GmailClient", message_data: dict) -> None:
        super().__init__(gmail_client, message_data)

    def get_full_message(self) -> Message:
        """Download the full message. Downloads the message using the "raw" format.

        Returns:
            :obj:`google_workspace.gmail.message.Message`: The full message.
        """

        return self.gmail_client.get_message_by_id(self.gmail_id, message_format="raw")

    def __str__(self) -> str:
        return self.gmail_id


class Attachment:
    """A file attachment.

    Parameters:
        attachment_part (``dict``):
            The message part that is the attachment as a dict.

    Attributes:
        is_inline: A boolean indicating if this attachment is inline.
        content_id: The content id.
        filename: The attachment's file name.
        payload: The raw attachment data.
    """

    def __init__(self, attachment_part: dict):
        self._part = attachment_part
        # Content-Disposition might be a Header in some cases.
        self.is_inline = utils.decode_if_header(
            attachment_part.get("Content-Disposition", "")
        ).startswith("inline")
        self.content_id = attachment_part["Content-ID"]

    @property
    def filename(self) -> str:
        return utils.decode(self._part.get_filename()) or ""

    @property
    def payload(self) -> bytes:
        data = self._part.get_payload(decode=True)
        return data

    def download(self, path: str = None) -> str:
        """Save the attachment data to disk.

        Parameters:
            path (``str``, *optional*):
                A path to save the file to, if not set we default to the file name
        """

        path = path or self.filename
        data = self.payload
        with open(path, "wb") as f:
            f.write(data)
        return path

    def __repr__(self) -> str:
        return self.filename
