# -*- coding: utf-8 -*-

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
from __future__ import absolute_import

import gc

from six.moves import configparser
import copy
import logging
import logging.handlers
import os

import twisted.internet.reactor
from twisted.internet import task
from twisted.python import log

from sydent.db.sqlitedb import SqliteDatabase

from sydent.http.httpcommon import SslComponents
from sydent.http.httpserver import (
    ClientApiHttpServer, ReplicationHttpsServer,
    InternalApiHttpServer,
)
from sydent.http.httpsclient import ReplicationHttpsClient
from sydent.http.servlets.blindlysignstuffservlet import BlindlySignStuffServlet
from sydent.http.servlets.pubkeyservlets import EphemeralPubkeyIsValidServlet, PubkeyIsValidServlet
from sydent.http.servlets.termsservlet import TermsServlet
from sydent.validators.emailvalidator import EmailValidator
from sydent.validators.msisdnvalidator import MsisdnValidator
from sydent.hs_federation.verifier import Verifier

from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.tokenutils import generateAlphanumericTokenOfLength

from sydent.sign.ed25519 import SydentEd25519

from sydent.http.servlets.emailservlet import EmailRequestCodeServlet, EmailValidateCodeServlet
from sydent.http.servlets.msisdnservlet import MsisdnRequestCodeServlet, MsisdnValidateCodeServlet
from sydent.http.servlets.lookupservlet import LookupServlet
from sydent.http.servlets.bulklookupservlet import BulkLookupServlet
from sydent.http.servlets.lookupv2servlet import LookupV2Servlet
from sydent.http.servlets.hashdetailsservlet import HashDetailsServlet
from sydent.http.servlets.pubkeyservlets import Ed25519Servlet
from sydent.http.servlets.threepidbindservlet import ThreePidBindServlet
from sydent.http.servlets.threepidunbindservlet import ThreePidUnbindServlet
from sydent.http.servlets.replication import ReplicationPushServlet
from sydent.http.servlets.getvalidated3pidservlet import GetValidated3pidServlet
from sydent.http.servlets.store_invite_servlet import StoreInviteServlet
from sydent.http.servlets.v1_servlet import V1Servlet
from sydent.http.servlets.accountservlet import AccountServlet
from sydent.http.servlets.registerservlet import RegisterServlet
from sydent.http.servlets.logoutservlet import LogoutServlet
from sydent.http.servlets.v2_servlet import V2Servlet

from sydent.db.valsession import ThreePidValSessionStore
from sydent.db.hashing_metadata import HashingMetadataStore

from sydent.threepid.bind import ThreepidBinder

from sydent.replication.pusher import Pusher

logger = logging.getLogger(__name__)

