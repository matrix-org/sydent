# Contributing code to Sydent

Everyone is welcome to contribute code to Sydent, provided you are willing to
license your contributions under the same license as the project itself. In
this case, the [Apache Software License v2](LICENSE).

## Set up your development environment

To contribute to Sydent, ensure you have Python 3.7 and `git` available on your 
system. You'll need to clone the source code first:

```shell
git clone https://github.com/matrix-org/sydent.git
```

### Installing `poetry`

Sydent uses [Poetry](https://python-poetry.org/) to manage its dependencies.
See [its installation instructions](https://python-poetry.org/docs/master/#installation)
to get started. They recommend using a custom installation script, which installs
poetry in an isolated environment capable of self updating. We recommend using
[`pipx`](https://pypa.github.io/pipx/) instead:

```shell
pip install pipx
pipx install poetry==1.1.12
poetry --version
```

For the time being, we are erring towards caution by using a pinned version of 
poetry.

### Generate a virtualenv

Poetry manages a virtual environment ('virtualenv') for Sydent, using specific versions of
every dependency. To create this environment, run

```bash
cd sydent
poetry install
```

This installs Sydent, its dependencies, and useful development tools into poetry's
virtual environment. To run a one-off command in this environment, use `poetry run`.
Otherwise, you'll end up running against the system python environment.

```shell
$ which python
/usr/bin/python
$ poetry run which python
/home/user/.cache/pypoetry/virtualenvs/matrix-sydent-Ew7U0NLX-py3.10/bin/python
```

To avoid repeatedly typing out `poetry run`, use `poetry shell`:

```shell
$ poetry shell
Spawning shell within /home/user/.cache/pypoetry/virtualenvs/matrix-sydent-Ew7U0NLX-py3.10
. /home/user/.cache/pypoetry/virtualenvs/matrix-sydent-Ew7U0NLX-py3.10/bin/activate

$ which python
~/.cache/pypoetry/virtualenvs/matrix-sydent-Ew7U0NLX-py3.10/bin/python
```

Be sure to do this _every time_ you open a new terminal window for working on
Sydent. Using `poetry run` or `poetry shell` ensures that any Python commands 
you run (`pip`, `python`, etc.) use the versions inside your venv, and not your 
system Python.

When you're done, you can close your terminal.

### Optional: `direnv`

If even typing `poetry shell` is too much work for you, take a look at 
[`direnv`](https://direnv.net/). A few steps are needed:

1. install direnv.
2. Add the configuration from [here](https://github.com/direnv/direnv/wiki/Python#poetry) to `~/.direnvrc`.
3. In the Sydent checkout, run `echo layout poetry >> .envrc`. Then run `direnv allow`.

From now on, when you `cd` into the sydent directory, `poetry shell` will run automatically. Whenever you navigate out of the sydent directory, you'll no longer be using poetry's venv.

### Run the unit tests

To make sure everything is working as expected, run the unit tests:

```bash
poetry run trial tests
```

If you see a message like:

```
-------------------------------------------------------------------------------
Ran 25 tests in 0.324s

PASSED (successes=25)
```

Then all is well and you're ready to work!

### Run the black-box tests

Sydent uses [matrix-is-tester](https://github.com/matrix-org/matrix-is-tester/) to provide
black-box testing of compliance with the [Matrix Identity Service API](https://matrix.org/docs/spec/identity_service/latest).
(Features that are Sydent-specific belong in unit tests rather than the black-box test suite.)
This project is marked as a development dependency, so Poetry will automatically
install for you.

Now, to run `matrix-is-tester`, execute:
```
poetry run trial matrix_is_tester
```

#### Advanced

The steps above are sufficient and describe a clean way to run the black-box tests.
However, in the event that you need more control, this subsection provides more information.

The `SYDENT_PYTHON` environment variable can be set to launch Sydent with a specific python binary:

```
SYDENT_PYTHON=/path/to/python trial matrix_is_tester
```

The `matrix_is_test` directory contains Sydent's launcher for `matrix_is_tester`: this means
that Sydent's directory needs to be on the Python path (e.g. `PYTHONPATH=$PYTHONPATH:/path/to/sydent`).

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

## Code style and continuous integration

Sydent uses `black`, `isort` and `flake8` to enforce code style. Use the following
script to enforce these style guides:

```shell
poetry run scripts-dev/lint.sh
```

(This also runs `mypy`, our preferred typechecker.)

All of these checks are automatically run against any pull request via GitHub
Actions. If your change breaks the build, this
will be shown in GitHub, with links to the build results. If your build fails,
please try to fix the errors and update your branch.

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
