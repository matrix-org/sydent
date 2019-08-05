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

    def retrieve_value(self, name)
        """Return a value from the hashing_metadata table
        
        :param name: The name of the db column to return the value for
        :type name: str

        :returns a value corresponding to the specified name, or None if a
        value does not exist
        """
        cur = self.sydent.db.cursor()
        res = cur.execute("select %s from hashing_metadata" % name)
        row = res.fetchone()

        if not row:
            return None

        return row[0]

    def is_new(self, name, value):
        """
        Returns whether a provided value does NOT match a value stored in the
        database under the specified db column name

        :param name: The name of the db column to check
        :type name: str

        :param value: The value to check against

        :returns a boolean that is true if the the provided value and the
        value of the item under the named db column is different
        :rtype: bool
        """
        db_value = self.retrieve_value(name)
        if not value:
            return False
        return value != db_value

    def store_values(self, names_and_values):
        """Stores values in the hashing_metadata table under the named columns

        :param names_and_values: Column names and associated values to store
                                 in the database
        :type names_and_values: Dict
        """
        cur = self.sydent.db.cursor()

        columns = ', '.join(names_and_values.keys())
        values = ', '.join('?' * len(names_and_values))
        sql = 'INSERT INTO hashing_metadata ({}) VALUES ({})'.format(columns, values)

        cur.execute(sql)
        self.sydent.db.commit()

    def rehash_threepids(self, hashing_function, pepper):
        """Rehash all 3PIDs using a given hashing_function and pepper

        :param hashing_function: A function with single input and output strings
        :type hashing_function func(str) -> str

        :param pepper: A pepper to append to the end of the 3PID (after a space) before hashing.
        :type pepper: str
        """
        self._rehash_threepids(hashing_function, pepper, "local_threepid_associations")
        self._rehash_threepids(hashing_function, pepper, "global_threepid_associations")

    def _rehash_threepids(self, hashing_function, pepper, table):
        """Rehash 3PIDs of a given table using a given hashing_function and pepper

        :param hashing_function: A function with single input and output strings
        :type hashing_function func(str) -> str

        :param pepper: A pepper to append to the end of the 3PID (after a space) before hashing.
        :type pepper: str

        :param table: The database table to perform the rehashing on
        :type table: str
        """
        # Pull items from the database
        cur = self.sydent.db.cursor()

        # Medium/address combos are marked as UNIQUE in the database
        sql = "SELECT medium, address FROM %s" % table
        res = cur.execute(sql)
        rows = res.fetchall()

        batch_size = 500
        count = 0
        while count < len(rows):
            for medium, address in rows[count:count+batch_size]:
                # Combine the medium, address and pepper together in the following form:
                # "address medium pepper"
                # According to MSC2134: https://github.com/matrix-org/matrix-doc/blob/hs/hash-identity/proposals/2134-identity-hash-lookup.md
                combo = "%s %s %s" % (address, medium, pepper)

                # Hash the resulting string
                result = hashing_function(combo)

                # Save the result to the DB
                sql = (
                    "UPDATE %s SET hash = '%s' "
                    "WHERE medium = %s AND address = %s"
                    % (table, result, medium, address)
                )
                cur.execute(sql)

            self.sydent.db.commit()

