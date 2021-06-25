# Copyright 2019 New Vector Ltd
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

import logging
import random
import time
from typing import Optional, Tuple, Union

import attr
from netaddr import IPAddress  # type: ignore
from twisted.internet import defer
from twisted.internet.endpoints import HostnameEndpoint, wrapClientTLS
from twisted.internet.interfaces import IStreamClientEndpoint
from twisted.web.client import URI, Agent, HTTPConnectionPool, RedirectAgent
from twisted.web.http import stringToDatetime
from twisted.web.http_headers import Headers
from twisted.web.iweb import IAgent, IBodyProducer, IResponse
from zope.interface import implementer

from sydent.http.httpcommon import read_body_with_max_size
from sydent.http.srvresolver import SrvResolver, pick_server_from_list
from sydent.util import json_decoder
from sydent.util.ttlcache import TTLCache

# period to cache .well-known results for by default
WELL_KNOWN_DEFAULT_CACHE_PERIOD = 24 * 3600

# jitter to add to the .well-known default cache ttl
WELL_KNOWN_DEFAULT_CACHE_PERIOD_JITTER = 10 * 60

# period to cache failure to fetch .well-known for
WELL_KNOWN_INVALID_CACHE_PERIOD = 1 * 3600

# cap for .well-known cache period
WELL_KNOWN_MAX_CACHE_PERIOD = 48 * 3600

# The maximum size (in bytes) to allow a well-known file to be.
WELL_KNOWN_MAX_SIZE = 50 * 1024  # 50 KiB

logger = logging.getLogger(__name__)
well_known_cache = TTLCache("well-known")


