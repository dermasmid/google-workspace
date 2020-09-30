from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.utils import getaddresses
from email.header import decode_header
from mimetypes import guess_type
import magic
import os
from datetime import datetime, date
import base64
from html.parser import HTMLParser

_not_important_tags = ('title', 'style')
def _handle_data(self, data):
    data = data.strip()
    if data and self.important_tag:
        self.text += data + '\n'

def _handle_starttag(self, tag, attrs):
    if tag in _not_important_tags:
        self.important_tag = False

def _handle_endtag(self, tag):
    if tag in _not_important_tags:
        self.important_tag = True



HTMLParser.handle_data = _handle_data
HTMLParser.handle_starttag = _handle_starttag
HTMLParser.handle_endtag = _handle_endtag


def is_english_chars(string: str):
    try:
        string.encode('utf-8').decode('ascii')
        return True
    except UnicodeDecodeError:
        return False


def encode_if_not_english(string: str):
    if not is_english_chars(string):
        b64_string = base64.b64encode(string.encode('utf-8')).decode('ascii')
        string = f"=?UTF-8?B?{b64_string}?="
    return string


def get_emails_address(raw: list or bool):
    result = []
    if raw:
        raw = getaddresses([raw])
        for _, email in raw:
            result.append(email.lower().strip())
    return result


def get_full_address_data(raw: list or bool):
    result = []
    if raw:
        raw = getaddresses([raw])
        for name, email in raw:
            result.append(
                {
                    "name": name,
                    "email": email.lower().strip()
                }
            )
    return result


def parse_date(date: str) -> datetime:
    if not date is None: # for chat messages that have no date
        if "," in date:
            data = datetime.strptime(date[:25].strip(), "%a, %d %b %Y %H:%M:%S")
        else:
            data = datetime.strptime(date[:20].strip(), "%d %b %Y %H:%M:%S") # edge case of getting "19 Aug 2020 11:05:13 -04" without weekday
    else:
        data = date
    return data



def decode(header: str):
    if not header is None:
        decode_data = decode_header(header)[0]
        data, encoding = decode_data
        if isinstance(data, bytes):
            try:
                return data.decode(encoding or 'utf-8', 'ignore')
            except LookupError:
                return data.decode('utf-8', 'ignore')
    else:
        data = header
    return data



def make_message(
    from_: str,
    sender_name: str = None,
    to: list or str = None,
    cc: list or str = None,
    bcc: list or str = None,
    subject: str = "",
    text: str = None,
    html: str = None,
    attachments: list = [], # list of file paths or list of tuples with (data, filename) format or (filepath, filename to use)
    references: str = None, # For replying emails
    in_reply_to: str = None # Same
    ):

    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = from_ if not sender_name else f'{sender_name} <{from_}>'

    if to:
        message["To"] = ", ".join(to) if isinstance(to, list) else to
    
    if cc:
        message["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc

    if bcc:
        message["Bcc"] = ", ".join(bcc) if isinstance(bcc, list) else bcc


    if references:
        message["References"] = references
        message["In-Reply-To"] = in_reply_to


    if text:
        text_message = MIMEMultipart("alternative")
        text_message.attach(MIMEText(text, "plain"))
        message.attach(text_message)
    

        if html:
            html_message = MIMEMultipart("related")
            html_message.attach(MIMEText(html, "html"))
            text_message.attach(html_message)

    mimes = {
        'text': MIMEText,
        'image': MIMEImage,
        'audio': MIMEAudio,
        'application': MIMEApplication
    }
    for attachment_path in attachments:
        if isinstance(attachment_path, str):
            file_name = os.path.basename(attachment_path)
            content_type = guess_type(attachment_path)[0]

            with open(attachment_path, 'rb') as f:
                data = f.read()
        elif isinstance(attachment_path, tuple):
            data = attachment_path[0]
            file_name = attachment_path[1]
            if isinstance(data, str):
                with open(data, 'rb') as f:
                    data = f.read()
            content_type = magic.from_buffer(data, mime= True)

        if content_type is None:
            content_type = 'application/octet-stream'
        main_type, sub_type = content_type.split('/', 1)
        
        if main_type in mimes.keys():
            if main_type == 'text' and type(data) is bytes:
                data = data.decode()
            attachment = mimes[main_type](data, _subtype=sub_type)
        else:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(data)
        attachment.add_header('Content-Disposition', 'attachment', filename= encode_if_not_english(file_name))
        message.attach(attachment)
    
    return message.as_string().encode()



def make_label_dict(name: str, message_list_visibility, label_list_visibility, background_color: str = None, text_color: str = None):
    body = {}
    if name:
        body['name'] = name

    if message_list_visibility:
        body['messageListVisibility'] = message_list_visibility.setting

    if label_list_visibility:
        body['LabelListVisibility'] = label_list_visibility.setting
        
    if background_color or text_color:
        color_dict = {
            'backgroundColor': background_color,
            'textColor': text_color
        }
        body['color'] = color_dict
    return body



def get_label_id(label_id: str):
    system_ids = (
        'chat', 
        'sent', 
        'inbox', 
        'important', 
        'trash', 
        'draft', 
        'spam', 
        'category_forums', 
        'category_updates', 
        'category_personal', 
        'category_promotions', 
        'category_social', 
        'starred', 
        'unread'
    )

    if label_id in system_ids:
        label_id = label_id.upper()

    return label_id




def get_html_text(html: str):
    parser = HTMLParser()
    parser.text = ''
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
    label_name: str = None
    ):
    query = ""

    if not seen is None:
        if seen:
            query += "is:read"
        else:
            query += "is:unread"
    
    if after:
        query += f'after:{after.strftime("%Y/%m/%d")}'

    if before:
        query += f'before:{before.strftime("%Y/%m/%d")}'

    if from_:
        query += f"from:({from_})"
    
    if to:
        query += f'to:({",".join(to) if isinstance(to, list) else to})'

    if subject:
        query += f"subject:({subject})"

    if label_name:
        query += f"label:{get_label_id(label_name)}"

    return query

