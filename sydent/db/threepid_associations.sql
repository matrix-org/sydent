/*
Copyright 2014 matrix.org

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

CREATE TABLE IF NOT EXISTS local_threepid_associations (id integer primary key, medium varchar(16) not null, address varchar(256) not null, mxId varchar(256) not null, createdAt bigint not null, expires bigint not null);
CREATE UNIQUE INDEX IF NOT EXISTS medium_address on local_threepid_associations(medium, address);

CREATE TABLE IF NOT EXISTS global_threepid_associations (id integer primary key, medium varchar(16) not null, address varchar(256) not null, mxId varchar(256) not null, createdAt bigint not null, expires bigint not null, originServer varchar(255) not null, originId integer not null, sgAssoc text not null);
CREATE INDEX IF NOT EXISTS medium_address_createdAt on global_threepid_associations (medium, address, createdAt);
