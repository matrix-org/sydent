#  Copyright 2021 The Matrix.org Foundation C.I.C.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import itertools
from typing import Iterable, Optional

from netaddr import AddrFormatError, IPNetwork, IPSet

# IP ranges that are considered private / unroutable / don't make sense.
DEFAULT_IP_RANGE_BLACKLIST = [
    # Localhost
    "127.0.0.0/8",
    # Private networks.
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    # Carrier grade NAT.
    "100.64.0.0/10",
    # Address registry.
    "192.0.0.0/24",
    # Link-local networks.
    "169.254.0.0/16",
    # Formerly used for 6to4 relay.
    "192.88.99.0/24",
    # Testing networks.
    "198.18.0.0/15",
    "192.0.2.0/24",
    "198.51.100.0/24",
    "203.0.113.0/24",
    # Multicast.
    "224.0.0.0/4",
    # Localhost
    "::1/128",
    # Link-local addresses.
    "fe80::/10",
    # Unique local addresses.
    "fc00::/7",
    # Testing networks.
    "2001:db8::/32",
    # Multicast.
    "ff00::/8",
    # Site-local addresses
    "fec0::/10",
]


def generate_ip_set(
    ip_addresses: Optional[Iterable[str]],
    extra_addresses: Optional[Iterable[str]] = None,
    config_path: Optional[Iterable[str]] = None,
) -> IPSet:
    """
    Generate an IPSet from a list of IP addresses or CIDRs.

    Additionally, for each IPv4 network in the list of IP addresses, also
    includes the corresponding IPv6 networks.

    This includes:

    * IPv4-Compatible IPv6 Address (see RFC 4291, section 2.5.5.1)
    * IPv4-Mapped IPv6 Address (see RFC 4291, section 2.5.5.2)
    * 6to4 Address (see RFC 3056, section 2)

    Args:
        ip_addresses: An iterable of IP addresses or CIDRs.
        extra_addresses: An iterable of IP addresses or CIDRs.
        config_path: The path in the configuration for error messages.

    Returns:
        A new IP set.
    """
    result = IPSet()
    for ip in itertools.chain(ip_addresses or (), extra_addresses or ()):
        try:
            network = IPNetwork(ip)
        except AddrFormatError as e:
            raise Exception(
                "Invalid IP range provided: %s." % (ip,), config_path
            ) from e
        result.add(network)

        # It is possible that these already exist in the set, but that's OK.
        if ":" not in str(network):
            result.add(IPNetwork(network).ipv6(ipv4_compatible=True))
            result.add(IPNetwork(network).ipv6(ipv4_compatible=False))
            result.add(_6to4(network))

    return result


def _6to4(network: IPNetwork) -> IPNetwork:
    """Convert an IPv4 network into a 6to4 IPv6 network per RFC 3056."""

    # 6to4 networks consist of:
    # * 2002 as the first 16 bits
    # * The first IPv4 address in the network hex-encoded as the next 32 bits
    # * The new prefix length needs to include the bits from the 2002 prefix.
    hex_network = hex(network.first)[2:]
    hex_network = ("0" * (8 - len(hex_network))) + hex_network
    return IPNetwork(
        "2002:%s:%s::/%d"
        % (
            hex_network[:4],
            hex_network[4:],
            16 + network.prefixlen,
        )
    )
