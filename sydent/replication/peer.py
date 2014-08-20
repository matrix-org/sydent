# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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

import syutil.crypto.jsonsign

import logging
import json

from StringIO import StringIO

import nacl.signing
import nacl.encoding

import twisted.internet.reactor
import twisted.internet.defer
from twisted.web.client import Agent, FileBodyProducer
from twisted.web.http_headers import Headers

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
        for localId,sgAssoc in sgAssocs:
            if localId > self.lastId:
                assocObj = threePidAssocFromDict(sgAssoc)

                # We can probably skip verification for the local peer (although it could be good as a sanity check)
                globalAssocStore.addAssociation(assocObj, json.dumps(sgAssoc), self.sydent.server_name, localId)

        d = twisted.internet.defer.succeed(True)
        return d

class RemotePeer(Peer):
    def verifyMessage(self, jsonMessage):
        if not 'signatures' in jsonMessage:
            raise NoSignaturesException()

        for keyType,key in self.pubkeys:
            keyDescriptor = '%s:%s' % (self.servername, keyType)
            if keyDescriptor in jsonMessage['signatures']:
                if keyType == 'ed25519':
                    verifyKey = nacl.signing.SigningKey(self.pubkeys['ed25519'], encoder=nacl.encoding.Base64Encoder)
                    syutil.crypto.jsonsign.verify_signed_json(jsonMessage, self.servername, verifyKey)
                    return True
                else:
                    logger.debug("Ignoring unknown key type: %s", keyType)

        raise NoMatchingSignatureException()

    def pushUpdates(self, sgAssocs):
        body = {'sgAssocs': sgAssocs}

        agent = Agent(twisted.internet.reactor)
        headers = Headers({'Content-Type':['application/json']})
        uri = "https://%s/matrix/identity/replicate/v1/push" % (self.servername)
        reqDeferred = agent.request('POST', uri.encode('utf8'), headers, FileBodyProducer(StringIO(json.dumps(body))))

        updateDeferred = twisted.internet.defer.Deferred()

        reqDeferred.addCallback(RemotePeer._pushSuccess, (self,updateDeferred))
        reqDeferred.addErrback(RemotePeer._pushFailed, (self,updateDeferred))

        return updateDeferred

    def _pushSuccess(self, updateDeferred):
        updateDeferred.callback()

    def _pushFailed(self, updateDeferred):
        updateDeferred.errback()

class NoSignaturesException(Exception):
    pass


class NoMatchingSignatureException(Exception):
    pass
