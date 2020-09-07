### Note:
pytogle is in it's very early stages and for now only has implemented a wrapper for Gmail.

## Getting Started:

For now theres no pip package for the module so you"ll have to download the files manualy to the folder in which your python packages are installed.

``` bash
git clone https://github.com/dermasmid/pytogle
```

Then you need to get a client secret file from [the google console] (https://console.developers.google.com/) and you need to enable the api you want to use, just google it.

after you saved the json file to your workdir - you are all set!

to use the gmail api simply create a python file and enter this:

``` python
from pytogle import Gmail

mailbox = Gmail()
 
for msg in mailbox.get_messages('inbox'):
    print(msg)
```

