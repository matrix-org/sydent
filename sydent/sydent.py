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

#from twisted.enterprise import adbapi

import ConfigParser
import logging
import os

from db.sqlitedb import SqliteDatabase

from http.httpserver import HttpServer
from validators.emailvalidator import EmailValidator

from sign.ed25519 import SydentEd25519

from http.servlets.emailservlet import EmailRequestCodeServlet, EmailValidateCodeServlet
from http.servlets.lookupservlet import LookupServlet
from http.servlets.pubkeyservlets import Ed25519Servlet

logger = logging.getLogger(__name__)

class Sydent:
    CONFIG_SECTIONS = ['general', 'db', 'http', 'email', 'crypto']
    CONFIG_DEFAULTS = {
        'server.name' : '',
        'db.file': 'sydent.sqlite',
        'token.length': '6',
        'http.port': '8090',
        'email.template': 'res/email.template',
        'email.from': 'Sydent Validation <noreply@{hostname}>',
        'email.subject': 'Your Validation Token',
        'email.smtphost': 'localhost',
        'log.path':'',
        'ed25519.signingkey':''
    }

    def __init__(self):
        logger.info("Starting Sydent server")
        self.parse_config()

        logPath = self.cfg.get('general', "log.path")
        if logPath != '':
            logging.basicConfig(level=logging.INFO, filename=logPath)
        else:
            logging.basicConfig(level=logging.INFO, filename=logPath)


        self.db = SqliteDatabase(self).db

        self.server_name = self.cfg.get('general', 'server.name')
        if self.server_name == '':
            self.server_name = os.uname()[1]
            logger.warn(("You had not specified a server name. I have guessed that this server is called '%s' "
                        +" and saved this in the config file. If this is incorrect, you should edit server.name in "
                        +"the config file.") % (self.server_name))
            self.cfg.set('general', 'server.name', self.server_name)
            self.save_config()

        self.validators = Validators()
        self.validators.email = EmailValidator(self)

        self.keyring = Keyring()
        self.keyring.ed25519 = SydentEd25519(self).signing_key

        self.servlets = Servlets()
        self.servlets.emailRequestCode = EmailRequestCodeServlet(self)
        self.servlets.emailValidate = EmailValidateCodeServlet(self)
        self.servlets.lookup = LookupServlet(self)
        self.servlets.pubkey_ed25519 = Ed25519Servlet(self)

        self.httpServer = HttpServer(self)

    def parse_config(self):
        self.cfg = ConfigParser.SafeConfigParser(Sydent.CONFIG_DEFAULTS)
        for sect in Sydent.CONFIG_SECTIONS:
            try:
                self.cfg.add_section(sect)
            except ConfigParser.DuplicateSectionError:
                pass
        self.cfg.read("sydent.conf")

    def save_config(self):
        fp = open("sydent.conf", 'w')
        self.cfg.write(fp)
        fp.close()

    def run(self):
        self.httpServer.run()

class Validators:
    pass

class Servlets:
    pass

class Keyring:
    pass

if __name__ == '__main__':
    syd = Sydent()
    syd.run()
