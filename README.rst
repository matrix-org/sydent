Installation
============

Installing the system dependencies
----------------------------------

To install Sydent's dependencies on a Debian-based system, run::

    sudo apt-get install build-essential python3-dev libffi-dev \
                         sqlite3 libssl-dev python-virtualenv libxslt1-dev

Creating the virtualenv
-----------------------

To create the virtual environment in which Sydent will run::

    virtualenv -p python3 ~/.sydent
    source ~/.sydent/bin/activate
    pip install --upgrade pip
    pip install --upgrade setuptools


Installing the latest Sydent release from PyPI
----------------------------------------------

Sydent and its dependencies can be installed using ``pip`` by running::

    pip install matrix-sydent

Installing from source
----------------------

Alternatively, Sydent can be installed using ``pip`` from a local git checkout::

    git clone https://github.com/matrix-org/sydent.git
    cd sydent
    pip install -e .


Running Sydent
==============

With the virtualenv activated, you can run Sydent using::

    python -m sydent.sydent

Before you run Sydent for the first time, you must run the generate-config script.

You should not write anything in the ``[DEFAULT]`` section. If a
setting is defined in both the ``[DEFAULT]`` section and another section in the configuration
file, then the value in the other section is used.

You'll most likely want to change the server name (``server.name``) and specify an email server
(look for the settings starting with ``email.``). 

See `<docs/configuration.md>` for more information on how to configure Sydent.

By default, Sydent will listen on ``[::]:8090``. This can be changed by changing the values for
the configuration settings ``clientapi.http.bind_address`` and ``clientapi.http.port``.

Sydent uses SQLite as its database backend. By default, it will create the database as ``sydent.db``
in its working directory. The name can be overridden by modifying the ``db.file`` configuration option.
Sydent is known to be working with SQLite version 3.16.2 and later.

SMS originators
---------------

Defaults for SMS originators will not be added to the generated config file, these should
be added to the ``[sms]`` section of that config file in the form::

    originators.<country code> = <long|short|alpha>:<originator>

Where country code is the numeric country code, or ``default`` to specify the originator
used for countries not listed. For example, to use a selection of long codes for the
US/Canada, a short code for the UK and an alphanumertic originator for everywhere else::

    originators.1 = long:12125552368,long:12125552369
    originators.44 = short:12345
    originators.default = alpha:Matrix

Docker
======

A Dockerfile is provided for sydent. To use it, run ``docker build -t sydent .`` in a sydent checkout.
To run it, use ``docker run --env=SYDENT_SERVER_NAME=my-sydent-server -p 8090:8090 sydent``.

Caution: All data will be lost when the container is terminated!

Persistent data
---------------

By default, all data is stored in ``/data``.
The best method is to put the data in a Docker volume.

.. code-block:: shell

   docker volume create sydent-data
   docker run ... --mount type=volume,source=sydent-data,destination=/data sydent

But you can also bind a local directory to the container.
However, you then have to pay attention to the file permissions.

.. code-block:: shell

   mkdir /path/to/sydent-data
   chown 993:993 /path/to/sydent-data
   docker run ... --mount type=bind,source=/path/to/sydent-data,destination=/data sydent

Environment variables
---------------------

.. warning:: These variables are taken into account when generate-config is run and
are written to the config file. They are only used by Sydent if they are not
overridden by the config file.

+--------------------+-----------------+-----------------------+
| Variable Name      | Sydent default  | Dockerfile default    |
+====================+=================+=======================+
| SYDENT_SERVER_NAME | *empty*         | *empty*               |
+--------------------+-----------------+-----------------------+
| SYDENT_CONF        | ``sydent.conf`` | ``/data/sydent.conf`` |
+--------------------+-----------------+-----------------------+
| SYDENT_PID_FILE    | ``sydent.pid``  | ``/data/sydent.pid``  |
+--------------------+-----------------+-----------------------+
| SYDENT_DB_PATH     | ``sydent.db``   | ``/data/sydent.db``   |
+--------------------+-----------------+-----------------------+

