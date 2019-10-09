/*
Copyright 2015 OpenMarket Ltd

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

CREATE TABLE IF NOT EXISTS invite_tokens (
    id integer primary key,
    medium varchar(16) not null,
    address varchar(256) not null,
    room_id varchar(256) not null,
    sender varchar(256) not null,
    token varchar(256) not null,
    received_ts bigint, -- When the invite was received by us from the homeserver
    sent_ts bigint -- When the token was sent by us to the user
);
CREATE INDEX IF NOT EXISTS invite_token_medium_address on invite_tokens(medium, address);
CREATE INDEX IF NOT EXISTS invite_token_token on invite_tokens(token);

CREATE TABLE IF NOT EXISTS ephemeral_public_keys(
    id integer primary key,
    public_key varchar(256) not null,
    verify_count bigint default 0,
    persistence_ts bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS ephemeral_public_keys_index on ephemeral_public_keys(public_key);
