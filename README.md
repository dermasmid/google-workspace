# Note

python-google-workspace is in it's very early stages and for now only has implemented a wrapper for Gmail.

## Getting Started

``` bash
pip3 install -U google-workspace
```

Then you need to get a client secret file from [the google console](https://console.developers.google.com/) and you need to enable the api you want to use, just google it.

After you saved the json file to your workdir - you are all set!

To use the Gmail API simply create a python file and enter this:

``` python
import google_workspace

mailbox = google_workspace.gmail.GmailClient()

for message in mailbox.get_messages('inbox'):
    print(message)
```
