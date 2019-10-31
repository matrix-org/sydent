# -*- coding: utf-8 -*-

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
import ConfigParser

from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.threepid import threePidAssocFromDict
from unpaddedbase64 import decode_base64

import signedjson.sign
import signedjson.key

import logging
import json

import nacl

from twisted.internet import defer
from twisted.web.client import readBody

logger = logging.getLogger(__name__)

SIGNING_KEY_ALGORITHM = "ed25519"


class Peer(object):
    def __init__(self, servername, pubkeys):
        self.servername = servername
        self.pubkeys = pubkeys
        self.shadow = False
        self.is_being_pushed_to = False


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
                assocObj = threePidAssocFromDict(sgAssocs[localId])
                if assocObj.mxid is not None:
                    # We can probably skip verification for the local peer (although it could be good as a sanity check)
                    globalAssocStore.addAssociation(assocObj, json.dumps(sgAssocs[localId]),
                                                    self.sydent.server_name, localId)
                else:
                    globalAssocStore.removeAssociation(assocObj.medium, assocObj.address)

                # if this is an association that matches one of our invite_tokens then we should call the onBind callback
                # at this point, in order to tell the inviting HS that someone out there has just bound the 3PID.
                self.sydent.threepidBinder.notifyPendingInvites(assocObj)

        d = defer.succeed(True)
        return d


class RemotePeer(Peer):
    def __init__(self, sydent, server_name, port, pubkeys):
        super(RemotePeer, self).__init__(server_name, pubkeys)
        self.sydent = sydent
        self.port = port
        # look up or build the replication URL
        try:
            replication_url = sydent.cfg.get(
                "peer.%s" % server_name, "base_replication_url",
            )
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            if not port:
                port = 1001
            replication_url = "https://%s:%i" % (server_name, port)

        if replication_url[-1:] != '/':
            replication_url += "/"

        replication_url += "_matrix/identity/replicate/v1/push"
        self.replication_url = replication_url

        # Get verify key for this peer
        key_bytes = decode_base64(self.pubkeys[SIGNING_KEY_ALGORITHM])
        self.verify_key = signedjson.key.decode_verify_key_bytes(SIGNING_KEY_ALGORITHM + ":", key_bytes)

        # Attach metadata
        self.verify_key.alg = SIGNING_KEY_ALGORITHM
        self.verify_key.version = 0

    def verifySignedAssociation(self, assoc):
        """Verifies a signature on a signed association.

        :param assoc: A signed association.
        :type assoc: Dict
        """
        if not 'signatures' in assoc:
            raise NoSignaturesException()

        key_ids = signedjson.sign.signature_ids(assoc, self.servername)
        if not key_ids or len(key_ids) == 0 or not key_ids[0].startswith(SIGNING_KEY_ALGORITHM + ":"):
            e = NoMatchingSignatureException()
            e.foundSigs = assoc['signatures'].keys()
            e.requiredServername = self.servername
            raise e

        # Verify the JSON
        signedjson.sign.verify_signed_json(assoc, self.servername, self.verify_key)

    def pushUpdates(self, data):
        """Push updates to a remote peer.

        :param data: A dictionary of possible `sg_assocs`, `invite_tokens`
            and `ephemeral_public_keys` keys.
        :type data: Dict
        :returns a deferred.
        :rtype: Deferred
        """

        reqDeferred = self.sydent.replicationHttpsClient.postJson(
            self.replication_url, data
        )

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
