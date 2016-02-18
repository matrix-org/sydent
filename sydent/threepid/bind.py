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
import collections
import json
import logging
import math
import random
import signedjson.sign
from sydent.db.invite_tokens import JoinTokenStore

from sydent.db.valsession import ThreePidValSessionStore
from sydent.db.threepid_associations import LocalAssociationStore

from sydent.util import time_msec
from sydent.threepid.assocsigner import AssociationSigner

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

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(s.medium, s.address)
        invites = []
        for token in pendingJoinTokens:
            token["mxid"] = mxid
            token["signed"] = {
                "mxid": mxid,
                "token": token["token"],
            }
            token["signed"] = signedjson.sign.sign_json(token["signed"], self.sydent.server_name, self.sydent.keyring.ed25519)
            invites.append(token)
        if invites:
            assoc.extra_fields["invites"] = invites
            joinTokenStore.markTokensAsSent(s.medium, s.address)

        assocSigner = AssociationSigner(self.sydent)
        sgassoc = assocSigner.signedThreePidAssociation(assoc)

        self._notify(sgassoc, 0)

        return sgassoc

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
