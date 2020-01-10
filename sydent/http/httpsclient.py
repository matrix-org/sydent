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
from __future__ import absolute_import

import logging
import json

from six import StringIO

from zope.interface import implementer

from twisted.internet.ssl import optionsForClientTLS
from twisted.web.client import Agent, FileBodyProducer
from twisted.web.iweb import IPolicyForHTTPS
from twisted.web.http_headers import Headers

logger = logging.getLogger(__name__)


class ReplicationHttpsClient:
    """
    An HTTPS client specifically for talking replication to other Matrix Identity Servers
    (ie. presents our replication SSL certificate and validates peer SSL certificates as we would in the
    replication HTTPS server)
    """
    def __init__(self, sydent):
        self.sydent = sydent
        self.agent = None

        if self.sydent.sslComponents.myPrivateCertificate:
            # We will already have logged a warn if this is absent, so don't do it again
            #cert = self.sydent.sslComponents.myPrivateCertificate
            #self.certOptions = twisted.internet.ssl.CertificateOptions(privateKey=cert.privateKey.original,
            #                                                      certificate=cert.original,
            #                                                      trustRoot=self.sydent.sslComponents.trustRoot)
            self.agent = Agent(self.sydent.reactor, SydentPolicyForHTTPS(self.sydent))

    def postJson(self, uri, jsonObject):
        logger.debug("POSTing request to %s", uri)
        if not self.agent:
            logger.error("HTTPS post attempted but HTTPS is not configured")
            return

        headers = Headers({'Content-Type': ['application/json'], 'User-Agent': ['Sydent']})
        reqDeferred = self.agent.request('POST', uri.encode('utf8'), headers,
                                         FileBodyProducer(StringIO(json.dumps(jsonObject))))

        return reqDeferred


@implementer(IPolicyForHTTPS)
class SydentPolicyForHTTPS(object):
    def __init__(self, sydent):
        self.sydent = sydent

    def creatorForNetloc(self, hostname, port):
        return optionsForClientTLS(hostname.decode("ascii"),
                                   trustRoot=self.sydent.sslComponents.trustRoot,
                                   clientCertificate=self.sydent.sslComponents.myPrivateCertificate)
