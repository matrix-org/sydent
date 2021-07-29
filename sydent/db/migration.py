from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.emailutils import sendEmail
import os.path
import sqlite3
from sydent.util import json_decoder
import json
import signedjson.sign


def update_assosc(self, conn: sqlite3.Connection):
    # from table local_threepid_associations, select all associations where the medium is 'email'
    cur = conn.cursor()

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
        pepper = pepper_result.fetchone()[0]
        combo = "%s %s %s" % (casefold_address, "email", pepper)
        lookup_hash = sha256_and_url_safe_base64(combo)

        if casefold_address in associations:
            associations[casefold_address].append((row[0], row[1], lookup_hash))
        else:
            associations[casefold_address] = [(row[0], row[1], lookup_hash)]

    db_update_args: List[Tuple[str, str, str, str]] = []
    to_delete: List[str] = []
    mxids: List[str] = []

    for casefold_address, assoc_tuples in associations.items():
        db_update_args.append(
            (
                casefold_address,
                assoc_tuples[0][2],
                assoc_tuples[0][0],
                assoc_tuples[0][1],
            )
        )

        if len(assoc_tuples) > 1:
            # Iterate over all associations except for the first one, since we've already
            # processed it.
            for assoc_tuple in assoc_tuples[1:]:
                to_delete.append([assoc_tuple[0]])
                mxids.append(assoc_tuple[1])

    # iterate through the mxids and send email
    for mxid in mxids:
        templateFile = self.sydent.get_branded_template(
            "matrix-org",
            "migration_template.eml",
            ("email", "email.template"),
        )
        res = cur.execute(
            "SELECT address FROM local_threepid_associations WHERE mxid = ?", (mxid,)
        )
        address = res.fetchone()[0]
        sendEmail(
            self.sydent,
            templateFile,
            address,
            {"mxid": "mxid", "subject_header_value": "MatrixID Deletion"},
        )

    if len(to_delete) > 0:
        cur.executemany(
            "DELETE FROM local_threepid_associations WHERE address = ?", to_delete
        )

    if len(db_update_args) > 0:
        cur.executemany(
            "UPDATE local_threepid_associations SET address = ?, lookup_hash = ? WHERE address = ? AND mxid = ?",
            db_update_args,
        )

    # We've finished updating the database, committing the transaction.
    conn.commit()


def update_global_assoc(self, conn: sqlite3.Connection):
    # get every row where the local server is origin server and medium is email
        originServer = self.sydent.server_name
        medium = "email"

        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT address, mxid, sgAssoc FROM global_threepid_associations WHERE medium = ?"
            "AND originServer = ? ORDER BY ts DESC",
            (medium, originServer),
        )

        associations: Dict[str, List[Tuple[str, str, str]]] = {}

        # iterate through selected associations, casefold email, rehash it, and add to
        # associations dict
        for row in res.fetchall():
            casefold_address = row[0].casefold()

            # rehash the email since hash functions are case-sensitive
            lookup_hash = self.calculate_lookup(casefold_address)

            # update associations with new casefolded address and re-sign
            sgassoc = json_decoder.decode(row[2])
            sgassoc["address"] = row[0].casefold()
            sgAssoc = json.dumps(
                signedjson.sign.sign_json(
                    sgassoc, self.sydent.server_name, self.sydent.keyring.ed25519
                )
            )

            if casefold_address in associations:
                associations[casefold_address].append(
                    (row[0], row[1], lookup_hash, sgAssoc)
                )
            else:
                associations[casefold_address] = [
                    (row[0], row[1], lookup_hash, sgAssoc)
                ]

        db_update_args: List[Tuple[str, str, str, str]] = []
        to_delete: List[str] = []
        mxids: List[str] = []

        for casefold_address, assoc_tuples in associations.items():
            db_update_args.append(
                (
                    casefold_address,
                    assoc_tuples[0][2],
                    assoc_tuples[0][3],
                    assoc_tuples[0][0],
                    assoc_tuples[0][1],
                )
            )

            if len(assoc_tuples) > 1:
                # Iterate over all associations except for the first one, since we've already
                # processed it.
                for assoc_tuple in assoc_tuples[1:]:
                    to_delete.append([assoc_tuple[0]])
                    mxids.append(assoc_tuple[1])

        # iterate through the mxids and send email
        for mxid in mxids:
            templateFile = self.sydent.get_branded_template(
                "matrix-org",
                "migration_template.eml",
                ("email", "email.template"),
            )
            res = cur.execute(
                "SELECT address FROM local_threepid_associations WHERE mxid = ?", (mxid,)
            )
            address = res.fetchone()[0]

            sendEmail(
                self.sydent,
                templateFile,
                address,
                {"mxid": "mxid", "subject_header_value": "MatrixID Deletion"},
            )

        if len(to_delete) > 0:
            cur.executemany(
                "DELETE FROM global_threepid_associations WHERE address = ?", to_delete
            )

        if len(db_update_args) > 0:
            cur.executemany(
                "UPDATE global_threepid_associations SET address = ?, lookup_hash = ?, sgAssoc = ? WHERE address = ? AND mxid = ?",
                db_update_args,
            )

        conn.commit()
