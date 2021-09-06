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
from typing import Any, Dict, List, Tuple

import attr
import signedjson.sign

from sydent.sydent import Sydent, parse_config_file
from sydent.util import json_decoder
from sydent.util.emailutils import EmailSendException, sendEmail
from sydent.util.hash import sha256_and_url_safe_base64
from tests.utils import ResolvingMemoryReactorClock

EMAIL_SUBJECT = "No action required: we have changed the way your Matrix account and email address are associated"

# Maximum number of attempts to send an email.
MAX_ATTEMPTS_FOR_EMAIL = 10


@attr.s(auto_attribs=True)
class UpdateDelta:
    """A row to update in the local_threepid_associations table."""
    address: str
    mxid: str
    lookup_hash: str


@attr.s(auto_attribs=True)
class DeleteDelta:
    """A row to delete from the local_threepid_associations table."""
    address: str
    mxid: str


@attr.s(auto_attribs=True)
class Delta:
    """Delta to apply to the local_threepid_associations table for a single
    case-insensitive email address.
    """
    to_update: UpdateDelta
    to_delete: List[DeleteDelta] = []


class CantSendEmailException(Exception):
    """Raised when we didn't succeed to send an email after MAX_ATTEMPTS_FOR_EMAIL
    attempts.
    """
    pass


def calculate_lookup_hash(sydent, address):
    cur = sydent.db.cursor()
    pepper_result = cur.execute("SELECT lookup_pepper from hashing_metadata")
    pepper = pepper_result.fetchone()[0]
    combo = "%s %s %s" % (address, "email", pepper)
    lookup_hash = sha256_and_url_safe_base64(combo)
    return lookup_hash


def sendEmailWithBackoff(
    sydent: Sydent,
    address: str,
    mxid: str,
    backoff: int,
    test: bool = False,
    attempts: int = 0,
) -> None:
    """Send an email with exponential backoff - that way we don't stop sending halfway
    through if the SMTP server rejects our email (e.g. because of rate limiting).

    Setting test to True disables the logging.
    """
    if attempts == MAX_ATTEMPTS_FOR_EMAIL:
        raise CantSendEmailException()

    time.sleep(backoff)
    try:
        template_file = sydent.get_branded_template(
            None,
            "migration_template.eml",
            ("email", "email.template"),
        )

        sendEmail(
            sydent,
            template_file,
            address,
            {"mxid": mxid, "subject_header_value": EMAIL_SUBJECT},
            log_send_errors=False,
        )
        if not test:
            print("Sent email to %s" % address)
    except EmailSendException:
        if not test:
            print(
                "Failed to send email to %s (attempt %d/%d)"
                % (address, attempts + 1, MAX_ATTEMPTS_FOR_EMAIL)
            )
        sendEmailWithBackoff(sydent, address, mxid, backoff * 2, test, attempts + 1)


def update_local_associations(
    sydent,
    db: sqlite3.Connection,
    send_email: bool,
    dry_run: bool,
    test: bool = False,
) -> None:
    """Update the DB table local_threepid_associations so that all stored
    emails are casefolded, and any duplicate mxid's associated with the
    given email are deleted.

    Setting dry_run to True means that the script is being run in dry-run mode
    by the user, i.e. it will run but will not send any email nor update the database.
    Setting test to True means that the function is being called as part of an automated
    test, and therefore we should neither backoff when sending emails or log.

    :return: None
    """
    res = db.execute(
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

    # Deltas to apply to the database, associated with the casefolded address they're for.
    deltas: Dict[str, Delta] = {}

    # Iterate through the results, to build the deltas.
    for casefold_address, assoc_tuples in associations.items():
        deltas[casefold_address] = Delta(
            to_update=UpdateDelta(
                mxid=assoc_tuples[0][0],
                lookup_hash=assoc_tuples[0][1],
                address=assoc_tuples[0][2],
            )
        )

        if len(assoc_tuples) > 1:
            # Iterate over all associations except for the first one, since we've already
            # processed it.
            for address, mxid, _ in assoc_tuples[1:]:
                deltas[casefold_address].to_delete.append(
                    DeleteDelta(
                        address=address,
                        mxid=mxid,
                    )
                )

    if not test:
        print(
            f"{len(deltas)} rows to update in local_threepid_associations"
        )

    # Apply the deltas
    for casefolded_address, delta in deltas.items():
        if not test:
            print(
                f"Updating {casefolded_address} and deleting {len(delta.to_delete)} rows associated with it"
            )

        try:
            # Delete each association, and send an email mentioning the affected MXID.
            for to_delete in delta.to_delete:
                cur = db.cursor()
                if not dry_run:
                    cur.execute(
                        "DELETE FROM local_threepid_associations WHERE address = ?",
                        (to_delete.address,)
                    )

                if send_email and not dry_run:
                    # If the MXID is one that will still be associated with this email address
                    # after this run, don't send an email for it.
                    if to_delete.mxid == delta.to_update.mxid:
                        continue

                    sendEmailWithBackoff(
                        sydent,
                        to_delete.address,
                        to_delete.mxid,
                        backoff=1 if not test else 0,
                        test=test,
                    )

                # We commit here, so that if we couldn't send the email for some reason we
                # don't update the database and have another go at it next time we run the
                # script.
                db.commit()

            # Update the row now that there's no duplicate.
            if not dry_run:
                cur = db.cursor()
                cur.execute(
                    "UPDATE local_threepid_associations SET address = ?, lookup_hash = ? WHERE address = ? AND mxid = ?",
                    (
                        casefolded_address,
                        delta.to_update.lookup_hash,
                        delta.to_update.address,
                        delta.to_update.mxid
                    )
                )
                db.commit()

        except CantSendEmailException:
            # If we failed because we couldn't send an email, rollback the current
            # transaction and move on to the next address to de-duplicate.
            # We catch this error here rather than when sending the email because we want
            # to avoid deleting rows we can't warn users about, and we don't want to
            # proceed with the subsequent deletion because there might still be
            # duplicates in the database (since we haven't deleted everything we wanted
            # to delete).
            db.rollback()
            continue


def update_global_associations(
    sydent,
    db: sqlite3.Connection,
    dry_run: bool,
    test: bool = False,
) -> None:
    """Update the DB table global_threepid_associations so that all stored
    emails are casefolded, the signed association is re-signed and any duplicate
    mxid's associated with the given email are deleted.

    Setting dry_run to True means that the script is being run in dry-run mode
    by the user, i.e. it will run but will not send any email nor update the database.
    Setting test to True means that the function is being called as part of an automated
    test, and therefore we should suppress logs.

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

    update_global_associations(sydent, sydent.db, dry_run=args.dry_run)
    update_local_associations(
        sydent, sydent.db, send_email=not args.no_email, dry_run=args.dry_run,
    )
