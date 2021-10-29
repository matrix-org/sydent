#! /usr/bin/env python3
import datetime
import re
import sys
import tempfile
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from subprocess import check_output, check_call, call, DEVNULL
from typing import List


extract_precision = re.compile(
    r"\|[^|]+" r"\|\s+([0-9.]+)% imprecise " r"\| (\d+) LOC \|"
)

extract_coverage = re.compile(r"^.* ([0-9.]+)%$")

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
    not_any_expressions: float


def main(args: Namespace) -> None:
    stats: List[Entry] = []

    current_commit = check_output(["git", "branch", "--show-current"]).strip().decode()
    print(f"currently at {current_commit}", file=sys.stderr)
    commits = check_output(
        ["git", "rev-list", "--reverse", f"^{args.start}~", args.end]
    ).decode()
    try:
        print("commit,imprecision,loc,timestamp,not_anys")
        with tempfile.TemporaryDirectory() as report_dir:
            commits = commits.splitlines()
            for i, commit in enumerate(commits, start=1):
                commit = commit.strip()
                print(f"({i}/{len(commits)} inspect {commit}", file=sys.stderr)
                stat = analyze_commit(commit, report_dir)
                print(f"{stat.commit},{stat.imprecision},{stat.loc},{stat.timestamp},{stat.not_any_expressions}")
    finally:
        check_call(["git", "checkout", current_commit])


def analyze_commit(commit: str, report_dir: str) -> Entry:
    check_call(["git", "checkout", commit], stderr=DEVNULL)
    timestamp = datetime.datetime.fromisoformat(
        check_output(["git", "log", "-s", "--format=%cI", "-1", commit])
        .decode()
        .strip()
    )
    call(
        [
            "mypy",
            "-p",
            "sydent",
            "--txt-report",
            report_dir,
            "--any-exprs-report",
            report_dir,
        ],
        stdout=DEVNULL,
    )
    with open(f"{report_dir}/index.txt") as f:
        for line in f:
            if line.startswith("| Total"):
                match = extract_precision.match(line)
                imprecision, loc = match.groups()
                break
        else:
            raise RuntimeError("Couldn't find total stats")
    with open(f"{report_dir}/any-exprs.txt") as f:
        for line in f:
            if "Total" in line:
                match = extract_coverage.match(line)
                (coverage,) = match.groups()
                break
        else:
            raise RuntimeError("Couldn't find total stats")

    return Entry(commit, imprecision, loc, timestamp, coverage)


if __name__ == "__main__":
    main(build_parser().parse_args())
