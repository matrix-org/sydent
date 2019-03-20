# -*- coding: utf-8 -*-
# Copyright 2014-2016 OpenMarket Ltd
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

import attr

from twisted.internet import defer
from twisted.internet.error import ConnectError
from twisted.names import client, dns
from twisted.names.error import DNSNameError, DomainError

logger = logging.getLogger(__name__)

SERVER_CACHE = {}


@attr.s
class Server(object):
    """
    Our record of an individual server which can be tried to reach a destination.
    Attributes:
        host (bytes): target hostname
        port (int):
        priority (int):
        weight (int):
        expires (int): when the cache should expire this record - in *seconds* since
            the epoch
    """
    host = attr.ib()
    port = attr.ib()
    priority = attr.ib(default=0)
    weight = attr.ib(default=0)
    expires = attr.ib(default=0)


def pick_server_from_list(server_list):
    """Randomly choose a server from the server list.

    :param server_list: List of candidate servers.
    :type server_list: list[Server]

    :returns a (host, port) pair for the chosen server.
    :rtype: Tuple[bytes, int]
    """
    if not server_list:
        raise RuntimeError("pick_server_from_list called with empty list")

    # TODO: currently we only use the lowest-priority servers. We should maintain a
    # cache of servers known to be "down" and filter them out

    min_priority = min(s.priority for s in server_list)
    eligible_servers = list(s for s in server_list if s.priority == min_priority)
    total_weight = sum(s.weight for s in eligible_servers)
    target_weight = random.randint(0, total_weight)

    for s in eligible_servers:
        target_weight -= s.weight

        if target_weight <= 0:
            return s.host, s.port

    # this should be impossible.
    raise RuntimeError(
        "pick_server_from_list got to end of eligible server list.",
    )


class SrvResolver(object):
    """Interface to the dns client to do SRV lookups, with result caching.
    The default resolver in twisted.names doesn't do any caching (it has a CacheResolver,
    but the cache never gets populated), so we add our own caching layer here.

    :param dns_client: Twisted resolver impl
    :type dns_client: twisted.internet.interfaces.IResolver

    :param cache: cache object
    :type cache: Dict

    :param get_time: Clock implementation. Should return seconds since the epoch.
    :type get_time: callable
    """
    def __init__(self, dns_client=client, cache=SERVER_CACHE, get_time=time.time):
        self._dns_client = dns_client
        self._cache = cache
        self._get_time = get_time

    @defer.inlineCallbacks
    def resolve_service(self, service_name):
        """Look up a SRV record

        :param service_name: The record to look up.
        :type service_name: bytes

        :returns a list of the SRV records, or an empty list if none found.
        :rtype: Deferred[list[Server]]
        """
        now = int(self._get_time())

        if not isinstance(service_name, bytes):
            raise TypeError("%r is not a byte string" % (service_name,))

        cache_entry = self._cache.get(service_name, None)
        if cache_entry:
            if all(s.expires > now for s in cache_entry):
                servers = list(cache_entry)
                defer.returnValue(servers)

        try:
            answers, _, _ = yield self._dns_client.lookupService(service_name)
        except DNSNameError:
            # TODO: cache this. We can get the SOA out of the exception, and use
            # the negative-TTL value.
            defer.returnValue([])
        except DomainError as e:
            # We failed to resolve the name (other than a NameError)
            # Try something in the cache, else rereaise
            cache_entry = self._cache.get(service_name, None)
            if cache_entry:
                logger.warn(
                    "Failed to resolve %r, falling back to cache. %r",
                    service_name, e
                )
                defer.returnValue(list(cache_entry))
            else:
                raise e

        if (len(answers) == 1
                and answers[0].type == dns.SRV
                and answers[0].payload
                and answers[0].payload.target == dns.Name(b'.')):
            raise ConnectError("Service %s unavailable" % service_name)

        servers = []

        for answer in answers:
            if answer.type != dns.SRV or not answer.payload:
                continue

            payload = answer.payload

            servers.append(Server(
                host=payload.target.name,
                port=payload.port,
                priority=payload.priority,
                weight=payload.weight,
                expires=now + answer.ttl,
            ))

        self._cache[service_name] = list(servers)
        defer.returnValue(servers)
