#! /usr/bin/env python3
import datetime
import re
import tempfile
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from subprocess import check_output, check_call, call, DEVNULL
from typing import List


extract_precision = re.compile(
    r"\|[^|]+" r"\|\s+([0-9.]+)% imprecise " r"\| (\d+) LOC \|"
)

"""Quick & dirty script to fetch mypy's precision metrics over a commit range.

Use e.g. as 
    python mypy-precision.py A B >> results.csv
    python mypy-precision.py B C >> results.csv
(But beware that'll duplicate the entry for commit B)
"""


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Compute mypy precision over time")
    parser.add_argument("start")
    parser.add_argument("end", nargs="?", default="main")
    return parser


@dataclass
class Entry:
    commit: str
    imprecision: float
    loc: int
    timestamp: datetime.datetime


def main(args: Namespace) -> None:
    stats: List[Entry] = []

    current_commit = check_output(["git", "rev-parse", "HEAD"])
    commits = check_output(["git", "rev-list", "--reverse", f"^{args.start}", args.end]).decode()
    try:
        with tempfile.TemporaryDirectory() as report_dir:
            for commit in commits.splitlines():
                stat = analyze_commit(commit, report_dir)
                print(f"{stat.commit},{stat.imprecision},{stat.loc},{stat.timestamp}")
    finally:
        check_call(["git", "checkout", current_commit])


def analyze_commit(commit: str, report_dir: str) -> Entry:
    check_call(["git", "checkout", commit], stderr=DEVNULL)
    call(["mypy", "-p", "sydent", "--txt-report", report_dir], stderr=DEVNULL)
    with open(f"{report_dir}/index.txt") as f:
        for line in f:
            if line.startswith("| Total"):
                match = extract_precision.match(line)
                imprecision, loc = match.groups()
                timestamp = datetime.datetime.fromisoformat(
                    check_output(["git", "log", "-s", "--format=%cI", "-1", commit])
                    .decode()
                    .strip()
                )

                return Entry(commit, imprecision, loc, timestamp)
    raise RuntimeError("Couldn't find total stats")


if __name__ == "__main__":
    main(build_parser().parse_args())
