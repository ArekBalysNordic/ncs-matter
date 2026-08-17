# Copyright (c) 2026 Nordic Semiconductor ASA
# SPDX-License-Identifier: Apache-2.0

"""Build and post the sdk-sync summary comment on the test PR."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import (  # noqa: E402
    FROM_NRF_MARKER,
    REPORT_MARKER,
    ChipSyncReport,
    SyncState,
    chip_repo,
    github_get,
    github_get_paginated,
    github_headers,
    github_token,
    nrf_repo,
    read_json,
    short_sha,
    within_last_days,
)

import requests


def recent_commits(*, repo: str, branch: str, days: int) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits = github_get_paginated(
        f"/repos/{repo}/commits",
        params={"sha": branch, "since": since, "per_page": 100},
    )
    recent: list[dict] = []
    for commit in commits:
        subject = commit["commit"]["message"].splitlines()[0]
        recent.append(
            {
                "sha": commit["sha"],
                "subject": subject,
                "html_url": commit["html_url"],
            }
        )
    return recent


def recent_pull_requests(*, repo: str, days: int) -> list[dict]:
    pulls = github_get_paginated(
        f"/repos/{repo}/pulls",
        params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 100},
    )
    recent = []
    for pull in pulls:
        if within_last_days(pull.get("updated_at"), days) or within_last_days(pull.get("merged_at"), days):
            recent.append(pull)
    return recent


def render_pr_list(pulls: list[dict]) -> str:
    if not pulls:
        return "_No pull requests updated in the last 7 days._\n"
    lines = []
    for pull in pulls:
        number = pull["number"]
        title = pull["title"].replace("\n", " ")
        url = pull["html_url"]
        state = pull.get("state", "unknown")
        lines.append(f"- [#{number} {title}]({url}) ({state})")
    return "\n".join(lines) + "\n"


def render_commit_list(commits: list[dict], *, empty_message: str = "_None._") -> str:
    if not commits:
        return f"{empty_message}\n"
    lines = []
    for commit in commits:
        lines.append(f"- [{commit['subject']}]({commit['html_url']}) (`{short_sha(commit['sha'])}`)")
    return "\n".join(lines) + "\n"


def build_report_body(
    *,
    state: SyncState,
    days: int,
    nrf_repo_name: str,
    chip_repo_name: str,
    nrf_branch: str = "main",
    chip_branch: str = "sdk-nrf",
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    chip = state.chip_sync
    nrf_commits = recent_commits(repo=nrf_repo_name, branch=nrf_branch, days=days)
    chip_commits = recent_commits(repo=chip_repo_name, branch=chip_branch, days=days)
    nrf_prs = recent_pull_requests(repo=nrf_repo_name, days=days)
    chip_prs = recent_pull_requests(repo=chip_repo_name, days=days)

    body = f"""{REPORT_MARKER}
## Weekly SDK sync report

Generated: {now}

### Manifest revisions under test

| Project | Revision |
|---------|----------|
| `sdk-nrf` (`nrf`, `{nrf_branch}`) | `{state.nrf_sha}` |
| `sdk-connectedhomeip` (`matter`, `{chip_branch}`) | `{state.matter_sha}` |

<details>
<summary>sdk-nrf commits on `{nrf_branch}` (last {days} days, {len(nrf_commits)})</summary>

{render_commit_list(nrf_commits, empty_message=f"_No commits on `{nrf_branch}` in the last {days} days._")}
</details>

<details>
<summary>sdk-connectedhomeip commits on `{chip_branch}` (last {days} days, {len(chip_commits)})</summary>

{render_commit_list(chip_commits, empty_message=f"_No commits on `{chip_branch}` in the last {days} days._")}
</details>

<details>
<summary>sdk-nrf pull requests (last {days} days, {len(nrf_prs)})</summary>

{render_pr_list(nrf_prs)}
</details>

<details>
<summary>sdk-connectedhomeip pull requests (last {days} days, {len(chip_prs)})</summary>

{render_pr_list(chip_prs)}
</details>

<details>
<summary>sdk-connectedhomeip commits above merge-base ({len(chip.commits_above_anchor)})</summary>

{render_commit_list([c.__dict__ for c in chip.commits_above_anchor])}
</details>

<details>
<summary>Commits missing {FROM_NRF_MARKER} ({len(chip.commits_missing_from_nrf)})</summary>

{render_commit_list([c.__dict__ for c in chip.commits_missing_from_nrf])}
</details>
"""
    return body


def find_existing_comment(*, repo: str, pr_number: int) -> int | None:
    comments = github_get_paginated(f"/repos/{repo}/issues/{pr_number}/comments")
    for comment in comments:
        if REPORT_MARKER in comment.get("body", ""):
            return int(comment["id"])
    return None


def upsert_pr_comment(*, repo: str, pr_number: int, body: str) -> None:
    existing_id = find_existing_comment(repo=repo, pr_number=pr_number)
    headers = github_headers()
    if existing_id is not None:
        response = requests.patch(
            f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}",
            headers=headers,
            json={"body": body},
            timeout=60,
        )
        action = "Updated"
    else:
        response = requests.post(
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
            headers=headers,
            json={"body": body},
            timeout=60,
        )
        action = "Posted"
    if response.status_code >= 400:
        sys.exit(f"Failed to comment on PR #{pr_number}: {response.status_code} {response.text}")
    print(f"{action} report comment on PR #{pr_number}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "nrfconnect/ncs-matter"))
    parser.add_argument("--nrf-repo", default=None)
    parser.add_argument("--chip-repo", default=None)
    parser.add_argument("--nrf-branch", default=os.environ.get("SDK_SYNC_NRF_BRANCH", "main"))
    parser.add_argument("--chip-branch", default=os.environ.get("SDK_SYNC_CHIP_BRANCH", "sdk-nrf"))
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    _ = github_token()
    raw = read_json(args.state_file)
    if "pr_number" not in raw:
        sys.exit("state file is missing pr_number; run prepare_pr.py first")

    nrf_repo_name = args.nrf_repo or nrf_repo()
    chip_repo_name = args.chip_repo or chip_repo()
    state = SyncState.from_dict(raw)
    body = build_report_body(
        state=state,
        days=args.days,
        nrf_repo_name=nrf_repo_name,
        chip_repo_name=chip_repo_name,
        nrf_branch=args.nrf_branch,
        chip_branch=args.chip_branch,
    )
    upsert_pr_comment(repo=args.repo, pr_number=state.pr_number, body=body)


if __name__ == "__main__":
    main()
