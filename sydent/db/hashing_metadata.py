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
from sqlite3 import Cursor
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from typing_extensions import Literal

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class HashingMetadataStore:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        self._cached_lookup_pepper: Optional[str] = None

    def get_lookup_pepper(self) -> Optional[str]:
        """Return the value of the current lookup pepper from the db

        :return: A pepper if it exists in the database, or None if one does
                 not exist
        """

        if self._cached_lookup_pepper is not None:
            return self._cached_lookup_pepper

        cur = self.sydent.db.cursor()
        res = cur.execute("select lookup_pepper from hashing_metadata")
        # Annotation safety: lookup_pepper is marked as varchar(256) in the
        # schema, so could be null. I.e. `row` should strictly be
        # Optional[Tuple[Optional[str]].
        # But I think the application code is such that either
        #  - hashing_metadata contains no rows
        #  - or it contains exactly one row with a nonnull lookup_pepper.
        row: Optional[Tuple[str]] = res.fetchone()

        if not row:
            return None

        pepper = row[0]

        # Ensure we're dealing with unicode.
        if isinstance(pepper, bytes):
            pepper = pepper.decode("UTF-8")

        self._cached_lookup_pepper = pepper

        return pepper

    def store_lookup_pepper(
        self, hashing_function: Callable[[str], str], pepper: str
    ) -> None:
        """Stores a new lookup pepper in the hashing_metadata db table and rehashes all 3PIDs

        :param hashing_function: A function with single input and output strings

        :param pepper: The pepper to store in the database
        """
        cur = self.sydent.db.cursor()

        # Create or update lookup_pepper
        sql = (
            "INSERT OR REPLACE INTO hashing_metadata (id, lookup_pepper) "
            "VALUES (0, ?)"
        )
        cur.execute(sql, (pepper,))

        # Hand the cursor to each rehashing function
        # Each function will queue some rehashing db transactions
        self._rehash_threepids(
            cur, hashing_function, pepper, "local_threepid_associations"
        )
        self._rehash_threepids(
            cur, hashing_function, pepper, "global_threepid_associations"
        )

        # Commit the queued db transactions so that adding a new pepper and hashing is atomic
        self.sydent.db.commit()

        # Update the cached pepper (only once the transaction has committed successfully!)
        self._cached_lookup_pepper = pepper

    def _rehash_threepids(
        self,
        cur: Cursor,
        hashing_function: Callable[[str], str],
        pepper: str,
        table: Literal["local_threepid_associations", "global_threepid_associations"],
    ) -> None:
        """Rehash 3PIDs of a given table using a given hashing_function and pepper

        A database cursor `cur` must be passed to this function. After this function completes,
        the calling function should make sure to call self`self.sydent.db.commit()` to commit
        the made changes to the database.

        :param cur: Database cursor
        :param hashing_function: A function with single input and output strings
        :param pepper: A pepper to append to the end of the 3PID (after a space) before hashing
        :param table: The database table to perform the rehashing on
        """

        # Get count of all 3PID records
        # Medium/address combos are marked as UNIQUE in the database
        sql = "SELECT COUNT(*) FROM %s" % table
        res = cur.execute(sql)
        row: Tuple[int] = res.fetchone()
        row_count = row[0]

        # Iterate through each medium, address combo, hash it,
        # and store in the db
        batch_size = 500
        count = 0
        while count < row_count:
            sql = "SELECT medium, address FROM %s ORDER BY id LIMIT %s OFFSET %s" % (
                table,
                batch_size,
                count,
            )
            res = cur.execute(sql)
            rows: List[Tuple[str, str]] = res.fetchall()

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
                    "WHERE medium = ? AND address = ?" % table
                )
                # Lines up the query to be executed on commit
                cur.execute(sql, (result, medium, address))

            count += len(rows)
