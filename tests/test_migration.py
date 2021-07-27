from tests.utils import make_sydent
from twisted.trial import unittest
from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.emailutils import sendEmail

class MigrationTestCase(unittest.TestCase):
  # create test instance of sydent
  def setUp(self):
  # Create a new sydent
    config = {
            "crypto": {
                "ed25519.signingkey": "ed25519 0 FJi1Rnpj3/otydngacrwddFvwz/dTDsBv62uZDN2fZM"
            }
    }
    self.sydent = make_sydent(test_config=config)

    def calculate_lookup(address):
      cur = self.sydent.db.cursor()
      pepper_result = cur.execute("SELECT lookup_pepper from hashing_metadata")
      pepper = pepper_result.fetchone()
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

  def test_migration(self):
    cur = self.sydent.db.cursor()

    res = cur.execute(
        "SELECT address, mxid FROM local_threepid_associations WHERE medium = 'email'"
        "ORDER BY ts DESC"
        )

    associations: Dict[str, List[Tuple[str, str, str]]] = {}

    # iterate through selected associations, casefold email, rehash it, and add to
    # associations dict
    for row in res.fetchall():
        casefold_address = row[0].casefold()

        # rehash the email since hash functions are case-sensitive
        pepper_result = cur.execute("SELECT lookup_pepper from hashing_metadata")
        pepper = pepper_result.fetchone()
        combo = "%s %s %s" % (casefold_address, "email", pepper)
        lookup_hash = sha256_and_url_safe_base64(combo)

        if casefold_address in associations:
            associations[casefold_address].append((row[0], row[1], lookup_hash))
        else:
            associations[casefold_address] = [(row[0], row[1], lookup_hash)]

    db_update_args: List[Tuple[str,str,str,str]] = []
    to_delete: List[str] = []

    for casefold_address, assoc_tuples in associations.items():
        db_update_args.append((casefold_address, assoc_tuples[0][2], assoc_tuples[0][0], assoc_tuples[0][1]))

        if len(assoc_tuples) > 1:
            # List of the MXIDs we need to tell the email address's owner they've been
            # disassociated from the address.
            mxids: List[str] = []

            # Iterate over all associations except for the first one, since we've already
            # processed it.
            for assoc_tuple in assoc_tuples[1:]:
                to_delete.append([assoc_tuple[0]])
                mxids.append(assoc_tuple[1])

            # Note: we could scope the mxids list outside of the for loop and process them
            # only after we've finished iterating.
            #send_mail(mxids)

    if len(to_delete) > 0:
        cur.executemany("DELETE FROM local_threepid_associations WHERE address = ?", to_delete)

    if len(db_update_args) > 0:
        cur.executemany(
            "UPDATE local_threepid_associations SET address = ?, lookup_hash = ? WHERE address = ? AND mxid = ?",
            db_update_args,
        )

    # We've finished updating the database, committing the transaction.
    self.sydent.db.commit()


