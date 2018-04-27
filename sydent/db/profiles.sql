/*
Copyright 2018 New Vector Ltd

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

CREATE TABLE IF NOT EXISTS profiles (user_id TEXT primary key, display_name TEXT DEFAULT NULL, avatar_url TEXT DEFAULT NULL, origin_server TEXT NOT NULL, batch BIGINT NOT NULL);

CREATE INDEX IF NOT EXISTS profiles_displayname on profiles(display_name);
CREATE INDEX IF NOT EXISTS profiles_origin_server_batch on profiles(origin_server, batch);

