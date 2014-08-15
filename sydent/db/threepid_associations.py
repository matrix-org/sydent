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


class LocalAssociationStore:
    def __init__(self, sydent):
        self.sydent = sydent

    def addOrUpdateAssociation(self, assoc):
        cur = self.sydent.db.cursor()

        # sqlite's support for upserts is atrocious
        cur.execute("insert or replace into local_threepid_associations "
                    "('medium', 'address', 'mxId', 'createdAt', 'expires')"
                    " values (?, ?, ?, ?, ?)",
            (assoc.medium, assoc.address, assoc.mxId, assoc.not_before, assoc.not_after))
        self.sydent.db.commit()