#  Copyright 2021 The Matrix.org Foundation C.I.C.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from unittest.mock import patch

from twisted.internet.error import DNSLookupError
from twisted.test.proto_helpers import StringTransport
from twisted.trial.unittest import TestCase
from twisted.web.client import Agent

from sydent.http.blacklisting_reactor import BlacklistingReactorWrapper
from sydent.http.srvresolver import Server
from tests.utils import AsyncMock, make_request, make_sydent


class BlacklistingAgentTest(TestCase):
    def setUp(self):
        config = {
            "general": {
                "ip.blacklist": "5.0.0.0/8",
                "ip.whitelist": "5.1.1.1",
            },
        }

        self.sydent = make_sydent(test_config=config)

        self.reactor = self.sydent.reactor

        self.safe_domain, self.safe_ip = b"safe.test", b"1.2.3.4"
        self.unsafe_domain, self.unsafe_ip = b"danger.test", b"5.6.7.8"
        self.allowed_domain, self.allowed_ip = b"allowed.test", b"5.1.1.1"

        # Configure the reactor's DNS resolver.
        for (domain, ip) in (
            (self.safe_domain, self.safe_ip),
            (self.unsafe_domain, self.unsafe_ip),
            (self.allowed_domain, self.allowed_ip),
        ):
            self.reactor.lookups[domain.decode()] = ip.decode()
            self.reactor.lookups[ip.decode()] = ip.decode()

        self.ip_whitelist = self.sydent.config.general.ip_whitelist
        self.ip_blacklist = self.sydent.config.general.ip_blacklist

    def test_reactor(self):
        """Apply the blacklisting reactor and ensure it properly blocks
        connections to particular domains and IPs.
        """
        agent = Agent(
            BlacklistingReactorWrapper(
                self.reactor,
                ip_whitelist=self.ip_whitelist,
                ip_blacklist=self.ip_blacklist,
            ),
        )

        # The unsafe domains and IPs should be rejected.
        for domain in (self.unsafe_domain, self.unsafe_ip):
            self.failureResultOf(
                agent.request(b"GET", b"http://" + domain), DNSLookupError
            )

        self.reactor.tcpClients = []

        # The safe domains IPs should be accepted.
        for domain in (
            self.safe_domain,
            self.allowed_domain,
            self.safe_ip,
            self.allowed_ip,
        ):
            agent.request(b"GET", b"http://" + domain)

            # Grab the latest TCP connection.
            (
                host,
                port,
                client_factory,
                _timeout,
                _bindAddress,
            ) = self.reactor.tcpClients.pop()

    @patch(
        "sydent.http.srvresolver.SrvResolver.resolve_service", new_callable=AsyncMock
    )
    def test_federation_client_allowed_ip(self, resolver):
        self.sydent.run()

        resolver.return_value = [
            Server(
                host=self.allowed_domain,
                port=443,
                priority=1,
                weight=1,
                expires=100,
            )
        ]

        request, channel = make_request(
            self.sydent.reactor,
            self.sydent.clientApiHttpServer.factory,
            "POST",
            "/_matrix/identity/v2/account/register",
            {
                "access_token": "foo",
                "expires_in": 300,
                "matrix_server_name": "example.com",
                "token_type": "Bearer",
            },
        )

        transport, protocol = self._get_http_request(
            self.allowed_ip.decode("ascii"), 443
        )

        self.assertRegex(
            transport.value(), b"^GET /_matrix/federation/v1/openid/userinfo"
        )
        self.assertRegex(transport.value(), b"Host: example.com")

        # Send it the HTTP response
        res_json = b'{ "sub": "@test:example.com" }'
        protocol.dataReceived(
            b"HTTP/1.1 200 OK\r\n"
            b"Server: Fake\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: %i\r\n"
            b"\r\n"
            b"%s" % (len(res_json), res_json)
        )

        self.assertEqual(channel.code, 200)

    @patch(
        "sydent.http.srvresolver.SrvResolver.resolve_service", new_callable=AsyncMock
    )
    def test_federation_client_safe_ip(self, resolver):
        self.sydent.run()

        resolver.return_value = [
            Server(
                host=self.safe_domain,
                port=443,
                priority=1,
                weight=1,
                expires=100,
            )
        ]

        request, channel = make_request(
            self.sydent.reactor,
            self.sydent.clientApiHttpServer.factory,
            "POST",
            "/_matrix/identity/v2/account/register",
            {
                "access_token": "foo",
                "expires_in": 300,
                "matrix_server_name": "example.com",
                "token_type": "Bearer",
            },
        )

        transport, protocol = self._get_http_request(self.safe_ip.decode("ascii"), 443)

        self.assertRegex(
            transport.value(), b"^GET /_matrix/federation/v1/openid/userinfo"
        )
        self.assertRegex(transport.value(), b"Host: example.com")

        # Send it the HTTP response
        res_json = b'{ "sub": "@test:example.com" }'
        protocol.dataReceived(
            b"HTTP/1.1 200 OK\r\n"
            b"Server: Fake\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: %i\r\n"
            b"\r\n"
            b"%s" % (len(res_json), res_json)
        )

        self.assertEqual(channel.code, 200)

    @patch("sydent.http.srvresolver.SrvResolver.resolve_service")
    def test_federation_client_unsafe_ip(self, resolver):
        self.sydent.run()

        resolver.return_value = [
            Server(
                host=self.unsafe_domain,
                port=443,
                priority=1,
                weight=1,
                expires=100,
            )
        ]

        request, channel = make_request(
            self.sydent.reactor,
            self.sydent.clientApiHttpServer.factory,
            "POST",
            "/_matrix/identity/v2/account/register",
            {
                "access_token": "foo",
                "expires_in": 300,
                "matrix_server_name": "example.com",
                "token_type": "Bearer",
            },
        )

        self.assertNot(self.reactor.tcpClients)

        self.assertEqual(channel.code, 500)

    def _get_http_request(self, expected_host, expected_port):
        clients = self.reactor.tcpClients
        (host, port, factory, _timeout, _bindAddress) = clients[-1]
        self.assertEqual(host, expected_host)
        self.assertEqual(port, expected_port)

        # complete the connection and wire it up to a fake transport
        protocol = factory.buildProtocol(None)
        transport = StringTransport()
        protocol.makeConnection(transport)

        return transport, protocol
