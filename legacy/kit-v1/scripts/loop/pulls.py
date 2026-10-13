"""Pull requests as the gate sees them: create, read, merge, close, comment.

Every call goes through `GitHub._gh`, so each one asks `credential()` first. Normal calls act
as the App and refuse with `NoApp` when it is absent. The person-only manual completion door
supplies the person's hub after its terminal and agent-marker checks. This module never
starts `gh` itself.

A merge always names the tested commit (`--match-head-commit`), so GitHub refuses it when the
branch moved after the last check. It never uses `--admin` or `--auto`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from loop.github import GitHubError

PR_FIELDS = ("number,title,body,state,url,headRefName,headRefOid,baseRefName,mergedAt,"
             "mergeCommit,comments")
PASSING = ("pass", "success")


@dataclass(frozen=True)
class Comment:
    id: int
    author: str
    body: str
    association: str = ""  # OWNER, MEMBER, COLLABORATOR, NONE...: who the author is to the repo


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str
    state: str  # OPEN, MERGED or CLOSED
    title: str
    body: str
    head_branch: str
    head_oid: str
    base: str
    merge_commit: str = ""
    comments: list[Comment] = field(default_factory=list)


def _unreadable(what: str) -> GitHubError:
    return GitHubError(f"GitHub's answer about {what} cannot be read",
                       next_command="run the same command again")


class Caller(Protocol):
    """What `Pulls` needs of the gate's GitHub wrapper: the one call that asks `credential()`."""

    def _gh(self, args: Sequence[str], stdin: str | None = None) -> str: ...


class Pulls:
    def __init__(self, hub: Caller) -> None:
        self.hub = hub

    def create(self, *, base: str, head: str, title: str, body: str) -> tuple[int, str]:
        """Open a pull request. Returns its number and address."""
        text = self.hub._gh(["pr", "create", "--base", base, "--head", head, "--title", title,
                             "--body-file", "-"], stdin=body)
        lines = text.strip().splitlines()
        address = lines[-1].strip() if lines else ""
        tail = address.rstrip("/").rsplit("/", 1)[-1]
        if not address.startswith("http") or not tail.isdigit():
            raise GitHubError(
                "GitHub made the pull request but gave no address for it",
                next_command=f"gh pr list --head {head}, then record the pull request")
        return int(tail), address

    def view(self, ref: int | str) -> PullRequest:
        text = self.hub._gh(["pr", "view", str(ref), "--json", PR_FIELDS])
        try:
            data = json.loads(text)
        except ValueError as error:
            raise _unreadable(f"pull request {ref}") from error
        if not isinstance(data, dict) or not isinstance(data.get("number"), int) \
                or not data.get("state"):
            raise _unreadable(f"pull request {ref}")
        merged: Any = data.get("mergeCommit") or {}
        comments = [
            Comment(int(c["id"]), str((c.get("author") or {}).get("login", "")),
                    str(c.get("body", "")), str(c.get("authorAssociation", "")))
            for c in data.get("comments") or [] if isinstance(c, dict) and "id" in c
        ]
        return PullRequest(
            number=int(data["number"]), url=str(data.get("url", "")),
            state=str(data["state"]).upper(), title=str(data.get("title", "")),
            body=str(data.get("body", "")), head_branch=str(data.get("headRefName", "")),
            head_oid=str(data.get("headRefOid", "")), base=str(data.get("baseRefName", "")),
            merge_commit=str(merged.get("oid", "")) if isinstance(merged, dict) else "",
            comments=comments)

    def checks(self, number: int) -> tuple[bool, str]:
        """True only when GitHub lists at least one check and every one passed.

        No checks, a pending check, a failed check and a failed read are all `False`.
        """
        try:
            text = self.hub._gh(["pr", "checks", str(number)])
        except GitHubError as error:
            return False, error.message
        rows = [line.split("\t") for line in text.splitlines() if line.strip()]
        if not rows:
            return False, "no checks ran on the pull request, and no checks is never green"
        bad = [r[0] for r in rows if len(r) < 2 or r[1].strip().lower() not in PASSING]
        if bad:
            return False, f"the checks that did not pass: {', '.join(bad)}"
        return True, f"{len(rows)} check(s) passed"

    def merge(self, number: int, *, head_commit: str) -> None:
        """Merge the pull request, only if its branch still holds `head_commit`."""
        if not head_commit.strip():
            raise ValueError("a merge must name the tested commit")
        self.hub._gh(["pr", "merge", str(number), "--merge", "--match-head-commit", head_commit])

    def close(self, number: int, comment: str) -> None:
        self.hub._gh(["pr", "close", str(number), "--comment", comment])

    def comment(self, number: int, body: str) -> None:
        self.hub._gh(["pr", "comment", str(number), "--body-file", "-"], stdin=body)

    def set_base(self, number: int, base: str) -> None:
        self.hub._gh(["pr", "edit", str(number), "--base", base])


__all__ = ["Comment", "PullRequest", "Pulls"]
