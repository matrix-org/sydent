Installation
============

Installing the system dependencies
----------------------------------

To install Sydent's dependencies on a Debian-based system, run::

    sudo apt-get install build-essential python3-dev libffi-dev \
                         sqlite3 libssl-dev python-virtualenv libxslt1-dev

From here, you can either install Sydent by using a PyPI release, or by recreating Sydent's locked runtime environment.


Installing the latest Sydent release from PyPI
----------------------------------------------

To create the virtual environment in which Sydent will run::

    virtualenv -p python3 ~/.sydent
    source ~/.sydent/bin/activate
    pip install --upgrade pip
    pip install --upgrade setuptools

Sydent and its dependencies can be installed using ``pip`` by running::

    pip install matrix-sydent
    
With the virtualenv activated, you can run Sydent using::

    python -m sydent.sydent

Installing from source
~~~~~~~~~~~~~~~~~~~~~~

Alternatively, Sydent can be installed using ``poetry`` from a local git checkout.
First install `poetry`. See `poetry's documentation <https://python-poetry.org/docs/#installation>`_ for details; we recommend installing via `pipx`. Once that's done::

    git clone https://github.com/matrix-org/sydent.git
    cd sydent
    poetry install --no-dev
    # For development, pull in extra tools with
    # poetry install

To start Sydent::

    poetry run sydent

Running Sydent
==============

When Sydent is first run, it will create a configuration file in ``sydent.conf`` with some defaults. 
If a setting is defined in both the ``[DEFAULT]`` section and another section in the configuration file,
then the value in the other section is used.

You'll most likely want to change the server name (``server.name``) and specify an email server
(look for the settings starting with ``email.``).

By default, Sydent will listen on ``0.0.0.0:8090``. This can be changed by changing the values for
the configuration settings ``clientapi.http.bind_address`` and ``clientapi.http.port``.

Sydent uses SQLite as its database backend. By default, it will create the database as ``sydent.db``
in its working directory. The name can be overridden by modifying the ``db.file`` configuration option.
Sydent is known to be working with SQLite version 3.16.2 and later.

Listening for HTTPS connections
-------------------------------

Most homeservers and clients will expect identity servers to be reachable using HTTPS.

Sydent does not currently support listening for HTTPS connection by itself. Instead, it
is recommended to use a reverse proxy to proxy requests from homeservers and clients to
Sydent. It is then possible to have this reverse proxy serve Sydent's API over HTTPS.

When using a reverse proxy, it is recommended to limit the requests proxied to Sydent to
ones which paths start with ``/_matrix/identity`` for security reasons.

An exception to this is Sydent's internal replication API, see `<docs/replication.md>`_.

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

Persistent data
---------------

By default, all data is stored in ``/data``. To persist this to disk, bind `/data` to a
Docker volume.

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

.. warning:: These variables are only taken into account at first start and are written to the configuration file.

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

Discussion
==========

Matrix room: `#sydent:matrix.org <https://matrix.to/#/#sydent:matrix.org>`_.

