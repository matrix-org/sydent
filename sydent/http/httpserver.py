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

from twisted.web.server import Site
from twisted.web.resource import Resource

import logging
import twisted.internet.reactor
import twisted.internet.ssl

from sydent.http.servlets.authenticated_bind_threepid_servlet import (
    AuthenticatedBindThreePidServlet,
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

        threepid = Resource()
        bind = self.sydent.servlets.threepidBind
        unbind = self.sydent.servlets.threepidUnbind

        pubkey = Resource()
        ephemeralPubkey = Resource()

        pk_ed25519 = self.sydent.servlets.pubkey_ed25519

        root.putChild('_matrix', matrix)
        matrix.putChild('identity', identity)
        identity.putChild('api', api)
        identity.putChild('v2', v2)
        api.putChild('v1', v1)

        v1.putChild('validate', validate)
        validate.putChild('email', email)
        validate.putChild('msisdn', msisdn)

        v1.putChild('lookup', lookup)
        v1.putChild('bulk_lookup', bulk_lookup)

        v1.putChild('pubkey', pubkey)
        pubkey.putChild('isvalid', self.sydent.servlets.pubkeyIsValid)
        pubkey.putChild('ed25519:0', pk_ed25519)
        pubkey.putChild('ephemeral', ephemeralPubkey)
        ephemeralPubkey.putChild('isvalid', self.sydent.servlets.ephemeralPubkeyIsValid)

        v1.putChild('3pid', threepid)
        threepid.putChild('bind', bind)
        threepid.putChild('unbind', unbind)
        threepid.putChild('getValidated3pid', getValidated3pid)

        email.putChild('requestToken', emailReqCode)
        email.putChild('submitToken', emailValCode)

        msisdn.putChild('requestToken', msisdnReqCode)
        msisdn.putChild('submitToken', msisdnValCode)

        v1.putChild('store-invite', self.sydent.servlets.storeInviteServlet)

        v1.putChild('sign-ed25519', self.sydent.servlets.blindlySignStuffServlet)

        # v2
        # note v2 loses the /api so goes on 'identity' not 'api'
        identity.putChild('v2', v2)

        # v2 exclusive APIs
        v2.putChild('terms', self.sydent.servlets.termsServlet)
        account = self.sydent.servlets.accountServlet
        v2.putChild('account', account)
        account.putChild('register', self.sydent.servlets.registerServlet)
        account.putChild('logout', self.sydent.servlets.logoutServlet)

        # v2 versions of existing APIs
        v2.putChild('validate', validate)
        v2.putChild('pubkey', pubkey)
        v2.putChild('3pid', threepid)
        v2.putChild('store-invite', self.sydent.servlets.storeInviteServlet)
        v2.putChild('sign-ed25519', self.sydent.servlets.blindlySignStuffServlet)
        v2.putChild('lookup', lookup_v2)
        v2.putChild('hash_details', hash_details)

        self.factory = Site(root)
        self.factory.displayTracebacks = False

    def setup(self):
        httpPort = int(self.sydent.cfg.get('http', 'clientapi.http.port'))
        interface = self.sydent.cfg.get('http', 'clientapi.http.bind_address')
        logger.info("Starting Client API HTTP server on %s:%d", interface, httpPort)
        twisted.internet.reactor.listenTCP(
            httpPort, self.factory, interface=interface,
        )


class InternalApiHttpServer(object):
    def __init__(self, sydent):
        self.sydent = sydent

    def setup(self, interface, port):
        logger.info("Starting Internal API HTTP server on %s:%d", interface, port)
        root = Resource()

        matrix = Resource()
        root.putChild('_matrix', matrix)

        identity = Resource()
        matrix.putChild('identity', identity)

        internal = Resource()
        identity.putChild('internal', internal)

        authenticated_bind = AuthenticatedBindThreePidServlet(self.sydent)
        internal.putChild('bind', authenticated_bind)

        factory = Site(root)
        factory.displayTracebacks = False
        twisted.internet.reactor.listenTCP(port, factory, interface=interface)


class ReplicationHttpsServer:
    def __init__(self, sydent):
        self.sydent = sydent

        root = Resource()
        matrix = Resource()
        identity = Resource()

        root.putChild('_matrix', matrix)
        matrix.putChild('identity', identity)

        replicate = Resource()
        replV1 = Resource()

        identity.putChild('replicate', replicate)
        replicate.putChild('v1', replV1)
        replV1.putChild('push', self.sydent.servlets.replicationPush)

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

            twisted.internet.reactor.listenSSL(httpPort, self.factory, certOptions, interface=interface)
