# Configuration

## Config file structure
Sydent uses Python's `configparser` libary to parse the config file. 
This libary's documentation can be found [here](https://docs.python.org/3/library/configparser.html).

As an example:
```
[DEFAULT]
tail.length = 10

[elephant]
name = Albert
trunk.length =
#wings.width =

[mouse]
name = Terrance
tail.length = 5

[human]
```

This config file is then translated to the following Python dict:
```python
cfg = {
    elephant: {
        name: "Albert",
        trunk.length: "",
        tail.length: "10",
    },
    mouse: {
        name: "Terrance",
        tail.length: "5",
    },
    human: {
        tail.length: "10",
    }
}
```

The important things to note are:  
1. Commenting out `wings.width` essentially sets it to `None`. But an empty
value for `trunk.length` sets it to an empty string.

2. Even though the `human` section was empty, it still has a `tail.length`
value of `"10"` (due to the `DEFAULT` section).  

3. Everything is a string and it's up to the program to decide what type to
cast things into.


## Example config file

An example minimal config file can be found in
[docs/example_config.conf](https://github.com/matrix-org/sydent/blob/main/docs/example_config.conf).


## Writing your own config

Your config file need only contain entries for things you are overwriting from the 
default. 

The DEFAULT section should be empty and is a deprecated way of configuring Sydent.

You can generate a new config file by running the [generate-config script](https://github.com/matrix-org/sydent/blob/main/scripts/generate-config)

## Config options

The string `XYZ` in an option name means that there is a family of config options,
each with a different substitution for `XYZ`.

See [docs/example_config.conf](https://github.com/matrix-org/sydent/blob/main/docs/example_config.conf)
for an example of this in the [sms] section.

### Definitions of emptiness:

Consider this snippet of config:
```
this.option.is.empty = 
this.option.is.non-empty = petal
```
* `this.option.is.empty` has been set to the empty string. This is **EMPTY**.
* `this.option.was.never.mentioned` was never mentioned. This is **UNSET**.
* `this.option.is.non-empty` is neither **EMPTY** nor **UNSET**. This is **NON-EMPTY**.

Leaving an option *empty*, overrides the default value with an empty string.  
Leaving an option *unset* uses the defualt value for that option.

### [general]

Name                    | Description
---------               | -------
`address_lookup_limit`  | The maximum number of addresses that someone can query in a single /lookup request. DEFAULTS TO `1000`
`brand.default`         | The default brand of templates to use. See [docs/templates.md](https://github.com/matrix-org/sydent/blob/main/docs/templates.md) for more information. DEFAULTS TO `matrix-org`
`delete_tokens_on_bind` | Whether to delete invite tokens after successful binding has taken place. DEFAULTS TO `true`
`enable_v1_associations`| Whether clients and homeservers can register an association using v1 API endpoints. DEFAULTS TO `true`
`ip.blacklist`          | A comma-seperated list of CIDR IP address ranges to block outbound requests to. DEFAULTS TO a list of private IP ranges to prevent DNS rebinding attacks. This list can be found in [sydent/util/ip_range.py](https://github.com/matrix-org/sydent/blob/main/sydent/util/ip_range.py).
`ip.whitelist`          | A comma-seperated of IP address CIDR ranges that should be allowed for outbound requests. This is useful for specifying exceptions to wide-ranging blacklisted target IP ranges. This list overrides the blacklist. DEFAULTS TO EMPTY
`log.level`             | The log level to use. This can be set to any level used by the Python `logging` module. DEFAULTS TO `INFO`
`log.path`              | The path of the file to write the logs to. Leaving this empty prints logs to stderr. DEFAULTS TO EMPTY
`pidfile.path`          | The file to save Sydent's process ID (PID) to. DEFAULTS TO the value stored in `SYDENT_PID_FILE` environment variable, or `sydent.pid` if that is unset.
`prometheus_addr`       | The local IPv4 or IPv6 address for Prometheus to bind to. This must be set to enable the Prometheus client. DEFAULTS TO UNSET
`prometheus_port`       | The port for Prometheus to bind to. This must be set to enable the Prometheus client. DEFAULTS TO UNSET
`server.name`           | The domain name of the server. DEFAULTS TO value returned by `os.uname()[1]`
`sentry.dsn`            | The Data Source Name (DSN) for Sentry to use. This must be set to enable Sentry. DEFAULTS TO UNSET
`templates.path`        | The path to the root template directory. See [docs/templates.md](https://github.com/matrix-org/sydent/blob/main/docs/templates.md) for more information. DEFAULTS TO `res`
`terms.path`            | The path to the file where the terms and conditions are configured, or empty if no terms are being used. DEFAULTS TO EMPTY


### [db]

Name        | Description
---------   | -------
`db.file`   | The path to the SQLite database file for Sydent to use. It can be set to `:memory:` to use a temporary database in RAM instead of on disk. DEFAULTS TO the value stored in the `SYDENT_DB_PATH` environment variable or `sydent.db` if that is unset.


### [http]

Name                            | Description
---------                       | -------
`client_http_base`              | The base url of Sydent. This should be of the form `scheme://base.url.com/here`. DEFAULTS TO EMPTY
`clientapi.http.bind_address`   | The local IPv4 or IPv6 address for the Identity Server API to bind to. DEFAULTS TO `::` (i.e. bind to all)
`clientapi.http.port`           | The port for the Identity Server API to bind to. DEFAULTS TO `8090`
`federation.verifycerts`        | Whether or not Sydent should verify the TLS certificates of homeservers it communicates with. DEFAULTS TO `true`
`internalapi.http.bind_address` | The local IPv4 or IPv6 address for the Internal Testing API to bind to. DEFAULTS TO `::1`
`internalapi.http.port`         | The port for the Internal Testing API to bind to. This must be non-empty to enable the Internal Testing API. Enabling this allows for binding and unbinding between identifiers and matrix IDs without any authentication. DEFAULTS TO EMPTY
`obey_x_forwarded_for`          | Whether or not Sydent should pay attention to X-Forwarded-For headers. DEFAULTS TO `false`
`replication.https.bind_address`| The local IPv4 or IPv6 address for the Replication API to bind to. DEFAULTS TO `::` (i.e. bind to all)
`replication.https.cacert`      | The file path to a root CA certificate. If this is SET then certificates of other Sydent servers signed by this CA will be trusted. This is useful for testing or when it's not practical to get the client cert signed by a real root CA but should never be used on a production server. DEFAULTS TO UNSET
`replication.https.certfile`    | The file path to a TLS certificate and private key. This file should contain **both** the public certificate and the private key used to generate it. This must be non-empty to enable the Replication API. DEFAULTS TO UNSET
`replication.https.port`        | The port for the Replication API to bind to. DEFAULTS TO `4434`


### [email]

Name                        | Description
---------                   | -------
`email.default_web_client_location` | The web client location which will be used in store invites if one is not provided by the homeserver. See [docs/templates.md](https://github.com/matrix-org/sydent/blob/main/docs/templates.md) for more information. This should be of the form 'scheme://base.url.com/here'. DEFAULTS TO `https://app.element.io`
`email.from`                | The email address that all emails should appear to have been sent from. This should take the form: `Display Name Here <actual.email@example.com>`. DEFAULTS TO `Sydent <noreply@example.com>`
`email.hostname`            | The fully qualified domain name (FQDN) to use with HELO/EHLO command when connecting to the SMTP server. DEFAULTS TO result of `socket.getfqdn()`
`email.invite.subject`      | The subject line of emails that invite someone to a room. This is a string template using `"%(variable)s"` substitution and can use any of the parameters sent to the `/store-invite` API. See See [docs/templates.md](https://github.com/matrix-org/sydent/blob/main/docs/templates.md) for more information. DEFAULTS TO `%(sender_display_name)s has invited you to chat`
`email.invite.subject_space`| The subject line of emails that invite someone to a space. This is a string template using `"%(variable)s"` substitution and can use any of the parameters sent to the `/store-invite` API. See [docs/templates.md](https://github.com/matrix-org/sydent/blob/main/docs/templates.md) for more information. DEFAULTS TO `%(sender_display_name)s has invited you to a space`
`email.smtphost`            | The address of the SMTP server to use. DEFAULTS TO `localhost`
`email.smtppassword`        | The password to connect to the SMTP server with. DEFAULTS TO EMPTY
`email.smtpport`            | The port to connect to the SMTP server on. DEFAULTS TO `25`
`email.smtpusername`        | The username to connect to the SMTP server with. DEFAULTS TO EMPTY
`email.third_party_invite_username_obfuscate_characters` | The number of characters to from the beginning to reveal of an email's username portion (left of the '@' sign). See the [README](https://github.com/matrix-org/sydent/blob/main/README.rst) for more information on email obfuscation. DEFAULTS TO `3`
`email.third_party_invite_domain_obfuscate_characters` | The number of characters to from the beginning to reveal of an email's domain portion (right of the '@' sign). See the [README](https://github.com/matrix-org/sydent/blob/main/README.rst) for more information on email obfuscation. DEFAULTS TO `3`
`email.tlsmode`             | The security mode to use when connecting with the SMTP server. This can take one of the following options: `NONE`, `TLS`, `SSL`, `STARTTLS`. Any other value is equivalent to `NONE`. DEFAULTS TO `NONE`


### [sms]

Name                    | Description
---------               | -------
`bodyTemplate`          | The template to use for SMS validation texts. The string '{token}' will get replaced with the validation code. DEFAULTS TO `Your code is {token}`
`username`              | The username to use when connecting to the SMS sender at https://smsc.openmarket.com/sms/v4/mt. DEFAULTS TO EMPTY
`password`              | The password to use when connecting to the SMS sender at https://smsc.openmarket.com/sms/v4/mt. DEFAULTS TO EMPTY
`originators.XYZ`       | The list of originators to use when sending an SMS to a number with country code `XYZ`. The originator is chosen deterministically from this list so if someone requests multiple codes, they come from a consistent number. The originators must be in form: `long:<number>`, `short:<number>` or `alpha:<text>`, separated by commas. DEFAULTS TO UNSET
`originators.default`   | The default originator to use when sending an SMS. This must be of the form `long:<number>`, `short:<number>` or `alpha:<text>`. DEFAULTS TO UNSET
`smsrule.XYZ`           | Whether or not to allow verification texts to numbers with country code `XYZ`. If this option is set to `reject` then that country is blacklisted, otherwise it is allowed. DEFAULTS TO UNSET

### [crypto]

Name                | Description
---------           | -------
`ed25519.signingkey`| The key used to sign JSON sent by this server. A new key can be generated by running the [generate-key script](https://github.com/matrix-org/sydent/blob/main/scripts/generate-key). This must be set to start the server. NO DEFAULT

### [peer.XYZ]

Name                    | Description
---------               | -------
`base_replication_url`  | The base url of the peer with name `XYZ`. This should be of the form `https://internal-address.example.com:4434`. See [docs/replication.md](https://github.com/matrix-org/sydent/blob/main/docs/replication.md) for more information. DEFAULTS TO UNSET
