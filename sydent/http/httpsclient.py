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

import json
import logging
from io import BytesIO
from typing import TYPE_CHECKING, Optional

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IOpenSSLClientConnectionCreator
from twisted.internet.ssl import optionsForClientTLS
from twisted.web.client import Agent, FileBodyProducer, Response
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS
from zope.interface import implementer

from sydent.types import JsonDict

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class ReplicationHttpsClient:
    """
    An HTTPS client specifically for talking replication to other Matrix Identity Servers
    (ie. presents our replication SSL certificate and validates peer SSL certificates as we would in the
    replication HTTPS server)
    """

    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        self.agent: Optional[Agent] = None

        if self.sydent.sslComponents.myPrivateCertificate:
            # We will already have logged a warn if this is absent, so don't do it again
            # cert = self.sydent.sslComponents.myPrivateCertificate
            # self.certOptions = twisted.internet.ssl.CertificateOptions(privateKey=cert.privateKey.original,
            #                                                      certificate=cert.original,
            #                                                      trustRoot=self.sydent.sslComponents.trustRoot)
            self.agent = Agent(self.sydent.reactor, SydentPolicyForHTTPS(self.sydent))

    def postJson(
        self, uri: str, jsonObject: JsonDict
    ) -> Optional["Deferred[Response]"]:
        """
        Sends an POST request over HTTPS.

        :param uri: The URI to send the request to.
        :param jsonObject: The request's body.

        :return: The request's response.
        """
        logger.debug("POSTing request to %s", uri)
        if not self.agent:
            logger.error("HTTPS post attempted but HTTPS is not configured")
            return None

        headers = Headers(
            {"Content-Type": ["application/json"], "User-Agent": ["Sydent"]}
        )

        json_bytes = json.dumps(jsonObject).encode("utf8")
        reqDeferred = self.agent.request(
            b"POST", uri.encode("utf8"), headers, FileBodyProducer(BytesIO(json_bytes))
        )

        return reqDeferred


@implementer(IPolicyForHTTPS)
class SydentPolicyForHTTPS:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

    def creatorForNetloc(
        self, hostname: bytes, port: int
    ) -> IOpenSSLClientConnectionCreator:
        return optionsForClientTLS(
            hostname.decode("ascii"),
            trustRoot=self.sydent.sslComponents.trustRoot,
            clientCertificate=self.sydent.sslComponents.myPrivateCertificate,
        )
