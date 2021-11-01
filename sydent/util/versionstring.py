import logging
import os
import subprocess

import sydent

logger = logging.getLogger(__name__)


def get_version_string() -> str:
    """Calculate a git-aware version string for sydent.

    Implementation nicked from Synapse.
    """
    version_string = sydent.__version__

    try:
        cwd = os.path.dirname(os.path.abspath(sydent.__file__))

        try:
            git_branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    cwd=cwd,
                )
                .strip()
                .decode("ascii")
            )
            git_branch = "b=" + git_branch
        except (subprocess.CalledProcessError, FileNotFoundError):
            # FileNotFoundError can arise when git is not installed
            git_branch = ""

        try:
            git_tag = (
                subprocess.check_output(
                    ["git", "describe", "--exact-match"],
                    stderr=subprocess.DEVNULL,
                    cwd=cwd,
                )
                .strip()
                .decode("ascii")
            )
            git_tag = "t=" + git_tag
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_tag = ""

        try:
            git_commit = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    cwd=cwd,
                )
                .strip()
                .decode("ascii")
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_commit = ""

        try:
            dirty_string = "-this_is_a_dirty_checkout"
            is_dirty = (
                subprocess.check_output(
                    ["git", "describe", "--dirty=" + dirty_string],
                    stderr=subprocess.DEVNULL,
                    cwd=cwd,
                )
                .strip()
                .decode("ascii")
                .endswith(dirty_string)
            )

            git_dirty = "dirty" if is_dirty else ""
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_dirty = ""

        if git_branch or git_tag or git_commit or git_dirty:
            git_version = ",".join(
                s for s in (git_branch, git_tag, git_commit, git_dirty) if s
            )

            version_string = f"sydent@{sydent.__version__} ({git_version})"
    except Exception as e:
        logger.info("Failed to check for git repository: %s", e)

    return version_string
