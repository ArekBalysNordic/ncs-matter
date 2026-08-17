# Copyright (c) 2026 Nordic Semiconductor ASA
# SPDX-License-Identifier: Apache-2.0

"""Create or reuse the weekly sdk-sync test pull request."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import configure_git_user, github_get, github_headers, run_git, write_json  # noqa: E402


def find_open_pr(*, repo: str, head_branch: str, base_branch: str) -> int | None:
    pulls = github_get(f"/repos/{repo}/pulls", params={"state": "open", "per_page": 100})
    owner = repo.split("/", 1)[0]
    head_ref = f"{owner}:{head_branch}"
    for pull in pulls:
        if pull.get("base", {}).get("ref") != base_branch:
            continue
        if pull.get("head", {}).get("ref") == head_branch or pull.get("head", {}).get("label") == head_ref:
            return int(pull["number"])
    return None


def create_pr(*, repo: str, base_branch: str, head_branch: str, title: str, body: str) -> int:
    existing = find_open_pr(repo=repo, head_branch=head_branch, base_branch=base_branch)
    if existing is not None:
        print(f"Reusing open PR #{existing} for head {head_branch}")
        return existing

    response = requests.post(
        f"https://api.github.com/repos/{repo}/pulls",
        headers=github_headers(),
        json={
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body,
        },
        timeout=60,
    )
    if response.status_code >= 400:
        sys.exit(f"Failed to create PR: {response.status_code} {response.text}")
    number = int(response.json()["number"])
    print(f"Created PR #{number} ({head_branch} -> {base_branch})")
    return number


def prepare_pr(
    *,
    repo: str,
    source_branch: str,
    pr_branch: str,
    base_branch: str,
    state_file: Path,
) -> int:
    configure_git_user()
    run_git(["fetch", "origin", source_branch, base_branch])
    run_git(["checkout", source_branch])
    run_git(["checkout", "-B", pr_branch])
    push = run_git(["push", "--force-with-lease", "origin", pr_branch], check=False)
    if push.returncode != 0:
        print(push.stderr, file=sys.stderr)
        sys.exit(f"Failed to push branch {pr_branch}")

    title = "manifest: Weekly sdk-nrf / sdk-connectedhomeip sync test"
    body = (
        "Automated weekly sync PR testing updated `sdk-nrf` and "
        "`sdk-connectedhomeip` revisions in `west.yml`.\n\n"
        "Do not merge without review."
    )
    pr_number = create_pr(
        repo=repo,
        base_branch=base_branch,
        head_branch=pr_branch,
        title=title,
        body=body,
    )

    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
    else:
        state = {}
    state["pr_number"] = pr_number
    write_json(state_file, state)
    return pr_number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "nrfconnect/ncs-matter"))
    parser.add_argument("--source-branch", default="main")
    parser.add_argument("--pr-branch", default="sdk-sync/test")
    parser.add_argument("--base-branch", default="sdk-nrf")
    parser.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()
    prepare_pr(
        repo=args.repo,
        source_branch=args.source_branch,
        pr_branch=args.pr_branch,
        base_branch=args.base_branch,
        state_file=args.state_file,
    )


if __name__ == "__main__":
    main()
