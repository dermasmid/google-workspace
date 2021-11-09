# Google Workspace

**Google Workspace** is a high level unofficial API wrapper for some of the productivity related Google API's.
This library has for now only implemented a client for Gmail, I hope to add Drive and much more in the near future.

# Installation

You can install from pypi:

``` bash
pip install -U google-workspace
```

Or get the latest updates (Not recommended for production):

```bash
pip install -U git+https://github.com/dermasmid/google-workspace.git
```

# Documentation

Take a look at the full documentation here [https://google-workspace.readthedocs.io/](https://google-workspace.readthedocs.io/)


# Getting project credentials

You need to get a client secret file from [the google console](https://console.developers.google.com/) and you need to enable the api you want to use, just Google it.

After you saved the credentials json file to your workdir - you are all set!


# Quick start's

Here you can see a few samples to get a feel of whats ahead.


## Authenticate on your local machine

This snippet will run a authentication flow using the `local_oauth` method.

```python
import google_workspace

service = google_workspace.service.GoogleService(
    api="gmail",
    session="my-gmail",
    client_secrets="path/to/secrets/file"
    )
service.local_oauth()

gmail_client = google_workspace.gmail.GmailClient(service=service)
print(gmail_client.email_address)

```

## Authenticate a remote user

This snippet will run a authentication flow using the `url_oauth` method.

```python
import google_workspace

service = google_workspace.service.GoogleService(
    api="gmail",
    session="my-gmail",
    client_secrets="path/to/secrets/file"
    )

service.url_oauth(
    server_host="yourdomain.com",
    block=True
    )

gmail_client = google_workspace.gmail.GmailClient(service=service)
print(gmail_client.email_address)
```

## Retrieve messages

This snippet will retrieve all messages from the inbox, print them to the console,
mark them as read, and reply with a message saying "Hi!".

``` python
import google_workspace

gmail_client = google_workspace.gmail.GmailClient()

for message in gmail_client.get_messages("inbox"):
    print(message)
    message.mark_read()
    message.reply("Hi!")
```

## Send html email with attachments

This snippet will send a html email with attachments and then delete it from
your sent messages.

```python
import google_workspace

gmail_client = google_workspace.gmail.GmailClient()
sent_message = gmail_client.send_message(
    to="test@test.com",
    subject="This is fun!",
    html="<b>HTML here</b>",
    attachments=["image.png", "doc.pdf"]
    )
gmail_client.delete_message(sent_message.get("id"))
```

## Forward incoming messages

This snippet will forward all incoming messages which have "python" in thier subject.

```python
import google_workspace

gmail_client = google_workspace.gmail.GmailClient()

def message_filter(history):
    return "python" in history.message.subject

@gmail_client.on_message(labels="inbox", filters=[message_filter])
def handle_message(history):
    history.message.forward(to="test@test.com")
```


# Feedback and contributing

This library is very focused on being easy and fun to use, so if you find something that you think can be improved
please open an issue or even better, a PR, thank you!
