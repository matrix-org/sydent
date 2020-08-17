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


def is_valid_client_secret(client_secret):
    """Validate that a given string matches the client_secret regex defined by the spec

    :param client_secret: The client_secret to validate
    :type client_secret: unicode

    :return: Whether the client_secret is valid
    :rtype: bool
    """
    return client_secret_regex.match(client_secret) is not None
