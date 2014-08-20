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

from sydent.util import time_msec

from sydent.threepid import ThreepidAssociation, threePidAssocFromDict

import json

class LocalAssociationStore:
    def __init__(self, sydent):
        self.sydent = sydent

    def addOrUpdateAssociation(self, assoc):
        cur = self.sydent.db.cursor()

        # sqlite's support for upserts is atrocious
        cur.execute("insert or replace into local_threepid_associations "
                    "('medium', 'address', 'mxid', 'ts', 'notBefore', 'notAfter')"
                    " values (?, ?, ?, ?, ?, ?)",
            (assoc.medium, assoc.address, assoc.mxid, assoc.ts, assoc.not_before, assoc.not_after))
        self.sydent.db.commit()

    def getAssociationsAfterId(self, afterId, limit):
        cur = self.sydent.db.cursor()

        if afterId is None:
            afterId = -1

        q = "select id, medium, address, mxid, ts, notBefore, notAfter from local_threepid_associations " \
            "where id > ? order by id asc"
        if limit is not None:
            q += " limit ?"
            res = cur.execute(q, (afterId, limit))
        else:
            # No no, no no no no, no no no no, no no, there's no limit.
            res = cur.execute(q, (afterId,))

        assocs = {}
        for row in res.fetchall():
            assoc = ThreepidAssociation(row[1], row[2], row[3], row[4], row[5], row[6])
            assocs[row[0]] = assoc

        return assocs

class GlobalAssociationStore:
    def __init__(self, sydent):
        self.sydent = sydent

    def signedAssociationForThreepid(self, medium, address):
        cur = self.sydent.db.cursor()
        res = cur.execute("select sgAssoc from global_threepid_associations where "
                    "medium = ? and address = ? and notBefore > ? and notAfter < ? "
                    "order by ts desc limit 1",
            (medium, address, time_msec(), time_msec()))

        row = res.fetchone()

        if not row:
            return None

        sgAssocBytes = row[0]

        sgAssocJsonObj = json.loads(sgAssocBytes)

        sgAssoc = threePidAssocFromDict(sgAssocJsonObj)

        return sgAssoc

    def addAssociation(self, assoc, rawSgAssoc, originServer, originId, commit=True):
        """
        :param assoc: (sydent.threepid.GlobalThreepidAssociation) The association to add as a high level object
        :param sgAssoc The original raw bytes of the signed association
        :return:
        """
        cur = self.sydent.db.cursor()
        res = cur.execute("insert into global_threepid_associations "
                          "(medium, address, mxid, ts, notBefore, notAfter, originServer, originId, sgAssoc) values "
                          "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (assoc.medium, assoc.address, assoc.mxid, assoc.ts, assoc.not_before, assoc.not_after,
                          originServer, originId, rawSgAssoc))
        if commit:
            self.sydent.db.commit()

    def lastIdFromServer(self, server):
        cur = self.sydent.db.cursor()
        res = cur.execute("select max(originId),count(originId) from global_threepid_associations "
                          "where originServer = ?", (server,))
        row = res.fetchone()

        if row[1] == 0:
            return None

        return row[0]
