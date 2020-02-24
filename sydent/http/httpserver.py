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

from twisted.web.server import Site
from twisted.web.resource import Resource

import logging
import twisted.internet.ssl

from sydent.http.servlets.authenticated_bind_threepid_servlet import (
    AuthenticatedBindThreePidServlet,
)
from sydent.http.servlets.authenticated_unbind_threepid_servlet import (
    AuthenticatedUnbindThreePidServlet,
)

logger = logging.getLogger(__name__)


class ClientApiHttpServer:
    def __init__(self, sydent):
        self.sydent = sydent

        root = Resource()
        matrix = Resource()
        identity = Resource()
        api = Resource()
        v1 = self.sydent.servlets.v1
        v2 = self.sydent.servlets.v2

        validate = Resource()
        email = Resource()
        msisdn = Resource()
        emailReqCode = self.sydent.servlets.emailRequestCode
        emailValCode = self.sydent.servlets.emailValidate
        msisdnReqCode = self.sydent.servlets.msisdnRequestCode
        msisdnValCode = self.sydent.servlets.msisdnValidate
        getValidated3pid = self.sydent.servlets.getValidated3pid

        lookup = self.sydent.servlets.lookup
        bulk_lookup = self.sydent.servlets.bulk_lookup

        hash_details = self.sydent.servlets.hash_details
        lookup_v2 = self.sydent.servlets.lookup_v2

        threepid_v1 = Resource()
        threepid_v2 = Resource()
        bind = self.sydent.servlets.threepidBind
        unbind = self.sydent.servlets.threepidUnbind

        pubkey = Resource()
        ephemeralPubkey = Resource()

        pk_ed25519 = self.sydent.servlets.pubkey_ed25519

        root.putChild(b'_matrix', matrix)
        matrix.putChild(b'identity', identity)
        identity.putChild(b'api', api)
        identity.putChild(b'v2', v2)
        api.putChild(b'v1', v1)

        validate.putChild(b'email', email)
        validate.putChild(b'msisdn', msisdn)

        v1.putChild(b'validate', validate)

        v1.putChild(b'lookup', lookup)
        v1.putChild(b'bulk_lookup', bulk_lookup)

        v1.putChild(b'pubkey', pubkey)
        pubkey.putChild(b'isvalid', self.sydent.servlets.pubkeyIsValid)
        pubkey.putChild(b'ed25519:0', pk_ed25519)
        pubkey.putChild(b'ephemeral', ephemeralPubkey)
        ephemeralPubkey.putChild(b'isvalid', self.sydent.servlets.ephemeralPubkeyIsValid)

        threepid_v2.putChild(b'getValidated3pid', getValidated3pid)
        threepid_v2.putChild(b'bind', bind)
        threepid_v2.putChild(b'unbind', unbind)

        threepid_v1.putChild(b'getValidated3pid', getValidated3pid)
        threepid_v1.putChild(b'unbind', unbind)
        if self.sydent.enable_v1_associations:
            threepid_v1.putChild(b'bind', bind)

        v1.putChild(b'3pid', threepid_v1)

        email.putChild(b'requestToken', emailReqCode)
        email.putChild(b'submitToken', emailValCode)

        msisdn.putChild(b'requestToken', msisdnReqCode)
        msisdn.putChild(b'submitToken', msisdnValCode)

        v1.putChild(b'store-invite', self.sydent.servlets.storeInviteServlet)

        v1.putChild(b'sign-ed25519', self.sydent.servlets.blindlySignStuffServlet)

        # v2
        # note v2 loses the /api so goes on 'identity' not 'api'
        identity.putChild(b'v2', v2)

        # v2 exclusive APIs
        v2.putChild(b'terms', self.sydent.servlets.termsServlet)
        account = self.sydent.servlets.accountServlet
        v2.putChild(b'account', account)
        account.putChild(b'register', self.sydent.servlets.registerServlet)
        account.putChild(b'logout', self.sydent.servlets.logoutServlet)

        # v2 versions of existing APIs
        v2.putChild(b'validate', validate)
        v2.putChild(b'pubkey', pubkey)
        v2.putChild(b'3pid', threepid_v2)
        v2.putChild(b'store-invite', self.sydent.servlets.storeInviteServlet)
        v2.putChild(b'sign-ed25519', self.sydent.servlets.blindlySignStuffServlet)
        v2.putChild(b'lookup', lookup_v2)
        v2.putChild(b'hash_details', hash_details)

        self.factory = Site(root)
        self.factory.displayTracebacks = False

    def setup(self):
        httpPort = int(self.sydent.cfg.get('http', 'clientapi.http.port'))
        interface = self.sydent.cfg.get('http', 'clientapi.http.bind_address')
        logger.info("Starting Client API HTTP server on %s:%d", interface, httpPort)
        self.sydent.reactor.listenTCP(
            httpPort, self.factory, interface=interface,
        )


class InternalApiHttpServer(object):
    def __init__(self, sydent):
        self.sydent = sydent

    def setup(self, interface, port):
        logger.info("Starting Internal API HTTP server on %s:%d", interface, port)
        root = Resource()

        matrix = Resource()
        root.putChild(b'_matrix', matrix)

        identity = Resource()
        matrix.putChild(b'identity', identity)

        internal = Resource()
        identity.putChild(b'internal', internal)

        authenticated_bind = AuthenticatedBindThreePidServlet(self.sydent)
        internal.putChild(b'bind', authenticated_bind)

        authenticated_unbind = AuthenticatedUnbindThreePidServlet(self.sydent)
        internal.putChild(b'unbind', authenticated_unbind)

        factory = Site(root)
        factory.displayTracebacks = False
        self.sydent.reactor.listenTCP(port, factory, interface=interface)


class ReplicationHttpsServer:
    def __init__(self, sydent):
        self.sydent = sydent

        root = Resource()
        matrix = Resource()
        identity = Resource()

        root.putChild(b'_matrix', matrix)
        matrix.putChild(b'identity', identity)

        replicate = Resource()
        replV1 = Resource()

        identity.putChild(b'replicate', replicate)
        replicate.putChild(b'v1', replV1)
        replV1.putChild(b'push', self.sydent.servlets.replicationPush)

        self.factory = Site(root)
        self.factory.displayTracebacks = False

    def setup(self):
        httpPort = int(self.sydent.cfg.get('http', 'replication.https.port'))
        interface = self.sydent.cfg.get('http', 'replication.https.bind_address')

        if self.sydent.sslComponents.myPrivateCertificate:
            # We will already have logged a warn if this is absent, so don't do it again
            cert = self.sydent.sslComponents.myPrivateCertificate
            certOptions = twisted.internet.ssl.CertificateOptions(privateKey=cert.privateKey.original,
                                                                  certificate=cert.original,
                                                                  trustRoot=self.sydent.sslComponents.trustRoot)

            logger.info("Loaded server private key and certificate!")
            logger.info("Starting Replication HTTPS server on %s:%d", interface, httpPort)

            self.sydent.reactor.listenSSL(httpPort, self.factory, certOptions,
                                          interface=interface)
