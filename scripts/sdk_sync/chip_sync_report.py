# Copyright (c) 2026 Nordic Semiconductor ASA
# SPDX-License-Identifier: Apache-2.0

"""Compare sdk-connectedhomeip master and sdk-nrf branches."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import (  # noqa: E402
    FROM_NRF_MARKER,
    ChipSyncReport,
    CommitInfo,
    chip_repo,
    github_get,
    nrf_repo,
    read_json,
    write_json,
)


def branch_tip(*, repo: str, branch: str) -> str:
    ref = github_get(f"/repos/{repo}/git/ref/heads/{branch}")
    return ref["object"]["sha"]


def merge_base(*, repo: str, base: str, head: str) -> str:
    comparison = github_get(f"/repos/{repo}/compare/{base}...{head}")
    return comparison["merge_base_commit"]["sha"]


def commits_on_branch(*, repo: str, branch: str, since_sha: str) -> list[CommitInfo]:
    comparison = github_get(f"/repos/{repo}/compare/{since_sha}...{branch}")
    commits: list[CommitInfo] = []
    for commit in comparison.get("commits", []):
        subject = commit["commit"]["message"].splitlines()[0]
        commits.append(
            CommitInfo(
                sha=commit["sha"],
                subject=subject,
                html_url=commit["html_url"],
                has_from_nrf=FROM_NRF_MARKER in subject,
            )
        )
    return commits


def build_chip_sync_report(*, chip_repo_name: str | None = None) -> ChipSyncReport:
    repo = chip_repo_name or chip_repo()
    master_sha = branch_tip(repo=repo, branch="master")
    sdk_nrf_sha = branch_tip(repo=repo, branch="sdk-nrf")
    anchor_sha = merge_base(repo=repo, base="master", head="sdk-nrf")
    above_anchor = commits_on_branch(repo=repo, branch="sdk-nrf", since_sha=anchor_sha)
    missing = [commit for commit in above_anchor if not commit.has_from_nrf]
    return ChipSyncReport(
        master_sha=master_sha,
        sdk_nrf_branch_sha=sdk_nrf_sha,
        merge_base_sha=anchor_sha,
        commits_above_anchor=above_anchor,
        commits_missing_from_nrf=missing,
    )


def nrf_main_branch_sha(*, nrf_repo_name: str | None = None, branch: str = "main") -> str:
    return branch_tip(repo=nrf_repo_name or nrf_repo(), branch=branch)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chip-repo", default=None)
    parser.add_argument("--nrf-repo", default=None)
    parser.add_argument("--nrf-branch", default="main")
    parser.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()

    chip_repo_name = args.chip_repo or chip_repo()
    nrf_repo_name = args.nrf_repo or nrf_repo()
    chip_report = build_chip_sync_report(chip_repo_name=chip_repo_name)
    nrf_sha = nrf_main_branch_sha(nrf_repo_name=nrf_repo_name, branch=args.nrf_branch)

    if args.state_file.exists():
        state = read_json(args.state_file)
    else:
        state = {}

    state["chip_sync"] = chip_report.to_dict()
    state["matter_sha"] = chip_report.sdk_nrf_branch_sha
    state["nrf_sha"] = nrf_sha
    write_json(args.state_file, state)

    print(f"sdk-connectedhomeip master: {chip_report.master_sha}")
    print(f"sdk-connectedhomeip sdk-nrf: {chip_report.sdk_nrf_branch_sha}")
    print(f"merge-base anchor: {chip_report.merge_base_sha}")
    print(f"commits above anchor: {len(chip_report.commits_above_anchor)}")
    print(f"commits missing {FROM_NRF_MARKER}: {len(chip_report.commits_missing_from_nrf)}")
    print(f"sdk-nrf {args.nrf_branch}: {nrf_sha}")


if __name__ == "__main__":
    main()
