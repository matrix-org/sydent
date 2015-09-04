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


class CallbackStore:
    def __init__(self, sydent):
        self.sydent = sydent

    def addCallbackRequest(self, medium, address, nonce, server):
        cur = self.sydent.db.cursor()

        cur.execute("INSERT INTO callbacks "
                    "('medium', 'address', 'nonce', 'server')"
                    " VALUES (?, ?, ?, ?)",
                    (medium, address, nonce, server,))
        self.sydent.db.commit()

    def getCallbackRequests(self, medium, address):
        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT id, nonce, server"
            " FROM callbacks "
            " WHERE medium = ? AND address = ?"
            " ORDER BY id ASC",
            (medium, address,)
        )

        requests = {}
        for row in res.fetchall():
            id, nonce, server = row
            requests[id] = {
                "nonce": nonce,
                "server": server,
            }
        return requests

    def deleteCallbackRequest(self, id):
        cur = self.sydent.db.cursor()
        cur.execute("DELETE FROM callbacks WHERE id = ?", (id,))
        self.sydent.db.commit()
