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
import random

import twisted
from twisted.internet import defer
from twisted.names import client, dns
from twisted.names.error import DNSNameError
from twisted.web.client import Agent, FileBodyProducer
from twisted.web.http_headers import Headers
from sydent.db.callbacks import CallbackStore

from sydent.db.valsession import ThreePidValSessionStore
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.http.httpsclient import SydentPolicyForHTTPS

from sydent.util import time_msec
from sydent.threepid.assocsigner import AssociationSigner

from sydent.threepid import ThreepidAssociation

from StringIO import StringIO


logger = logging.getLogger(__name__)


class ThreepidBinder:
    # the lifetime of a 3pid association
    THREEPID_ASSOCIATION_LIFETIME_MS = 100 * 365 * 24 * 60 * 60 * 1000

    def __init__(self, sydent):
        self.sydent = sydent
        self.store = CallbackStore(self.sydent)
        self.agent = Agent(twisted.internet.reactor, SydentPolicyForHTTPS(self.sydent))

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

        self._callCallbacks(assoc)

        return sgassoc

    @defer.inlineCallbacks
    def _callCallbacks(self, assoc):
        callbacks = self.store.getCallbackRequests(assoc.medium, assoc.address)
        for id, callback in callbacks.items():
            headers = Headers({
                'Content-Type': ['application/json'],
                'User-Agent': ['Sydent'],
            })
            payload = {
                "nonce": callback['nonce'],
                "mxid": assoc.mxid,
            }
            server = yield ThreepidBinder._pickServer(callback["server"])
            callbackUrl= 'https://%s/_matrix/client/api/v1/3pid-register-callback' % (
                server,
            )

            logger.info('Making bind callback to: %s' % callbackUrl)
            reqDeferred = self.agent.request(
                'POST',
                callbackUrl.encode('utf8'),
                headers,
                FileBodyProducer(StringIO(json.dumps(payload)))
            )
            reqDeferred.addCallback(
                lambda _, capturedId=id: self.store.deleteCallbackRequest(capturedId)
            )

            reqDeferred.addErrback(
                lambda err: logger.warn('Error making bind callback to %s: %s', (
                    callbackUrl, err
                ))
            )

    # The below is lovingly ripped off of synapse/http/endpoint.py

    _Server = collections.namedtuple('_Server', 'priority weight host port')

    @staticmethod
    @defer.inlineCallbacks
    def _pickServer(host):
        servers = yield ThreepidBinder._fetchServers(host)
        if not servers:
            raise DNSNameError('Not server available for %s', host)

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
                defer.returnValue('%s:%d' % (server.host, server.port,))
                return

    @staticmethod
    @defer.inlineCallbacks
    def _fetchServers(host):
        try:
            service = '_matrix._tcp.%s' % host
            answers, auth, add = yield client.lookupService(service)
        except DNSNameError:
            answers = []

        if (len(answers) == 1
                and answers[0].type == dns.SRV
                and answers[0].payload
                and answers[0].payload.target == dns.Name('.')):
            raise DNSNameError('Service %s unavailable', service)

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