CONFIG_DEFAULTS = {
    'general': {
        'server.name': os.environ.get('SYDENT_SERVER_NAME', ''),
        'log.path': '',
        'log.level': 'INFO',
        'pidfile.path': os.environ.get('SYDENT_PID_FILE', 'sydent.pid'),
        'terms.path': '',
        'address_lookup_limit': '10000',  # Maximum amount of addresses in a single /lookup request

        # The root path to use for load templates. This should contain branded
        # directories. Each directory should contain the following templates:
        #
        # * invite_template.eml
        # * verification_template.eml
        # * verify_response_template.html
        'templates.path': 'res',
        # The brand directory to use if no brand hint (or an invalid brand hint)
        # is provided by the request.
        'brand.default': 'matrix-org',

        # The following can be added to your local config file to enable prometheus
        # support.
        # 'prometheus_port': '8080',  # The port to serve metrics on
        # 'prometheus_addr': '',  # The address to bind to. Empty string means bind to all.

        # The following can be added to your local config file to enable sentry support.
        # 'sentry_dsn': 'https://...'  # The DSN has configured in the sentry instance project.

        # Whether clients and homeservers can register an association using v1 endpoints.
        'enable_v1_associations': 'true',
        'delete_tokens_on_bind': 'true',
    },
    'db': {
        'db.file': os.environ.get('SYDENT_DB_PATH', 'sydent.db'),
    },
    'http': {
        'clientapi.http.bind_address': '::',
        'clientapi.http.port': '8090',
        'internalapi.http.bind_address': '::1',
        'internalapi.http.port': '',
        'replication.https.certfile': '',
        'replication.https.cacert': '', # This should only be used for testing
        'replication.https.bind_address': '::',
        'replication.https.port': '4434',
        'obey_x_forwarded_for': 'False',
        'federation.verifycerts': 'True',
        # verify_response_template is deprecated, but still used if defined Define
        # templates.path and brand.default under general instead.
        #
        # 'verify_response_template': 'res/verify_response_page_template',
        'client_http_base': '',
    },
    'email': {
        # email.template and email.invite_template are deprecated, but still used
        # if defined. Define templates.path and brand.default under general instead.
        #
        # 'email.template': 'res/verification_template.eml',
        # 'email.invite_template': 'res/invite_template.eml',
        'email.from': 'Sydent Validation <noreply@{hostname}>',
        'email.subject': 'Your Validation Token',
        'email.invite.subject': '%(sender_display_name)s has invited you to chat',
        'email.smtphost': 'localhost',
        'email.smtpport': '25',
        'email.smtpusername': '',
        'email.smtppassword': '',
        'email.hostname': '',
        'email.tlsmode': '0',
        # The web client location which will be used if it is not provided by
        # the homeserver.
        #
        # This should be the scheme and hostname only, see res/invite_template.eml
        # for the full URL that gets generated.
        'email.default_web_client_location': 'https://app.element.io',
        # When a user is invited to a room via their email address, that invite is
        # displayed in the room list using an obfuscated version of the user's email
        # address. These config options determine how much of the email address to
        # obfuscate. Note that the '@' sign is always included.
        #
        # If the string is longer than a configured limit below, it is truncated to that limit
        # with '...' added. Otherwise:
        #
        # * If the string is longer than 5 characters, it is truncated to 3 characters + '...'
        # * If the string is longer than 1 character, it is truncated to 1 character + '...'
        # * If the string is 1 character long, it is converted to '...'
        #
        # This ensures that a full email address is never shown, even if it is extremely
        # short.
        #
        # The number of characters from the beginning to reveal of the email's username
        # portion (left of the '@' sign)
        'email.third_party_invite_username_obfuscate_characters': '3',
        # The number of characters from the beginning to reveal of the email's domain
        # portion (right of the '@' sign)
        'email.third_party_invite_domain_obfuscate_characters': '3',
    },
    'sms': {
        'bodyTemplate': 'Your code is {token}',
        'username': '',
        'password': '',
    },
    'crypto': {
        'ed25519.signingkey': '',
    },
}


