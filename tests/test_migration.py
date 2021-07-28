from tests.utils import make_sydent
from twisted.trial import unittest
from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.emailutils import sendEmail
import os.path
from sydent.db.migration import update_assosc
from unittest.mock import patch

class MigrationTestCase(unittest.TestCase):
  # create test instance of sydent
  def setUp(self):
  # Create a new sydent
    config = {
            "general": {
                "templates.path": os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "res"
                ),
            },
    }
    self.sydent = make_sydent(test_config=config)

    def calculate_lookup(address):
      cur = self.sydent.db.cursor()
      pepper_result = cur.execute("SELECT lookup_pepper from hashing_metadata")
      pepper = pepper_result.fetchone()[0]
      combo = "%s %s %s" % (address, "email", pepper)
      lookup_hash = sha256_and_url_safe_base64(combo)
      return lookup_hash

    # create some associations
    associations = []

    for i in range(15):
      if i < 10:
        address = "bob%d@example.com" % i
        associations.append({"medium":"email",
                             "address":address,
                             "lookup_hash":calculate_lookup(address),
                             "mxid":"@bob%d:example.com" % i,
                             "ts":(i * 10000),
                             "not_before":0,
                             "not_after":99999999999,})
      else:
        # create some casefold-conflicting associations
        address = "BOB%d@example.com" % (i-10)
        associations.append({"medium":"email",
                             "address":address,
                             "lookup_hash":calculate_lookup(address),
                             "mxid":"@BOB%d:example.com" % (i-10),
                             "ts":(i * 10000),
                             "not_before":0,
                             "not_after":99999999999,})

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

  def test_migration_email(self):
    with patch("sydent.util.emailutils.smtplib") as smtplib:
        templateFile = self.sydent.get_branded_template(
            "matrix-org",
            "migration_template.eml",
            ("email", "email.template"),
        )
        sendEmail(self.sydent, templateFile, "bob@example.com", {"mxid":"blob@blob", "subject_header_value": "MatrixID Deletion"})
        smtp = smtplib.SMTP.return_value
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertIn("This is a notification", email_contents)