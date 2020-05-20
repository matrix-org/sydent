Sydent 2.0.1 (2020-05-20)
=========================

Features
--------

- Add a config option to disable deleting invite tokens on bind. ([\#293](https://github.com/matrix-org/sydent/issues/293))


Bugfixes
--------

- Fix a bug that prevented Sydent from checking for OpenID auth tokens in request parameters when running on Python3. ([\#294](https://github.com/matrix-org/sydent/issues/294))


Internal Changes
----------------

- Make replication tests more reliable. ([\#278](https://github.com/matrix-org/sydent/issues/278))
- Add a configuration for towncrier. ([\#295](https://github.com/matrix-org/sydent/issues/295))


Changes in [2.0.0](https://github.com/matrix-org/sydent/releases/tag/v2.0.0) (2020-02-25)
=========================================================================================

**Note:** Starting with this release, Sydent releases are available on
[PyPI](https://pypi.org/project/matrix-sydent). This means that the
recommended method for stable installations is now by using the PyPI
project rather than a tarball of the `master` branch of this repository.
See [the README](https://github.com/matrix-org/sydent/blob/v2.0.0/README.rst)
for more details.

**Warning:** This release deprecates v1 APIs for existing endpoints in favour
of v2 APIs. Homeserver and client developers are encouraged to migrate their
applications to the v2 APIs. See below for more information.

Features
--------
 * Implement the items and MSCs from the [privacy project](https://matrix.org/blog/2019/09/27/privacy-improvements-in-synapse-1-4-and-riot-1-4)
   targeting identity servers. This introduces v2 APIs for every existing endpoint. v1 APIs are now deprecated and
   homeserver and client developers are encouraged to migrate their applications to the v2 APIs.
 * Add Python 3 compatibility to all of the codebase. Python 2 is still supported for now.
 * Delete stored invites upon successful delivery to a homeserver
 * Filter out delivered invites when delivering invites to a homeserver upon
   successful binding
 * Implement support for authenticating unbind queries by providing a `sid` and a
   `client_secret`, as per [MSC1915](https://github.com/matrix-org/matrix-doc/blob/master/proposals/1915-unbind-identity-server-param.md)
 * Add support for Prometheus and Sentry
 * Handle `.well-known` files when talking to homeservers
 * Validate `client_secret` parameters according to the Matrix specification
 * Return 400/404 on incorrect session validation
 * Add a default 10,000 address limit on v2 `/lookup` (which supports multiple lookups at once)

Documentation
-------------

 * Rewrite part of the README to make it more user-friendly

Bugfixes
--------

 * Fix a bug that would prevent requests to the `/store-invite` endpoint with
   JSON payloads from being correctly processed
 * Fix a bug where multiple cleanup tasks would be unnecessary spawned
 * Fix logging so Sydent doesn't log 3PIDs when processing lookup requests
 * Fix incorrect HTTP response from `/3pid/getValidated3pid` endpoint on
   failure.
 * Prevent a single failure from aborting the federation loop
 * Fix federation lookups in `/onBind` callbacks
 * Don't fail the unbind request if the binding doesn't exist
 * Fix the signing servlet missing a reference to the Sydent object
 * Fix content types & OPTIONS requests

Internal changes
----------------

 * Add unit tests to test startup and replication
 * Add support for testing with `matrix-is-tester`
 * Remove instances of `setResponseCode(200)`


Changes in [1.0.3](https://github.com/matrix-org/sydent/releases/tag/v1.0.3) (2019-05-03)
=========================================================================================

 * Use trustRoot instead of verify for request verification

Security Fixes
--------------
 * Ensures that authentication tokens are generated using a secure random number
   generator, ensuring they cannot be predicted by an attacker. Thanks to @opnsec
   for identifying and responsibly disclosing the issue!
 * Mitigate an HTML injection bug where an invalid room_id could result in
   malicious HTML being injected into validation emails. Thanks to @opnsec
   for identifying and responsibly disclosing this issue too!
 * Randomise session_ids to avoid leaking info about the total number of
   identity validations, and whether a given ID has been validated.
   Thanks to @fs0c131y for this one.
 * Don't send tracebacks to the browser when errors occur.


Changes in [1.0.2](https://github.com/matrix-org/sydent/releases/tag/v1.0.2) (2019-04-18)
=========================================================================================

Security Fixes
--------------
 * Fix for validating malformed email addresses: https://github.com/matrix-org/sydent/commit/3103b65dcfa37a9241dabedba560c4ded6c05ff6


Changes in [1.0.1](https://github.com/matrix-org/sydent/releases/tag/v1.0.1) (2019-04-18)
=========================================================================================

Release pointed to wrong commit, fixed by 1.0.2
