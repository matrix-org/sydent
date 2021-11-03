Sydent 2.4.7 (2021-11-03)
=========================

Features
--------

- Support the stable room type field for [MSC3288](https://github.com/matrix-org/matrix-doc/pull/3288). ([\#437](https://github.com/matrix-org/sydent/issues/437))


Bugfixes
--------

- Fix a bug introduced in v2.4.0 that caused association unbindings to fail with an Internal Server Error. ([\#397](https://github.com/matrix-org/sydent/issues/397))
- Fix an issue which could cause new local associations to be replicated multiple times to peers. ([\#400](https://github.com/matrix-org/sydent/issues/400))
- Fix issue with `obey_x_forwarded_for` not being honoured. ([\#403](https://github.com/matrix-org/sydent/issues/403))
- Fix a bug which could cause SMS sending to fail silently. ([\#412](https://github.com/matrix-org/sydent/issues/412))
- Fix misleading logging and potential TypeErrors related to replication ports in Sydent's database. ([\#420](https://github.com/matrix-org/sydent/issues/420))
- Fix a bug introduced in Sydent 2.0.0 where requesting `GET` from `/identity/api/v1/validate/msisdn/submitToken` or `/identity/v2/validate/msisdn/submitToken` would fail with an internal server error. ([\#445](https://github.com/matrix-org/sydent/issues/445))
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
- Run mypy on the sydent package as part of CI. ([\#416](https://github.com/matrix-org/sydent/issues/416))
- Add linting script and `.gitignore` config for development. ([\#417](https://github.com/matrix-org/sydent/issues/417))
- Add type hints to `sydent.util`. ([\#418](https://github.com/matrix-org/sydent/issues/418))
- Add type hints to `sydent.db`. ([\#421](https://github.com/matrix-org/sydent/issues/421))
- Add type hints so `sydent.validators` passes `mypy --strict`. ([\#425](https://github.com/matrix-org/sydent/issues/425))
- Type annotate the result of reading from the db in `sydent.db`. ([\#426](https://github.com/matrix-org/sydent/issues/426))
- Make `sydent.threepid` pass `mypy --strict`. ([\#427](https://github.com/matrix-org/sydent/issues/427))
- Make `sydent.terms` pass `mypy --strict`. ([\#428](https://github.com/matrix-org/sydent/issues/428))
- Make `sydent.sms` pass `mypy --strict`. ([\#429](https://github.com/matrix-org/sydent/issues/429))
- Make `sydent.replication` pass `mypy --strict`. ([\#430](https://github.com/matrix-org/sydent/issues/430))
- Make `sydent.config` pass `mypy --strict`. ([\#431](https://github.com/matrix-org/sydent/issues/431))
- Make `sydent.hs_federation` pass `mypy --strict`. ([\#432](https://github.com/matrix-org/sydent/issues/432))
- Make `sydent.http.auth` pass `mypy --strict`. ([\#433](https://github.com/matrix-org/sydent/issues/433))
- Add type annotations to `mypy.http.federation_tls_options`. ([\#434](https://github.com/matrix-org/sydent/issues/434))
- Make `sydent.http.srvresolver` pass `mypy --strict`. ([\#435](https://github.com/matrix-org/sydent/issues/435))
- Configure @matrix-org/synapse-core to be the code owner for the repository. ([\#436](https://github.com/matrix-org/sydent/issues/436))
- Make `sydent.http.{httpclient, httpsclient, httpcommon}` pass `mypy --strict`. ([\#439](https://github.com/matrix-org/sydent/issues/439))
- Run linters over stub files. ([\#441](https://github.com/matrix-org/sydent/issues/441))
- Make `sydent.http.httpserver` pass `mypy --strict`. ([\#442](https://github.com/matrix-org/sydent/issues/442))
- More accurately use `IResponse` rather than `http.Response` in type hints. ([\#443](https://github.com/matrix-org/sydent/issues/443))
- Get `sydent.http.matrixfederationagent` to pass `mypy --strict`. ([\#444](https://github.com/matrix-org/sydent/issues/444))
- Make `sydent.http.servlets` pass `mypy --strict`. ([\#446](https://github.com/matrix-org/sydent/issues/446))
- Finish `mypy --strict` coverage for `sydent`. ([\#448](https://github.com/matrix-org/sydent/issues/448))
- Properly lint stub files in CI. ([\#450](https://github.com/matrix-org/sydent/issues/450))
- Include Sydent's version number (and git commit hash if available) when reporting to Sentry. ([\#453](https://github.com/matrix-org/sydent/issues/453), [\#454](https://github.com/matrix-org/sydent/issues/454))