@implementer(IAgent)
class MatrixFederationAgent:
    """An Agent-like thing which provides a `request` method which will look up a matrix
    server and send an HTTP request to it.
    Doesn't implement any retries. (Those are done in MatrixFederationHttpClient.)

    :param reactor: twisted reactor to use for underlying requests
    :type reactor: IReactor

    :param tls_client_options_factory: Factory to use for fetching client tls
        options, or none to disable TLS.
    :type tls_client_options_factory: ClientTLSOptionsFactory, None

    :param _well_known_tls_policy: TLS policy to use for fetching .well-known
        files. None to use a default (browser-like) implementation.
    :type _well_known_tls_policy: IPolicyForHTTPS, None

    :param _srv_resolver: SRVResolver impl to use for looking up SRV records.
        None to use a default implementation.
    :type _srv_resolver: SrvResolver, None

    :param _well_known_cache: TTLCache impl for storing cached well-known
        lookups. Omit to use a default implementation.
    :type _well_known_cache: TTLCache
    """

    def __init__(
        self,
        reactor,
        tls_client_options_factory,
        _well_known_tls_policy=None,
        _srv_resolver: Optional["SrvResolver"] = None,
        _well_known_cache: "TTLCache" = well_known_cache,
    ) -> None:
        self._reactor = reactor

        self._tls_client_options_factory = tls_client_options_factory
        if _srv_resolver is None:
            _srv_resolver = SrvResolver()
        self._srv_resolver = _srv_resolver

        self._pool = HTTPConnectionPool(reactor)
        self._pool.retryAutomatically = False
        self._pool.maxPersistentPerHost = 5
        self._pool.cachedConnectionTimeout = 2 * 60

        agent_args = {}
        if _well_known_tls_policy is not None:
            # the param is called 'contextFactory', but actually passing a
            # contextfactory is deprecated, and it expects an IPolicyForHTTPS.
            agent_args["contextFactory"] = _well_known_tls_policy
        _well_known_agent = RedirectAgent(
            Agent(self._reactor, pool=self._pool, **agent_args),
        )
        self._well_known_agent = _well_known_agent

        # our cache of .well-known lookup results, mapping from server name
        # to delegated name. The values can be:
        #   `bytes`:     a valid server-name
        #   `None`:      there is no (valid) .well-known here
        self._well_known_cache = _well_known_cache

    @defer.inlineCallbacks
    def request(
        self,
        method: bytes,
        uri: bytes,
        headers: Optional["Headers"] = None,
        bodyProducer: Optional["IBodyProducer"] = None,
    ) -> IResponse:
        """
        :param method: HTTP method (GET/POST/etc).

        :param uri: Absolute URI to be retrieved.

        :param headers: HTTP headers to send with the request, or None to
            send no extra headers.

        :param bodyProducer: An object which can generate bytes to make up the
            body of this request (for example, the properly encoded contents of
            a file for a file upload).  Or None if the request is to have
            no body.

        :returns a deferred that fires when the header of the response has
            been received (regardless of the response status code). Fails if
            there is any problem which prevents that response from being received
            (including problems that prevent the request from being sent).
        """
        parsed_uri = URI.fromBytes(uri, defaultPort=-1)
        res = yield defer.ensureDeferred(self._route_matrix_uri(parsed_uri))

        # set up the TLS connection params
        #
        # XXX disabling TLS is really only supported here for the benefit of the
        # unit tests. We should make the UTs cope with TLS rather than having to make
        # the code support the unit tests.
        if self._tls_client_options_factory is None:
            tls_options = None
        else:
            tls_options = self._tls_client_options_factory.get_options(
                res.tls_server_name.decode("ascii")
            )

        # make sure that the Host header is set correctly
        if headers is None:
            headers = Headers()
        else:
            headers = headers.copy()
            assert headers is not None

        if not headers.hasHeader(b"host"):
            headers.addRawHeader(b"host", res.host_header)

        class EndpointFactory:
            @staticmethod
            def endpointForURI(_uri):
                ep = LoggingHostnameEndpoint(
                    self._reactor,
                    res.target_host,
                    res.target_port,
                )
                if tls_options is not None:
                    ep = wrapClientTLS(tls_options, ep)
                return ep

        agent = Agent.usingEndpointFactory(self._reactor, EndpointFactory(), self._pool)
        res = yield agent.request(method, uri, headers, bodyProducer)
        return res

    async def _route_matrix_uri(
        self, parsed_uri: "URI", lookup_well_known: bool = True
    ) -> "_RoutingResult":
        """Helper for `request`: determine the routing for a Matrix URI

        :param parsed_uri: uri to route. Note that it should be parsed with
            URI.fromBytes(uri, defaultPort=-1) to set the `port` to -1 if there
            is no explicit port given.
        :param lookup_well_known: True if we should look up the .well-known
            file if there is no SRV record.

        :returns a routing result.
        """
        # check for an IP literal
        try:
            ip_address = IPAddress(parsed_uri.host.decode("ascii"))
        except Exception:
            # not an IP address
            ip_address = None

        if ip_address:
            port = parsed_uri.port
            if port == -1:
                port = 8448
            return _RoutingResult(
                host_header=parsed_uri.netloc,
                tls_server_name=parsed_uri.host,
                target_host=parsed_uri.host,
                target_port=port,
            )

        if parsed_uri.port != -1:
            # there is an explicit port
            return _RoutingResult(
                host_header=parsed_uri.netloc,
                tls_server_name=parsed_uri.host,
                target_host=parsed_uri.host,
                target_port=parsed_uri.port,
            )

        if lookup_well_known:
            # try a .well-known lookup
            well_known_server = await self._get_well_known(parsed_uri.host)

            if well_known_server:
                # if we found a .well-known, start again, but don't do another
                # .well-known lookup.

                # parse the server name in the .well-known response into host/port.
                # (This code is lifted from twisted.web.client.URI.fromBytes).
                if b":" in well_known_server:
                    well_known_host, well_known_port = well_known_server.rsplit(b":", 1)
                    try:
                        well_known_port = int(well_known_port)
                    except ValueError:
                        # the part after the colon could not be parsed as an int
                        # - we assume it is an IPv6 literal with no port (the closing
                        # ']' stops it being parsed as an int)
                        well_known_host, well_known_port = well_known_server, -1
                else:
                    well_known_host, well_known_port = well_known_server, -1

                new_uri = URI(
                    scheme=parsed_uri.scheme,
                    netloc=well_known_server,
                    host=well_known_host,
                    port=well_known_port,
                    path=parsed_uri.path,
                    params=parsed_uri.params,
                    query=parsed_uri.query,
                    fragment=parsed_uri.fragment,
                )

                res = await self._route_matrix_uri(new_uri, lookup_well_known=False)
                return res

        # try a SRV lookup
        service_name = b"_matrix._tcp.%s" % (parsed_uri.host,)
        server_list = await self._srv_resolver.resolve_service(service_name)

        if not server_list:
            target_host = parsed_uri.host
            port = 8448
            logger.debug(
                "No SRV record for %s, using %s:%i",
                parsed_uri.host.decode("ascii"),
                target_host.decode("ascii"),
                port,
            )
        else:
            target_host, port = pick_server_from_list(server_list)
            logger.debug(
                "Picked %s:%i from SRV records for %s",
                target_host.decode("ascii"),
                port,
                parsed_uri.host.decode("ascii"),
            )

        return _RoutingResult(
            host_header=parsed_uri.netloc,
            tls_server_name=parsed_uri.host,
            target_host=target_host,
            target_port=port,
        )

    async def _get_well_known(self, server_name: bytes) -> Optional[bytes]:
        """Attempt to fetch and parse a .well-known file for the given server

        :param server_name: Name of the server, from the requested url.

        :returns either the new server name, from the .well-known, or None if
            there was no .well-known file.
        """
        try:
            result = self._well_known_cache[server_name]
        except KeyError:
            # TODO: should we linearise so that we don't end up doing two .well-known
            # requests for the same server in parallel?
            result, cache_period = await self._do_get_well_known(server_name)

            if cache_period > 0:
                self._well_known_cache.set(server_name, result, cache_period)

        return result

    async def _do_get_well_known(
        self, server_name: bytes
    ) -> Tuple[Union[bytes, None, object], int]:
        """Actually fetch and parse a .well-known, without checking the cache

        :param server_name: Name of the server, from the requested url

        :returns a tuple of (result, cache period), where result is one of:
            - the new server name from the .well-known (as a `bytes`)
            - None if there was no .well-known file.
            - INVALID_WELL_KNOWN if the .well-known was invalid
        """
        uri = b"https://%s/.well-known/matrix/server" % (server_name,)
        uri_str = uri.decode("ascii")
        logger.info("Fetching %s", uri_str)
        try:
            response = await self._well_known_agent.request(b"GET", uri)
            body = await read_body_with_max_size(response, WELL_KNOWN_MAX_SIZE)
            if response.code != 200:
                raise Exception("Non-200 response %s" % (response.code,))

            parsed_body = json_decoder.decode(body.decode("utf-8"))
            logger.info("Response from .well-known: %s", parsed_body)
            if not isinstance(parsed_body, dict):
                raise Exception("not a dict")
            if "m.server" not in parsed_body:
                raise Exception("Missing key 'm.server'")
        except Exception as e:
            logger.info("Error fetching %s: %s", uri_str, e)

            # add some randomness to the TTL to avoid a stampeding herd every hour
            # after startup
            cache_period: float = WELL_KNOWN_INVALID_CACHE_PERIOD
            cache_period += random.uniform(0, WELL_KNOWN_DEFAULT_CACHE_PERIOD_JITTER)
            return (None, cache_period)

        result = parsed_body["m.server"].encode("ascii")

        cache_period = _cache_period_from_headers(
            response.headers,
            time_now=self._reactor.seconds,
        )
        if cache_period is None:
            cache_period = WELL_KNOWN_DEFAULT_CACHE_PERIOD
            # add some randomness to the TTL to avoid a stampeding herd every 24 hours
            # after startup
            cache_period += random.uniform(0, WELL_KNOWN_DEFAULT_CACHE_PERIOD_JITTER)
        else:
            cache_period = min(cache_period, WELL_KNOWN_MAX_CACHE_PERIOD)

        return (result, cache_period)


