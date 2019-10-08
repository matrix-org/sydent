/*
Copyright 2014,2017 OpenMarket Ltd

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

-- Note that this SQL file is not up to date, and migrations can be found in sydent/db/sqlitedb.py

CREATE TABLE IF NOT EXISTS local_threepid_associations (
    id integer primary key,
    medium varchar(16) not null,
    address varchar(256) not null,
    mxid varchar(256) not null,
    ts integer not null,
    notBefore bigint not null,
    notAfter bigint not null
);

CREATE TABLE IF NOT EXISTS global_threepid_associations (
    id integer primary key,
    medium varchar(16) not null,
    address varchar(256) not null,
    mxid varchar(256) not null,
    ts integer not null,
    notBefore bigint not null,
    notAfter integer not null,
    originServer varchar(255) not null,
    originId integer not null,
    sgAssoc text not null
);
CREATE UNIQUE INDEX IF NOT EXISTS originServer_originId on global_threepid_associations (originServer, originId);
