#!/usr/bin/env bash
#
# A script which checks that an appropriate news file has been added on this
# branch.

echo -e "+++ \033[32mChecking newsfragment\033[m"

set -e

pr="$1"

# Print a link to the contributing guide if the user makes a mistake
CONTRIBUTING_GUIDE_TEXT="!! Please see the contributing guide for help writing your changelog entry:
https://github.com/matrix-org/sygnal/blob/main/CONTRIBUTING.md#changelog"

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
    [[ -n "$pr" && "$f" == changelog.d/"$pr".* ]] && matched=1
done

if [[ -n "$pr" && "$matched" -eq 0 ]]; then
    echo -e "\e[31mERROR: Did not find a news fragment with the right number: expected changelog.d/$pr.*.\e[39m" >&2
    echo -e "$CONTRIBUTING_GUIDE_TEXT" >&2
    exit 1
fi
