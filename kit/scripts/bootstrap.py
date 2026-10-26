"""Start a project from any folder: git, the GitHub repository, the first commit,
the one push that makes main, and branch protection. Each step runs only when
it is not done yet, so a second run changes nothing."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from loopkit import SECRET_PATTERNS, Refused

IGNORE = ["/.loop/", ".env", ".env.*", "!.env.example", ".venv/", "__pycache__/",
          "node_modules/", ".DS_Store"]
SECRET_FILE = re.compile(r"(^|/)(id_(rsa|dsa|ecdsa|ed25519)|[^/]*\.(pem|key|p12|pfx))$")
PROTECTION = {"required_status_checks": None, "enforce_admins": True,
              "required_pull_request_reviews": {"required_approving_review_count": 0},
              "restrictions": None, "allow_force_pushes": False, "allow_deletions": False}


def run(args: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, input=stdin,
                          check=False)


def must(args: list[str], cwd: Path) -> str:
    res = run(args, cwd)
    if res.returncode:
        raise Refused(f"{' '.join(args[:3])} failed: {res.stderr.strip()}",
                      "fix the cause named above, then run setup again")
    return res.stdout.strip()


def first_commit(root: Path, loop_section: str) -> None:
    if not any(root.glob("README*")):
        (root / "README.md").write_text(f"# {root.name}\n")
    ignore = root / ".gitignore"
    lines = ignore.read_text().splitlines() if ignore.exists() else []
    ignore.write_text("\n".join(lines + [p for p in IGNORE if p not in lines]) + "\n")
    if loop_section:
        agents = root / "AGENTS.md"
        text = agents.read_text() if agents.exists() else "# AGENTS.md\n"
        if "## The loop" not in text:
            agents.write_text(text.rstrip("\n") + "\n\n" + loop_section.strip() + "\n")
    must(["git", "symbolic-ref", "HEAD", "refs/heads/main"], root)
    must(["git", "add", "-A"], root)
    staged = must(["git", "diff", "--cached", "--name-only"], root).splitlines()
    found = [path for path in staged if SECRET_FILE.search(path)]
    diff = run(["git", "diff", "--cached", "--no-ext-diff"], root).stdout
    if found or any(re.search(pattern, diff) for pattern in SECRET_PATTERNS):
        must(["git", "read-tree", "--empty"], root)  # unstage only; files stay on disk
        raise Refused("the first commit would hold a secret: "
                      + (", ".join(found) or "a secret-shaped value"),
                      "ask the person to move it or add it to .gitignore, then run setup again")
    must(["git", "commit", "--quiet", "-m", "Start the project"], root)


def protect(root: Path) -> str:
    try:
        repo = must(["gh", "repo", "view", "--json", "nameWithOwner", "--jq",
                     ".nameWithOwner"], root)
    except Refused as refusal:
        return f"warn main is not protected: {refusal.reason}"
    res = run(["gh", "api", "-X", "PUT", f"repos/{repo}/branches/main/protection",
               "--input", "-"], root, stdin=json.dumps(PROTECTION))
    if not res.returncode:
        return "ok   main requires a pull request"
    why = ("this plan has no branch protection for a private repository; "
           "the guard and the gate still hold" if "Upgrade to GitHub Pro" in res.stderr
           else res.stderr.strip())
    return f"warn main is not protected: {why}"


def bootstrap(root: Path, name: str = "", visibility: str = "private",
              loop_section: str = "", protect_main: bool = False) -> list[str]:
    if run(["gh", "auth", "status", "--active"], root).returncode:
        raise Refused("gh is not signed in", "the person runs: ! gh auth login")
    done: list[str] = []
    try:
        return _bootstrap(root, name, visibility, loop_section, protect_main, done)
    except Refused:
        if done:  # what this run made stays, so say so before the refusal
            print("\n".join(done))
        raise


def _bootstrap(root: Path, name: str, visibility: str, loop_section: str,
               protect_main: bool, done: list[str]) -> list[str]:
    top = run(["git", "rev-parse", "--show-toplevel"], root)
    if top.returncode:
        must(["git", "init", "--quiet", "-b", "main"], root)
        done.append("ok   made a git repository")
    elif Path(top.stdout.strip()).resolve() != root.resolve():
        raise Refused(f"this folder is inside another git repository: {top.stdout.strip()}",
                      "run setup from that repository's top folder, or ask the person "
                      "whether this folder should be its own project")
    has_origin = not run(["git", "remote", "get-url", "origin"], root).returncode
    if not has_origin and not name:
        raise Refused("the project has no GitHub repository",
                      "ask the person for a name and visibility, then run: "
                      "gate.py bootstrap --name <name> --visibility private --protect")
    remote_main = has_origin and bool(must(["git", "ls-remote", "--heads", "origin", "main"],
                                           root))
    if run(["git", "rev-parse", "--verify", "--quiet", "main^{commit}"], root).returncode:
        if remote_main:
            raise Refused("origin has a main branch but this folder does not",
                          "ask the person whether to fetch origin main here; keep local files")
        if run(["git", "rev-parse", "--verify", "--quiet", "HEAD"], root).returncode == 0:
            raise Refused("the project has commits but no main branch",
                          "ask the person to name the default branch main")
        first_commit(root, loop_section)
        done.append("ok   made the first commit on main"
                    + (" with the loop section" if loop_section else ""))
    elif loop_section and (remote_main or "## The loop" not in run(
            ["git", "show", "main:AGENTS.md"], root).stdout):
        raise Refused("main already has commits, so the loop section needs review",
                      "commit AGENTS.md on a branch and open a pull request")
    if not has_origin:
        must(["gh", "repo", "create", name, f"--{visibility}", "--source", ".",
              "--remote", "origin"], root)
        done.append(f"ok   made the {visibility} GitHub repository {name}")
    # The one push to main, made in code and only when origin has no main yet.
    if not remote_main and not must(["git", "ls-remote", "--heads", "origin", "main"], root):
        must(["git", "push", "--quiet", "-u", "origin", "main"], root)
        done.append("ok   pushed the first main")
    if protect_main:
        done.append(protect(root))
    return done or ["ok   already set up: nothing to change"]
