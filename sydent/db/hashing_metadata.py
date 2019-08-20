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

# Actions on the hashing_metadata table which is defined in the migration process in
# sqlitedb.py

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

    def store_lookup_pepper(self, hashing_function, pepper):
        """Stores a new lookup pepper in the hashing_metadata db table and rehashes all 3PIDs

        :param hashing_function: A function with single input and output strings
        :type hashing_function func(str) -> str

        :param pepper: The pepper to store in the database
        :type pepper: str
        """
        cur = self.sydent.db.cursor()

        # Create or update lookup_pepper
        sql = (
            'INSERT OR REPLACE INTO hashing_metadata (id, lookup_pepper) '
            'VALUES (0, ?)'
        )
        cur.execute(sql, (pepper,))

        # Hand the cursor to each rehashing function
        # Each function will queue some rehashing db transactions
        self._rehash_threepids(cur, hashing_function, pepper, "local_threepid_associations")
        self._rehash_threepids(cur, hashing_function, pepper, "global_threepid_associations")

        # Commit the queued db transactions so that adding a new pepper and hashing is atomic
        self.sydent.db.commit()

    def _rehash_threepids(self, cur, hashing_function, pepper, table):
        """Rehash 3PIDs of a given table using a given hashing_function and pepper

        A database cursor `cur` must be passed to this function. After this function completes,
        the calling function should make sure to call self`self.sydent.db.commit()` to commit
        the made changes to the database.

        :param cur: Database cursor
        :type cur:

        :param hashing_function: A function with single input and output strings
        :type hashing_function func(str) -> str

        :param pepper: A pepper to append to the end of the 3PID (after a space) before hashing
        :type pepper: str

        :param table: The database table to perform the rehashing on
        :type table: str
        """

        # Get count of all 3PID records
        # Medium/address combos are marked as UNIQUE in the database
        sql = "SELECT COUNT(*) FROM %s" % table
        res = cur.execute(sql)
        row_count = res.fetchone()
        row_count = row_count[0]

        # Iterate through each medium, address combo, hash it,
        # and store in the db
        batch_size = 500
        count = 0
        while count < row_count:
            sql = (
                "SELECT medium, address FROM %s ORDER BY id LIMIT %s OFFSET %s" %
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
                    % table
                )
                # Lines up the query to be executed on commit
                cur.execute(sql, (result, medium, address))

            count += len(rows)
