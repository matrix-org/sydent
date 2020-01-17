# -*- coding: utf-8 -*-
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


class Account(object):
    def __init__(self, user_id, creation_ts, consent_version):
        """
        :param user_id: The Matrix user ID for the account.
        :type user_id: str
        :param creation_ts: The timestamp in milliseconds of the account's creation.
        :type creation_ts: int
        :param consent_version: The version of the terms of services that the user last
            accepted.
        """
        self.userId = user_id
        self.creationTs = creation_ts
        self.consentVersion = consent_version
