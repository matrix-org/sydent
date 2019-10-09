/*
Copyright 2014 OpenMarket Ltd

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

CREATE TABLE IF NOT EXISTS peers (id integer primary key, name varchar(255) not null, port integer default null, lastSentVersion integer, lastPokeSucceededAt integer, active integer not null default 0);
CREATE UNIQUE INDEX IF NOT EXISTS name on peers(name);

CREATE TABLE IF NOT EXISTS peer_pubkeys (id integer primary key, peername varchar(255) not null, alg varchar(16) not null, key text not null, foreign key (peername) references peers (name));
CREATE UNIQUE INDEX IF NOT EXISTS peername_alg on peer_pubkeys(peername, alg);
