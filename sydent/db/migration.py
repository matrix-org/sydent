import json
import sqlite3

import signedjson.sign

from sydent.util import json_decoder
from sydent.util.emailutils import sendEmail


def update_local_associations(self, conn: sqlite3.Connection):
    """Update the DB table local_threepid_associations so that all stored
    emails are casefolded, and any duplicate mxid's associated with the
    given email are deleted.

    :return: None
    """
    cur = conn.cursor()

    res = cur.execute(
        "SELECT address, mxid FROM local_threepid_associations WHERE medium = 'email'"
        "ORDER BY ts DESC"
    )

    # a dict that associates an email address with correspoinding mxids and lookup hashes
    associations: Dict[str, List[Tuple[str, str, str]]] = {}

    # iterate through selected associations, casefold email, rehash it, and add to
    # associations dict
    for address, mxid in res.fetchall():
        casefold_address = address.casefold()

        # rehash email since hashes are case-sensitive
        lookup_hash = self.calculate_lookup(casefold_address)

        if casefold_address in associations:
            associations[casefold_address].append((address, mxid, lookup_hash))
        else:
            associations[casefold_address] = [(address, mxid, lookup_hash)]

    # list of arguments to update db with
    db_update_args: List[Tuple[str, str, str, str]] = []

    # list of mxids to delete
    to_delete: List[Tuple[str]] = []

    # list of mxids to send emails to letting them know the mxid has been deleted
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
            for address, mxid, _ in assoc_tuples[1:]:
                to_delete.append((address,))
                mxids.append((mxid, address))

    # iterate through the mxids and send email
    for mxid, address in mxids:
        templateFile = self.sydent.get_branded_template(
            "matrix-org",
            "migration_template.eml",
            ("email", "email.template"),
        )

        sendEmail(
            self.sydent,
            templateFile,
            address,
            {"mxid": "mxid", "subject_header_value": "MatrixID Update"},
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
    """Update the DB table global_threepid_associations so that all stored
    emails are casefolded, the signed association is re-signed and any duplicate
    mxid's associated with the given email are deleted.

    :return: None
    """

    # get every row where the local server is origin server and medium is email
    origin_server = self.sydent.server_name
    medium = "email"

    cur = self.sydent.db.cursor()
    res = cur.execute(
        "SELECT address, mxid, sgAssoc FROM global_threepid_associations WHERE medium = ?"
        "AND originServer = ? ORDER BY ts DESC",
        (medium, origin_server),
    )

    # dict that stores email address with mxid, email address, lookup hash, and
    # signed association
    associations: Dict[str, List[Tuple[str, str, str, str]]] = {}

    # iterate through selected associations, casefold email, rehash it, re-sign the
    # associations and add to associations dict
    for address, mxid, sg_assoc in res.fetchall():
        casefold_address = address.casefold()

        # rehash the email since hash functions are case-sensitive
        lookup_hash = self.calculate_lookup(casefold_address)

        # update signed associations with new casefolded address and re-sign
        sg_assoc = json_decoder.decode(sg_assoc)
        sg_assoc["address"] = address.casefold()
        sg_assoc = json.dumps(
            signedjson.sign.sign_json(
                sg_assoc, self.sydent.server_name, self.sydent.keyring.ed25519
            )
        )

        if casefold_address in associations:
            associations[casefold_address].append(
                (address, mxid, lookup_hash, sg_assoc)
            )
        else:
            associations[casefold_address] = [(address, mxid, lookup_hash, sg_assoc)]

    # list of arguments to update db with
    db_update_args: List[Tuple[str, str, str, str]] = []

    # list of mxids to delete
    to_delete: List[Tuple[str]] = []

    # list of mxids and addresses to send emails to letting them know the mxid
    # has been deleted
    mxids: List[Tuple[str]] = []

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
            for address, mxid, _, _ in assoc_tuples[1:]:
                to_delete.append((address,))
                mxids.append((mxid, address))

    # iterate through the mxids and send email
    for mxid, address in mxids:
        templateFile = self.sydent.get_branded_template(
            "matrix-org",
            "migration_template.eml",
            ("email", "email.template"),
        )

        sendEmail(
            self.sydent,
            templateFile,
            address,
            {"mxid": "mxid", "subject_header_value": "MatrixID Update"},
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
