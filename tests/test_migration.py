import json
import os.path
from unittest.mock import patch

from twisted.trial import unittest

from sydent.db.migration import update_global_assoc, update_local_associations
from sydent.util import json_decoder
from sydent.util.emailutils import sendEmail
from sydent.util.hash import sha256_and_url_safe_base64
from tests.utils import make_sydent


class MigrationTestCase(unittest.TestCase):
    def calculate_lookup(self, address):
        cur = self.sydent.db.cursor()
        pepper_result = cur.execute("SELECT lookup_pepper from hashing_metadata")
        pepper = pepper_result.fetchone()[0]
        combo = "%s %s %s" % (address, "email", pepper)
        lookup_hash = sha256_and_url_safe_base64(combo)
        return lookup_hash

    def create_signedassoc(self, medium, address, mxid, ts, not_before, not_after):
        sgassoc = {
            "medium": medium,
            "address": address,
            "mxid": mxid,
            "ts": ts,
            "not_before": not_before,
            "not_after": not_after,
        }
        return sgassoc

    def setUp(self):
        # Create a new sydent
        config = {
            "general": {
                "templates.path": os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "res"
                ),
            },
            "crypto": {
                "ed25519.signingkey": "ed25519 0 FJi1Rnpj3/otydngacrwddFvwz/dTDsBv62uZDN2fZM"
            },
        }
        self.sydent = make_sydent(test_config=config)

        # create some local associations
        associations = []

        for i in range(15):
            if i < 10:
                address = "bob%d@example.com" % i
                associations.append(
                    {
                        "medium": "email",
                        "address": address,
                        "lookup_hash": self.calculate_lookup(address),
                        "mxid": "@bob%d:example.com" % i,
                        "ts": (i * 10000),
                        "not_before": 0,
                        "not_after": 99999999999,
                    }
                )
            else:
                # create some casefold-conflicting associations
                address = "BOB%d@example.com" % (i - 10)
                associations.append(
                    {
                        "medium": "email",
                        "address": address,
                        "lookup_hash": self.calculate_lookup(address),
                        "mxid": "@BOB%d:example.com" % (i - 10),
                        "ts": (i * 10000),
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
        originServer = self.sydent.server_name

        for i in range(15):
            if i < 10:
                address = "bob%d@example.com" % i
                mxid = "@bob%d:example.com" % i
                ts = 10000 * i
                associations.append(
                    {
                        "medium": "email",
                        "address": address,
                        "lookup_hash": self.calculate_lookup(address),
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
            else:
                # create some casefold-conflicting associations
                address = "BOB%d@example.com" % (i - 10)
                mxid = "@BOB%d:example.com" % (i - 10)
                ts = 10000 * i
                associations.append(
                    {
                        "medium": "email",
                        "address": address,
                        "lookup_hash": self.calculate_lookup(address),
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
            templateFile = self.sydent.get_branded_template(
                "matrix-org",
                "migration_template.eml",
                ("email", "email.template"),
            )
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
            self.assertIn("This is a notification", email_contents)

            # test email was sent
            smtp.sendmail.assert_called()

    def test_local_db_migration(self):
        with patch("sydent.util.emailutils.smtplib"):
            update_local_associations(self, self.sydent.db)

        cur = self.sydent.db.cursor()
        res = cur.execute("SELECT * FROM local_threepid_associations")

        # five addresses should have been deleted
        self.assertEqual(len(res.fetchall()), 10)

        # iterate through db and make sure all addresses are casefolded and hash matches casefolded address
        for row in res.fetchall():
            casefolded = row[2].casefold()
            self.assertEqual(row[2], casefolded)
            self.assertEqual(
                self.calculate_lookup(row[2]), self.calculate_lookup(casefolded)
            )

    def test_global_db_migration(self):
        with patch("sydent.util.emailutils.smtplib"):
            update_global_assoc(self, self.sydent.db)

        cur = self.sydent.db.cursor()
        res = cur.execute("SELECT * FROM global_threepid_associations")

        # five addresses should have been deleted
        self.assertEqual(len(res.fetchall()), 10)

        # iterate through db and make sure all addresses are casefolded and hash matches casefolded address
        # and make sure the casefolded address matches the address in sgAssoc
        for row in res.fetchall():
            casefolded = row[2].casefold()
            self.assertEqual(row[2], casefolded)
            self.assertEqual(
                self.calculate_lookup(row[2]), self.calculate_lookup(casefolded)
            )
            sgassoc = json_decoder.decode(row[9])
            self.assertEqual(row[2], sgassoc["address"])
