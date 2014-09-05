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

import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

class SqliteDatabase:
    def __init__(self, syd):
        self.sydent = syd

        dbFilePath = self.sydent.cfg.get("db", "db.file")
        logger.info("Using DB file %s", dbFilePath)

        self.db = sqlite3.connect(dbFilePath)

        schemaDir = os.path.dirname(__file__)

        c = self.db.cursor()

        for f in os.listdir(schemaDir):
            if not f.endswith(".sql"):
                continue
            scriptPath = os.path.join(schemaDir, f)
            fp = open(scriptPath, 'r')
            try:
                c.executescript(fp.read())
            except:
                logger.error("Error importing %s", f)
                raise
            fp.close()

        c.close()
        self.db.commit()
