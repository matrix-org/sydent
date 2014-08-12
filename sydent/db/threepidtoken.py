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

from sydent.validators import Token

class ThreePidTokenStore:
    def __init__(self, syd):
        self.sydent = syd

    def addToken(self, medium, address, token, clientSecret, createdAt):
        cur = self.sydent.db.cursor()

        cur.execute("insert into threepid_validation_tokens ('medium', 'address', 'token', 'clientSecret', 'createdAt')"+
            " values (?, ?, ?, ?, ?)", (medium, address, token, clientSecret, createdAt))
        self.sydent.db.commit()
        return cur.lastrowid

    def getTokenById(self, tokId):
        cur = self.sydent.db.cursor()

        cur.execute("select id, medium, address, token, clientSecret, validated, createdAt from "+
            "threepid_validation_tokens where id = ?", [tokId])
        row = cur.fetchone()

        if not row:
            return None

        return Token(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
