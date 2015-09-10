# -*- coding: utf-8 -*-

# Copyright 2015 OpenMarket Ltd
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

class JoinTokenStore(object):
    def __init__(self, sydent):
        self.sydent = sydent

    def storeToken(self, medium, address, roomId, token):
        cur = self.sydent.db.cursor()

        cur.execute("INSERT INTO invite_tokens"
                    " ('medium', 'address', 'room_id', 'token')"
                    " VALUES (?, ?, ?, ?)",
                    (medium, address, roomId, token,))
        self.sydent.db.commit()

    def getTokens(self, medium, address):
        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT medium, address, room_id, token FROM invite_tokens"
            " WHERE medium = ? AND address = ?",
            (medium, address,)
        )
        rows = res.fetchall()

        ret = []

        for row in rows:
            medium, address, roomId, token = row
            ret.append({
                "medium": medium,
                "address": address,
                "room_id": roomId,
                "token": token,
            })

        return ret

    def deleteTokens(self, medium, address):
        cur = self.sydent.db.cursor()

        cur.execute(
            "DELETE FROM invite_tokens WHERE medium = ? AND address = ?",
            (medium, address,)
        )
        self.sydent.db.commit()
