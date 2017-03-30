Installation
============

Dependencies can be installed using setup.py in the same way as synapse: see synapse/README.rst.

Having installed dependencies, you can run sydent using::

    $ python -m sydent.sydent

This will create a configuration file in sydent.conf with some defaults. You'll most likely want to change the server name and specify a mail relay.

Requests
========

The requests that synapse servers and clients submit to the identity server are, briefly, as follows:

Request the validation of your email address:

curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/validate/email/requestToken' -H "Content-Type: application/json" -d '{"email": "matthew@arasphere.net", "client_secret": "abcd", "send_attempt": 1}'
{"success": true, "sid": "1"}

# receive 943258 by mail

Use this code to validate your email address:

curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/validate/email/submitToken' -H "Content-Type: application/json" -d '{"token": "943258", "sid": "1", "client_secret": "abcd"}'
{"success": true}

Use the validated email address to bind it to a matrix ID:

curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/3pid/bind' -H "Content-Type: application/json" -d '{"sid": "1", "client_secret": "abcd", "mxid": "%40matthew%3amatrix.org"}'

# lookup:

curl 'http://localhost:8090/_matrix/identity/api/v1/lookup?medium=email&address=henry%40matrix.org'

# fetch pubkey key for a server

curl http://localhost:8090/_matrix/identity/api/v1/pubkey/ed25519

