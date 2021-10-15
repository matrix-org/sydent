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

import attr

# how long a user can wait before validating a session after starting it
THREEPID_SESSION_VALIDATION_TIMEOUT_MS = 24 * 60 * 60 * 1000

# how long we keep sessions for after they've been validated
THREEPID_SESSION_VALID_LIFETIME_MS = 24 * 60 * 60 * 1000


@attr.s(frozen=True, slots=True, auto_attribs=True)
class ValidationSession:
    id: int
    medium: str
    address: str
    client_secret: str
    validated: bool
    mtime: int


@attr.s(frozen=True, slots=True, auto_attribs=True)
class TokenInfo:
    token: str
    send_attempt_number: int


class IncorrectClientSecretException(Exception):
    pass


class SessionExpiredException(Exception):
    pass


class InvalidSessionIdException(Exception):
    pass


class IncorrectSessionTokenException(Exception):
    pass


class SessionNotValidatedException(Exception):
    pass


class DestinationRejectedException(Exception):
    pass
