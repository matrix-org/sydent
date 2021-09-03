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

# azren TODO
import configparser
import copy
import gc
import logging
import logging.handlers
import os
from sydent.config.server import SydentConfig
from typing import Set

import twisted.internet.reactor
from jinja2 import Environment, FileSystemLoader
from twisted.internet import address, task
from twisted.python import log

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
from sydent.http.servlets.accountservlet import AccountServlet
from sydent.http.servlets.blindlysignstuffservlet import BlindlySignStuffServlet
from sydent.http.servlets.bulklookupservlet import BulkLookupServlet
from sydent.http.servlets.emailservlet import (
    EmailRequestCodeServlet,
    EmailValidateCodeServlet,
)
from sydent.http.servlets.getvalidated3pidservlet import GetValidated3pidServlet
from sydent.http.servlets.hashdetailsservlet import HashDetailsServlet
from sydent.http.servlets.logoutservlet import LogoutServlet
from sydent.http.servlets.lookupservlet import LookupServlet
from sydent.http.servlets.lookupv2servlet import LookupV2Servlet
from sydent.http.servlets.msisdnservlet import (
    MsisdnRequestCodeServlet,
    MsisdnValidateCodeServlet,
)
from sydent.http.servlets.pubkeyservlets import (
    Ed25519Servlet,
    EphemeralPubkeyIsValidServlet,
    PubkeyIsValidServlet,
)
from sydent.http.servlets.registerservlet import RegisterServlet
from sydent.http.servlets.replication import ReplicationPushServlet
from sydent.http.servlets.store_invite_servlet import StoreInviteServlet
from sydent.http.servlets.termsservlet import TermsServlet
from sydent.http.servlets.threepidbindservlet import ThreePidBindServlet
from sydent.http.servlets.threepidunbindservlet import ThreePidUnbindServlet
from sydent.http.servlets.v1_servlet import V1Servlet
from sydent.http.servlets.v2_servlet import V2Servlet
from sydent.replication.pusher import Pusher
from sydent.sign.ed25519 import SydentEd25519
from sydent.threepid.bind import ThreepidBinder
from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.ip_range import DEFAULT_IP_RANGE_BLACKLIST, generate_ip_set
from sydent.util.tokenutils import generateAlphanumericTokenOfLength
from sydent.validators.emailvalidator import EmailValidator
from sydent.validators.msisdnvalidator import MsisdnValidator

logger = logging.getLogger(__name__)


