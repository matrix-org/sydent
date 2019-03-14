Intra-sydent replication
------------------------

Replication takes place over HTTPs connections, using server and client TLS
certificates (currently each sydent instance can only be configured with a
single certificate which is used as both a server and a client certificate).

Replication peers are (currently) configured in the sqlite database; you
need to add a row to both the `peers` and `peer_pubkeys` tables.

The `name` / `peername` in these tables must match the `server_name` in the
configuration of the peer, which is the name that peer will use to sign
associations.

Inbound replication connections are authenticated according to the Common Name
in the client certificate, so that must also match the `server_name`.

By default, that name is also used for outbound connections, but it is possible
to override this by adding a setting to the config file such as:

    [peer.example.com]
    base_replication_url = https://internal-address.example.com:4434
