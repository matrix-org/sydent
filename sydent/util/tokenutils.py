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

import random
import string

r = random.SystemRandom()


def generateTokenForMedium(medium: str) -> str:
    """
    Generates a token of a different format depending on the medium, a 32 characters
    alphanumeric one if the medium is email, a 6 characters numeric one otherwise.

    :param medium: The medium to generate a token for.

    :return: The generated token.
    """
    if medium == "email":
        return generateAlphanumericTokenOfLength(32)
    else:
        return generateNumericTokenOfLength(6)


def generateNumericTokenOfLength(length: int) -> str:
    """
    Generates a token of the given length with the character set [0-9].

    :param length: The length of the token to generate.

    :return: The generated token.
    """
    return "".join([r.choice(string.digits) for _ in range(length)])


def generateAlphanumericTokenOfLength(length: int) -> str:
    """
    Generates a token of the given length with the character set [a-zA-Z0-9].

    :param length: The length of the token to generate.

    :return: The generated token.
    """
    return "".join(
        [
            r.choice(string.digits + string.ascii_lowercase + string.ascii_uppercase)
            for _ in range(length)
        ]
    )
