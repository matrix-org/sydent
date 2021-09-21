# Contributing code to Sydent

Everyone is welcome to contribute code to Sydent, provided you are willing to
license your contributions under the same license as the project itself. In
this case, the [Apache Software License v2](LICENSE).

### Create a virtualenv

To contribute to Sydent, ensure you have Python 3.7 or newer and then run:

```bash
python3 -m venv venv
./venv/bin/pip install -e '.[dev]'
```

This creates an isolated virtual Python environment ("virtualenv") just for
use with Sydent, then installs Sydent along with its dependencies, and lastly
installs a handful of useful tools

If you get `ConnectTimeoutError`, this is caused by slow internet whereby 
`pip` has a default time out of _15 sec_. You can specify a larger timeout 
by passing `--timeout 120` to the `pip install` command above.

Finally, activate the virtualenv by running:

```bash
source ./venv/bin/activate
```

Be sure to do this _every time_ you open a new terminal window for working on
Sydent. Activating the venv ensures that any Python commands you run (`pip`,
`python`, etc.) use the versions inside your venv, and not your system Python.

When you're done, you can close your terminal or run `deactivate` to disable
the virtualenv.

### Run the tests

To make sure everything is working as expected, run the unit tests:

```bash
trial tests
```

If you see a message like:

```
-------------------------------------------------------------------------------
Ran 25 tests in 0.324s

PASSED (successes=25)
```

Then all is well and you're ready to work!

If `trial tests` fails but `python -m twisted.trial tests` succeeds, try ensuring
your venv is activated and re-installing using `pip install -e '.[dev]'`, making
sure to remember the `-e` flag.

## How to contribute