Testing
=======

Sydent uses matrix-is-tester (https://github.com/matrix-org/matrix-is-tester/) to provide
black-box testing of compliance with the `Matrix Identity Service API <https://matrix.org/docs/spec/identity_service/latest>`_.
This can be run as follows::

    pip install git+https://github.com/matrix-org/matrix-is-tester.git
    trial matrix_is_tester

The ``SYDENT_PYTHON`` enviroment variable can be set to launch Sydent with a specific python binary::

    SYDENT_PYTHON=/path/to/python trial matrix_is_tester

The ``matrix_is_test`` directory contains Sydent's launcher for ``matrix_is_tester``: this means
that Sydent's directory needs to be on the Python path (e.g. ``PYTHONPATH=$PYTHONPATH:/path/to/sydent``).

Sydent also has some unit tests to ensure some of its features that aren't part of the Matrix
specification (e.g. replication) keep on working. To run these tests, run the following with Sydent's
virtualenv activated from the root of the Sydent repository::

     trial tests


Internal bind and unbind API
============================

It is possible to enable an internal API which allows for binding and unbinding
between identifiers and matrix IDs without any validation.
This is open to abuse, so is disabled by
default, and when it is enabled, is available only on a separate socket which
is bound to ``localhost`` by default.

To enable it, configure the port in the config file. For example::

    [http]
    internalapi.http.port = 8091

To change the address to which that API is bound, set the ``internalapi.http.bind_address`` configuration
setting in the ``[http]`` section, for example::

    [http]
    internalapi.http.port = 8091
    internalapi.http.bind_address = 192.168.0.18

As already mentioned above, this is open to abuse, so make sure this address is not publicly accessible.

To use bind::

    curl -XPOST 'http://localhost:8091/_matrix/identity/internal/bind' -H "Content-Type: application/json" -d '{"address": "matthew@arasphere.net", "medium": "email", "mxid": "@matthew:matrix.org"}'

The response has the same format as
`/_matrix/identity/api/v1/3pid/bind <https://matrix.org/docs/spec/identity_service/r0.3.0#deprecated-post-matrix-identity-api-v1-3pid-bind>`_.

To use unbind::

    curl -XPOST 'http://localhost:8091/_matrix/identity/internal/unbind' -H "Content-Type: application/json" -d '{"address": "matthew@arasphere.net", "medium": "email", "mxid": "@matthew:matrix.org"}'

The response has the same format as
`/_matrix/identity/api/v1/3pid/unbind <https://matrix.org/docs/spec/identity_service/r0.3.0#deprecated-post-matrix-identity-api-v1-3pid-unbind>`_.


Replication
===========

It is possible to configure a mesh of Sydent instances which replicate identity bindings
between each other. See `<docs/replication.md>`_.

Email obfuscation
=================
When a user is invited to a room via their email address, that invite is
displayed in the room list using an obfuscated version of the user's email
address.

The amount of obfuscation is controlled by the 
`email.third_party_invite_username_obfuscate_characters` and
`email.third_party_invite_domain_obfuscate_characters` config options. The first
sets the number of characters from the beginning to reveal of the email's username
portion (left of the '@' sign). The second, the number of characters from the
beginning to reveal of the email's domain portion (right of the '@' sign).

The '@' sign is always included. 

If the string is longer than a configured limit below, it is truncated to
that limit with '...' added. For shorter strings, the following rules are
used:

* If the string has more than 5 characters, it is truncated to 3 characters
  + '...' (e.g. 'username' would become 'use...')

* If the string has between 2 and 5 characters inclusive, it is truncated
  to 1 character + '...' (e.g. 'user' would become 'u...')

* If the string is 1 character long, it is converted to just '...'
  (e.g. 'a' would become '...')

This ensures that a full email address is never shown, even if it is extremely
short.
