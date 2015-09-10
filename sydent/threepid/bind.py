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
from sydent.db.invite_tokens import JoinTokenStore

from sydent.db.valsession import ThreePidValSessionStore
from sydent.db.threepid_associations import LocalAssociationStore

from sydent.util import time_msec
from sydent.threepid.assocsigner import AssociationSigner

from sydent.threepid import ThreepidAssociation

class ThreepidBinder:
    # the lifetime of a 3pid association
    THREEPID_ASSOCIATION_LIFETIME_MS = 100 * 365 * 24 * 60 * 60 * 1000

    def __init__(self, sydent):
        self.sydent = sydent

    def addBinding(self, valSessionId, clientSecret, mxid):
        valSessionStore = ThreePidValSessionStore(self.sydent)
        localAssocStore = LocalAssociationStore(self.sydent)

        s = valSessionStore.getValidatedSession(valSessionId, clientSecret)

        createdAt = time_msec()
        expires = createdAt + ThreepidBinder.THREEPID_ASSOCIATION_LIFETIME_MS

        assoc = ThreepidAssociation(s.medium, s.address, mxid, createdAt, createdAt, expires)

        localAssocStore.addOrUpdateAssociation(assoc)

        self.sydent.pusher.doLocalPush()

        assocSigner = AssociationSigner(self.sydent)
        sgassoc = assocSigner.signedThreePidAssociation(assoc)

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(s.medium, s.address)
        if pendingJoinTokens:
            sgassoc["invites"] = pendingJoinTokens
            joinTokenStore.deleteTokens(s.medium, s.address)

        return sgassoc
