"""The end-of-loop pass: smoke, drift, rubric, red team and lessons on the loop branch."""
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import common
import flow
import merge
import session
from common import gh, git

TITLES = (("drift", "Drift"), ("confirmed", "Red team: confirmed"), ("rejected", "Red team: rejected"),
          ("rubric", "Rubric"), ("lessons", "Lessons"), ("guardrails", "Proposed guardrails"),
          ("issues", "Issues created"), ("batch", "Merged in this batch"), ("errors", "Problems"))


def section(plan, name):
    return (re.search(r"^## %s\s*\n(.*?)(?=^## |\Z)" % name, plan, re.S | re.M) or [0, ""])[1]


def approves(plan, word):
    # fails closed: a paragraph must name `word`, say it may be queued as ready, and hold no negation
    return any(word in p and re.search(r"\b(may|can) be (queued as |marked |labelled )?ready\b", p)
               and not re.search(r"n't|\b(not|never|no|none|nothing|unless|until|only after)\b", p)
               for p in section(plan, "Standing approvals").lower().split("\n\n"))


def esc(text):  # a finding cannot start a section of the issue
    return re.sub(r"(?m)^(\s*#)", r"\\\1", text)


def failing(project, sha, test, tree, path):
    # (where the Test command finds the red-team file, None) if the file under .lite/pass/ fails the
    # Test command once copied there; else (None, why it was rejected)
    base, full = os.path.realpath(os.path.join(tree, ".lite", "pass")), os.path.join(tree, path)
    rel = os.path.relpath(os.path.realpath(full), base)
    bad = ("no test file" if not path else "the path is a symlink: " + path if os.path.islink(full)
           else "the path is outside .lite/pass/: " + path if rel.split(os.sep)[0] == ".."
           else "no test file at " + path if not os.path.isfile(full)
           else "a file already exists at " + rel if os.path.lexists(os.path.join(tree, rel)) else "")
    if bad:
        return None, bad
    why = merge.run_tests(project, sha, test, tail=60, overlay=(base, [rel]))
    if not why:
        return None, "the test passes under the Test command"
    if re.search(r"SyntaxError|IndentationError|ImportError|ModuleNotFound|NameError|errors? during collection|"
                 r"error collecting|cannot find module|timed out", why, re.I):
        return None, "the test errors (syntax or import) or times out"
    return rel, None


def findings(text, name="FINDINGS"):  # (title, detail, path) per `title | detail | path` line
    rows = [(l.split("|", 2) + ["", ""])[:3] for l in flow.parse_block(text, name) if l.lower() != "none"]
    return [(t.strip(), d.strip(), p.strip()) for t, d, p in rows]


def fix_rounds(texts):
    # the review comments the loop posts, one per round, so the fix rounds are one fewer
    return max(0, sum(t.startswith("## Review, round") for t in texts) - 1)


def batch_lines(project, since, loop):
    # one line per issue merged since `since`: build note title, fix rounds, parks, deviations
    log = git(["log", "--format=%s", "%s..origin/%s" % (since, loop)], cwd=project, check=False)
    lines = []
    for n in sorted({int(m) for m in re.findall(r"^Issue (\d+)", log, re.M)}):
        info = json.loads(gh(["issue", "view", str(n), "--json", "title,comments"]))
        prs = json.loads(gh(["pr", "list", "--head", "issue/%d" % n, "--state", "all", "--json", "comments"]))
        texts = [c.get("body") or "" for c in info["comments"] + [c for p in prs for c in p["comments"]]]
        built = next((t for t in texts if t.startswith("## Built")), "\nno build note")
        lines.append("#%d %s: %s (fix rounds %d, parks %d, deviations: %s)" % (
            n, info["title"], next((l for l in built.splitlines()[1:] if l.strip()), "no build note")[:100],
            fix_rounds(texts), sum("## Needs you" in t for t in texts),
            (re.search(r"^Deviations: (.*)$", built, re.M) or [0, "none"])[1]))
    return lines


def create(title, body, label):
    # create an issue unless any one has the title; return its number, or None
    title, out, args = title[:100], [], ["issue", "list", "--state", "all", "--limit", "500", "--json", "title"]
    flow.once(lambda: out.append(gh(["issue", "create", "--title", title, "--label", label, "--body-file", "-"],
                                    input=body + "\n\n" + common.MARKER + "\n", retry=False)),
              lambda: title in [i["title"] for i in json.loads(gh(args) or "[]")])
    return (re.findall(r"\d+", out[0]) or ["?"])[-1] if out else None


