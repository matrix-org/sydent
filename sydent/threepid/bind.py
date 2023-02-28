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

import collections
import logging
import math
from typing import TYPE_CHECKING, Any, Dict, Union

import signedjson.sign
from twisted.internet import defer

from sydent.db.hashing_metadata import HashingMetadataStore
from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.http.httpclient import FederationHttpClient
from sydent.threepid import ThreepidAssociation
from sydent.threepid.signer import Signer
from sydent.util import time_msec
from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.stringutils import is_valid_matrix_server_name, normalise_address

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class ThreepidBinder:
    # the lifetime of a 3pid association
    THREEPID_ASSOCIATION_LIFETIME_MS = 100 * 365 * 24 * 60 * 60 * 1000

    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        self.hashing_store = HashingMetadataStore(sydent)

    def addBinding(self, medium: str, address: str, mxid: str) -> Dict[str, Any]:
        """
        Binds the given 3pid to the given mxid.

        It's assumed that we have somehow validated that the given user owns
        the given 3pid

        :param medium: The medium of the 3PID to bind.
        :param address: The address of the 3PID to bind.
        :param mxid: The MXID to bind the 3PID to.

        :return: The signed association.
        """

        # ensure we casefold email address before storing
        normalised_address = normalise_address(address, medium)

        localAssocStore = LocalAssociationStore(self.sydent)

        # Fill out the association details
        createdAt = time_msec()
        expires = createdAt + ThreepidBinder.THREEPID_ASSOCIATION_LIFETIME_MS

        # Hash the medium + address and store that hash for the purposes of
        # later lookups
        lookup_pepper = self.hashing_store.get_lookup_pepper()
        assert lookup_pepper is not None
        str_to_hash = " ".join(
            [normalised_address, medium, lookup_pepper],
        )
        lookup_hash = sha256_and_url_safe_base64(str_to_hash)

        assoc = ThreepidAssociation(
            medium,
            normalised_address,
            lookup_hash,
            mxid,
            createdAt,
            createdAt,
            expires,
        )

        localAssocStore.addOrUpdateAssociation(assoc)

        self.sydent.pusher.doLocalPush()

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(medium, normalised_address)
        invites = []
        # Widen the value type to Any: we're going to set the signed key
        # to point to a dict, but pendingJoinTokens yields Dict[str, str]
        token: Dict[str, Any]
        for token in pendingJoinTokens:
            token["mxid"] = mxid
            presigned = {
                "mxid": mxid,
                "token": token["token"],
            }
            token["signed"] = signedjson.sign.sign_json(
                presigned,
                self.sydent.config.general.server_name,
                self.sydent.keyring.ed25519,
            )
            invites.append(token)
        if invites:
            assoc.extra_fields["invites"] = invites
            joinTokenStore.markTokensAsSent(medium, normalised_address)

        signer = Signer(self.sydent)
        sgassoc = signer.signedThreePidAssociation(assoc)

        defer.ensureDeferred(self._notify(sgassoc, 0))

        return sgassoc

    def removeBinding(self, threepid: Dict[str, str], mxid: str) -> None:
        """
        Removes the binding between a given 3PID and a given MXID.

        :param threepid: The 3PID of the binding to remove.
        :param mxid: The MXID of the binding to remove.
        """

        # ensure we are casefolding email addresses
        threepid["address"] = normalise_address(threepid["address"], threepid["medium"])

        localAssocStore = LocalAssociationStore(self.sydent)
        localAssocStore.removeAssociation(threepid, mxid)
        self.sydent.pusher.doLocalPush()

    async def _notify(self, assoc: Dict[str, Any], attempt: int) -> None:
        """
        Sends data about a new association (and, if necessary, the associated invites)
        to the associated MXID's homeserver.

        :param assoc: The association to send down to the homeserver.
        :param attempt: The number of previous attempts to send this association.
        """
        mxid = assoc["mxid"]
        mxid_parts = mxid.split(":", 1)

        if len(mxid_parts) != 2:
            logger.error(
                "Can't notify on bind for unparseable mxid %s. Not retrying.",
                assoc["mxid"],
            )
            return

        matrix_server = mxid_parts[1]

        if not is_valid_matrix_server_name(matrix_server):
            logger.error(
                "MXID server part '%s' not a valid Matrix server name. Not retrying.",
                matrix_server,
            )
            return

        post_url = "matrix://%s/_matrix/federation/v1/3pid/onbind" % (matrix_server,)

        logger.info("Making bind callback to: %s", post_url)

        # Make a POST to the chosen Synapse server
        http_client = FederationHttpClient(self.sydent)
        try:
            response = await http_client.post_json_get_nothing(post_url, assoc, {})
        except Exception as e:
            self._notifyErrback(assoc, attempt, e)
            return

        # If the request failed, try again with exponential backoff
        if response.code != 200:
            self._notifyErrback(
                assoc, attempt, "Non-OK error code received (%d)" % response.code
            )
        else:
            logger.info("Successfully notified on bind for %s" % (mxid,))

            # Skip the deletion step if instructed so by the config.
            if not self.sydent.config.general.delete_tokens_on_bind:
                return

            # Only remove sent tokens when they've been successfully sent.
            try:
                joinTokenStore = JoinTokenStore(self.sydent)
                joinTokenStore.deleteTokens(assoc["medium"], assoc["address"])
                logger.info(
                    "Successfully deleted invite for %s from the store",
                    assoc["address"],
                )
            except Exception:
                logger.exception(
                    "Couldn't remove invite for %s from the store",
                    assoc["address"],
                )

    def _notifyErrback(
        self, assoc: Dict[str, Any], attempt: int, error: Union[Exception, str]
    ) -> None:
        """
        Handles errors when trying to send an association down to a homeserver by
        logging the error and scheduling a new attempt.

        :param assoc: The association to send down to the homeserver.
        :param attempt: The number of previous attempts to send this association.
        :param error: The error that was raised when trying to send the association.
        """
        logger.warning(
            "Error notifying on bind for %s: %s - rescheduling", assoc["mxid"], error
        )
        self.sydent.reactor.callLater(
            math.pow(2, attempt), defer.ensureDeferred, self._notify(assoc, attempt + 1)
        )

    # The below is lovingly ripped off of synapse/http/endpoint.py

    _Server = collections.namedtuple("_Server", "priority weight host port")
