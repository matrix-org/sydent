# Copyright 2014 OpenMarket Ltd
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

import logging
import os
import sqlite3
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class SqliteDatabase:
    def __init__(self, syd: "Sydent") -> None:
        self.sydent = syd

        dbFilePath = self.sydent.config.database.database_path
        logger.info("Using DB file %s", dbFilePath)

        self.db = sqlite3.connect(dbFilePath)
        curVer = self._getSchemaVersion()

        # We always run the schema files if the version is zero: either the db is
        # completely empty and schema-less or it has the v0 schema, which is safe to
        # replay the schema files. The files in the sql directory are the v0 schema, so
        # a new installations will start as v0 then be upgraded to the current version.
        if curVer == 0:
            self._createSchema()
        self._upgradeSchema()

    def _createSchema(self) -> None:
        logger.info("Running schema files...")
        schemaDir = os.path.dirname(__file__)

        c = self.db.cursor()

        for f in os.listdir(schemaDir):
            if not f.endswith(".sql"):
                continue
            scriptPath = os.path.join(schemaDir, f)
            fp = open(scriptPath, "r")
            try:
                logger.info("Importing %s", scriptPath)
                c.executescript(fp.read())
            except Exception:
                logger.error("Error importing %s", scriptPath)
                raise
            fp.close()

        c.close()
        self.db.commit()

    def _upgradeSchema(self) -> None:
        curVer = self._getSchemaVersion()

        if curVer < 1:
            cur = self.db.cursor()

            # add auto_increment to the primary key of local_threepid_associations to ensure ids are never re-used,
            # allow the mxid column to be null to represent the deletion of a binding
            # and remove not null constraints on ts, notBefore and notAfter (again for when a binding has been deleted
            # and these wouldn't be very meaningful)
            logger.info("Migrating schema from v0 to v1")
            cur.execute("DROP INDEX IF EXISTS medium_address")
            cur.execute("DROP INDEX IF EXISTS local_threepid_medium_address")
            cur.execute(
                "ALTER TABLE local_threepid_associations RENAME TO old_local_threepid_associations"
            )
            cur.execute(
                "CREATE TABLE local_threepid_associations (id integer primary key autoincrement, "
                "medium varchar(16) not null, "
                "address varchar(256) not null, "
                "mxid varchar(256), "
                "ts integer, "
                "notBefore bigint, "
                "notAfter bigint)"
            )
            cur.execute(
                "INSERT INTO local_threepid_associations (medium, address, mxid, ts, notBefore, notAfter) "
                "SELECT medium, address, mxid, ts, notBefore, notAfter FROM old_local_threepid_associations"
            )
            cur.execute(
                "CREATE UNIQUE INDEX local_threepid_medium_address on local_threepid_associations(medium, address)"
            )
            cur.execute("DROP TABLE old_local_threepid_associations")

            # same autoincrement for global_threepid_associations (fields stay non-nullable because we don't need
            # entries in this table for deletions, we can just delete the rows)
            cur.execute("DROP INDEX IF EXISTS global_threepid_medium_address")
            cur.execute("DROP INDEX IF EXISTS global_threepid_medium_lower_address")
            cur.execute("DROP INDEX IF EXISTS global_threepid_originServer_originId")
            cur.execute("DROP INDEX IF EXISTS medium_lower_address")
            cur.execute("DROP INDEX IF EXISTS threepid_originServer_originId")
            cur.execute(
                "ALTER TABLE global_threepid_associations RENAME TO old_global_threepid_associations"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS global_threepid_associations "
                "(id integer primary key autoincrement, "
                "medium varchar(16) not null, "
                "address varchar(256) not null, "
                "mxid varchar(256) not null, "
                "ts integer not null, "
                "notBefore bigint not null, "
                "notAfter integer not null, "
                "originServer varchar(255) not null, "
                "originId integer not null, "
                "sgAssoc text not null)"
            )
            cur.execute(
                "INSERT INTO global_threepid_associations "
                "(medium, address, mxid, ts, notBefore, notAfter, originServer, originId, sgAssoc) "
                "SELECT medium, address, mxid, ts, notBefore, notAfter, originServer, originId, sgAssoc "
                "FROM old_global_threepid_associations"
            )
            cur.execute(
                "CREATE INDEX global_threepid_medium_address on global_threepid_associations (medium, address)"
            )
            cur.execute(
                "CREATE INDEX global_threepid_medium_lower_address on "
                "global_threepid_associations (medium, lower(address))"
            )
            cur.execute(
                "CREATE UNIQUE INDEX global_threepid_originServer_originId on "
                "global_threepid_associations (originServer, originId)"
            )
            cur.execute("DROP TABLE old_global_threepid_associations")
            self.db.commit()
            logger.info("v0 -> v1 schema migration complete")
            self._setSchemaVersion(1)

        if curVer < 2:
            logger.info("Migrating schema from v1 to v2")
            cur = self.db.cursor()
            cur.execute(
                "CREATE INDEX threepid_validation_sessions_mtime ON threepid_validation_sessions(mtime)"
            )
            self.db.commit()
            logger.info("v1 -> v2 schema migration complete")
            self._setSchemaVersion(2)

        if curVer < 3:
            cur = self.db.cursor()

            # Add lookup_hash columns to threepid association tables
            cur.execute(
                "ALTER TABLE local_threepid_associations "
                "ADD COLUMN lookup_hash VARCHAR(256)"
            )
            cur.execute(
                "ALTER TABLE global_threepid_associations "
                "ADD COLUMN lookup_hash VARCHAR(256)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS lookup_hash_medium "
                "on global_threepid_associations "
                "(lookup_hash, medium)"
            )

            # Create hashing_metadata table to store the current lookup_pepper
            cur.execute(
                "CREATE TABLE IF NOT EXISTS hashing_metadata ("
                "id integer primary key, "
                "lookup_pepper varchar(256)"
                ")"
            )

            self.db.commit()
            logger.info("v2 -> v3 schema migration complete")
            self._setSchemaVersion(3)

        if curVer < 4:
            cur = self.db.cursor()
            cur.execute(
                "CREATE TABLE accounts(user_id TEXT NOT NULL PRIMARY KEY, created_ts BIGINT NOT NULL, consent_version TEXT)"
            )
            cur.execute(
                "CREATE TABLE tokens(token TEXT NOT NULL PRIMARY KEY, user_id TEXT NOT NULL)"
            )
            cur.execute(
                "CREATE TABLE accepted_terms_urls(user_id TEXT NOT NULL, url TEXT NOT NULL)"
            )
            cur.execute(
                "CREATE UNIQUE INDEX accepted_terms_urls_idx ON accepted_terms_urls (user_id, url)"
            )
            self.db.commit()
            logger.info("v3 -> v4 schema migration complete")
            self._setSchemaVersion(4)

        if curVer < 5:
            # Fix lookup_hash index for selecting on mxid instead of medium
            cur = self.db.cursor()
            cur.execute("DROP INDEX IF EXISTS lookup_hash_medium")
            cur.execute(
                "CREATE INDEX global_threepid_lookup_hash ON global_threepid_associations(lookup_hash)"
            )
            self.db.commit()
            logger.info("v4 -> v5 schema migration complete")
            self._setSchemaVersion(5)

    def _getSchemaVersion(self) -> int:
        cur = self.db.cursor()
        cur.execute("PRAGMA user_version")
        row: Tuple[int] = cur.fetchone()
        return row[0]

    def _setSchemaVersion(self, ver: int) -> None:
        cur = self.db.cursor()
        # NB. pragma doesn't support variable substitution so we
        # do it in python (as a decimal so we don't risk SQL injection)
        cur.execute("PRAGMA user_version = %d" % (ver,))