class Sydent:
    def __init__(self, cfg, reactor=twisted.internet.reactor):
        self.reactor = reactor
        self.config_file = get_config_file_path()

        self.cfg = cfg

        logger.info("Starting Sydent server")

        self.pidfile = self.cfg.get('general', "pidfile.path");

        self.db = SqliteDatabase(self).db

        self.server_name = self.cfg.get('general', 'server.name')
        if self.server_name == '':
            self.server_name = os.uname()[1]
            logger.warn(("You had not specified a server name. I have guessed that this server is called '%s' "
                        + "and saved this in the config file. If this is incorrect, you should edit server.name in "
                        + "the config file.") % (self.server_name,))
            self.cfg.set('general', 'server.name', self.server_name)
            self.save_config()

        if self.cfg.has_option("general", "sentry_dsn"):
            # Only import and start sentry SDK if configured.
            import sentry_sdk
            sentry_sdk.init(
                dsn=self.cfg.get("general", "sentry_dsn"),
            )
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("sydent_server_name", self.server_name)

        if self.cfg.has_option("general", "prometheus_port"):
            import prometheus_client
            prometheus_client.start_http_server(
                port=self.cfg.getint("general", "prometheus_port"),
                addr=self.cfg.get("general", "prometheus_addr"),
            )

        if self.cfg.has_option("general", "templates.path"):
            # Get the possible brands by looking at directories under the
            # templates.path directory.
            root_template_path = self.cfg.get("general", "templates.path")
            if os.path.exists(root_template_path):
                self.valid_brands = {
                    p for p in os.listdir(root_template_path) if os.path.isdir(os.path.join(root_template_path, p))
                }
            else:
                # This is a legacy code-path and assumes that verify_response_template,
                # email.template, and email.invite_template are defined.
                self.valid_brands = set()

        self.enable_v1_associations = parse_cfg_bool(
            self.cfg.get("general", "enable_v1_associations")
        )

        self.delete_tokens_on_bind = parse_cfg_bool(
            self.cfg.get("general", "delete_tokens_on_bind")
        )

        self.default_web_client_location = self.cfg.get(
            "email", "email.default_web_client_location"
        )
        self.username_obfuscate_characters = int(self.cfg.get(
            "email", "email.third_party_invite_username_obfuscate_characters"
        ))
        self.domain_obfuscate_characters = int(self.cfg.get(
            "email", "email.third_party_invite_domain_obfuscate_characters"
        ))

        # See if a pepper already exists in the database
        # Note: This MUST be run before we start serving requests, otherwise lookups for
        # 3PID hashes may come in before we've completed generating them
        hashing_metadata_store = HashingMetadataStore(self)
        lookup_pepper = hashing_metadata_store.get_lookup_pepper()
        if not lookup_pepper:
            # No pepper defined in the database, generate one
            lookup_pepper = generateAlphanumericTokenOfLength(5)

            # Store it in the database and rehash 3PIDs
            hashing_metadata_store.store_lookup_pepper(sha256_and_url_safe_base64,
                                                       lookup_pepper)

        self.validators = Validators()
        self.validators.email = EmailValidator(self)
        self.validators.msisdn = MsisdnValidator(self)

        self.keyring = Keyring()
        self.keyring.ed25519 = SydentEd25519(self).signing_key
        self.keyring.ed25519.alg = 'ed25519'

        self.sig_verifier = Verifier(self)

        self.servlets = Servlets()
        self.servlets.v1 = V1Servlet(self)
        self.servlets.v2 = V2Servlet(self)
        self.servlets.emailRequestCode = EmailRequestCodeServlet(self)
        self.servlets.emailRequestCodeV2 = EmailRequestCodeServlet(self, require_auth=True)
        self.servlets.emailValidate = EmailValidateCodeServlet(self)
        self.servlets.emailValidateV2 = EmailValidateCodeServlet(self, require_auth=True)
        self.servlets.msisdnRequestCode = MsisdnRequestCodeServlet(self)
        self.servlets.msisdnRequestCodeV2 = MsisdnRequestCodeServlet(self, require_auth=True)
        self.servlets.msisdnValidate = MsisdnValidateCodeServlet(self)
        self.servlets.msisdnValidateV2 = MsisdnValidateCodeServlet(self, require_auth=True)
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
        self.servlets.getValidated3pidV2 = GetValidated3pidServlet(self, require_auth=True)
        self.servlets.storeInviteServlet = StoreInviteServlet(self)
        self.servlets.storeInviteServletV2 = StoreInviteServlet(self, require_auth=True)
        self.servlets.blindlySignStuffServlet = BlindlySignStuffServlet(self)
        self.servlets.blindlySignStuffServletV2 = BlindlySignStuffServlet(self, require_auth=True)
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

    def save_config(self):
        fp = open(self.config_file, 'w')
        self.cfg.write(fp)
        fp.close()

    def run(self):
        self.clientApiHttpServer.setup()
        self.replicationHttpsServer.setup()
        self.pusher.setup()

        internalport = self.cfg.get('http', 'internalapi.http.port')
        if internalport:
            try:
                interface = self.cfg.get('http', 'internalapi.http.bind_address')
            except configparser.NoOptionError:
                interface = '::1'
            self.internalApiHttpServer = InternalApiHttpServer(self)
            self.internalApiHttpServer.setup(interface, int(internalport))

        if self.pidfile:
            with open(self.pidfile, 'w') as pidfile:
                pidfile.write(str(os.getpid()) + "\n")

        self.reactor.run()

    def ip_from_request(self, request):
        if (self.cfg.get('http', 'obey_x_forwarded_for') and
                request.requestHeaders.hasHeader("X-Forwarded-For")):
            return request.requestHeaders.getRawHeaders("X-Forwarded-For")[0]
        return request.getClientIP()

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

    def get_branded_template(self, brand, template_name, deprecated_template_name):
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

        # If the deprecated setting is defined, return it.
        try:
            return self.cfg.get(*deprecated_template_name)
        except configparser.NoOptionError:
            pass

        # If a brand hint is provided, attempt to use it if it is valid.
        if brand:
            if brand not in self.valid_brands:
                brand = None

        # If the brand hint is not valid, or not provided, fallback to the default brand.
        if not brand:
            brand = self.cfg.get("general", "brand.default")

        root_template_path = self.cfg.get("general", "templates.path")
        return os.path.join(root_template_path, brand, template_name)


