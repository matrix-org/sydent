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

# import ldap3
# import ldap3.core.exceptions
import logging
import os


try:
    import ldap3
    import ldap3.core.exceptions
    import ldapurl

    # ldap3 v2 changed ldap3.AUTH_SIMPLE -> ldap3.SIMPLE
    try:
        LDAP_AUTH_SIMPLE = ldap3.AUTH_SIMPLE
    except AttributeError:
        LDAP_AUTH_SIMPLE = ldap3.SIMPLE
except ImportError:
    ldap3 = None
    pass

# Config example
# [ldap]
# uri = ldap://example.com:389/
# startls =  false
# base = dc=example,dc=com
# mail_attr = mail
# id_attr = samAccountName
# # if hs_name empty we assume that id_attr contain users matrix id
# # othercase we generate matrix id as @id_attr:hs_name
# hs_name = example.com
# bind_dn = cn=manager,cn=Users,dc=example,dc=com
# bind_pw = some_secret
# filter = (&(objectClass=user)(objectCategory=person))


logger = logging.getLogger(__name__)

class LDAPDatabase:
    def __init__(self, syd):
        if not ldap3:
            logger.info("Missing ldap3 library. This is required for LDAP integration")
            return

        self.sydent = syd

        self.ldap_uri = self.sydent.cfg.get("ldap", "uri")
        self.start_tls = self.sydent.cfg.get("ldap", "startls")
        self.base = self.sydent.cfg.get("ldap", "base")
        self.mail_attr = self.sydent.cfg.get("ldap", "mail_attr")
        self.id_attr = self.sydent.cfg.get("ldap", "id_attr").replace('"','').replace("'","")
        self.hs_name = self.sydent.cfg.get("ldap", "hs_name").replace('"','').replace("'","")
        self.bind_dn = self.sydent.cfg.get("ldap", "bind_dn")
        self.bind_pw = self.sydent.cfg.get("ldap", "bind_pw")
        self.ldap_filter = self.sydent.cfg.get("ldap", "filter").replace('"','').replace("'","")

    def HasLdapConfiguration(self):
        if (not self.ldap_uri):
            # No configuration
            return False
        else:
            logger.info("Exists LDAP configuration.")
            return True

    def getMxid(self,medium,address):
        if (not medium == "email"):
            # Support only Email from LDAP
            return None
        try:
            # URI support
            ldap_url = ldapurl.LDAPUrl(self.ldap_uri.lower())
            use_ssl = False
            if (ldap_url.urlscheme == "ldaps"):
                use_ssl = True
            if (":" not in ldap_url.hostport):
                ldap_host = ldap_url.hostport
                if use_ssl:
                    ldap_port = 636
                else:
                    ldap_port = 389
            else:
                ldap_host = ldap_url.hostport.split(':')[0]
                ldap_port = ldap_url.hostport.split(':')[1]

            server = ldap3.Server(
                host = ldap_host,
                port = ldap_port,
                use_ssl=use_ssl,
                get_info=None
            )
            logger.debug(
                "Attempting LDAP connection with %s",
                self.ldap_uri
            )
            conn = ldap3.Connection(server, user=self.bind_dn, password=self.bind_pw, auto_bind='NONE')
            if (not conn):
                logger.debug("Can't connect to %s", self.ldap_uri)
                return None
            if self.start_tls:
                conn.open
                conn.start_tls
            if (conn.bind()):
                logger.debug("LDAP bind succefull as %s", self.bind_dn)
            else:
                logger.debug("LDAP bind as %s error: %s", self.bind_dn, conn.result['description'])
            conn.search(search_base=self.base,
                 search_filter="(&(" + self.mail_attr + "=" + address + ")" + self.ldap_filter + ")",
                 attributes=[self.mail_attr, self.id_attr]
            )
            responses = [
                response
                for response
                in conn.response
                if response['type'] == 'searchResEntry'
            ]

            logger.debug("LDAP return %d records for filter: %s", len(responses), "(&(" + self.mail_attr + "=" + address + ")" + self.ldap_filter + ")")

            if len(responses) == 1:
                logger.debug("LDAP found one record with %s = %s", self.mail_attr, address)
                # # if hs_name empty we assume that id_attr contain users matrix id
                # # othercase we generate matrix id as @id_attr:hs_name
                if (self.hs_name):
                    mxid = "@" + responses[0]['attributes'][self.id_attr][0] +  ":" + self.hs_name
                else:
                    mxid = responses[0]['attributes'][self.id_attr][0]
                conn.unbind
                return (medium, address, mxid)

            conn.unbind
            return None

        except ldap3.core.exceptions.LDAPException as e:
            logger.error("Error during LDAP operation: %r", e)
            return None
