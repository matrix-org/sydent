#!/usr/bin/env bash
#
# A script which checks that an appropriate news file has been added on this
# branch.
#
# As first argument, it requires the PR number, so that it can check that the
# newsfragment has the correct name.
#
# Usage:
#   ./scripts-dev/check_newsfragment.sh 382
#
# Exit codes:
#   0: all is well
#   1: the newsfragment is wrong in some way
#   9: the script has not been invoked properly

echo -e "+++ \e[32mChecking newsfragment\e[m"

set -e

if [ -z "$1" ]; then
  echo "Please specify the PR number as the first argument (e.g. 382)."
  exit 9
fi

pull_request_number="$1"

# Print a link to the contributing guide if the user makes a mistake
CONTRIBUTING_GUIDE_TEXT="!! Please see the contributing guide for help writing your changelog entry:
https://github.com/matrix-org/sydent/blob/main/CONTRIBUTING.md#changelog"

# If towncrier returns a non-zero exit code, print the contributing guide link and exit
python -m towncrier.check --compare-with="origin/main" || (echo -e "$CONTRIBUTING_GUIDE_TEXT" >&2 && exit 1)

echo
echo "--------------------------"
echo

matched=0
for f in `git diff --name-only origin/main... -- changelog.d`; do
    # check that any modified newsfiles on this branch end with a full stop.
    lastchar=`tr -d '\n' < $f | tail -c 1`
    if [ $lastchar != '.' -a $lastchar != '!' ]; then
        echo -e "\e[31mERROR: newsfragment $f does not end with a '.' or '!'\e[39m" >&2
        echo -e "$CONTRIBUTING_GUIDE_TEXT" >&2
        exit 1
    fi

    # see if this newsfile corresponds to the right PR
    [[ -n "$pull_request_number" && "$f" == changelog.d/"$pull_request_number".* ]] && matched=1
done

if [[ -n "$pull_request_number" && "$matched" -eq 0 ]]; then
    echo -e "\e[31mERROR: Did not find a news fragment with the right number: expected changelog.d/$pull_request_number.*.\e[39m" >&2
    echo -e "$CONTRIBUTING_GUIDE_TEXT" >&2
    exit 1
fi
