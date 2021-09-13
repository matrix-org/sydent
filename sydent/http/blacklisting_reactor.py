# Copyright 2021 The Matrix.org Foundation C.I.C.
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
from typing import Any, List, Optional

from netaddr import IPAddress, IPSet
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.interfaces import (
    IAddress,
    IHostResolution,
    IReactorPluggableNameResolver,
    IResolutionReceiver,
)
from zope.interface import implementer, provider

logger = logging.getLogger(__name__)


def check_against_blacklist(
    ip_address: IPAddress, ip_whitelist: Optional[IPSet], ip_blacklist: IPSet
) -> bool:
    """
    Compares an IP address to allowed and disallowed IP sets.

    Args:
        ip_address: The IP address to check
        ip_whitelist: Allowed IP addresses.
        ip_blacklist: Disallowed IP addresses.

    Returns:
        True if the IP address is in the blacklist and not in the whitelist.
    """
    if ip_address in ip_blacklist:
        if ip_whitelist is None or ip_address not in ip_whitelist:
            return True
    return False


class _IPBlacklistingResolver:
    """
    A proxy for reactor.nameResolver which only produces non-blacklisted IP
    addresses, preventing DNS rebinding attacks on URL preview.
    """

    def __init__(
        self,
        reactor: IReactorPluggableNameResolver,
        ip_whitelist: Optional[IPSet],
        ip_blacklist: IPSet,
    ):
        """
        Args:
            reactor: The twisted reactor.
            ip_whitelist: IP addresses to allow.
            ip_blacklist: IP addresses to disallow.
        """
        self._reactor = reactor
        self._ip_whitelist = ip_whitelist
        self._ip_blacklist = ip_blacklist

    def resolveHostName(
        self, recv: IResolutionReceiver, hostname: str, portNumber: int = 0
    ) -> IResolutionReceiver:
        addresses = []  # type: List[IAddress]

        def _callback() -> None:
            has_bad_ip = False
            for address in addresses:
                # We only expect IPv4 and IPv6 addresses since only A/AAAA lookups
                # should go through this path.
                if not isinstance(address, (IPv4Address, IPv6Address)):
                    continue

                ip_address = IPAddress(address.host)

                if check_against_blacklist(
                    ip_address, self._ip_whitelist, self._ip_blacklist
                ):
                    logger.info(
                        "Dropped %s from DNS resolution to %s due to blacklist"
                        % (ip_address, hostname)
                    )
                    has_bad_ip = True

            # if we have a blacklisted IP, we'd like to raise an error to block the
            # request, but all we can really do from here is claim that there were no
            # valid results.
            if not has_bad_ip:
                for address in addresses:
                    recv.addressResolved(address)
            recv.resolutionComplete()

        @provider(IResolutionReceiver)
        class EndpointReceiver:
            @staticmethod
            def resolutionBegan(resolutionInProgress: IHostResolution) -> None:
                recv.resolutionBegan(resolutionInProgress)

            @staticmethod
            def addressResolved(address: IAddress) -> None:
                addresses.append(address)

            @staticmethod
            def resolutionComplete() -> None:
                _callback()

        self._reactor.nameResolver.resolveHostName(
            EndpointReceiver, hostname, portNumber=portNumber
        )

        return recv


@implementer(IReactorPluggableNameResolver)
class BlacklistingReactorWrapper:
    """
    A Reactor wrapper which will prevent DNS resolution to blacklisted IP
    addresses, to prevent DNS rebinding.
    """

    def __init__(
        self,
        reactor: IReactorPluggableNameResolver,
        ip_whitelist: Optional[IPSet],
        ip_blacklist: IPSet,
    ):
        self._reactor = reactor

        # We need to use a DNS resolver which filters out blacklisted IP
        # addresses, to prevent DNS rebinding.
        self.nameResolver = _IPBlacklistingResolver(
            self._reactor, ip_whitelist, ip_blacklist
        )

    def __getattr__(self, attr: str) -> Any:
        # Passthrough to the real reactor except for the DNS resolver.
        return getattr(self._reactor, attr)