class Validators:
    pass


class Servlets:
    pass


class Keyring:
    pass


def parse_config_dict(config_dict):
    """Parse the given config from a dictionary, populating missing items and sections

    Args:
        config_dict (dict): the configuration dictionary to be parsed
    """
    # Build a config dictionary from the defaults merged with the given dictionary
    config = copy.deepcopy(CONFIG_DEFAULTS)
    for section, section_dict in config_dict.items():
        if section not in config:
            config[section] = {}
        for option in section_dict.keys():
            config[section][option] = config_dict[section][option]

    # Build a ConfigParser from the merged dictionary
    cfg = configparser.ConfigParser()
    for section, section_dict in config.items():
        cfg.add_section(section)
        for option, value in section_dict.items():
            cfg.set(section, option, value)

    return cfg


def parse_config_file(config_file):
    """Parse the given config from a filepath, populating missing items and
    sections
    Args:
        config_file (str): the file to be parsed
    """
    # if the config file doesn't exist, prepopulate the config object
    # with the defaults, in the right section.
    #
    # otherwise, we have to put the defaults in the DEFAULT section,
    # to ensure that they don't override anyone's settings which are
    # in their config file in the default section (which is likely,
    # because sydent used to be braindead).
    use_defaults = not os.path.exists(config_file)
    cfg = configparser.ConfigParser()
    for sect, entries in CONFIG_DEFAULTS.items():
        cfg.add_section(sect)
        for k, v in entries.items():
            cfg.set(configparser.DEFAULTSECT if use_defaults else sect, k, v)

    cfg.read(config_file)

    return cfg


def setup_logging(cfg):
    log_format = (
        "%(asctime)s - %(name)s - %(lineno)d - %(levelname)s"
        " - %(message)s"
    )
    formatter = logging.Formatter(log_format)

    logPath = cfg.get('general', "log.path")
    if logPath != '':
        handler = logging.handlers.TimedRotatingFileHandler(
            logPath, when='midnight', backupCount=365
        )
        handler.setFormatter(formatter)

        def sighup(signum, stack):
            logger.info("Closing log file due to SIGHUP")
            handler.doRollover()
            logger.info("Opened new log file due to SIGHUP")
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    rootLogger = logging.getLogger('')
    rootLogger.setLevel(cfg.get('general', 'log.level'))
    rootLogger.addHandler(handler)

    observer = log.PythonLoggingObserver()
    observer.start()


def get_config_file_path():
    return os.environ.get('SYDENT_CONF', "sydent.conf")


def parse_cfg_bool(value):
    return value.lower() == "true"


def run_gc():
    threshold = gc.get_threshold()
    counts = gc.get_count()
    for i in reversed(range(len(threshold))):
        if threshold[i] < counts[i]:
            gc.collect(i)


if __name__ == '__main__':
    cfg = parse_config_file(get_config_file_path())
    setup_logging(cfg)
    syd = Sydent(cfg)
    syd.run()
