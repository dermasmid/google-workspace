
Welcome to Google Workspace's documentation!
================================================
**Google Workspace** is a high level unofficial API wrapper for some of the productivity related Google API's.
This library has for now only implemented a client for Gmail, I hope to add Drive and much more in the near future.

Installation
*************
.. code-block:: text

   $ pip3 install google_workspace


Quick start
============
After you have got your credentials from the google cloud console and put them inside your working directory, You can
run the following:

.. code-block:: python

   import google_workspace

   gmail_client = google_workspace.gmail.GmailClient()

   for message in gmail_client.get_messages('inbox'):
      print(message)


.. toctree::
   :caption: Service Reference

   api/service/service

.. toctree::
   :caption: Gmail Reference

   api/gmail/gmail-client
   api/gmail/message/index
   api/gmail/thread
   api/gmail/label
   api/gmail/handler
   api/gmail/histories/index
