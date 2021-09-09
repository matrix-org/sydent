Sydent 2.4.0 (2021-09-09)
=========================

**Action required when upgrading**: server administrators should run [the e-mail address migration script](./docs/casefold_migration.md).

Features
--------

- Experimental support for [MSC3288](https://github.com/matrix-org/matrix-doc/pull/3288), receiving `room_type` for 3pid invites over the `/store-invite` API and using it in Jinja templates for Space invites. ([\#375](https://github.com/matrix-org/sydent/issues/375))
- Add support for using Jinja2 in e-mail templates. Contributed by @H-Shay. ([\#376](https://github.com/matrix-org/sydent/issues/376))
- Case-fold email addresses when binding to MXIDs or performing look-ups. Contributed by @H-Shay. ([\#374](https://github.com/matrix-org/sydent/issues/374), [\#378](https://github.com/matrix-org/sydent/issues/378), [\#379](https://github.com/matrix-org/sydent/issues/379), [\#386](https://github.com/matrix-org/sydent/issues/386))


Bugfixes
--------

- Handle CORS for `GetValidated3pidServlet`. Endpoint `/3pid/getValidated3pid` returns valid CORS headers. ([\#342](https://github.com/matrix-org/sydent/issues/342))
- Use the `web_client_location` parameter in default templates for both text and HTML emails. ([\#380](https://github.com/matrix-org/sydent/issues/380))


Internal Changes
----------------

- Add `/_trial_temp.lock` and `/sydent.pid` to .gitignore. ([\#384](https://github.com/matrix-org/sydent/issues/384))
- Reformat code using Black. Contributed by @H-Shay. ([\#344](https://github.com/matrix-org/sydent/issues/344), [\#369](https://github.com/matrix-org/sydent/issues/369))
- Configure Flake8 and resolve errors. ([\#345](https://github.com/matrix-org/sydent/issues/345), [\#347](https://github.com/matrix-org/sydent/issues/347))
- Add GitHub Actions for unit tests (Python 3.6 and 3.9), matrix_is_tester tests (Python 3.6 and 3.9), towncrier checks and black and flake8 codestyle checks. ([\#346](https://github.com/matrix-org/sydent/issues/346), [\#348](https://github.com/matrix-org/sydent/issues/348))
- Remove support for Python < 3.6. Contributed by @sunweaver. ([\#349](https://github.com/matrix-org/sydent/issues/349), [\#356](https://github.com/matrix-org/sydent/issues/356))
- Bump minimum supported version of Twisted to 18.4.0 and stop calling deprecated APIs. ([\#350](https://github.com/matrix-org/sydent/issues/350))
- Replace deprecated `logging.warn()` method with `logging.warning()`. ([\#351](https://github.com/matrix-org/sydent/issues/351))
- Reformat imports using isort. ([\#352](https://github.com/matrix-org/sydent/issues/352), [\#353](https://github.com/matrix-org/sydent/issues/353))
- Update `.gitignore` to only ignore `sydent.conf` and `sydent.db` if they occur in the project's base folder. ([\#354](https://github.com/matrix-org/sydent/issues/354))
- Add type hints and validate with mypy. ([\#355](https://github.com/matrix-org/sydent/issues/355), [\#357](https://github.com/matrix-org/sydent/issues/357), [\#358](https://github.com/matrix-org/sydent/issues/358), [\#360](https://github.com/matrix-org/sydent/issues/360), [\#361](https://github.com/matrix-org/sydent/issues/361), [\#367](https://github.com/matrix-org/sydent/issues/367), [\#371](https://github.com/matrix-org/sydent/issues/371))
- Convert `inlineCallbacks` to async/await. ([\#364](https://github.com/matrix-org/sydent/issues/364), [\#365](https://github.com/matrix-org/sydent/issues/365), [\#368](https://github.com/matrix-org/sydent/issues/368), [\#372](https://github.com/matrix-org/sydent/issues/372), [\#373](https://github.com/matrix-org/sydent/issues/373))
- Use `mock` module from the standard library. ([\#370](https://github.com/matrix-org/sydent/issues/370))
- Fix email templates to be valid python format strings. ([\#377](https://github.com/matrix-org/sydent/issues/377))


Sydent 2.3.0 (2021-04-15)
=========================

**Note**: this will be the last release of Sydent to support Python 3.5 or earlier. Future releases will require at least Python 3.6.

Security advisory
-----------------

This release contains fixes to the following security issues:

- Denial of service attack via disk space or memory exhaustion ([CVE-2021-29430](https://cve.mitre.org/cgi-bin/cvename.cgi?name=2021-29430)).
- SSRF due to missing validation of hostnames ([CVE-2021-29431](https://cve.mitre.org/cgi-bin/cvename.cgi?name=2021-29431)).
- Malicious users could control the content of invitation emails ([CVE-2021-29432](https://cve.mitre.org/cgi-bin/cvename.cgi?name=2021-29432)).
- Denial of service (via resource exhaustion) due to improper input validation ([CVE-2021-29433](https://cve.mitre.org/cgi-bin/cvename.cgi?name=2021-29433)).

Although we are not aware of these vulnerabilities being exploited in the wild, Sydent server administrators are advised to update as soon as possible. Note that as well as changes to the package, there are also changes to the default email templates. If any templates have been updated locally, they must also be updated in line with the changes to the defaults for full protection from CVE-2021-29432.

Features
--------

- Accept an optional `web_client_location` argument to the invite endpoint which allows customisation of the email template. ([\#326](https://github.com/matrix-org/sydent/issues/326))
- Move templates to a per-brand subdirectory of `/res`. Add `templates.path` and `brand.default` config options. ([\#328](https://github.com/matrix-org/sydent/issues/328))


Bugfixes
--------

- Fix a regression in v2.2.0 where the wrong characters would be obfuscated in a 3pid invite. ([\#317](https://github.com/matrix-org/sydent/issues/317))
- Fix a long-standing bug where invalid JSON would be accepted over the HTTP interfaces. ([\#337](https://github.com/matrix-org/sydent/issues/337))
- During user registration on the identity server, validate that the MXID returned by the contacted homeserver is valid for that homeserver. ([cc97fff](https://github.com/matrix-org/sydent/commit/cc97fff))
- Ensure that `/v2/` endpoints are correctly authenticated. ([ce04a68](https://github.com/matrix-org/sydent/commit/ce04a68))
- Perform additional validation on the response received when requesting server signing keys. ([07e6da7](https://github.com/matrix-org/sydent/commit/07e6da7))
- Validate the `matrix_server_name` parameter given during user registration. ([9e57334](https://github.com/matrix-org/sydent/commit/9e57334), [8936925](https://github.com/matrix-org/sydent/commit/8936925), [3d531ed](https://github.com/matrix-org/sydent/commit/3d531ed), [0f00412](https://github.com/matrix-org/sydent/commit/0f00412))
- Limit the size of requests received from HTTP clients. ([89071a1](https://github.com/matrix-org/sydent/commit/89071a1), [0523511](https://github.com/matrix-org/sydent/commit/0523511), [f56eee3](https://github.com/matrix-org/sydent/commit/f56eee3))
- Limit the size of responses received from HTTP servers. ([89071a1](https://github.com/matrix-org/sydent/commit/89071a1), [0523511](https://github.com/matrix-org/sydent/commit/0523511), [f56eee3](https://github.com/matrix-org/sydent/commit/f56eee3))
- In invite emails, randomise the multipart boundary, and include MXIDs where available. ([4469d1d](https://github.com/matrix-org/sydent/commit/4469d1d), [6b405a8](https://github.com/matrix-org/sydent/commit/6b405a8), [65a6e91](https://github.com/matrix-org/sydent/commit/65a6e91))
- Perform additional validation on the `client_secret` and `email` parameters to various APIs. ([3175fd3](https://github.com/matrix-org/sydent/commit/3175fd3))


Updates to the Docker image
---------------------------

- Base docker image on Debian rather than Alpine Linux. ([\#335](https://github.com/matrix-org/sydent/issues/335))


Internal Changes
----------------

- Fix test logging to allow braces in log output. ([\#318](https://github.com/matrix-org/sydent/issues/318))
- Install prometheus_client in the Docker image. ([\#325](https://github.com/matrix-org/sydent/issues/325))
- Bump the version of signedjson to 1.1.1. ([\#334](https://github.com/matrix-org/sydent/issues/334))


Sydent 2.2.0 (2020-09-11)
=========================

Bugfixes
--------

- Fix intermittent deadlock in Sentry integration. ([\#312](https://github.com/matrix-org/sydent/issues/312))


Sydent 2.1.0 (2020-09-10)
=========================

Features
--------

- Add a Dockerfile and allow environment variables `SYDENT_SERVER_NAME`, `SYDENT_PID_FILE` and `SYDENT_DB_PATH` to modify default configuration values. ([\#290](https://github.com/matrix-org/sydent/issues/290))
- Add config options for controlling how email addresses are obfuscated in third party invites. ([\#311](https://github.com/matrix-org/sydent/issues/311))


Bugfixes
--------

- Fix a bug in the error handling of 3PID session validation, if the token submitted is incorrect. ([\#296](https://github.com/matrix-org/sydent/issues/296))
- Stop sending the unspecified `success` parameter in responses to `/requestToken` requests. ([\#302](https://github.com/matrix-org/sydent/issues/302))
- Fix a bug causing Sydent to ignore `nextLink` parameters. ([\#303](https://github.com/matrix-org/sydent/issues/303))
- Fix the HTTP status code returned during some error responses. ([\#305](https://github.com/matrix-org/sydent/issues/305))
- Sydent now correctly enforces the valid characters in the `client_secret` parameter used in various endpoints. ([\#309](https://github.com/matrix-org/sydent/issues/309))


Internal Changes
----------------

- Replace instances of Riot with Element. ([\#308](https://github.com/matrix-org/sydent/issues/308))


Sydent 2.0.1 (2020-05-20)
=========================

Features
--------

- Add a config option to disable deleting invite tokens on bind. ([\#293](https://github.com/matrix-org/sydent/issues/293))


Bugfixes
--------

- Fix a bug that prevented Sydent from checking for access tokens in request parameters when running on Python3. ([\#294](https://github.com/matrix-org/sydent/issues/294))


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
