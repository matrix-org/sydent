# Copyright 2014 OpenMarket Ltd
# Copyright 2019 New Vector Ltd
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

import binascii
import json
import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Dict, Generic, Optional, Sequence, TypeVar

import signedjson.key
import signedjson.sign
from twisted.internet import defer
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.web.client import readBody
from twisted.web.iweb import IResponse
from unpaddedbase64 import decode_base64

from sydent.config.exceptions import ConfigError
from sydent.db.hashing_metadata import HashingMetadataStore
from sydent.db.threepid_associations import GlobalAssociationStore, SignedAssociations
from sydent.threepid import threePidAssocFromDict
from sydent.types import JsonDict
from sydent.util import json_decoder
from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.stringutils import normalise_address

PushUpdateReturn = TypeVar("PushUpdateReturn")

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)

SIGNING_KEY_ALGORITHM = "ed25519"


class Peer(Generic[PushUpdateReturn]):
    def __init__(self, servername: str, pubkeys: Dict[str, str]):
        """
        :param server_name: The peer's server name.
        :param pubkeys: The peer's public keys in a Dict[key_id, key_b64]
        """
        self.servername = servername
        self.pubkeys = pubkeys
        self.is_being_pushed_to = False

    @abstractmethod
    def pushUpdates(self, sgAssocs: SignedAssociations) -> "Deferred[PushUpdateReturn]":
        """
        :param sgAssocs: Map from originId to sgAssoc,  where originId is the id
                         on the creating server and sgAssoc is the json object
                         of the signed association
        """
        ...


class LocalPeer(Peer[bool]):
    """
    The local peer (ourselves: essentially copying from the local associations table to the global one)
    """

    def __init__(self, sydent: "Sydent") -> None:
        super().__init__(sydent.config.general.server_name, {})
        self.sydent = sydent
        self.hashing_store = HashingMetadataStore(sydent)

        globalAssocStore = GlobalAssociationStore(self.sydent)
        lastId = globalAssocStore.lastIdFromServer(self.servername)
        self.lastId = lastId if lastId is not None else -1

    def pushUpdates(self, sgAssocs: SignedAssociations) -> "Deferred[bool]":
        """
        Saves the given associations in the global associations store. Only stores an
        association if its ID is greater than the last seen ID.

        :param sgAssocs: The associations to save.

        :return: A deferred that succeeds with the value `True`.
        """
        globalAssocStore = GlobalAssociationStore(self.sydent)
        for localId in sgAssocs:
            if localId > self.lastId:
                assocObj = threePidAssocFromDict(sgAssocs[localId])

                # ensure we are casefolding email addresses
                assocObj.address = normalise_address(assocObj.address, assocObj.medium)

                if assocObj.mxid is not None:
                    # Assign a lookup_hash to this association
                    pepper = self.hashing_store.get_lookup_pepper()
                    if not pepper:
                        raise RuntimeError("No lookup_pepper in the database.")
                    str_to_hash = " ".join(
                        [
                            assocObj.address,
                            assocObj.medium,
                            pepper,
                        ],
                    )
                    assocObj.lookup_hash = sha256_and_url_safe_base64(str_to_hash)

                    # We can probably skip verification for the local peer (although it could
                    # be good as a sanity check)
                    globalAssocStore.addAssociation(
                        assocObj,
                        json.dumps(sgAssocs[localId]),
                        self.sydent.config.general.server_name,
                        localId,
                    )
                else:
                    globalAssocStore.removeAssociation(
                        assocObj.medium, assocObj.address
                    )

        d = defer.succeed(True)
        return d


