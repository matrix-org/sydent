Unreleased changes
==================

 * Delete stored invites upon successful delivery to a homeserver
 * Fix a bug that would prevent requests to the `/store-invite` endpoint with
   JSON payloads from being correctly processed
 * Filter out delivered invites when delivering invites to a homserver upon
   successful binding
 * Implement support for authenticating unbind queries by providing a `sid` and a
   `client_secret`, as per [MSC1915](https://github.com/matrix-org/matrix-doc/blob/master/proposals/1915-unbind-identity-server-param.md)
 * Add support for Prometheus and Sentry
 * Handle .well-known files when talking to homeservers
 * Fix a bug where multiple cleanup tasks would be unnecessary spawned
 * Fix logging so Sydent doesn't log 3PIDs when processing lookup requests
 * Fix incorrect HTTP response from `/3pid/getValidated3pid` endpoint on
   failure. [#216](https://github.com/matrix-org/sydent/pull/216)
 * Improve performance of hashed lookups


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
