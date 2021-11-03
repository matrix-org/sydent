Sydent 2.4.7 (2021-11-03)
=========================

This release [supports](https://github.com/matrix-org/sydent/issues/437) [MSC3288](https://github.com/matrix-org/matrix-doc/pull/3288), [deprecates `.eml` templates](https://github.com/matrix-org/sydent/issues/395)) and includes many internal changes related to typechecking.

Features
--------

- Support the stable `room_type` field for [MSC3288](https://github.com/matrix-org/matrix-doc/pull/3288). ([\#437](https://github.com/matrix-org/sydent/issues/437))


Bugfixes
--------

- Fix a bug introduced in v2.4.0 that caused association unbindings to fail with an internal server error. ([\#397](https://github.com/matrix-org/sydent/issues/397))
- Fix an issue which could cause new local associations to be replicated multiple times to peers. ([\#400](https://github.com/matrix-org/sydent/issues/400))
- Fix an issue where `obey_x_forwarded_for` was not being honoured. ([\#403](https://github.com/matrix-org/sydent/issues/403))
- Fix a bug which could cause SMS sending to fail silently. ([\#412](https://github.com/matrix-org/sydent/issues/412))
- Fix misleading logging and potential TypeErrors related to replication ports in Sydent's database. ([\#420](https://github.com/matrix-org/sydent/issues/420))
- Fix a bug introduced in v2.0.0 where requesting `GET` from `/identity/api/v1/validate/msisdn/submitToken` or `/identity/v2/validate/msisdn/submitToken` would fail with an internal server error. ([\#445](https://github.com/matrix-org/sydent/issues/445))
- Fix `/v2/account/logout` to return HTTP 400 BAD REQUEST instead of 200 OK if a token was not provided. ([\#447](https://github.com/matrix-org/sydent/issues/447))
- Fix a long-standing spec compliance bug where the response to `POST /identity/{api/v1,v2}/3pid/unbind` was `null`, not `{}`. ([\#449](https://github.com/matrix-org/sydent/issues/449))


Improved Documentation
----------------------

- Fix the documentation around the command line arguments for the email address migration script. ([\#392](https://github.com/matrix-org/sydent/issues/392))
- Add documentation on writing templates. Deprecate .eml templates. ([\#395](https://github.com/matrix-org/sydent/issues/395))


Internal Changes
----------------

- Extend the changelog check so that it checks for the correct pull request number being used. ([\#382](https://github.com/matrix-org/sydent/issues/382))
- Move the configuration file handling code into a separate module. ([\#385](https://github.com/matrix-org/sydent/issues/385), [\#405](https://github.com/matrix-org/sydent/issues/405))
- Add a primitive contributing guide and tweak the pull request template. ([\#393](https://github.com/matrix-org/sydent/issues/393))
- Improve type annotations throughout Sydent. Sydent now passes `mypy --strict`. ([\#414](https://github.com/matrix-org/sydent/issues/414) and others).
- Run mypy on the sydent package as part of CI. ([\#416](https://github.com/matrix-org/sydent/issues/416))
- Configure @matrix-org/synapse-core to be the code owner for the repository. ([\#436](https://github.com/matrix-org/sydent/issues/436))
- Run linters over stub files. ([\#441](https://github.com/matrix-org/sydent/issues/441), [\#450](https://github.com/matrix-org/sydent/issues/450))
- Include Sydent's version number (and git commit hash if available) when reporting to Sentry. ([\#453](https://github.com/matrix-org/sydent/issues/453), [\#454](https://github.com/matrix-org/sydent/issues/454))
