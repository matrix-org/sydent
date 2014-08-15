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
from twisted.python import log

import logging
import twisted.internet.reactor

logger = logging.getLogger(__name__)


class HttpServer:
    def __init__(self, sydent):
        self.sydent = sydent

        observer = log.PythonLoggingObserver()
        observer.start()

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

        email.putChild('requestToken', emailReqCode)
        email.putChild('submitToken', emailValCode)

        self.factory = Site(root)

    def setup(self):
        httpPort = int(self.sydent.cfg.get('http', 'http.port'))
        logger.info("Starting HTTP server on port %d", httpPort)
        twisted.internet.reactor.listenTCP(httpPort, self.factory)
