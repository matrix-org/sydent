# -*- coding: utf-8 -*-
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

# https://matrix.org/docs/spec/client_server/r0.6.0#post-matrix-client-r0-register-email-requesttoken
client_secret_regex = re.compile(r"^[0-9a-zA-Z\.\=\_\-]+$")

# hostname/domain name + optional port
# https://regex101.com/r/OyN1lg/2
hostname_regex = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
    flags=re.IGNORECASE)


def is_valid_client_secret(client_secret):
    """Validate that a given string matches the client_secret regex defined by the spec

    :param client_secret: The client_secret to validate
    :type client_secret: str

    :return: Whether the client_secret is valid
    :rtype: bool
    """
    return client_secret_regex.match(client_secret) is not None


def is_valid_hostname(string: str) -> bool:
    """Validate that a given string is a valid hostname or domain name, with an
    optional port number.

    For domain names, this only validates that the form is right (for
    instance, it doesn't check that the TLD is valid). If a port is
    specified, it has to be a valid port number.

    :param string: The string to validate
    :type string: str

    :return: Whether the input is a valid hostname
    :rtype: bool
    """

    host_parts = string.split(":", 1)

    if len(host_parts) == 1:
        return hostname_regex.match(string) is not None
    else:
        host, port = host_parts
        valid_hostname = hostname_regex.match(host) is not None

        try:
            port_num = int(port)
            valid_port = (
                port == str(port_num)  # exclude things like '08090' or ' 8090'
                and 1 <= port_num < 65536)
        except ValueError:
            valid_port = False

        return valid_hostname and valid_port
