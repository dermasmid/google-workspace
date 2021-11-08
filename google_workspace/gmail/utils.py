import base64
import os
import textwrap
from datetime import date, datetime
from email.header import Header, decode_header
from email.message import Message
from email.mime.application import MIMEApplication
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.parser import BytesParser
from email.utils import getaddresses
from html.parser import HTMLParser
from mimetypes import guess_type
from typing import Iterable, Tuple, Union

import magic
from googleapiclient.errors import HttpError
from typing_extensions import Literal

from . import gmail, histories, message

handler_update_key_to_type_map = {
    "messagesAdded": "messageAdded",
    "messagesDeleted": "messageDeleted",
    "labelsAdded": "labelAdded",
    "labelsRemoved": "labelRemoved",
}


def get_message_class(
    message_format: Literal["minimal", "full", "raw", "metadata"] = "raw"
):
    return {
        "minimal": message.MessageMinimal,
        "full": message.Message.from_full_format,
        "raw": message.Message,
        "metadata": message.MessageMetadata,
    }[message_format]


_not_important_tags = ("title", "style", "script")


def _handle_data(self, data):
    data = data.strip()
    if data and self.important_tag:
        self.text += data + "\n"


def _handle_starttag(self, tag, attrs):
    if tag in _not_important_tags:
        self.important_tag = False


def _handle_endtag(self, tag):
    if tag in _not_important_tags:
        self.important_tag = True


HTMLParser.handle_data = _handle_data
HTMLParser.handle_starttag = _handle_starttag
HTMLParser.handle_endtag = _handle_endtag


def is_english_chars(string: str) -> str:
    try:
        string.encode("utf-8").decode("ascii")
        return True
    except UnicodeDecodeError:
        return False


def encode_if_not_english(string: Union[str, None]) -> Union[str, None]:
    if string and not is_english_chars(string):
        b64_string = base64.b64encode(string.encode("utf-8")).decode("ascii")
        string = f"=?UTF-8?B?{b64_string}?="
    return string


def get_email_addresses(raw: Union[list, None]) -> Union[list, None]:
    result = []
    if raw:
        raw = getaddresses([decode_if_header(raw)])
        for _, email in raw:
            result.append(email.lower().strip())
    return result


def get_email_name(raw: Union[str, None]) -> Union[str, None]:
    if raw:
        raw = getaddresses([decode_if_header(raw)])
        for name, _ in raw:
            return name
    return raw


def get_from_info(raw_from: Union[str, None]):
    from_ = get_email_addresses(raw_from)
    if from_:
        from_ = from_[0]
    else:
        from_ = None
    raw_from_name = encode_if_not_english(get_email_name(raw_from))
    from_name = decode(raw_from_name)
    # We fixing `raw_from` so it can be used in `to` field when sending message
    # and `from_name` contains none ascii chars
    raw_from = f"{raw_from_name} <{from_}>" if all((raw_from_name, from_)) else None
    return raw_from, raw_from_name, from_, from_name


def decode_if_header(data: Union[list, None, Header]) -> Union[list, None]:
    if isinstance(data, Header):
        return decode(data)
    return data


def parse_date(date: str) -> datetime:
    if not date is None:  # for chat messages that have no date
        if "," in date:
            data = datetime.strptime(date[:25].strip(), "%a, %d %b %Y %H:%M:%S")
        else:
            data = datetime.strptime(
                date[:20].strip(), "%d %b %Y %H:%M:%S"
            )  # edge case of getting "19 Aug 2020 11:05:13 -04" without weekday
    else:
        data = date
    return data


def decode(header: Union[list, None, Header]) -> Union[str, None]:
    if not header is None:
        decode_data = decode_header(header)[0]
        data, encoding = decode_data
        if isinstance(data, bytes):
            try:
                return data.decode(encoding or "utf-8", "ignore")
            except LookupError:
                return data.decode("utf-8", "ignore")
        return data
    return header


def get_email_object(message_data: str) -> Message:
    b64decoded = base64.urlsafe_b64decode(message_data)
    parser = BytesParser()
    return parser.parsebytes(b64decoded)


