# Note

pytogle is in it's very early stages and for now only has implemented a wrapper for Gmail.

## Getting Started

``` bash
pip3 install pytogle
```

Then you need to get a client secret file from [the google console](https://console.developers.google.com/) and you need to enable the api you want to use, just google it.

After you saved the json file to your workdir - you are all set!

To use the Gmail API simply create a python file and enter this:

``` python
import pytogle

mailbox = pytogle.gmail.Gmail()

for msg in mailbox.get_messages('inbox'):
    print(msg)
```
