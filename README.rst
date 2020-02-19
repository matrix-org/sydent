Installation
============

Dependencies can be installed using setup.py in the same way as synapse: see synapse/README.rst.  For instance::

    sudo apt-get install build-essential python2.7-dev libffi-dev \
                         sqlite3 libssl-dev python-virtualenv libxslt1-dev

    virtualenv -p python2.7 ~/.sydent
    source ~/.sydent/bin/activate
    pip install --upgrade pip
    pip install --upgrade setuptools
    pip install https://github.com/matrix-org/sydent/tarball/master

Having installed dependencies, you can run sydent using::

    python -m sydent.sydent

This will create a configuration file in sydent.conf with some defaults. You'll most likely want to change the server name and specify a mail relay.

Defaults for SMS originators will not be added to the generated config file, these should be added in the form::

    originators.<country code> = <long|short|alpha>:<originator>

Where country code is the numeric country code, or 'default' to specify the originator used for countries not listed. For example, to use a selection of long codes for the US/Canda, a short code for the UK and an alphanumertic originator for everywhere else::

    originators.1 = long:12125552368,long:12125552369
    originators.44 = short:12345
    originators.default = alpha:Matrix

Testing
=======

Sydent uses matrix-is-tester (https://github.com/matrix-org/matrix-is-tester/) to provide black-box testing of its API.
This can be run as follows:

    pip install git+https://github.com/matrix-org/matrix-is-tester.git
    trial matrix_is_tester

The SYDENT_PYTHON enviroment variable can be set to launch sydent with a specific python binary:

    SYDENT_PYTHON=/path/to/python trial matrix_is_tester

The matrix_is_test directory contains sydent's launcher for matrix_is_tester: this needs to be on the
python path.

Requests
========

The requests that synapse servers and clients submit to the identity server are, briefly, as follows:

Request the validation of your email address::

    curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/validate/email/requestToken' -H "Content-Type: application/json" -d '{"email": "matthew@arasphere.net", "client_secret": "abcd", "send_attempt": 1}'
    {"success": true, "sid": "1"}

(Receive 943258 by mail)

Use this code to validate your email address::

    curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/validate/email/submitToken' -H "Content-Type: application/json" -d '{"token": "943258", "sid": "1", "client_secret": "abcd"}'
    {"success": true}

Use the validated email address to bind it to a matrix ID::

    curl -XPOST 'http://localhost:8090/_matrix/identity/api/v1/3pid/bind' -H "Content-Type: application/json" -d '{"sid": "1", "client_secret": "abcd", "mxid": "%40matthew%3amatrix.org"}'

Lookup::

    curl 'http://localhost:8090/_matrix/identity/api/v1/lookup?medium=email&address=henry%40matrix.org'

Fetch pubkey key for a server::

    curl http://localhost:8090/_matrix/identity/api/v1/pubkey/ed25519:0

Internal bind api
-----------------

It is possible to enable an internal API which allows identifiers to be bound
to matrix IDs without any validation. This is open to abuse, so is disabled by
default, and when it is enabled, is available only on a separate socket which
is bound to 'localhost' by default.

To enable it, configure the port in the config file. For example::

    [http]
    internalapi.http.port = 8091

To use it::

    curl -XPOST 'http://localhost:8091/_matrix/identity/internal/bind' -H "Content-Type: application/json" -d '{"address": "matthew@arasphere.net", "medium": "email", "mxid": "@matthew:matrix.org"}'

The response has the same format as ``/_matrix/identity/api/v1/3pid/bind``.


Replication
===========

It is possible to configure a mesh of sydents which replicate identity bindings
between each other. See `<docs/replication.md>`_.
