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

class HashingMetadataStore:
    def __init__(self, sydent):
        self.sydent = sydent

    def get_lookup_pepper(self):
        """Return the value of the current lookup pepper from the db
        
        :returns a pepper if it exists in the database, or None if one does
                 not exist
        """
        cur = self.sydent.db.cursor()
        res = cur.execute("select lookup_pepper from hashing_metadata")
        row = res.fetchone()

        if not row:
            return None
        return row[0]

    def store_lookup_pepper(self, lookup_pepper):
        """Stores a new lookup pepper in the hashing_metadata db table

        :param lookup_pepper: The pepper to store in the database
        :type lookup_pepper: str
        """
        cur = self.sydent.db.cursor()

        # Create or update lookup_pepper
        sql = (
            'INSERT OR REPLACE INTO hashing_metadata (id, lookup_pepper) '
            'VALUES (0, ?)'
        )
        cur.execute(sql, lookup_pepper)
        self.sydent.db.commit()

    def rehash_threepids(self, hashing_function, pepper):
        """Rehash all 3PIDs using a given hashing_function and pepper

        :param hashing_function: A function with single input and output strings
        :type hashing_function func(str) -> str

        :param pepper: A pepper to append to the end of the 3PID (after a space) before hashing
        :type pepper: str
        """
        self._rehash_threepids(hashing_function, pepper, "local_threepid_associations")
        self._rehash_threepids(hashing_function, pepper, "global_threepid_associations")

    def _rehash_threepids(self, hashing_function, pepper, table):
        """Rehash 3PIDs of a given table using a given hashing_function and pepper

        :param hashing_function: A function with single input and output strings
        :type hashing_function func(str) -> str

        :param pepper: A pepper to append to the end of the 3PID (after a space) before hashing
        :type pepper: str

        :param table: The database table to perform the rehashing on
        :type table: str
        """
        cur = self.sydent.db.cursor()

        # Get count of all 3PID records
        # Medium/address combos are marked as UNIQUE in the database
        sql = "SELECT COUNT(*) FROM %s" % table
        res = cur.execute(sql)
        row_count = res.fetchone()
        row_count = row_count[0]

        # Iterate through each medium, address combo, hash it,
        # and store in the db
        batch_size = 500
        while count < row_count:
            sql = (
                "SELECT medium, address FROM %s LIMIT %s OFFSET %s ORDER BY id" % 
                (table, batch_size, count)
            )
            res = cur.execute(sql)
            rows = res.fetchall()

            for medium, address in rows:
                # Skip broken db entry
                if not medium or not address:
                    continue

                # Combine the medium, address and pepper together in the
                # following form: "address medium pepper"
                # According to MSC2134: https://github.com/matrix-org/matrix-doc/pull/2134
                combo = "%s %s %s" % (address, medium, pepper)

                # Hash the resulting string
                result = hashing_function(combo)

                # Save the result to the DB
                sql = (
                    "UPDATE %s SET lookup_hash = ? "
                    "WHERE medium = ? AND address = ?"
                    % (table)
                )
                cur.execute(sql, (result, medium, address))

            count += len(rows)

            self.sydent.db.commit()
