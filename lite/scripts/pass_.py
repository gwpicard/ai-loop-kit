"""The end-of-loop pass: smoke, drift, rubric, red team and lessons on the loop branch."""
import json
import os
import re
import subprocess
import tempfile
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


def approves(plan, word):  # a Standing approvals line allows `word` to be queued as ready
    return any(word in l.lower() and "ready" in l.lower() and not re.search(r"\b(not|never|no)\b", l.lower())
               for l in section(plan, "Standing approvals").splitlines())


def findings(text, name="FINDINGS"):  # (title, detail, path) per `title | detail | path` line
    rows = [(l.split("|", 2) + ["", ""])[:3] for l in flow.parse_block(text, name) if l.lower() != "none"]
    return [(t.strip(), d.strip(), p.strip()) for t, d, p in rows]


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
            n, info["title"], next(l for l in built.splitlines()[1:] if l.strip())[:100],
            sum(t.count("VERDICT: CHANGES") for t in texts), sum("## Needs you" in t for t in texts),
            (re.search(r"^Deviations: (.*)$", built, re.M) or [0, "none"])[1]))
    return lines


def create(title, body, label):
    # create an issue unless an open one has the title; return its number, or None
    title, out, args = title[:100], [], ["issue", "list", "--state", "open", "--limit", "500", "--json", "title"]
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
    except (common.LoopError, OSError, ValueError, KeyError) as e:
        r["errors"].append(str(e))
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
    r["batch"] = batch_lines(project, since, settings["Loop branch"])
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
            if (path.startswith(".lite/pass/") and ".." not in path
                    and merge.run_tests(project, sha, test, overlay=(tree, [path]))):
                candidates.append((title, detail, path, Path(tree, path).read_text(encoding="utf-8")))
            else:
                r["rejected"].append((title, "no failing test file"))
    said = findings(ask("confirm", "\nFindings to judge:\n" + "\n".join(
        "%s | %s | %s" % c[:3] for c in candidates)), "CONFIRMED") if candidates else []
    for c in candidates:
        yes = any(c[0] in s[0] for s in said)
        r["confirmed" if yes else "rejected"].append(c if yes else (c[0], "not confirmed"))
    reply = ask("lessons", "\nMerged in this batch:\n" + "\n".join(r["batch"]) + "\n\nFindings so far:\n"
                + "\n".join(f[0] for f in r["drift"] + r["rubric"] + r["confirmed"]) + "\n")
    r["lessons"], r["guardrails"] = [f[0] for f in findings(reply, "LESSONS")], findings(reply, "GUARDRAILS")
    ready = "ready" if approves(plan, "confirmed defect") else "inbox"
    jobs = [(t, "%s\n\n## Failing test\n\nPath: %s\n\n```\n%s```" % (d, p, c), ready) for t, d, p, c in r["confirmed"]]
    jobs += [(t, d, "inbox") for t, d, _ in r["drift"] + r["rubric"] + r["guardrails"]]
    jobs += [("Add lessons from the latest batch to PLAN.md", "Append under ## Lessons, merging or dropping "
              "the oldest lines if full:\n\n- " + "\n- ".join(r["lessons"]),
              "ready" if approves(plan, "lessons") else "inbox")] * bool(r["lessons"])
    r["issues"] += ["#%s %s (%s)" % (n, t, l) for t, b, l in jobs for n in [create(t, b, l)] if n]


def markdown(r):
    show = lambda v: "\n".join("- " + (": ".join(x[:2]) if isinstance(x, tuple) else x) for x in v) or "none"
    return "## End-of-loop pass (%d sessions)\n\n### Smoke\n\n%s\n\n" % (r["sessions"], r["smoke"]) + "\n\n".join(
        "### %s\n\n%s" % (title, show(r[key])) for key, title in TITLES)