class Sydent:
    def __init__(
        self,
        cfg: SydentConfig,
        reactor=twisted.internet.reactor,
        use_tls_for_federation=True,
    ):
        logger.info("Starting Sydent Server")

        self.config = cfg
        self.reactor = reactor
        self.use_tls_for_federation = use_tls_for_federation

        self.db = SqliteDatabase(self).db

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

        self.validators = Validators()
        self.validators.email = EmailValidator(self)
        self.validators.msisdn = MsisdnValidator(self)

        self.keyring = Keyring()
        self.keyring.ed25519 = self.config.crypto.signing_key
        self.keyring.ed25519.alg = "ed25519"

        self.sig_verifier = Verifier(self)

        self.servlets = Servlets()
        self.servlets.v1 = V1Servlet(self)
        self.servlets.v2 = V2Servlet(self)
        self.servlets.emailRequestCode = EmailRequestCodeServlet(self)
        self.servlets.emailRequestCodeV2 = EmailRequestCodeServlet(
            self, require_auth=True
        )
        self.servlets.emailValidate = EmailValidateCodeServlet(self)
        self.servlets.emailValidateV2 = EmailValidateCodeServlet(
            self, require_auth=True
        )
        self.servlets.msisdnRequestCode = MsisdnRequestCodeServlet(self)
        self.servlets.msisdnRequestCodeV2 = MsisdnRequestCodeServlet(
            self, require_auth=True
        )
        self.servlets.msisdnValidate = MsisdnValidateCodeServlet(self)
        self.servlets.msisdnValidateV2 = MsisdnValidateCodeServlet(
            self, require_auth=True
        )
        self.servlets.lookup = LookupServlet(self)
        self.servlets.bulk_lookup = BulkLookupServlet(self)
        self.servlets.hash_details = HashDetailsServlet(self, lookup_pepper)
        self.servlets.lookup_v2 = LookupV2Servlet(self, lookup_pepper)
        self.servlets.pubkey_ed25519 = Ed25519Servlet(self)
        self.servlets.pubkeyIsValid = PubkeyIsValidServlet(self)
        self.servlets.ephemeralPubkeyIsValid = EphemeralPubkeyIsValidServlet(self)
        self.servlets.threepidBind = ThreePidBindServlet(self)
        self.servlets.threepidBindV2 = ThreePidBindServlet(self, require_auth=True)
        self.servlets.threepidUnbind = ThreePidUnbindServlet(self)
        self.servlets.replicationPush = ReplicationPushServlet(self)
        self.servlets.getValidated3pid = GetValidated3pidServlet(self)
        self.servlets.getValidated3pidV2 = GetValidated3pidServlet(
            self, require_auth=True
        )
        self.servlets.storeInviteServlet = StoreInviteServlet(self)
        self.servlets.storeInviteServletV2 = StoreInviteServlet(self, require_auth=True)
        self.servlets.blindlySignStuffServlet = BlindlySignStuffServlet(self)
        self.servlets.blindlySignStuffServletV2 = BlindlySignStuffServlet(
            self, require_auth=True
        )
        self.servlets.termsServlet = TermsServlet(self)
        self.servlets.accountServlet = AccountServlet(self)
        self.servlets.registerServlet = RegisterServlet(self)
        self.servlets.logoutServlet = LogoutServlet(self)

        self.threepidBinder = ThreepidBinder(self)

        self.sslComponents = SslComponents(self)

        self.clientApiHttpServer = ClientApiHttpServer(self)
        self.replicationHttpsServer = ReplicationHttpsServer(self)
        self.replicationHttpsClient = ReplicationHttpsClient(self)

        self.pusher = Pusher(self)

        # A dedicated validation session store just to clean up old sessions every N minutes
        self.cleanupValSession = ThreePidValSessionStore(self)
        cb = task.LoopingCall(self.cleanupValSession.deleteOldSessions)
        cb.clock = self.reactor
        cb.start(10 * 60.0)

        # workaround for https://github.com/getsentry/sentry-python/issues/803: we
        # disable automatic GC and run it periodically instead.
        gc.disable()
        cb = task.LoopingCall(run_gc)
        cb.clock = self.reactor
        cb.start(1.0)

    def run(self):
        self.clientApiHttpServer.setup()
        self.replicationHttpsServer.setup()
        self.pusher.setup()

        if self.config.http.internal_port:
            self.internalApiHttpServer = InternalApiHttpServer(self)
            self.internalApiHttpServer.setup(
                self.config.http.internal_bind_address,
                self.config.http.internal_port,
            )

        if self.config.general.pidfile:
            with open(self.config.general.pidfile, "w") as pidfile:
                pidfile.write(str(os.getpid()) + "\n")

        self.reactor.run()

    def ip_from_request(self, request):
        # azren TODO
        if self.config.http.obey_x_forwarded_for and request.requestHeaders.hasHeader(
            "X-Forwarded-For"
        ):
            return request.requestHeaders.getRawHeaders("X-Forwarded-For")[0]

        client = request.getClientAddress()
        if isinstance(client, (address.IPv4Address, address.IPv6Address)):
            return client.host
        else:
            return None

    def brand_from_request(self, request):
        """
        If the brand GET parameter is passed, returns that as a string, otherwise returns None.

        :param request: The incoming request.
        :type request: twisted.web.http.Request

        :return: The brand to use or None if no hint is found.
        :rtype: str or None
        """
        if b"brand" in request.args:
            return request.args[b"brand"][0].decode("utf-8")
        return None

    # azren TODO: change all usages to check deprecated config template before calling
    def get_branded_template(self, brand, template_name):
        """
        Calculate a (maybe) branded template filename to use.

        If the deprecated email.template setting is defined, always use it.
        Otherwise, attempt to use the hinted brand from the request if the brand
        is valid. Otherwise, fallback to the default brand.

        :param brand: The hint of which brand to use.
        :type brand: str or None
        :param template_name: The name of the template file to load.
        :type template_name: str
        :param deprecated_template_name: The deprecated setting to use, if provided.
        :type deprecated_template_name: Tuple[str]

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


class Validators:
    pass


class Servlets:
    pass


class Keyring:
    pass


# azren TODO
def get_legacy_config_file_path():
    return os.environ.get("SYDENT_CONF", "sydent.conf")


def run_gc():
    threshold = gc.get_threshold()
    counts = gc.get_count()
    for i in reversed(range(len(threshold))):
        if threshold[i] < counts[i]:
            gc.collect(i)


if __name__ == "__main__":
    # azren TODO
    config = SydentConfig()
    config.parse_legacy_config_file(get_legacy_config_file_path())
    syd = Sydent(config)
    syd.run()