class RemotePeer(Peer[IResponse]):
    def __init__(
        self,
        sydent: "Sydent",
        server_name: str,
        port: Optional[int],
        pubkeys: Dict[str, str],
        lastSentVersion: Optional[int],
    ) -> None:
        """
        :param sydent: The current Sydent instance.
        :param server_name: The peer's server name.
        :param port: The peer's port. Only used if no replication url is configured.
        :param pubkeys: The peer's public keys in a dict[key_id, key_b64]
        :param lastSentVersion: The ID of the last association sent to the peer.
        """
        super().__init__(server_name, pubkeys)
        self.sydent = sydent
        self.lastSentVersion = lastSentVersion

        # look up or build the replication URL
        replication_url = self.sydent.config.http.base_replication_urls.get(server_name)

        if replication_url is None:
            if not port:
                port = 1001
            replication_url = "https://%s:%i" % (server_name, port)

        if replication_url[-1:] != "/":
            replication_url += "/"

        # Capture the interesting bit of the url for logging.
        self.replication_url_origin = replication_url
        replication_url += "_matrix/identity/replicate/v1/push"
        self.replication_url = replication_url

        # Get verify key for this peer

        # Check if their key is base64 or hex encoded
        pubkey = self.pubkeys[SIGNING_KEY_ALGORITHM]
        try:
            # Check for hex encoding
            int(pubkey, 16)

            # Decode hex into bytes
            pubkey_decoded = binascii.unhexlify(pubkey)

            logger.warning(
                "Peer public key of %s is hex encoded. Please update to base64 encoding",
                server_name,
            )
        except ValueError:
            # Check for base64 encoding
            try:
                pubkey_decoded = decode_base64(pubkey)
            except Exception as e:
                raise ConfigError(
                    "Unable to decode public key for peer %s: %s" % (server_name, e),
                )

        self.verify_key = signedjson.key.decode_verify_key_bytes(
            SIGNING_KEY_ALGORITHM + ":", pubkey_decoded
        )

        # Attach metadata
        self.verify_key.alg = SIGNING_KEY_ALGORITHM
        self.verify_key.version = 0

    def verifySignedAssociation(self, assoc: JsonDict) -> None:
        """Verifies a signature on a signed association. Raises an exception if the
        signature is incorrect or couldn't be verified.

        :param assoc: A signed association.
        """
        if "signatures" not in assoc:
            raise NoSignaturesException()

        key_ids = signedjson.sign.signature_ids(assoc, self.servername)
        if (
            not key_ids
            or len(key_ids) == 0
            or not key_ids[0].startswith(SIGNING_KEY_ALGORITHM + ":")
        ):
            e = NoMatchingSignatureException(
                foundSigs=assoc["signatures"].keys(),
                requiredServername=self.servername,
            )
            raise e

        # Verify the JSON
        signedjson.sign.verify_signed_json(assoc, self.servername, self.verify_key)

    def pushUpdates(self, sgAssocs: SignedAssociations) -> "Deferred[IResponse]":
        """
        Pushes the given associations to the peer.

        :param sgAssocs: The associations to push.

        :return: A deferred which results in the response to the push request.
        """
        body = {"sgAssocs": sgAssocs}

        reqDeferred = self.sydent.replicationHttpsClient.postJson(
            self.replication_url, body
        )
        if reqDeferred is None:
            raise RuntimeError(f"Unable to push sgAssocs to {self.replication_url}")

        # XXX: We'll also need to prune the deleted associations out of the
        # local associations table once they've been replicated to all peers
        # (ie. remove the record we kept in order to propagate the deletion to
        # other peers).

        updateDeferred: "Deferred[IResponse]" = defer.Deferred()

        reqDeferred.addCallback(self._pushSuccess, updateDeferred=updateDeferred)
        reqDeferred.addErrback(self._pushFailed, updateDeferred=updateDeferred)

        return updateDeferred

    def _pushSuccess(
        self,
        result: "IResponse",
        updateDeferred: "Deferred[IResponse]",
    ) -> None:
        """
        Processes a successful push request. If the request resulted in a status code
        that's not a success, consider it a failure

        :param result: The HTTP response.
        :param updateDeferred: The deferred to make either succeed or fail depending on
            the status code.
        """
        if result.code >= 200 and result.code < 300:
            updateDeferred.callback(result)
        else:
            d = readBody(result)
            d.addCallback(self._failedPushBodyRead, updateDeferred=updateDeferred)
            d.addErrback(self._pushFailed, updateDeferred=updateDeferred)

    def _failedPushBodyRead(
        self, body: bytes, updateDeferred: "Deferred[IResponse]"
    ) -> None:
        """
        Processes a response body from a failed push request, then calls the error
        callback of the provided deferred.

        :param body: The response body.
        :param updateDeferred: The deferred to call the error callback of.
        """
        errObj = json_decoder.decode(body.decode("utf8"))
        e = RemotePeerError(errObj)
        updateDeferred.errback(e)

    def _pushFailed(
        self,
        failure: Failure,
        updateDeferred: "Deferred[object]",
    ) -> None:
        """
        Processes a failed push request, by calling the error callback of the given
        deferred with it.

        :param failure: The failure to process.
        :param updateDeferred: The deferred to call the error callback of.
        """
        updateDeferred.errback(failure)
        return None


class NoSignaturesException(Exception):
    pass


class NoMatchingSignatureException(Exception):
    def __init__(self, foundSigs: Sequence[str], requiredServername: str):
        self.foundSigs = foundSigs
        self.requiredServername = requiredServername

    def __str__(self) -> str:
        return "Found signatures: %s, required server name: %s" % (
            self.foundSigs,
            self.requiredServername,
        )


class RemotePeerError(Exception):
    def __init__(self, errorDict: JsonDict):
        self.errorDict = errorDict

    def __str__(self) -> str:
        return repr(self.errorDict)
