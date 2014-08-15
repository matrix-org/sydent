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

import twisted.internet.reactor
import twisted.internet.task

from Peer import LocalPeer
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.util.validationutils import signedThreePidAssociation

class Pusher:
    def __init__(self, sydent):
        self.sydent = sydent

    def setup(self):
        cb = twisted.internet.task.LoopingCall(Pusher.scheduledPush, self)
        cb.start(10.0)

    def getSignedAssociationsAfterId(self, afterId, limit):
        signedAssocTuples = []

        localAssocStore = LocalAssociationStore(self.sydent)
        localAssocTuples = localAssocStore.getAssociationsAfterId(afterId, limit)

        for tup in localAssocTuples:
            (localId, assoc) = tup

            sgAssoc = signedThreePidAssociation(self.sydent, assoc)
            signedAssocTuples.append( (localId, sgAssoc) )

        return signedAssocTuples

    def doLocalPush(self):
        """
        Synchronously push local associations to this server (ie. copy them to globals table)
        The local server is essentially treated the same as any other peer except we don't do the
        network round-trip and this function can be used so the association goes into the global table
        before the http call returns (so clients know it will be available on at least the same ID server they used)
        """
        localPeer = LocalPeer(self.sydent)

        signedAssocTuples = self.getSignedAssociationsAfterId(localPeer.lastId, None)

        localPeer.pushUpdates(signedAssocTuples)


    def scheduledPush(self):
        print "PUSH!"
