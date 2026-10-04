#!/usr/bin/env python3
"""Port exported repository content into a target repository.

Reads the JSON written by the export step and recreates labels, issues,
archived pull requests, comments, sub-issue links and releases in a target
repository.

Issue numbers are the point. GitHub gives issues and pull requests numbers from
one counter, so walking 1 to N in order and creating something at every number
is what keeps issue 21 called issue 21. If a single creation lands on the wrong
number the run stops there, because everything after it would be wrong too and
there is no way to renumber afterwards.

Usage:
    port.py --export DIR --target owner/name [--dry-run]
"""

import argparse
import json
import pathlib
import subprocess
import sys
import time

PAUSE = 1.0  # seconds between writes, to stay under the secondary rate limit


def gh(args, payload=None):
    cmd = ["gh"] + args
    text = json.dumps(payload) if payload is not None else None
    run = subprocess.run(cmd, capture_output=True, text=True, input=text)
    if run.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}\n{run.stderr.strip()[:500]}")
    return json.loads(run.stdout) if run.stdout.strip() else {}


def api(path, method="GET", payload=None):
    args = ["api", "-X", method, path]
    if payload is not None:
        args += ["--input", "-"]
    return gh(args, payload)


def provenance(item, kind):
    """The header line that says where this came from and who wrote it.

    Reproducing somebody else's words under your own account is the one thing
    this port cannot do honestly, so every item says who wrote it and when.
    """
    who = item["user"]["login"]
    when = item["created_at"][:10]
    if kind == "pull":
        # merged_at is nested inside the pull_request object on the issues
        # endpoint, not at the top level. Reading the top level made every
        # merged pull request record itself as merely closed.
        merged = (item.get("pull_request") or {}).get("merged_at") or item.get("merged_at")
        state = "merged" if merged else "closed"
        return (f"> **Archived pull request.** Opened by @{who} on {when} and {state}. "
                f"Ported from the previous repository, where it was a pull request. "
                f"The changes it describes are in the commit history.")
    if kind == "issue":
        return f"> **Originally opened by @{who} on {when}.** Ported from the previous repository."
    return f"> **@{who} commented on {when}.** Ported from the previous repository."


def body_for(item, kind):
    return provenance(item, kind) + "\n\n" + (item.get("body") or "_No description._")


def port_labels(target, labels, dry):
    print(f"== labels ({len(labels)}) ==")
    for lab in labels:
        payload = {"name": lab["name"], "color": lab["color"],
                   "description": lab.get("description") or ""}
        if dry:
            continue
        try:
            api(f"repos/{target}/labels", "POST", payload)
        except RuntimeError:
            # A new repository ships with some of these already. Match ours.
            api(f"repos/{target}/labels/{lab['name'].replace(' ', '%20')}", "PATCH", payload)
        time.sleep(PAUSE)

    # A new repository arrives with a set of default labels of GitHub's
    # choosing, which is not the set this repository kept. Anything the source
    # does not have is removed, or the label list quietly grows by whatever
    # GitHub happened to seed that week.
    wanted = {lab["name"] for lab in labels}
    for present in api(f"repos/{target}/labels?per_page=100"):
        if present["name"] not in wanted:
            api(f"repos/{target}/labels/{present['name'].replace(' ', '%20')}", "DELETE")
            print(f"   removed default label not on the source: {present['name']}")
            time.sleep(PAUSE)

    print(f"   {len(labels)} labels in place")


def port_items(target, items, comments, dry):
    print(f"== issues and archived pull requests (1..{max(items)}) ==")
    for n in range(1, max(items) + 1):
        item = items[n]
        kind = "pull" if "pull_request" in item else "issue"
        payload = {
            "title": item["title"],
            "body": body_for(item, kind),
            "labels": [l["name"] for l in item.get("labels", [])],
        }
        if dry:
            print(f"   would create {n:>3} [{kind}] {item['title'][:50]}")
            continue

        made = api(f"repos/{target}/issues", "POST", payload)
        got = made["number"]
        if got != n:
            raise SystemExit(
                f"STOP: created number {got} where {n} was expected. "
                f"Every number after this one would be wrong and cannot be "
                f"renumbered. Delete the target repository and start again."
            )
        time.sleep(PAUSE)

        for com in comments.get(n, []):
            api(f"repos/{target}/issues/{n}/comments", "POST",
                {"body": body_for(com, "comment")})
            time.sleep(PAUSE)

        # An archived pull request is always closed. An issue keeps the state
        # it had, and the reason it was closed for.
        if kind == "pull" or item["state"] == "closed":
            patch = {"state": "closed"}
            reason = item.get("state_reason")
            if kind == "issue" and reason in ("completed", "not_planned"):
                patch["state_reason"] = reason
            api(f"repos/{target}/issues/{n}", "PATCH", patch)
            time.sleep(PAUSE)

        print(f"   {n:>3} [{kind}] {item['title'][:50]}")


def port_sub_issues(target, links, dry):
    if not links:
        return
    print(f"== sub-issue links ({sum(len(v) for v in links.values())}) ==")
    for parent, children in links.items():
        for child in children:
            if dry:
                print(f"   would put {child} under {parent}")
                continue
            got = api(f"repos/{target}/issues/{child}", "GET")
            api(f"repos/{target}/issues/{parent}/sub_issues", "POST",
                {"sub_issue_id": got["id"]})
            time.sleep(PAUSE)
            print(f"   {child} under {parent}")


def port_releases(target, releases, dry):
    print(f"== releases ({len(releases)}) ==")
    # Oldest first, so the newest ends up marked as latest.
    for rel in sorted(releases, key=lambda r: r["created_at"]):
        payload = {
            "tag_name": rel["tag_name"],
            "name": rel["name"],
            "body": rel.get("body") or "",
            "draft": rel["draft"],
            "prerelease": rel["prerelease"],
        }
        if dry:
            print(f"   would create {rel['tag_name']}")
            continue
        api(f"repos/{target}/releases", "POST", payload)
        time.sleep(PAUSE)
        print(f"   {rel['tag_name']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-releases", action="store_true")
    args = ap.parse_args()

    ex = pathlib.Path(args.export)
    items = {i["number"]: i for i in json.loads((ex / "issues.json").read_text())}
    labels = json.loads((ex / "labels.json").read_text())
    releases = json.loads((ex / "releases.json").read_text())
    comments = {}
    for path in (ex / "comments").glob("*.json"):
        loaded = json.loads(path.read_text())
        if loaded:
            comments[int(path.stem)] = loaded

    missing = [n for n in range(1, max(items) + 1) if n not in items]
    if missing:
        raise SystemExit(f"export has gaps at {missing}; numbering cannot be preserved")

    links_path = ex / "sub-issues.json"
    links = {int(k): v for k, v in json.loads(links_path.read_text()).items()} \
        if links_path.exists() else {}

    print(f"target: {args.target}   dry-run: {args.dry_run}")
    port_labels(args.target, labels, args.dry_run)
    port_items(args.target, items, comments, args.dry_run)
    port_sub_issues(args.target, links, args.dry_run)
    if not args.skip_releases:
        port_releases(args.target, releases, args.dry_run)
    print("\ndone")


if __name__ == "__main__":
    main()