def run_pass(project, settings, since_ref):
    # run the pass on origin/<loop branch>; return (report dict, Markdown report)
    project = os.path.abspath(project)
    r = dict({k: [] for k, _ in TITLES}, smoke="not set", sessions=0)
    parent = tempfile.mkdtemp(prefix="lite-pass-")
    tree = os.path.join(parent, "tree")
    try:
        git(["worktree", "add", "--detach", tree, "origin/" + settings["Loop branch"]], cwd=project)
        _pass(project, settings, since_ref, tree, r)
    except Exception as e:  # the pass never raises; it reports
        r["errors"].append("pass stopped: %s" % e)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tree], cwd=project, capture_output=True)
        subprocess.run(["rmdir", parent], capture_output=True)
    return r, markdown(r)


def _pass(project, settings, since, tree, r):
    sha, test = git(["rev-parse", "HEAD"], cwd=tree), settings["Test command"]
    plan = git(["show", "HEAD:PLAN.md"], cwd=tree, check=False)
    context = "\n\nPLAN.md: %s\nLoop branch: %s\nTest command: %s\nBatch diff: git diff %s...HEAD\n" % (
        os.path.join(tree, "PLAN.md"), settings["Loop branch"], test, since)
    def ask(name, extra=""):  # at most 8 calls: drift, rubric, four red teams, confirm, lessons
        r["sessions"] += 1
        try:
            return session.run("pass", Path(flow.BRIEFS, "pass-%s.md" % name).read_text(encoding="utf-8") + context + extra,
                               tree, settings["Reviewer model"], project, "pass")[0]
        except common.LoopError as e:
            r["errors"].append("%s session: %s" % (name, e))
            return ""
    if settings.get("Smoke command"):
        bad = merge.run_tests(project, sha, settings["Smoke command"], tail=5)
        r["smoke"] = bad.replace("the Test command", "the Smoke command") if bad else "passed"
        r["drift"] += [("Smoke command failed on the loop branch", r["smoke"], "")] if bad else []
    try:
        r["batch"] = batch_lines(project, since, settings["Loop branch"])
    except Exception as e:
        r["errors"].append("batch notes: %s" % e)
    drift = ask("drift")
    r["drift"] += findings(drift)
    r["rubric"] = findings(ask("rubric"))
    surfaces = re.findall(r"^\s*[-*]\s+(\S.*)$", section(plan, "Surfaces"), re.M)[:4]
    if findings(drift, "SURFACES") and not surfaces:
        r["drift"].append(("Add red-team surfaces to PLAN.md", "Proposed under ## Surfaces:\n- "
                           + "\n- ".join(f[0] for f in findings(drift, "SURFACES")[:4]), ""))
    candidates = []
    for surface in surfaces:
        for title, detail, path in findings(ask("redteam", "\nSurface: %s\n" % surface)):
            rel, why = failing(project, sha, test, tree, path)
            if rel:
                candidates.append((title, detail, rel, Path(tree, path).read_text(encoding="utf-8")))
            else:
                r["rejected"].append((title, why))
    said = findings(ask("confirm", "\nFindings to judge:\n" + "\n".join(
        "%s | %s | .lite/pass/%s" % c[:3] for c in candidates)), "CONFIRMED") if candidates else []
    for c in candidates:
        yes = any(c[0] == s[0] for s in said)
        r["confirmed" if yes else "rejected"].append(c if yes else (c[0], "not confirmed"))
    reply = ask("lessons", "\nMerged in this batch:\n" + "\n".join(r["batch"]) + "\n\nFindings so far:\n"
                + "\n".join(f[0] for f in r["drift"] + r["rubric"] + r["confirmed"]) + "\n")
    r["lessons"], r["guardrails"] = [f[0] for f in findings(reply, "LESSONS")], findings(reply, "GUARDRAILS")
    ready = "ready" if approves(plan, "confirmed defect") else "inbox"
    fence = lambda c: "`" * max([3] + [len(m) + 1 for m in re.findall(r"`+", c)])
    jobs = [(t, "%s\n\n## Failing test\n\nPath: %s\n\n%s\n%s\n%s\n" % (esc(d), p, fence(c), c.rstrip("\n"), fence(c)),
             ready) for t, d, p, c in r["confirmed"]]
    found = r["drift"] + r["rubric"] + r["guardrails"] + [("Add to PLAN.md ## Lessons", l, "") for l in r["lessons"]]
    jobs += [("Pass findings, %s, %s" % (time.strftime("%Y-%m-%d"), sha[:7]), "\n".join(
        "- [ ] **%s**: %s" % (t, esc(d).replace("\n", "\n  ")) for t, d, _ in found), "inbox")] * bool(found)
    for title, body, label in jobs:
        number = create(title, body, label)
        r["issues"] += ["#%s %s (%s)" % (number, title, label)] if number else []


def markdown(r):
    show = lambda v: "\n".join("- " + (": ".join(x[:2]) if isinstance(x, tuple) else x) for x in v) or "none"
    return "## End-of-loop pass (%d sessions)\n\n### Smoke\n\n%s\n\n" % (r["sessions"], r["smoke"]) + "\n\n".join(
        "### %s\n\n%s" % (title, show(r[key])) for key, title in TITLES)