def make_message(
    from_: str,
    sender_name: str = None,
    to: Union[list, str] = None,
    cc: Union[list, str] = None,
    bcc: Union[list, str] = None,
    subject: str = "",
    text: str = None,
    html: str = None,
    attachments: Union[Iterable[str], Iterable[Tuple[bytes, str]]] = [],
    references: str = None,
    in_reply_to: str = None,
    headers: dict = None,
) -> bytes:

    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = from_ if not sender_name else f"{sender_name} <{from_}>"

    if to:
        message["To"] = ", ".join(to) if isinstance(to, list) else to

    if cc:
        message["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc

    if bcc:
        message["Bcc"] = ", ".join(bcc) if isinstance(bcc, list) else bcc

    if headers:
        for header_name, header_value in headers.items():
            message.add_header(header_name, header_value)

    if references:
        message["References"] = references
        message["In-Reply-To"] = in_reply_to

    if not text and html:  # User did not pass text, We will be taking it from the html
        text = get_html_text(html)

    if text is not None:
        text_message = MIMEMultipart("alternative")
        text_message.attach(MIMEText(text, "plain"))
        message.attach(text_message)

        if html:
            html_message = MIMEMultipart("related")
            html_message.attach(MIMEText(html, "html"))
            text_message.attach(html_message)

    mimes = {
        "text": MIMEText,
        "image": MIMEImage,
        "audio": MIMEAudio,
        "application": MIMEApplication,
    }
    for attachment_path in attachments:
        if isinstance(attachment_path, str):
            file_name = os.path.basename(attachment_path)
            content_type = guess_type(attachment_path)[0]

            with open(attachment_path, "rb") as f:
                data = f.read()
        elif isinstance(attachment_path, Iterable):
            data = attachment_path[0]
            file_name = attachment_path[1]
            content_type = magic.from_buffer(data, mime=True)

        if content_type is None:
            content_type = "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)

        if main_type in mimes.keys():
            if main_type == "text" and type(data) is bytes:
                data = data.decode()
            attachment = mimes[main_type](data, _subtype=sub_type)
        else:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(data)
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=encode_if_not_english(file_name),
        )
        message.attach(attachment)

    return message.as_string().encode()


def make_label_dict(
    name: str,
    message_list_visibility,
    label_list_visibility,
    background_color: str = None,
    text_color: str = None,
):
    body = {}
    if name:
        body["name"] = name

    if message_list_visibility:
        body["messageListVisibility"] = message_list_visibility

    if label_list_visibility:
        body["LabelListVisibility"] = label_list_visibility

    if background_color or text_color:
        color_dict = {"backgroundColor": background_color, "textColor": text_color}
        body["color"] = color_dict
    return body


def get_label_id(label_id: str):
    system_ids = (
        "chat",
        "sent",
        "inbox",
        "important",
        "trash",
        "draft",
        "spam",
        "category_forums",
        "category_updates",
        "category_personal",
        "category_promotions",
        "category_social",
        "starred",
        "unread",
    )

    if label_id in system_ids:
        return label_id.upper()

    return label_id


def get_proper_label_ids(label_ids: Union[list, str]) -> Union[list, None]:
    """Convert labels we get from users to the ones used by gmail.
    EX. 'inbox' to ['INBOX'].

    Parameters:
        label_ids (``list`` | ``str``):
            Either a list of labels or a single one.

    Returns:
        ``list`` | None:
            If `label_id` was not None this will be a list.
    """

    if isinstance(label_ids, str):
        return [get_label_id(label_ids)]
    elif isinstance(label_ids, list):
        return list(map(get_label_id, label_ids))


def get_html_text(html: str):
    parser = HTMLParser()
    parser.text = ""
    parser.important_tag = True
    parser.feed(html)

    return parser.text.strip()


def gmail_query_maker(
    seen: bool = None,
    from_: str = None,
    to: list = None,
    subject: str = None,
    after: date = None,
    before: date = None,
    label_name: str = None,
) -> str:
    querys = []

    if not seen is None:
        if seen:
            querys.append("is:read")
        else:
            querys.append("is:unread")

    if after:
        querys.append(f'after:{after.strftime("%Y/%m/%d")}')

    if before:
        querys.append(f'before:{before.strftime("%Y/%m/%d")}')

    if from_:
        querys.append(f"from:({from_})")

    if to:
        querys.append(f'to:({",".join(to) if isinstance(to, list) else to})')

    if subject:
        querys.append(f"subject:({subject})")

    if label_name:
        querys.append(f"label:{get_label_id(label_name)}")

    return " ".join(querys)


def create_forwarded_message(message) -> Tuple[str, str]:
    formated_to = ", ".join(message.to)
    formated_date = message.date.strftime("%a, %b %d, %Y at %I:%M %p")
    text_email = """

    ---------- Forwarded message ---------
    From: {from_name} <{from_email}>
    Date: {date}
    Subject: {subject}
    To: <{to_email}>

    {body}
    """.format(
        from_email=message.from_,
        from_name=message.from_name,
        date=formated_date,
        subject=message.subject,
        to_email=formated_to,
        body=message.text,
    )

    html_email = """<div dir="ltr"><br><br><div class="gmail_quote"><div dir="ltr" class="gmail_attr">---------- Forwarded message ---------<br>
    From: <strong class="gmail_sendername" dir="auto">{from_name}</strong> <span dir="auto">&lt;<a href="mailto:{from_email}">{from_email}</a>&gt;</span><br>
    Date: {date}<br>Subject: {subject}<br>To: &lt;<a href="mailto:{to_email}" target="_blank">{to_email}</a>&gt;<br></div><br><br>{body}</div></div>
    """.format(
        from_email=message.from_,
        from_name=message.from_name,
        to_email=formated_to,
        subject=message.subject,
        date=formated_date,
        body=message.html,
    )

    return textwrap.dedent(text_email), textwrap.dedent(html_email.replace("\n", ""))


