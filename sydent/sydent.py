# Copyright 2014 OpenMarket Ltd
# Copyright 2018 New Vector Ltd
# Copyright 2019 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import gc
import logging
import logging.handlers
import os
import sqlite3
from typing import Optional

import attr
import prometheus_client
import twisted.internet.reactor
from matrix_common.versionstring import get_distribution_version_string
from signedjson.types import SigningKey
from twisted.internet import address, task
from twisted.internet.interfaces import (
    IReactorCore,
    IReactorPluggableNameResolver,
    IReactorSSL,
    IReactorTCP,
    IReactorTime,
)
from twisted.python import log
from twisted.web.http import Request
from zope.interface import Interface

from sydent.config import SydentConfig
from sydent.db.hashing_metadata import HashingMetadataStore
from sydent.db.sqlitedb import SqliteDatabase
from sydent.db.valsession import ThreePidValSessionStore
from sydent.hs_federation.verifier import Verifier
from sydent.http.httpcommon import SslComponents
from sydent.http.httpsclient import ReplicationHttpsClient
from sydent.http.httpserver import (
    ClientApiHttpServer,
    InternalApiHttpServer,
    ReplicationHttpsServer,
)
from sydent.replication.pusher import Pusher
from sydent.threepid.bind import ThreepidBinder
from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.ratelimiter import Ratelimiter
from sydent.util.tokenutils import generateAlphanumericTokenOfLength
from sydent.validators.emailvalidator import EmailValidator
from sydent.validators.msisdnvalidator import MsisdnValidator

logger = logging.getLogger(__name__)


class SydentReactor(
    IReactorCore,
    IReactorTCP,
    IReactorSSL,
    IReactorTime,
    IReactorPluggableNameResolver,
    Interface,
):
    pass


