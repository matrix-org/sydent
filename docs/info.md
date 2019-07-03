# info endpoints

This branch contains two endpoints that aren't included in mainline
Sydent and are not mentioned in the Matrix spec. This file describes
them.

### `GET /_matrix/identity/api/v1/info`

Gives info on the homeserver(s) in charge of a given 3PID.

Up to 2 homeservers can be in charge of a same 3PID:

* a "protected" one only accessible from a whitelist of IP addresses
  (mandatory).
* a "shadow" one (or "normal" one, depending on the document), which is
  accessible from the wider Internet (optional).

When successfully processing the query, Sydent checks whether the client IP
address is included in a configured whitelist to figure out which response to
build.

The server names are located in a YAML file named `info.yaml` which follows
this structure:

```yaml
medium:
  email:
    entries:
      john.doe@matrix.org:
        hs: protected-matrix.example.com
        shadow_hs: public-matrix.example.com
        requires_invite: True
    patterns:
      - .*@(.*\.|)matrix\.org:
        shadow_hs: public-matrix.example.com
        requires_invite: False
```

*Note: if this setup with shadow and non-shadow HS isn't being used, i.e.
if `ips.nonshadow` isn't set in Sydent's `general` config, this file would
look like this:*

```yaml
medium:
  email:
    entries:
      john.doe@matrix.org:
        hs: public-matrix-1.example.com
        requires_invite: True
    patterns:
      - .*@(.*\.|)matrix\.org:
        hs: public-matrix.example.com
        requires_invite: False
```

#### Query parameters

* `medium`: The medium of the 3PID to get info for (`email`, `msisdn`).
* `address`: The address of the 3PID to get info for.

#### 200 response

```json
{
    "hs": "<protected HS>",
    "shadow_hs": "<shadow HS>",
    "new_server": "<new HS>"
}
```

* `hs`: the homeserver clients should talk to for the user with this 3PID.
If this 3PID is already associated with an MXID, this is the homeserver
the account with this ID is registered on, otherwise it is the one it can be
registered on as per the `info.yaml` file. If the request comes from an IP
address in the protected range, this is the protected homeserver for this
user.
* `shadow_hs`: the publicly-accessible homeserver for this 3PID. Set
only if `hs` is a protected homeserver.
* `new_hs`: the homeserver clients should encourage the user with this 3PID
to move to by deactivating their account and creating a new one on that server.
Set only if a MXID is already associated with the 3PID and the domain of this
MXID differs from the matching value in the `info.yaml` file.

All string values are HS server names that can be resolved in standard ways
(e.g. through `/.well-known` files).

### `GET /_matrix/identity/api/v1/internal-info`

Acts similarly to `GET /_matrix/identity/api/v1/info` (therefore uses the same
query parameters and the same definitions), except that it's designed to be
queried by homeservers to know if they can let a user register with a given
3PID. Therefore, its response features a few additional properties (see
below) and the meaning of `hs` isn't exactly the same (see below).

Moreover, the requests will always come from an IP address in the protected
range, therefore `hs` will always be a protected homeserver if there's one
available for the given 3PID.

#### 200 response

Here's an example of a response following the successful processing of a 3PID:

```json
{
    "hs": "<protected HS>",
    "shadow_hs": "<shadow HS>",
    "invited": true,
    "requires_invite": true
}
```

* `hs`: The homeserver the user with this 3PID will be allowed to register on.
* `shadow_hs`: the publicly-accessible homeserver for this 3PID. Set
only if `hs` is a protected homeserver.
* `invited`: Whether this 3PID has been invited in a room. This is `true` as
long as the Sydent instance processing the request is aware of an existing
valid invite for this 3PID.
* `requires_invite`: This 3PID can't be used to register a new account
without having been invited in a room first, as specified in the `info.yaml`
file.
