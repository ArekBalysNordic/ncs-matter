# Copyright (c) 2026 Nordic Semiconductor ASA
# SPDX-License-Identifier: Apache-2.0

"""Shared helpers for sdk_sync scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

GITHUB_API = "https://api.github.com"
FROM_NRF_MARKER = "[from nrf]"
REPORT_MARKER = "<!-- sdk-sync-report -->"

DEFAULT_NRF_REPO = "nrfconnect/sdk-nrf"
DEFAULT_CHIP_REPO = "nrfconnect/sdk-connectedhomeip"


def env_repo(name: str, default: str) -> str:
    return os.environ.get(name, default)


def nrf_repo() -> str:
    return env_repo("SDK_SYNC_NRF_REPO", DEFAULT_NRF_REPO)


def chip_repo() -> str:
    return env_repo("SDK_SYNC_CHIP_REPO", DEFAULT_CHIP_REPO)


@dataclass
class CommitInfo:
    sha: str
    subject: str
    html_url: str
    has_from_nrf: bool


@dataclass
class ChipSyncReport:
    master_sha: str
    sdk_nrf_branch_sha: str
    merge_base_sha: str
    commits_above_anchor: list[CommitInfo]
    commits_missing_from_nrf: list[CommitInfo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "master_sha": self.master_sha,
            "sdk_nrf_branch_sha": self.sdk_nrf_branch_sha,
            "merge_base_sha": self.merge_base_sha,
            "commits_above_anchor": [asdict(c) for c in self.commits_above_anchor],
            "commits_missing_from_nrf": [asdict(c) for c in self.commits_missing_from_nrf],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChipSyncReport:
        def _commits(key: str) -> list[CommitInfo]:
            return [CommitInfo(**item) for item in data[key]]

        return cls(
            master_sha=data["master_sha"],
            sdk_nrf_branch_sha=data["sdk_nrf_branch_sha"],
            merge_base_sha=data["merge_base_sha"],
            commits_above_anchor=_commits("commits_above_anchor"),
            commits_missing_from_nrf=_commits("commits_missing_from_nrf"),
        )


@dataclass
class SyncState:
    nrf_sha: str
    matter_sha: str
    chip_sync: ChipSyncReport
    pr_number: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "nrf_sha": self.nrf_sha,
            "matter_sha": self.matter_sha,
            "chip_sync": self.chip_sync.to_dict(),
            "pr_number": self.pr_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncState:
        return cls(
            nrf_sha=data["nrf_sha"],
            matter_sha=data["matter_sha"],
            chip_sync=ChipSyncReport.from_dict(data["chip_sync"]),
            pr_number=data["pr_number"],
        )


def github_token() -> str:
    token = os.environ.get("SDK_SYNC_PAT") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("SDK_SYNC_PAT or GH_TOKEN must be set")
    return token


def github_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {github_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    url = path if path.startswith("https://") else f"{GITHUB_API}{path}"
    response = requests.get(url, headers=github_headers(), params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def github_get_paginated(path: str, *, params: dict[str, Any] | None = None) -> list[Any]:
    url = path if path.startswith("https://") else f"{GITHUB_API}{path}"
    items: list[Any] = []
    while url:
        response = requests.get(url, headers=github_headers(), params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return payload
        items.extend(payload)
        url = response.links.get("next", {}).get("url")
        params = None
    return items


def run_git(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        text=True,
        capture_output=True,
    )


def configure_git_user() -> None:
    run_git(["config", "user.email", "sdk-sync-bot@users.noreply.github.com"])
    run_git(["config", "user.name", "sdk-sync-bot"])


def short_sha(sha: str) -> str:
    return sha[:12]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_github_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def within_last_days(value: str | None, days: int) -> bool:
    parsed = parse_github_time(value)
    if parsed is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return parsed >= cutoff
