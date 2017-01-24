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

from twisted.web.server import Site
from twisted.web.resource import Resource

import logging
import twisted.internet.reactor
import twisted.internet.ssl

logger = logging.getLogger(__name__)


class ClientApiHttpServer:
    def __init__(self, sydent):
        self.sydent = sydent

        root = Resource()
        matrix = Resource()
        identity = Resource()
        api = Resource()
        v1 = Resource()

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

        threepid = Resource()
        bind = self.sydent.servlets.threepidBind

        pubkey = Resource()
        ephemeralPubkey = Resource()

        pk_ed25519 = self.sydent.servlets.pubkey_ed25519

        root.putChild('_matrix', matrix)
        matrix.putChild('identity', identity)
        identity.putChild('api', api)
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
        threepid.putChild('getValidated3pid', getValidated3pid)

        email.putChild('requestToken', emailReqCode)
        email.putChild('submitToken', emailValCode)

        msisdn.putChild('requestToken', msisdnReqCode)
        msisdn.putChild('submitToken', msisdnValCode)

        v1.putChild('store-invite', self.sydent.servlets.storeInviteServlet)

        v1.putChild('sign-ed25519', self.sydent.servlets.blindlySignStuffServlet)

        self.factory = Site(root)

    def setup(self):
        httpPort = int(self.sydent.cfg.get('http', 'clientapi.http.port'))
        logger.info("Starting Client API HTTP server on port %d", httpPort)
        twisted.internet.reactor.listenTCP(httpPort, self.factory)


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

    def setup(self):
        httpPort = int(self.sydent.cfg.get('http', 'replication.https.port'))

        if self.sydent.sslComponents.myPrivateCertificate:
            # We will already have logged a warn if this is absent, so don't do it again
            cert = self.sydent.sslComponents.myPrivateCertificate
            certOptions = twisted.internet.ssl.CertificateOptions(privateKey=cert.privateKey.original,
                                                                  certificate=cert.original,
                                                                  trustRoot=self.sydent.sslComponents.trustRoot)

            logger.info("Loaded server private key and certificate!")
            logger.info("Starting Replication HTTPS server on port %d", httpPort)

            twisted.internet.reactor.listenSSL(httpPort, self.factory, certOptions)
