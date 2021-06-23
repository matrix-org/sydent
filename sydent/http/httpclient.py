# Copyright 2016 OpenMarket Ltd
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
from typing import TYPE_CHECKING, Any, Dict, Optional

from twisted.web.client import Agent, FileBodyProducer
from twisted.web.http_headers import Headers
from twisted.web.iweb import IAgent, IResponse

from sydent.http.blacklisting_reactor import BlacklistingReactorWrapper
from sydent.http.federation_tls_options import ClientTLSOptionsFactory
from sydent.http.httpcommon import BodyExceededMaxSize, read_body_with_max_size
from sydent.http.matrixfederationagent import MatrixFederationAgent
from sydent.types import JsonDict
from sydent.util import json_decoder

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class HTTPClient:
    """A base HTTP class that contains methods for making GET and POST HTTP
    requests.
    """

    agent: IAgent

    async def get_json(self, uri: str, max_size: Optional[int] = None) -> JsonDict:
        """Make a GET request to an endpoint returning JSON and parse result

        :param uri: The URI to make a GET request to.

        :param max_size: The maximum size (in bytes) to allow as a response.

        :return: A deferred containing JSON parsed into a Python object.
        """
        logger.debug("HTTP GET %s", uri)

        response = await self.agent.request(
            b"GET",
            uri.encode("utf8"),
        )
        body = await read_body_with_max_size(response, max_size)
        try:
            # json.loads doesn't allow bytes in Python 3.5
            json_body = json_decoder.decode(body.decode("UTF-8"))
        except Exception:
            logger.exception("Error parsing JSON from %s", uri)
            raise
        return json_body

    async def post_json_get_nothing(
        self, uri: str, post_json: Dict[Any, Any], opts: Dict[str, Any]
    ) -> IResponse:
        """Make a POST request to an endpoint returning JSON and parse result

        :param uri: The URI to make a POST request to.

        :param post_json: A Python object that will be converted to a JSON
            string and POSTed to the given URI.

        :param opts: A dictionary of request options. Currently only opts.headers
            is supported.

        :return: a response from the remote server.
        """
        json_bytes = json.dumps(post_json).encode("utf8")

        headers = opts.get(
            "headers",
            Headers(
                {
                    b"Content-Type": [b"application/json"],
                }
            ),
        )

        logger.debug("HTTP POST %s -> %s", json_bytes, uri)

        response = await self.agent.request(
            b"POST",
            uri.encode("utf8"),
            headers,
            bodyProducer=FileBodyProducer(BytesIO(json_bytes)),
        )

        # Ensure the body object is read otherwise we'll leak HTTP connections
        # as per
        # https://twistedmatrix.com/documents/current/web/howto/client.html
        try:
            # TODO Will this cause the server to think the request was a failure?
            await read_body_with_max_size(response, 0)
        except BodyExceededMaxSize:
            pass

        return response


class SimpleHttpClient(HTTPClient):
    """A simple, no-frills HTTP client based on the class of the same name
    from Synapse.
    """

    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        # The default endpoint factory in Twisted 14.0.0 (which we require) uses the
        # BrowserLikePolicyForHTTPS context factory which will do regular cert validation
        # 'like a browser'
        self.agent = Agent(
            BlacklistingReactorWrapper(
                reactor=self.sydent.reactor,
                ip_whitelist=sydent.ip_whitelist,
                ip_blacklist=sydent.ip_blacklist,
            ),
            connectTimeout=15,
        )


class FederationHttpClient(HTTPClient):
    """HTTP client for federation requests to homeservers. Uses a
    MatrixFederationAgent.
    """

    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        self.agent = MatrixFederationAgent(
            BlacklistingReactorWrapper(
                reactor=self.sydent.reactor,
                ip_whitelist=sydent.ip_whitelist,
                ip_blacklist=sydent.ip_blacklist,
            ),
            ClientTLSOptionsFactory(sydent.cfg)
            if sydent.use_tls_for_federation
            else None,
        )
