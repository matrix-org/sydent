# Copyright 2020 The Matrix.org Foundation C.I.C.
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

import re
from typing import Optional, Tuple

from twisted.internet.abstract import isIPAddress, isIPv6Address

# https://matrix.org/docs/spec/client_server/r0.6.0#post-matrix-client-r0-register-email-requesttoken
CLIENT_SECRET_REGEX = re.compile(r"^[0-9a-zA-Z\.=_\-]+$")

# hostname/domain name
# https://regex101.com/r/OyN1lg/2
hostname_regex = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
    flags=re.IGNORECASE,
)

# it's unclear what the maximum length of an email address is. RFC3696 (as corrected
# by errata) says:
#    the upper limit on address lengths should normally be considered to be 254.
#
# In practice, mail servers appear to be more tolerant and allow 400 characters
# or so. Let's allow 500, which should be plenty for everyone.
#
MAX_EMAIL_ADDRESS_LENGTH = 500


def is_valid_client_secret(client_secret: str) -> bool:
    """Validate that a given string matches the client_secret regex defined by the spec

    :param client_secret: The client_secret to validate

    :return: Whether the client_secret is valid
    """
    return (
        0 < len(client_secret) <= 255
        and CLIENT_SECRET_REGEX.match(client_secret) is not None
    )


def is_valid_hostname(string: str) -> bool:
    """Validate that a given string is a valid hostname or domain name.

    For domain names, this only validates that the form is right (for
    instance, it doesn't check that the TLD is valid).

    :param string: The string to validate

    :return: Whether the input is a valid hostname
    """

    return hostname_regex.match(string) is not None


def parse_server_name(server_name: str) -> Tuple[str, Optional[str]]:
    """Split a server name into host/port parts.

    No validation is done on the host part. The port part is validated to be
    a valid port number.

    Args:
        server_name: server name to parse

    Returns:
        host/port parts.

    Raises:
        ValueError if the server name could not be parsed.
    """
    try:
        if server_name[-1] == "]":
            # ipv6 literal, hopefully
            return server_name, None

        host_port = server_name.rsplit(":", 1)
        host = host_port[0]
        port = host_port[1] if host_port[1:] else None

        if port:
            port_num = int(port)

            # exclude things like '08090' or ' 8090'
            if port != str(port_num) or not (1 <= port_num < 65536):
                raise ValueError("Invalid port")

        return host, port
    except Exception:
        raise ValueError("Invalid server name '%s'" % server_name)


def is_valid_matrix_server_name(string: str) -> bool:
    """Validate that the given string is a valid Matrix server name.

    A string is a valid Matrix server name if it is one of the following, plus
    an optional port:

    a. IPv4 address
    b. IPv6 literal (`[IPV6_ADDRESS]`)
    c. A valid hostname

    :param string: The string to validate

    :return: Whether the input is a valid Matrix server name
    """

    try:
        host, port = parse_server_name(string)
    except ValueError:
        return False

    valid_ipv4_addr = isIPAddress(host)
    valid_ipv6_literal = (
        host[0] == "[" and host[-1] == "]" and isIPv6Address(host[1:-1])
    )

    return valid_ipv4_addr or valid_ipv6_literal or is_valid_hostname(host)


def normalise_address(address: str, medium: str) -> str:
    if medium == "email":
        return address.casefold()
    else:
        return address
