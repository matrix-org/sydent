# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
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

from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.threepid import threePidAssocFromDict

import signedjson.sign
import signedjson.key

import logging
import json

import nacl

import twisted.internet.reactor
from twisted.internet import defer
from twisted.web.client import readBody

logger = logging.getLogger(__name__)


class Peer(object):
    def __init__(self, servername, pubkeys):
        self.servername = servername
        self.pubkeys = pubkeys
        self.shadow = False


class LocalPeer(Peer):
    """
    The local peer (ourselves: essentially copying from the local associations table to the global one)
    """
    def __init__(self, sydent):
        super(LocalPeer, self).__init__(sydent.server_name, {})
        self.sydent = sydent

        globalAssocStore = GlobalAssociationStore(self.sydent)
        self.lastId = globalAssocStore.lastIdFromServer(self.servername)
        if self.lastId is None:
            self.lastId = -1

    def pushUpdates(self, sgAssocs):
        """Push updates from local associations table to the global one."""
        globalAssocStore = GlobalAssociationStore(self.sydent)
        for localId in sgAssocs:
            if localId > self.lastId:
                assocObj = threePidAssocFromDict(sgAssocs[localId][0])
                if assocObj.mxid is not None:
                    # We can probably skip verification for the local peer (although it could be good as a sanity check)
                    globalAssocStore.addAssociation(assocObj, json.dumps(sgAssocs[localId][0]),
                                                    self.sydent.server_name, localId)
                else:
                    globalAssocStore.removeAssociation(assocObj.medium, assocObj.address)

                # inject the shadow association, if any.
                if sgAssocs[localId][1] is not None:
                    shadowAssocObj = threePidAssocFromDict(sgAssocs[localId][1])
                    if shadowAssocObj.mxid is not None:
                        # we deliberately identify this as originating from us rather than the shadow IS
                        globalAssocStore.addAssociation(shadowAssocObj, json.dumps(sgAssocs[localId][1]),
                                                        self.sydent.server_name, localId)
                    else:
                        globalAssocStore.removeAssociation(shadowAssocObj.medium, shadowAssocObj.address)

                # if this is an association that matches one of our invite_tokens then we should call the onBind callback
                # at this point, in order to tell the inviting HS that someone out there has just bound the 3PID.
                self.sydent.threepidBinder.notifyPendingInvites(assocObj)

        d = defer.succeed(True)
        return d


class RemotePeer(Peer):
    def __init__(self, sydent, server_name, pubkeys):
        super(RemotePeer, self).__init__(server_name, pubkeys)
        self.sydent = sydent
        self.port = 1001

        # Get verify key from signing key
        signing_key = signedjson.key.decode_signing_key_base64(alg, "0", self.pubkeys[alg])
        self.verify_key = signing_key.verify_key

        # Attach metadata
        self.verify_key.alg = alg
        self.verify_key.version = 0

    def verifyMessage(self, jsonMessage):
        """Verify a JSON structure has a valid signature from the remote peer."""
        if not 'signatures' in jsonMessage:
            raise NoSignaturesException()

        alg = 'ed25519'

        key_ids = signedjson.sign.signature_ids(jsonMessage, self.servername)
        if not key_ids or len(key_ids) == 0 or not key_ids[0].startswith(alg + ":"):
            e = NoMatchingSignatureException()
            e.foundSigs = jsonMessage['signatures'].keys()
            e.requiredServername = self.servername
            raise e

        # Get verify key from signing key
        signing_key = signedjson.key.decode_signing_key_base64(alg, "0", self.pubkeys[alg])
        verify_key = signing_key.verify_key

        # Attach metadata
        verify_key.alg = alg
        verify_key.version = 0

        # Verify the JSON
        signedjson.sign.verify_signed_json(jsonMessage, self.servername, self.verify_key)

    def pushUpdates(self, data):
        """Push updates to a remote peer.

        :param data: A dictionary of possible `sg_assocs`, `invite_tokens`
            and `ephemeral_public_keys` keys.
        :type data: Dict
        :returns a deferred.
        :rtype: Deferred
        """

        # sgAssocs is comprised of tuples (sgAssoc, shadowSgAssoc)
        if self.shadow:
            data["sg_assocs"] = { k: v[1] for k, v in data["sg_assocs"].items() }
        else:
            data["sg_assocs"] = { k: v[0] for k, v in data["sg_assocs"].items() }

        reqDeferred = self.sydent.replicationHttpsClient.postJson(self.servername,
                                                                  self.port,
                                                                  '/_matrix/identity/replicate/v1/push',
                                                                  data)

        # XXX: We'll also need to prune the deleted associations out of the
        # local associations table once they've been replicated to all peers
        # (ie. remove the record we kept in order to propagate the deletion to
        # other peers).

        updateDeferred = defer.Deferred()

        reqDeferred.addCallback(self._pushSuccess, updateDeferred=updateDeferred)
        reqDeferred.addErrback(self._pushFailed, updateDeferred=updateDeferred)

        return updateDeferred

    def _pushSuccess(self, result, updateDeferred):
        if result.code >= 200 and result.code < 300:
            updateDeferred.callback(result)
        else:
            d = readBody(result)
            d.addCallback(self._failedPushBodyRead, updateDeferred=updateDeferred)
            d.addErrback(self._pushFailed, updateDeferred=updateDeferred)

    def _failedPushBodyRead(self, body, updateDeferred):
        errObj = json.loads(body)
        e = RemotePeerError()
        e.errorDict = errObj
        updateDeferred.errback(e)

    def _pushFailed(self, failure, updateDeferred):
        updateDeferred.errback(failure)
        return None


class NoSignaturesException(Exception):
    pass


class NoMatchingSignatureException(Exception):
    def __str__(self):
        return "Found signatures: %s, required server name: %s" % (self.foundSigs, self.requiredServername)


class RemotePeerError(Exception):
    def __str__(self):
        return repr(self.errorDict)
