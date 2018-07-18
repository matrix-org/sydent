# -*- coding: utf-8 -*-

# Copyright 2018 New Vector Ltd
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


class ProfileStore:
    def __init__(self, sydent):
        self.sydent = sydent

    def getLastBatchForOriginServer(self, host):
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT MAX(batch) FROM profiles WHERE origin_server = ?", (host,)
        )
        return res.fetchone()[0]

    def addBatch(self, host, batchnum, batch):
        cur = self.sydent.db.cursor()

        vals = []
        for userid, val in batch.items():
            if val is None:
                vals.append((userid, None, None, False, host, batchnum))
            else:
                vals.append((userid, val['display_name'], val['avatar_url'], True, host, batchnum))

        cur.executemany(
            "INSERT OR REPLACE INTO profiles "
            "('user_id', 'display_name', 'avatar_url', 'active', 'origin_server', 'batch')"
            " values (?, ?, ?, ?, ?, ?)",
            vals,
        )
        self.sydent.db.commit()

    def getProfilesMatchingSearchTerm(self, search_term, limit):
        cur = self.sydent.db.cursor()

        sql = (
            "SELECT user_id, display_name, avatar_url FROM profiles WHERE "
            "active = 1 and ("
            "    user_id LIKE LOWER(?) OR "
            "    LOWER(display_name) LIKE LOWER(?) "
            ")"
            "LIMIT ?"
        )

        like_pat = '%' + search_term.replace('%', '%%') + '%'

        res = cur.execute(sql, (like_pat, like_pat, limit))
        return [{
            'user_id': r[0],
            'display_name': r[1],
            'avatar_url': r[2],
        } for r in res.fetchall()]
