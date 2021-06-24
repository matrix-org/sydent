# Copyright 2019 The Matrix.org Foundation C.I.C.
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
import time
from typing import TYPE_CHECKING

from sydent.db.accounts import AccountStore
from sydent.util.tokenutils import generateAlphanumericTokenOfLength

if TYPE_CHECKING:
    from sydent.sydent import Sydent


logger = logging.getLogger(__name__)


def issueToken(sydent: "Sydent", user_id: str) -> str:
    """
    Creates an account for the given Matrix user ID, then generates, saves and returns
    an access token for that account.

    :param sydent: The Sydent instance to use for storing the token.
    :param user_id: The Matrix user ID to issue a token for.

    :return: The access token for that account.
    """
    accountStore = AccountStore(sydent)
    accountStore.storeAccount(user_id, int(time.time() * 1000), None)

    new_token = generateAlphanumericTokenOfLength(64)
    accountStore.addToken(user_id, new_token)

    return new_token