def create_replied_message(message, text_body: str, html_body: str) -> Tuple[str, str]:
    formated_date = message.date.strftime("%a, %b %d, %Y at %I:%M %p")
    if text_body:
        text_email = """
        {text_body}

        On {date} {from_name} <{from_email}>
        wrote:

        {body}
        """.format(
            text_body=text_body,
            date=formated_date,
            from_name=message.from_name,
            from_email=message.from_,
            body="\n".join("> " + line for line in message.text.split("\n")),
        )
        text_email = "\n".join(map(lambda line: line.lstrip(), text_email.split("\n")))
    else:
        text_email = None

    if html_body:
        html_email = """
        {html_body}<br><div class="gmail_quote"><div dir="ltr" class="gmail_attr">On {date} {from_name} &lt;<a
        href="{from_email}">{from_email}</a>&gt; wrote:<br></div><blockquote class="gmail_quote"
        style="margin:0px 0px 0px 0.8ex;border-left:1px solid rgb(204,204,204);padding-left:1ex"><u></u>
        {body}</blockquote></div>
        """.format(
            html_body=html_body,
            date=formated_date,
            from_name=message.from_name,
            from_email=message.from_,
            body=message.html,
        )
        html_email = textwrap.dedent(html_email.replace("\n", ""))
    else:
        html_email = None

    return text_email, html_email


def invert_message_headers(message_headers: list) -> dict:
    return {header["name"]: header["value"] for header in message_headers}


def add_encoding_aliases():
    # https://bugs.python.org/issue18624
    from encodings import _aliases

    _aliases["iso_8859_8_i"] = "iso8859_8"
    _aliases["iso-8859-8-e"] = "iso8859_8"


def handle_update(gmail_client: "gmail.GmailClient", history: "histories.History"):
    handle_labels = gmail_client._handlers_config["labels_per_type"][
        history.history_type
    ]

    if handle_labels and not any(label in handle_labels for label in history.label_ids):
        # Don't even bother downloading the full message
        return
    try:
        history.message
    except HttpError as e:
        if e._get_reason().strip() == "Requested entity was not found.":
            # We got an update for a draft, but was deleted (sent out) or updated since.
            return
        raise e

    for handler in gmail_client.handlers[history.history_type]:
        if handler.check(history):
            handler.callback(history)


def add_labels_to_handler_config(
    labels: list, config: Union[list, None]
) -> Union[list, None]:
    if labels:
        if not config is None:
            for label in labels:
                if not label in config:
                    config.append(label)
    else:
        config = None
    return config


def full_format_to_message_object(
    parts: Union[dict, list], message: MIMEBase = None
) -> MIMEBase:
    if not message:
        # This is the root part
        maintype, subtype = parts["mimeType"].split("/", 1)
        message = MIMEBase(maintype, subtype)
        for header in parts["headers"]:
            message[header["name"]] = header["value"]
        if message.get_content_maintype() == "multipart":
            full_format_to_message_object(parts["parts"], message)
        else:
            message.set_payload(parts["body"].get("data"))
    else:
        for part in parts:
            if part["mimeType"].split("/")[0] == "multipart":
                message_part = MIMEMultipart("mixed")
                full_format_to_message_object(part["parts"], message_part)
                message.attach(message_part)
            else:
                try:
                    maintype, subtype = part["mimeType"].split("/", 1)
                except ValueError:
                    # There's no valid mimetype, I saw the python parser set the mimetype to text/plain
                    # when it did not understand the mimetype.
                    maintype, subtype = "text", "plain"
                message_part = MIMEBase(maintype, subtype)
                for header in part["headers"]:
                    message_part[header["name"]] = header["value"]
                # Dispite the Content-Transfer-Encoding, it seems like everything is encoded
                # in b64
                data = base64.urlsafe_b64decode(part["body"].get("data", "")).decode()
                message_part.set_payload(data)
                message.attach(message_part)
    return message


def get_message_format_from_message(
    message_obj: "message.BaseMessage", allow_raw: bool = True
) -> str:
    if isinstance(message_obj, message.MessageMetadata):
        return "metadata"
    if isinstance(message_obj, message.MessageMinimal):
        return "minimal"
    if isinstance(message_obj, message.Message):
        if message_obj.message_data.get("raw") and allow_raw:
            return "raw"
        return "full"
