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

CREATE TABLE IF NOT EXISTS threepid_validation_sessions (id integer primary key, medium varchar(16) not null, address varchar(256) not null, clientSecret varchar(32) not null, validated int default 0, mtime bigint not null);
CREATE TABLE IF NOT EXISTS threepid_token_auths (id integer primary key, validationSession integer not null, token varchar(32) not null, sendAttemptNumber integer not null, foreign key (validationSession) references threepid_validations(id));