@implementer(IStreamClientEndpoint)
class LoggingHostnameEndpoint:
    """A wrapper for HostnameEndpint which logs when it connects"""

    def __init__(self, reactor, host, port, *args, **kwargs):
        self.host = host
        self.port = port
        self.ep = HostnameEndpoint(reactor, host, port, *args, **kwargs)
        logger.info("Endpoint created with %s:%d", host, port)

    def connect(self, protocol_factory):
        logger.info("Connecting to %s:%i", self.host.decode("ascii"), self.port)
        return self.ep.connect(protocol_factory)


def _cache_period_from_headers(headers, time_now=time.time):
    cache_controls = _parse_cache_control(headers)

    if b"no-store" in cache_controls:
        return 0

    if b"max-age" in cache_controls:
        try:
            max_age = int(cache_controls[b"max-age"])
            return max_age
        except ValueError:
            pass

    expires = headers.getRawHeaders(b"expires")
    if expires is not None:
        try:
            expires_date = stringToDatetime(expires[-1])
            return expires_date - time_now()
        except ValueError:
            # RFC7234 says 'A cache recipient MUST interpret invalid date formats,
            # especially the value "0", as representing a time in the past (i.e.,
            # "already expired").
            return 0

    return None


def _parse_cache_control(headers):
    cache_controls = {}
    for hdr in headers.getRawHeaders(b"cache-control", []):
        for directive in hdr.split(b","):
            splits = [x.strip() for x in directive.split(b"=", 1)]
            k = splits[0].lower()
            v = splits[1] if len(splits) > 1 else None
            cache_controls[k] = v
    return cache_controls


@attr.s
class _RoutingResult:
    """The result returned by `_route_matrix_uri`.
    Contains the parameters needed to direct a federation connection to a particular
    server.
    Where a SRV record points to several servers, this object contains a single server
    chosen from the list.
    """

    host_header = attr.ib()
    """
    The value we should assign to the Host header (host:port from the matrix
    URI, or .well-known).
    :type: bytes
    """

    tls_server_name = attr.ib()
    """
    The server name we should set in the SNI (typically host, without port, from the
    matrix URI or .well-known)
    :type: bytes
    """

    target_host = attr.ib()
    """
    The hostname (or IP literal) we should route the TCP connection to (the target of the
    SRV record, or the hostname from the URL/.well-known)
    :type: bytes
    """

    target_port = attr.ib()
    """
    The port we should route the TCP connection to (the target of the SRV record, or
    the port from the URL/.well-known, or 8448)
    :type: int
    """