The preferred and easiest way to contribute changes is to fork the relevant
project on github, and then [create a pull request](
https://help.github.com/articles/using-pull-requests/) to ask us to pull your
changes into our repo.

Some other points to follow:

 * Please base your changes on the `main` branch.

 * Please follow the [code style requirements](#code-style).

 * Please include a [changelog entry](#changelog) with each PR.

 * Please [sign off](#sign-off) your contribution.

 * Please keep an eye on the pull request for feedback from the [continuous
   integration system](#continuous-integration-and-testing) and try to fix any
   errors that come up.

 * If you need to [update your PR](#updating-your-pull-request), just add new
   commits to your branch rather than rebasing.

## Code style

Sydent follows the [Synapse code style].

[Synapse code style]: https://github.com/matrix-org/synapse/blob/master/CONTRIBUTING.md

<!-- TODO
Many of the conventions are enforced by scripts which are run as part of the
[continuous integration system](#continuous-integration-and-testing).


To help check and fix adherence to the code style, you can run `tox`
locally. You'll need Python 3.7 or later, and a virtual environment configured and
active:

```bash
# Activate the virtual environment
source ./venv/bin/activate

# Run the code style check
tox -e check_codestyle

# Run the types check
tox -e check_types
```

These commands will consider the paths and files related to the project (i.e.
everything in `sydent/` and in `tests/` as well as the `setup.py` file).

Before pushing new changes, ensure they don't produce linting errors. Commit any
files that were corrected.
-->

Please ensure your changes match the cosmetic style of the existing project,
and **never** mix cosmetic and functional changes in the same commit, as it
makes it horribly hard to review otherwise.

## Changelog

All changes, even minor ones, need a corresponding changelog / newsfragment
entry. These are managed by [Towncrier](https://github.com/hawkowl/towncrier).

To create a changelog entry, make a new file in the `changelog.d` directory named
in the format of `PRnumber.type`. The type can be one of the following:

* `feature`
* `bugfix`
* `docker` (for updates to the Docker image)
* `doc` (for updates to the documentation)
* `removal` (also used for deprecations)
* `misc` (for internal-only changes)

This file will become part of our [changelog](
https://github.com/matrix-org/sydent/blob/master/CHANGELOG.md) at the next
release, so the content of the file should be a short description of your
change in the same style as the rest of the changelog. The file can contain Markdown
formatting, and should end with a full stop (.) or an exclamation mark (!) for
consistency.

**PLEASE DO** add credits for yourself to your changelog entry, by writing
'Contributed by *Your Name*.' or 'Contributed by @*your-github-username*.' at the
end of your changelog entry, unless you would prefer not to.
We value your contributions and would like to have you shouted out in the release
notes!

For example, a fix in PR #1234 would have its changelog entry in
`changelog.d/1234.bugfix`, and contain content like:

> The security levels of Florbs are now validated when received
> via the `/federation/florb` endpoint. Contributed by Jane Matrix.

If there are multiple pull requests involved in a single bugfix/feature/etc,
then the content for each `changelog.d` file should be the same. Towncrier will
merge the matching files together into a single changelog entry when we come to
release.

### How do I know what to call the changelog file before I create the PR?

Obviously, you don't know if you should call your newsfile
`1234.bugfix` or `5678.bugfix` until you create the PR, which leads to a
chicken-and-egg problem.

There are two options for solving this:

 1. Open the PR without a changelog file, see what number you got, and *then*
    add the changelog file to your branch (see [Updating your pull
    request](#updating-your-pull-request)), or:

 2. Look at the [list of all
    issues/PRs](https://github.com/matrix-org/sydent/issues?q=), add one to the
    highest number you see, and quickly open the PR before somebody else claims
    your number.

    [This
    script](https://github.com/richvdh/scripts/blob/master/next_github_number.sh)
    might be helpful if you find yourself doing this a lot.

Sorry, we know it's a bit fiddly, but it's *really* helpful for us when we come
to put together a release!

## Sign off

In order to have a concrete record that your contribution is intentional
and you agree to license it under the same terms as the project's license, we've adopted the
same lightweight approach that the Linux Kernel
[submitting patches process](
https://www.kernel.org/doc/html/latest/process/submitting-patches.html#sign-your-work-the-developer-s-certificate-of-origin>),
[Docker](https://github.com/docker/docker/blob/master/CONTRIBUTING.md), and many other
projects use: the DCO (Developer Certificate of Origin:
https://developercertificate.org/). This is a simple declaration that you wrote
the contribution or otherwise have the right to contribute it to Matrix:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
660 York Street, Suite 102,
San Francisco, CA 94110 USA

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

If you agree to this for your contribution, then all that's needed is to
include the line in your commit or pull request comment:

```
Signed-off-by: Your Name <your@email.example.org>
```

We accept contributions under a legally identifiable name, such as
your name on government documentation or common-law names (names
claimed by legitimate usage or repute). Unfortunately, we cannot
accept anonymous contributions at this time.

Git allows you to add this signoff automatically when using the `-s`
flag to `git commit`, which uses the name and email set in your
`user.name` and `user.email` git configs.


## Continuous integration and testing

*GitHub Actions* will automatically run a series of checks and tests against any
PR which is opened against the project; if your change breaks the build, this
will be shown in GitHub, with links to the build results. If your build fails,
please try to fix the errors and update your branch.

<!-- TODO
After installing tox with `pip install tox`, you can use the following to run
unit tests and lints in a local development environment:

- `tox -e py37` to run unit tests on Python 3.7.
- `tox -e check_codestyle` to check code style and formatting.
- `tox -e check_types` to check types with MyPy.
- `tox` **to do all of the above.**
-->

## Updating your pull request

If you decide to make changes to your pull request - perhaps to address issues
raised in a review, or to fix problems highlighted by [continuous
integration](#continuous-integration-and-testing) - just add new commits to your
branch, and push to GitHub. The pull request will automatically be updated.

Please **avoid** rebasing your branch, especially once the PR has been
reviewed: doing so makes it very difficult for a reviewer to see what has
changed since a previous review.

## Conclusion

That's it! Matrix is a very open and collaborative project as you might expect
given our obsession with open communication. If we're going to successfully
matrix together all the fragmented communication technologies out there we are
reliant on contributions and collaboration from the community to do so. So
please get involved - and we hope you have as much fun hacking on Matrix as we
do!
