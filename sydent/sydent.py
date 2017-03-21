# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
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

import ConfigParser
import logging
import os

import twisted.internet.reactor
from twisted.python import log

from db.sqlitedb import SqliteDatabase

from http.httpcommon import SslComponents
from http.httpserver import ClientApiHttpServer, ReplicationHttpsServer
from http.httpsclient import ReplicationHttpsClient
from http.servlets.blindlysignstuffservlet import BlindlySignStuffServlet
from http.servlets.pubkeyservlets import EphemeralPubkeyIsValidServlet, PubkeyIsValidServlet
from validators.emailvalidator import EmailValidator
from validators.msisdnvalidator import MsisdnValidator

from sign.ed25519 import SydentEd25519

from http.servlets.emailservlet import EmailRequestCodeServlet, EmailValidateCodeServlet
from http.servlets.msisdnservlet import MsisdnRequestCodeServlet, MsisdnValidateCodeServlet
from http.servlets.lookupservlet import LookupServlet
from http.servlets.bulklookupservlet import BulkLookupServlet
from http.servlets.pubkeyservlets import Ed25519Servlet
from http.servlets.threepidbindservlet import ThreePidBindServlet
from http.servlets.replication import ReplicationPushServlet
from http.servlets.getvalidated3pidservlet import GetValidated3pidServlet
from http.servlets.store_invite_servlet import StoreInviteServlet

from threepid.bind import ThreepidBinder

from replication.pusher import Pusher

logger = logging.getLogger(__name__)


class Sydent:
    CONFIG_SECTIONS = ['general', 'db', 'http', 'email', 'crypto', 'sms']
    CONFIG_DEFAULTS = {
        # general
        'server.name': '',
        'log.path': '',
        'pidfile.path': 'sydent.pid',
        # db
        'db.file': 'sydent.db',
        # http
        'clientapi.http.port': '8090',
        'replication.https.certfile': '',
        'replication.https.cacert': '', # This should only be used for testing
        'replication.https.port': '4434',
        'obey_x_forwarded_for': False,
        # email
        'token.length': '6',
        'email.template': 'res/email.template',
        'email.from': 'Sydent Validation <noreply@{hostname}>',
        'email.subject': 'Your Validation Token',
        'email.invite.subject': '%(sender_display_name)s has invited you to chat',
        'email.smtphost': 'localhost',
        'email.smtpport': '25',
        'email.smtpusername': '',
        'email.smtppassword': '',
        'email.hostname': '',
        'email.tlsmode': '0',
        # sms
        'bodyTemplate': 'Your code is {token}',
        # crypto
        'ed25519.signingkey': '',
    }

    def __init__(self):
        logger.info("Starting Sydent server")
        self.parse_config()

        logPath = self.cfg.get('general', "log.path")
        if logPath != '':
            logging.basicConfig(level=logging.INFO, filename=logPath)
        else:
            logging.basicConfig(level=logging.INFO, filename=logPath)

        self.pidfile = self.cfg.get('general', "pidfile.path");

        observer = log.PythonLoggingObserver()
        observer.start()

        self.db = SqliteDatabase(self).db

        self.server_name = self.cfg.get('general', 'server.name')
        if self.server_name == '':
            self.server_name = os.uname()[1]
            logger.warn(("You had not specified a server name. I have guessed that this server is called '%s' "
                        + " and saved this in the config file. If this is incorrect, you should edit server.name in "
                        + "the config file.") % (self.server_name,))
            self.cfg.set('general', 'server.name', self.server_name)
            self.save_config()

        self.validators = Validators()
        self.validators.email = EmailValidator(self)
        self.validators.msisdn = MsisdnValidator(self)

        self.keyring = Keyring()
        self.keyring.ed25519 = SydentEd25519(self).signing_key
        self.keyring.ed25519.alg = 'ed25519'

        self.servlets = Servlets()
        self.servlets.emailRequestCode = EmailRequestCodeServlet(self)
        self.servlets.emailValidate = EmailValidateCodeServlet(self)
        self.servlets.msisdnRequestCode = MsisdnRequestCodeServlet(self)
        self.servlets.msisdnValidate = MsisdnValidateCodeServlet(self)
        self.servlets.lookup = LookupServlet(self)
        self.servlets.bulk_lookup = BulkLookupServlet(self)
        self.servlets.pubkey_ed25519 = Ed25519Servlet(self)
        self.servlets.pubkeyIsValid = PubkeyIsValidServlet(self)
        self.servlets.ephemeralPubkeyIsValid = EphemeralPubkeyIsValidServlet(self)
        self.servlets.threepidBind = ThreePidBindServlet(self)
        self.servlets.replicationPush = ReplicationPushServlet(self)
        self.servlets.getValidated3pid = GetValidated3pidServlet(self)
        self.servlets.storeInviteServlet = StoreInviteServlet(self)
        self.servlets.blindlySignStuffServlet = BlindlySignStuffServlet(self)

        self.threepidBinder = ThreepidBinder(self)

        self.sslComponents = SslComponents(self)

        self.clientApiHttpServer = ClientApiHttpServer(self)
        self.replicationHttpsServer = ReplicationHttpsServer(self)
        self.replicationHttpsClient = ReplicationHttpsClient(self)

        self.pusher = Pusher(self)

    def parse_config(self):
        self.cfg = ConfigParser.SafeConfigParser(Sydent.CONFIG_DEFAULTS)
        for sect in Sydent.CONFIG_SECTIONS:
            try:
                self.cfg.add_section(sect)
            except ConfigParser.DuplicateSectionError:
                pass
        self.cfg.read("sydent.conf")

    def save_config(self):
        fp = open("sydent.conf", 'w')
        self.cfg.write(fp)
        fp.close()

    def run(self):
        self.clientApiHttpServer.setup()
        self.replicationHttpsServer.setup()
        self.pusher.setup()

        if self.pidfile:
            with open(self.pidfile, 'w') as pidfile:
                pidfile.write(str(os.getpid()) + "\n")

        twisted.internet.reactor.run()

    def ip_from_request(self, request):
        if (self.cfg.get('http', 'obey_x_forwarded_for') and
                request.requestHeaders.hasHeader("X-Forwarded-For")):
            return request.requestHeaders.getRawHeaders("X-Forwarded-For")[0]
        return request.getClientIP()


class Validators:
    pass


class Servlets:
    pass


class Keyring:
    pass


if __name__ == '__main__':
    syd = Sydent()
    syd.run()
