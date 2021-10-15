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
from typing import Optional


class Account:
    def __init__(
        self, user_id: str, creation_ts: int, consent_version: Optional[str]
    ) -> None:
        """
        :param user_id: The Matrix user ID for the account.
        :param creation_ts: The timestamp in milliseconds of the account's creation.
        :param consent_version: The version of the terms of services that the user last
            accepted.
        """
        self.userId = user_id
        self.creationTs = creation_ts
        self.consentVersion = consent_version
