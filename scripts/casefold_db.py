#!/usr/bin/env python
# Copyright 2021 The Matrix.org Foundation C.I.C.
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

import argparse
import json
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Set, Tuple

import signedjson.sign

from sydent.sydent import Sydent, parse_config_file
from sydent.util import json_decoder
from sydent.util.emailutils import sendEmail
from sydent.util.hash import sha256_and_url_safe_base64
from tests.utils import ResolvingMemoryReactorClock

EMAIL_SUBJECT = "No action required: we have changed the way your Matrix account and email address are associated"


def calculate_lookup_hash(sydent, address):
    cur = sydent.db.cursor()
    pepper_result = cur.execute("SELECT lookup_pepper from hashing_metadata")
    pepper = pepper_result.fetchone()[0]
    combo = "%s %s %s" % (address, "email", pepper)
    lookup_hash = sha256_and_url_safe_base64(combo)
    return lookup_hash


def update_local_associations(
    sydent,
    db: sqlite3.Connection,
    send_email: bool,
    dry_run: bool,
    test=False,
):
    """Update the DB table local_threepid_associations so that all stored
    emails are casefolded, and any duplicate mxid's associated with the
    given email are deleted.

    :return: None
    """
    cur = db.cursor()

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
        lookup_hash = calculate_lookup_hash(sydent, casefold_address)

        if casefold_address in associations:
            associations[casefold_address].append((address, mxid, lookup_hash))
        else:
            associations[casefold_address] = [(address, mxid, lookup_hash)]

    # list of arguments to update db with
    db_update_args: List[Tuple[str, str, str, str]] = []

    # list of mxids to delete
    to_delete: List[Tuple[str]] = []

    # The MXIDs associated with rows we're about to delete, indexed by the casefolded
    # address they're associated with.
    to_delete_mxids: Dict[str, Set[str]] = {}
    # The MXIDs associated with rows we're not going to delete, so we can compare the one
    # associated with a given casefolded address with the one(s) we want to delete for the
    # same address and figure out if we want to send them an email.
    to_keep_mxids: Dict[str, str] = {}

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
            to_delete_mxids[casefold_address] = set()
            to_keep_mxids[casefold_address] = assoc_tuples[0][1].lower()
            for address, mxid, _ in assoc_tuples[1:]:
                to_delete.append((address,))
                to_delete_mxids[casefold_address].add(mxid.lower())

    if not test:
        print(
            f"{len(to_delete)} rows to delete, {len(db_update_args)} rows to update in local_threepid_associations"
        )

    # Update the database before sending the emails, that way if the update fails the
    # affected users haven't been notified.
    if not dry_run:
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
        db.commit()

    # iterate through the mxids and send emails
    if send_email and not dry_run:
        for address, mxids in to_delete_mxids.items():
            for mxid in mxids:
                # If the MXID is one that will still be associated with this email address
                # after this run, don't send an email for it.
                if mxid == to_keep_mxids[address]:
                    continue

                # Send the email with exponential backoff - that way we don't stop
                # sending halfway through if the SMTP server rejects our email (e.g.
                # because of rate limiting). The alternative would mean the first
                # addresses of the list receive duplicate emails.
                def sendWithBackoff(backoff):
                    time.sleep(backoff)
                    try:
                        templateFile = sydent.get_branded_template(
                            None,
                            "migration_template.eml",
                            ("email", "email.template"),
                        )

                        sendEmail(
                            sydent,
                            templateFile,
                            address,
                            {"mxid": mxid, "subject_header_value": EMAIL_SUBJECT},
                        )
                        if not test:
                            print("Sent email to %s" % address)
                    except Exception:
                        if not test:
                            print(
                                "Failed to send email to %s, retrying in %ds"
                                % (address, backoff * 2)
                            )
                        sendWithBackoff(backoff * 2)

                sendWithBackoff(1 if not test else 0)


def update_global_associations(
    sydent,
    db: sqlite3.Connection,
    send_email: bool,
    dry_run: bool,
    test=False,
):
    """Update the DB table global_threepid_associations so that all stored
    emails are casefolded, the signed association is re-signed and any duplicate
    mxid's associated with the given email are deleted.

    :return: None
    """

    # get every row where the local server is origin server and medium is email
    origin_server = sydent.server_name
    medium = "email"

    cur = db.cursor()
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
        lookup_hash = calculate_lookup_hash(sydent, casefold_address)

        # update signed associations with new casefolded address and re-sign
        sg_assoc = json_decoder.decode(sg_assoc)
        sg_assoc["address"] = address.casefold()
        sg_assoc = json.dumps(
            signedjson.sign.sign_json(
                sg_assoc, sydent.server_name, sydent.keyring.ed25519
            )
        )

        if casefold_address in associations:
            associations[casefold_address].append(
                (address, mxid, lookup_hash, sg_assoc)
            )
        else:
            associations[casefold_address] = [(address, mxid, lookup_hash, sg_assoc)]

    # list of arguments to update db with
    db_update_args: List[Tuple[Any, str, str, str, str]] = []

    # list of mxids to delete
    to_delete: List[Tuple[str]] = []

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

    if not test:
        print(
            f"{len(to_delete)} rows to delete, {len(db_update_args)} rows to update in global_threepid_associations"
        )

    if not dry_run:
        if len(to_delete) > 0:
            cur.executemany(
                "DELETE FROM global_threepid_associations WHERE address = ?", to_delete
            )

        if len(db_update_args) > 0:
            cur.executemany(
                "UPDATE global_threepid_associations SET address = ?, lookup_hash = ?, sgAssoc = ? WHERE address = ? AND mxid = ?",
                db_update_args,
            )

        db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Casefold email addresses in database")
    parser.add_argument(
        "--no-email", action="store_true", help="run script but do not send emails"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run script but do not send emails or alter database",
    )

    parser.add_argument("config_path", help="path to the sydent configuration file")

    args = parser.parse_args()

    # if the path the user gives us doesn't work, find it for them
    if not os.path.exists(args.config_path):
        print(f"The config file '{args.config_path}' does not exist.")
        sys.exit(1)

    config = parse_config_file(args.config_path)

    reactor = ResolvingMemoryReactorClock()
    sydent = Sydent(config, reactor, False)

    update_global_associations(sydent, sydent.db, not args.no_email, args.dry_run)
    update_local_associations(sydent, sydent.db, not args.no_email, args.dry_run)
