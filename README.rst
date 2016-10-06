Sydent Should not be Used
=========================
Sydent could be repalced soon and should not be used.

See Issue `#22 
<https://github.com/matrix-org/sydent/issues/22>`_ and `#21 <https://github.com/matrix-org/sydent/issues/21>`_:

    Typically you really don't need to run a sydent; all it does is map email addresses to matrix ids so people can discover you publically on matrix by your email addres. This only works if you are part of the public cluster of sydents, which a personal instance won't be. We are looking at how to fix this (by replacing sydent) to be decentralised but haven't got there yet.

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

curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/validate/email/requestToken' -d'email=matthew@arasphere.net&clientSecret=abcd&sendAttempt=1'
{"success": true, "tokenId": 1}

# receive 943258 by mail

Use this code to validate your email address:

curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/validate/email/submitToken' -d'token=943258&sid=1&clientSecret=abcd'
{"success": true}

Use the validated email address to bind it to a matrix ID:

curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/3pid/bind' -d'sid=1&clientSecret=abcd&mxid=%40matthew%3amatrix.org'

# lookup:

curl 'http://localhost:8090/_matrix/identity/api/v1/lookup?medium=email&address=henry%40matrix.org'

# fetch pubkey key for a server

curl http://localhost:8090/_matrix/identity/api/v1/pubkey/ed25519

