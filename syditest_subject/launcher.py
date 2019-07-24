# -*- coding: utf-8 -*-

# Copyright 2019 The Matrix.org Foundation C.I.C.
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

import os
import tempfile
import shutil
import time
from subprocess import Popen

CFG_TEMPLATE = """
[http]
clientapi.http.bind_address = localhost
clientapi.http.port = 8099
client_http_base = http://localhost:8099

[db]
db.file = :memory:

[general]
server.name = test.local

[email]
email.tlsmode = 0
email.template = {testsubject_path}/res/verification_template.eml
email.invite.subject = %(sender_display_name)s has invited you to chat
email.smtphost = localhost
email.from = Sydent Validation <noreply@localhost>
email.smtpport = 1025
email.subject = Your Validation Token
email.invite_template = {testsubject_path}/res/invite_template.eml
"""

class SyditestLauncher(object):
    def launch(self):
        sydent_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..',
        ))
        testsubject_path = os.path.join(
            sydent_path, 'syditest_subject',
        )

        self.tmpdir = tempfile.mkdtemp(prefix='sydenttest')

        with open(os.path.join(self.tmpdir, 'sydent.conf'), 'w') as cfgfp:
            cfgfp.write(CFG_TEMPLATE.format(testsubject_path=testsubject_path))

        newEnv = os.environ.copy()
        newEnv.update({
            'PYTHONPATH': sydent_path,
        })

        stderr_fp = open(os.path.join(testsubject_path, 'sydent.stderr'), 'w')

        self.process = Popen(
            args=['python', '-m', 'sydent.sydent'],
            cwd=self.tmpdir,
            env=newEnv,
            stderr=stderr_fp,
        )
        # XXX: wait for startup in a sensible way
        time.sleep(2)

        return 'http://localhost:8099'

    def tearDown(self):
        print("Stopping sydent...")
        self.process.terminate()
        shutil.rmtree(self.tmpdir)
