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
import twisted.internet.defer

from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.threepid import threePidAssocFromDict

import signedjson.sign

import logging
import json

import twisted.internet.reactor
import twisted.internet.defer
from twisted.web.client import readBody

logger = logging.getLogger(__name__)


class Peer(object):
    def __init__(self, servername, pubkeys):
        self.servername = servername
        self.pubkeys = pubkeys

    def pushUpdates(self, sgAssocs):
        """
        :param sgAssocs: Sequence of (originId, sgAssoc) tuples where originId is the id on the creating server and
                        sgAssoc is the json object of the signed association
        :return a deferred
        """
        pass


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
        globalAssocStore = GlobalAssociationStore(self.sydent)
        for localId in sgAssocs:
            if localId > self.lastId:
                assocObj = threePidAssocFromDict(sgAssocs[localId])

                # We can probably skip verification for the local peer (although it could be good as a sanity check)
                globalAssocStore.addAssociation(assocObj, json.dumps(sgAssocs[localId]),
                                                self.sydent.server_name, localId)

        d = twisted.internet.defer.succeed(True)
        return d


class RemotePeer(Peer):
    def __init__(self, sydent, server_name, pubkeys):
        super(RemotePeer, self).__init__(server_name, pubkeys)
        self.sydent = sydent
        self.port = 1001

    def verifyMessage(self, jsonMessage):
        if not 'signatures' in jsonMessage:
            raise NoSignaturesException()

        key_ids = signedjson.sign.signature_ids(jsonMessage, self.servername)
        if not key_ids or len(key_ids) == 0 or not key_ids[0].startswith("ed25519:"):
            e = NoMatchingSignatureException()
            e.foundSigs = jsonMessage['signatures'].keys()
            e.requiredServername = self.servername
            raise e
        verify_key = yield self.get_server_verify_key(server_name, key_ids)
        verifyKey = nacl.signing.VerifyKey(self.pubkeys['ed25519'], encoder=nacl.encoding.HexEncoder)
        verifyKey.alg = 'ed25519'
        signedjson.sign.verify_signed_json(jsonMessage, self.servername, verifyKey)

    def pushUpdates(self, sgAssocs):
        body = {'sgAssocs': sgAssocs}

        reqDeferred = self.sydent.replicationHttpsClient.postJson(self.servername,
                                                                  self.port,
                                                                  '/_matrix/identity/replicate/v1/push',
                                                                  body)

        updateDeferred = twisted.internet.defer.Deferred()

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
