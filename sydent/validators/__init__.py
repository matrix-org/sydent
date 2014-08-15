# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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


class ValidationSession:
    def __init__(self, _id, _medium, _address, _clientSecret, _validated, _mtime):
        self.id = _id
        self.medium = _medium
        self.address = _address
        self.clientSecret = _clientSecret
        self.validated = _validated
        self.mtime = _mtime


class IncorrectClientSecretException(Exception):
    pass


class SessionExpiredException(Exception):
    pass


class InvalidSessionIdException(Exception):
    pass