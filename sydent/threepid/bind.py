# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
# Copyright 2018, 2019 New Vector Ltd
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
import json
import logging
import math
import random
import signedjson.sign
from sydent.db.invite_tokens import JoinTokenStore

from sydent.db.threepid_associations import LocalAssociationStore

from sydent.util import time_msec
from sydent.threepid.signer import Signer

from sydent.threepid import ThreepidAssociation

from OpenSSL import SSL
from OpenSSL.SSL import VERIFY_NONE
from StringIO import StringIO
from twisted.internet import reactor, defer, ssl
from twisted.names import client, dns
from twisted.names.error import DNSNameError
from twisted.web.client import FileBodyProducer, Agent
from twisted.web.http_headers import Headers

logger = logging.getLogger(__name__)

def parseMxid(mxid):
    if len(mxid) > 255:
        raise Exception("This mxid is too long")

    if len(mxid) == 0 or mxid[0:1] != "@":
        raise Exception("mxid does not start with '@'")

    parts = mxid[1:].split(':', 1)
    if len(parts) != 2:
        raise Exception("Not enough colons in mxid")

    return parts

class BindingNotPermittedException(Exception):
    pass

class ThreepidBinder:
    # the lifetime of a 3pid association
    THREEPID_ASSOCIATION_LIFETIME_MS = 100 * 365 * 24 * 60 * 60 * 1000

    def __init__(self, sydent, info):
        self.sydent = sydent
        self._info = info


    def addBinding(self, medium, address, mxid):
        """Binds the given 3pid to the given mxid.

        It's assumed that we have somehow validated that the given user owns
        the given 3pid

        Args:
            medium (str): the type of 3pid
            address (str): the 3pid
            mxid (str): the mxid to bind it to
        Returns: The resulting signed association
        """
        mxidParts = parseMxid(mxid)
        result = self._info.match_user_id(medium, address)
        possible_hses = []
        if 'hs' in result:
            possible_hses.append(result['hs'])
        if 'shadow_hs' in result:
            possible_hses.append(result['shadow_hs'])

        if mxidParts[1] not in possible_hses:
            logger.info("Denying bind of %r/%r -> %r (info result: %r)", medium, address, mxid, result)
            raise BindingNotPermittedException()

        localAssocStore = LocalAssociationStore(self.sydent)

        createdAt = time_msec()
        expires = createdAt + ThreepidBinder.THREEPID_ASSOCIATION_LIFETIME_MS
        assoc = ThreepidAssociation(medium, address, mxid, createdAt, createdAt, expires)

        localAssocStore.addOrUpdateAssociation(assoc)

        self.sydent.pusher.doLocalPush()

        signer = Signer(self.sydent)
        sgassoc = signer.signedThreePidAssociation(assoc)
        return sgassoc

    def notifyPendingInvites(self, assoc):
        # this is called back by the replication code once we see new bindings
        # (including local ones created by addBinding() above)

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(assoc.medium, assoc.address)
        invites = []
        for token in pendingJoinTokens:
            # only notify for join tokens we created ourselves,
            # not replicated ones: the HS can only claim the 3pid
            # invite if it has a signature from the IS whose public
            # key is in the 3pid invite event. This will only be us
            # if we created the invite, not if the invite was replicated
            # to us.
            if token['origin_server'] is None:
                token["mxid"] = assoc.mxid
                token["signed"] = {
                    "mxid": assoc.mxid,
                    "token": token["token"],
                }
                token["signed"] = signedjson.sign.sign_json(token["signed"], self.sydent.server_name, self.sydent.keyring.ed25519)
                invites.append(token)
        if len(invites) > 0:
            assoc.extra_fields["invites"] = invites
            joinTokenStore.markTokensAsSent(assoc.medium, assoc.address)

            signer = Signer(self.sydent)
            sgassoc = signer.signedThreePidAssociation(assoc)

            self._notify(sgassoc, 0)

            return sgassoc
        return None

    def removeBinding(self, threepid, mxid):
        localAssocStore = LocalAssociationStore(self.sydent)
        localAssocStore.removeAssociation(threepid, mxid)
        self.sydent.pusher.doLocalPush()

    @defer.inlineCallbacks
    def _notify(self, assoc, attempt):
        mxid = assoc["mxid"]
        domain = mxid.split(":")[-1]
        server = yield self._pickServer(domain)
        callbackUrl = "https://%s/_matrix/federation/v1/3pid/onbind" % (
            server,
        )

        logger.info("Making bind callback to: %s", callbackUrl)
        # TODO: Not be woefully insecure
        agent = Agent(reactor, InsecureInterceptableContextFactory())
        reqDeferred = agent.request(
            "POST",
            callbackUrl.encode("utf8"),
            Headers({
                "Content-Type": ["application/json"],
                "User-Agent": ["Sydent"],
            }),
            FileBodyProducer(StringIO(json.dumps(assoc)))
        )
        reqDeferred.addCallback(
            lambda _: logger.info("Successfully notified on bind for %s" % (mxid,))
        )

        reqDeferred.addErrback(
            lambda err: self._notifyErrback(assoc, attempt, err)
        )

    def _notifyErrback(self, assoc, attempt, error):
        logger.warn("Error notifying on bind for %s: %s - rescheduling", assoc["mxid"], error)
        reactor.callLater(math.pow(2, attempt), self._notify, assoc, attempt + 1)

    # The below is lovingly ripped off of synapse/http/endpoint.py

    _Server = collections.namedtuple("_Server", "priority weight host port")

    @defer.inlineCallbacks
    def _pickServer(self, host):
        servers = yield self._fetchServers(host)
        if not servers:
            defer.returnValue("%s:8448" % (host,))

        min_priority = servers[0].priority
        weight_indexes = list(
            (index, server.weight + 1)
            for index, server in enumerate(servers)
            if server.priority == min_priority
        )

        total_weight = sum(weight for index, weight in weight_indexes)
        target_weight = random.randint(0, total_weight)

        for index, weight in weight_indexes:
            target_weight -= weight
            if target_weight <= 0:
                server = servers[index]
                defer.returnValue("%s:%d" % (server.host, server.port,))
                return

    @defer.inlineCallbacks
    def _fetchServers(self, host):
        try:
            service = "_matrix._tcp.%s" % host
            answers, auth, add = yield client.lookupService(service)
        except DNSNameError:
            answers = []

        if (len(answers) == 1
                and answers[0].type == dns.SRV
                and answers[0].payload
                and answers[0].payload.target == dns.Name(".")):
            raise DNSNameError("Service %s unavailable", service)

        servers = []

        for answer in answers:
            if answer.type != dns.SRV or not answer.payload:
                continue
            payload = answer.payload
            servers.append(ThreepidBinder._Server(
                host=str(payload.target),
                port=int(payload.port),
                priority=int(payload.priority),
                weight=int(payload.weight)
            ))

        servers.sort()
        defer.returnValue(servers)


class InsecureInterceptableContextFactory(ssl.ContextFactory):
    """
    Factory for PyOpenSSL SSL contexts which accepts any certificate for any domain.

    Do not use this since it allows an attacker to intercept your communications.
    """

    def __init__(self):
        self._context = SSL.Context(SSL.SSLv23_METHOD)
        self._context.set_verify(VERIFY_NONE, lambda *_: None)

    def getContext(self, hostname, port):
        return self._context
