# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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
        emailReqCode = self.sydent.servlets.emailRequestCode
        emailValCode = self.sydent.servlets.emailValidate

        lookup = self.sydent.servlets.lookup

        threepid = Resource()
        bind = self.sydent.servlets.threepidBind

        pubkey = Resource()
        pk_ed25519 = self.sydent.servlets.pubkey_ed25519

        root.putChild('matrix', matrix)
        matrix.putChild('identity', identity)
        identity.putChild('api', api)
        api.putChild('v1', v1)

        v1.putChild('validate', validate)
        validate.putChild('email', email)

        v1.putChild('lookup', lookup)

        v1.putChild('pubkey', pubkey)
        pubkey.putChild('ed25519', pk_ed25519)

        v1.putChild('3pid', threepid)
        threepid.putChild('bind', bind)

        email.putChild('requestToken', emailReqCode)
        email.putChild('submitToken', emailValCode)

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

        root.putChild('matrix', matrix)
        matrix.putChild('identity', identity)

        replicate = Resource()
        replV1 = Resource()

        identity.putChild('replicate', replicate)
        replicate.putChild('v1', replV1)
        replV1.putChild('push', self.sydent.servlets.replicationPush)

        self.factory = Site(root)

    def setup(self):
        httpPort = int(self.sydent.cfg.get('http', 'replication.https.port'))

        privKeyAndCertFilename = self.sydent.cfg.get('http', 'replication.https.certfile')
        if privKeyAndCertFilename == '':
            logger.warn("No HTTPS private key / cert found: not starting the replication HTTPS server")
            return

        try:
            fp = open(privKeyAndCertFilename)
        except IOError:
            logger.warn("Unable to read private key / cert file from %s: not starting the replication HTTPS server.",
                        privKeyAndCertFilename)
            return

        authData = fp.read()
        fp.close()
        certificate = twisted.internet.ssl.PrivateCertificate.loadPEM(authData)

        # If this option is specified, use a specific root CA cert. This is useful for testing when it's not
        # practical to get the client cert signed by a real root CA but should never be used on a production server.
        caCertFilename = self.sydent.cfg.get('http', 'replication.https.cacert')
        if len(caCertFilename) > 0:
            try:
                fp = open(caCertFilename)
                caCert = twisted.internet.ssl.Certificate.loadPEM(fp.read())
                fp.close()
            except:
                logger.warn("Failed to open CA cert file %s", caCertFilename)
                raise
            logger.warn("Using custom CA cert file: %s", caCertFilename)
            trustRoot = twisted.internet._sslverify.OpenSSLCertificateAuthorities([caCert.original])
        else:
            trustRoot = twisted.internet.ssl.OpenSSLDefaultPaths()

        certOptions = twisted.internet.ssl.CertificateOptions(privateKey=certificate.privateKey.original,
                                                              certificate=certificate.original,
                                                              trustRoot=trustRoot)

        logger.info("Loaded server private key and certificate!")
        logger.info("Starting Replication HTTPS server on port %d", httpPort)

        twisted.internet.reactor.listenSSL(httpPort, self.factory, certOptions)