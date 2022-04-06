# Copyright 2021 Matrix.org Foundation C.I.C.
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
import json
from unittest.mock import patch

from twisted.trial import unittest

from scripts.casefold_db import (
    calculate_lookup_hash,
    update_global_associations,
    update_local_associations,
)
from sydent.util import json_decoder
from sydent.util.emailutils import sendEmail
from tests.utils import make_sydent


class MigrationTestCase(unittest.TestCase):
    def create_signedassoc(self, medium, address, mxid, ts, not_before, not_after):
        return {
            "medium": medium,
            "address": address,
            "mxid": mxid,
            "ts": ts,
            "not_before": not_before,
            "not_after": not_after,
        }

    def setUp(self):
        # Create a new sydent
        self.sydent = make_sydent()

        # create some local associations
        associations = []

        for i in range(10):
            address = "bob%d@example.com" % i
            associations.append(
                {
                    "medium": "email",
                    "address": address,
                    "lookup_hash": calculate_lookup_hash(self.sydent, address),
                    "mxid": "@bob%d:example.com" % i,
                    "ts": (i * 10000),
                    "not_before": 0,
                    "not_after": 99999999999,
                }
            )
        # create some casefold-conflicting associations
        for i in range(5):
            address = "BOB%d@example.com" % i
            associations.append(
                {
                    "medium": "email",
                    "address": address,
                    "lookup_hash": calculate_lookup_hash(self.sydent, address),
                    "mxid": "@otherbob%d:example.com" % i,
                    "ts": (i * 10000),
                    "not_before": 0,
                    "not_after": 99999999999,
                }
            )

        associations.append(
            {
                "medium": "email",
                "address": "BoB4@example.com",
                "lookup_hash": calculate_lookup_hash(self.sydent, "BoB4@example.com"),
                "mxid": "@otherbob4:example.com",
                "ts": 42000,
                "not_before": 0,
                "not_after": 99999999999,
            }
        )

        # add all associations to db
        cur = self.sydent.db.cursor()

        cur.executemany(
            "INSERT INTO  local_threepid_associations "
            "(medium, address, lookup_hash, mxid, ts, notBefore, notAfter) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    assoc["medium"],
                    assoc["address"],
                    assoc["lookup_hash"],
                    assoc["mxid"],
                    assoc["ts"],
                    assoc["not_before"],
                    assoc["not_after"],
                )
                for assoc in associations
            ],
        )

        self.sydent.db.commit()

        # create some global associations
        associations = []
        originServer = self.sydent.config.general.server_name

        for i in range(10):
            address = "bob%d@example.com" % i
            mxid = "@bob%d:example.com" % i
            ts = 10000 * i
            associations.append(
                {
                    "medium": "email",
                    "address": address,
                    "lookup_hash": calculate_lookup_hash(self.sydent, address),
                    "mxid": mxid,
                    "ts": ts,
                    "not_before": 0,
                    "not_after": 99999999999,
                    "originServer": originServer,
                    "originId": i,
                    "sgAssoc": json.dumps(
                        self.create_signedassoc(
                            "email", address, mxid, ts, 0, 99999999999
                        )
                    ),
                }
            )
        # create some casefold-conflicting associations
        for i in range(5):
            address = "BOB%d@example.com" % i
            mxid = "@BOB%d:example.com" % i
            ts = 10000 * i
            associations.append(
                {
                    "medium": "email",
                    "address": address,
                    "lookup_hash": calculate_lookup_hash(self.sydent, address),
                    "mxid": mxid,
                    "ts": ts + 1,
                    "not_before": 0,
                    "not_after": 99999999999,
                    "originServer": originServer,
                    "originId": i + 10,
                    "sgAssoc": json.dumps(
                        self.create_signedassoc(
                            "email", address, mxid, ts, 0, 99999999999
                        )
                    ),
                }
            )

        # add all associations to db
        cur = self.sydent.db.cursor()

        cur.executemany(
            "INSERT INTO global_threepid_associations "
            "(medium, address, lookup_hash, mxid, ts, notBefore, notAfter, originServer, originId, sgAssoc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    assoc["medium"],
                    assoc["address"],
                    assoc["lookup_hash"],
                    assoc["mxid"],
                    assoc["ts"],
                    assoc["not_before"],
                    assoc["not_after"],
                    assoc["originServer"],
                    assoc["originId"],
                    assoc["sgAssoc"],
                )
                for assoc in associations
            ],
        )

        self.sydent.db.commit()

    def test_migration_email(self):
        with patch("sydent.util.emailutils.smtplib") as smtplib:
            # self.sydent.config.email.template is deprecated
            if self.sydent.config.email.template is None:
                templateFile = self.sydent.get_branded_template(
                    None,
                    "migration_template.eml",
                )
            else:
                templateFile = self.sydent.config.email.template

            sendEmail(
                self.sydent,
                templateFile,
                "bob@example.com",
                {
                    "mxid": "@bob:example.com",
                    "subject_header_value": "MatrixID Deletion",
                },
            )
            smtp = smtplib.SMTP.return_value
            email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
            self.assertIn("In the past", email_contents)

            # test email was sent
            smtp.sendmail.assert_called()

    def test_local_db_migration(self):
        with patch("sydent.util.emailutils.smtplib") as smtplib:
            update_local_associations(
                self.sydent,
                self.sydent.db,
                send_email=True,
                dry_run=False,
                test=True,
            )

        # test 5 emails were sent
        smtp = smtplib.SMTP.return_value
        self.assertEqual(smtp.sendmail.call_count, 5)

        # don't send emails to people who weren't affected
        self.assertNotIn(
            smtp.sendmail.call_args_list,
            [
                "bob5@example.com",
                "bob6@example.com",
                "bob7@example.com",
                "bob8@example.com",
                "bob9@example.com",
            ],
        )

        # make sure someone who is affected gets email
        self.assertIn("bob4@example.com", smtp.sendmail.call_args_list[0][0])

        cur = self.sydent.db.cursor()
        res = cur.execute("SELECT * FROM local_threepid_associations")

        db_state = res.fetchall()

        # five addresses should have been deleted
        self.assertEqual(len(db_state), 10)

        # iterate through db and make sure all addresses are casefolded and hash matches casefolded address
        for row in db_state:
            casefolded = row[2].casefold()
            self.assertEqual(row[2], casefolded)
            self.assertEqual(
                calculate_lookup_hash(self.sydent, row[2]),
                calculate_lookup_hash(self.sydent, casefolded),
            )

    def test_global_db_migration(self):
        update_global_associations(
            self.sydent,
            self.sydent.db,
            dry_run=False,
        )

        cur = self.sydent.db.cursor()
        res = cur.execute("SELECT * FROM global_threepid_associations")

        db_state = res.fetchall()

        # five addresses should have been deleted
        self.assertEqual(len(db_state), 10)

        # iterate through db and make sure all addresses are casefolded and hash matches casefolded address
        # and make sure the casefolded address matches the address in sgAssoc
        for row in db_state:
            casefolded = row[2].casefold()
            self.assertEqual(row[2], casefolded)
            self.assertEqual(
                calculate_lookup_hash(self.sydent, row[2]),
                calculate_lookup_hash(self.sydent, casefolded),
            )
            sgassoc = json_decoder.decode(row[9])
            self.assertEqual(row[2], sgassoc["address"])

    def test_local_no_email_does_not_send_email(self):
        with patch("sydent.util.emailutils.smtplib") as smtplib:
            update_local_associations(
                self.sydent,
                self.sydent.db,
                send_email=False,
                dry_run=False,
                test=True,
            )
            smtp = smtplib.SMTP.return_value

            # test no emails were sent
            self.assertEqual(smtp.sendmail.call_count, 0)

    def test_dry_run_does_nothing(self):
        # reset DB
        self.setUp()

        cur = self.sydent.db.cursor()

        # grab a snapshot of global table before running script
        res1 = cur.execute("SELECT mxid FROM global_threepid_associations")
        list1 = res1.fetchall()

        with patch("sydent.util.emailutils.smtplib") as smtplib:
            update_global_associations(
                self.sydent,
                self.sydent.db,
                dry_run=True,
            )

        # test no emails were sent
        smtp = smtplib.SMTP.return_value
        self.assertEqual(smtp.sendmail.call_count, 0)

        res2 = cur.execute("SELECT mxid FROM global_threepid_associations")
        list2 = res2.fetchall()

        self.assertEqual(list1, list2)

        # grab a snapshot of local table db before running script
        res3 = cur.execute("SELECT mxid FROM local_threepid_associations")
        list3 = res3.fetchall()

        with patch("sydent.util.emailutils.smtplib") as smtplib:
            update_local_associations(
                self.sydent,
                self.sydent.db,
                send_email=True,
                dry_run=True,
                test=True,
            )

        # test no emails were sent
        smtp = smtplib.SMTP.return_value
        self.assertEqual(smtp.sendmail.call_count, 0)

        res4 = cur.execute("SELECT mxid FROM local_threepid_associations")
        list4 = res4.fetchall()
        self.assertEqual(list3, list4)