class Sydent:
    def __init__(
        self,
        sydent_config: SydentConfig,
        reactor: SydentReactor = twisted.internet.reactor,  # type: ignore[assignment]
        use_tls_for_federation: bool = True,
    ):
        self.config = sydent_config

        self.reactor = reactor
        self.use_tls_for_federation = use_tls_for_federation

        logger.info("Starting Sydent server")

        self.db: sqlite3.Connection = SqliteDatabase(self).db

        if self.config.general.sentry_enabled:
            import sentry_sdk

            sentry_sdk.init(
                dsn=self.config.general.sentry_dsn,
                release=get_distribution_version_string("matrix-sydent"),
            )
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("sydent_server_name", self.config.general.server_name)

            # workaround for https://github.com/getsentry/sentry-python/issues/803: we
            # disable automatic GC and run it periodically instead.
            gc.disable()
            cb = task.LoopingCall(run_gc)
            cb.clock = self.reactor
            cb.start(1.0)

        # See if a pepper already exists in the database
        # Note: This MUST be run before we start serving requests, otherwise lookups for
        # 3PID hashes may come in before we've completed generating them
        hashing_metadata_store = HashingMetadataStore(self)
        lookup_pepper = hashing_metadata_store.get_lookup_pepper()
        if not lookup_pepper:
            # No pepper defined in the database, generate one
            lookup_pepper = generateAlphanumericTokenOfLength(5)

            # Store it in the database and rehash 3PIDs
            hashing_metadata_store.store_lookup_pepper(
                sha256_and_url_safe_base64, lookup_pepper
            )

        self.validators: Validators = Validators(
            EmailValidator(self), MsisdnValidator(self)
        )

        self.keyring: Keyring = Keyring(self.config.crypto.signing_key)
        self.keyring.ed25519.alg = "ed25519"

        self.sig_verifier: Verifier = Verifier(self)

        self.threepidBinder: ThreepidBinder = ThreepidBinder(self)

        self.sslComponents: SslComponents = SslComponents(self)

        self.clientApiHttpServer = ClientApiHttpServer(self, lookup_pepper)
        self.replicationHttpsServer = ReplicationHttpsServer(self)
        self.replicationHttpsClient: ReplicationHttpsClient = ReplicationHttpsClient(
            self
        )

        self.pusher: Pusher = Pusher(self)

        self.email_sender_ratelimiter: Ratelimiter[str] = Ratelimiter(
            self.reactor,
            burst=self.config.email.email_sender_ratelimit_burst,
            rate_hz=self.config.email.email_sender_ratelimit_rate_hz,
        )

    def run(self) -> None:
        self.clientApiHttpServer.setup()
        self.replicationHttpsServer.setup()
        self.pusher.setup()
        self.maybe_start_prometheus_server()

        # A dedicated validation session store just to clean up old sessions every N minutes
        self.cleanupValSession = ThreePidValSessionStore(self)
        cb = task.LoopingCall(self.cleanupValSession.deleteOldSessions)
        cb.clock = self.reactor
        cb.start(10 * 60.0)

        if self.config.http.internal_port is not None:
            internalport = self.config.http.internal_port
            interface = self.config.http.internal_bind_address

            self.internalApiHttpServer = InternalApiHttpServer(self)
            self.internalApiHttpServer.setup(interface, internalport)

        if self.config.general.pidfile:
            with open(self.config.general.pidfile, "w") as pidfile:
                pidfile.write(str(os.getpid()) + "\n")

        self.reactor.run()

    def maybe_start_prometheus_server(self) -> None:
        if self.config.general.prometheus_enabled:
            assert self.config.general.prometheus_addr is not None
            assert self.config.general.prometheus_port is not None
            prometheus_client.start_http_server(
                port=self.config.general.prometheus_port,
                addr=self.config.general.prometheus_addr,
            )

    def ip_from_request(self, request: Request) -> Optional[str]:
        if self.config.http.obey_x_forwarded_for and request.requestHeaders.hasHeader(
            "X-Forwarded-For"
        ):
            # Type safety: hasHeaders returning True means that getRawHeaders
            # returns a nonempty list
            return request.requestHeaders.getRawHeaders("X-Forwarded-For")[0]  # type: ignore[index]
        client = request.getClientAddress()
        if isinstance(client, (address.IPv4Address, address.IPv6Address)):
            return client.host
        else:
            return None

    def brand_from_request(self, request: Request) -> Optional[str]:
        """
        If the brand GET parameter is passed, returns that as a string, otherwise returns None.

        :param request: The incoming request.

        :return: The brand to use or None if no hint is found.
        """
        if b"brand" in request.args:
            return request.args[b"brand"][0].decode("utf-8")
        return None

    def get_branded_template(
        self,
        brand: Optional[str],
        template_name: str,
    ) -> str:
        """
        Calculate a branded template filename to use.

        Attempt to use the hinted brand from the request if the brand
        is valid. Otherwise, fallback to the default brand.

        :param brand: The hint of which brand to use.
        :type brand: str or None
        :param template_name: The name of the template file to load.
        :type template_name: str

        :return: The template filename to use.
        :rtype: str
        """

        # If a brand hint is provided, attempt to use it if it is valid.
        if brand:
            if brand not in self.config.general.valid_brands:
                brand = None

        # If the brand hint is not valid, or not provided, fallback to the default brand.
        if not brand:
            brand = self.config.general.default_brand

        root_template_path = self.config.general.templates_path

        # Grab jinja template if it exists
        if os.path.exists(
            os.path.join(root_template_path, brand, template_name + ".j2")
        ):
            return os.path.join(brand, template_name + ".j2")
        else:
            return os.path.join(root_template_path, brand, template_name)


@attr.s(frozen=True, slots=True, auto_attribs=True)
class Validators:
    email: EmailValidator
    msisdn: MsisdnValidator


@attr.s(frozen=True, slots=True, auto_attribs=True)
class Keyring:
    ed25519: SigningKey


def get_config_file_path() -> str:
    return os.environ.get("SYDENT_CONF", "sydent.conf")


def run_gc() -> None:
    threshold = gc.get_threshold()
    counts = gc.get_count()
    for i in reversed(range(len(threshold))):
        if threshold[i] < counts[i]:
            gc.collect(i)


def setup_logging(config: SydentConfig) -> None:
    """
    Setup logging using the options specified in the config

    :param config: the configuration to use
    """
    log_path = config.general.log_path
    log_level = config.general.log_level

    log_format = "%(asctime)s - %(name)s - %(lineno)d - %(levelname)s" " - %(message)s"
    formatter = logging.Formatter(log_format)

    handler: logging.Handler
    if log_path != "":
        handler = logging.handlers.TimedRotatingFileHandler(
            log_path, when="midnight", backupCount=365
        )
        handler.setFormatter(formatter)

    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    rootLogger = logging.getLogger("")
    rootLogger.setLevel(log_level)
    rootLogger.addHandler(handler)

    observer = log.PythonLoggingObserver()
    observer.start()


def main() -> None:
    sydent_config = SydentConfig()
    sydent_config.parse_config_file(get_config_file_path())
    setup_logging(sydent_config)

    syd = Sydent(sydent_config)
    syd.run()


if __name__ == "__main__":
    main()
