"""The end-of-loop pass: smoke, drift, rubric, red team and lessons on the loop branch."""
import json
import os
import re
import time
from pathlib import Path

import common
import flow
import merge
import session
from common import gh, git

FINDINGS = "Pass findings"
TITLES = (("drift", "Drift"), ("confirmed", "Red team: confirmed"), ("rejected", "Red team: rejected"),
          ("rubric", "Rubric"), ("held", "Held for an open decision"), ("lessons", "Lessons"), ("guardrails", "Proposed guardrails"),
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
    # (path the Test command finds the file at, None) if it fails there once copied; else (None, why not)
    base, full = os.path.realpath(os.path.join(tree, ".lite", "pass")), os.path.join(tree, path)
    rel = os.path.relpath(os.path.realpath(full), base)
    parts = rel.split(os.sep)
    parent = next((q for q in (os.path.join(tree, *parts[:i]) for i in range(1, len(parts)))
                   if os.path.islink(q) or os.path.lexists(q) and not os.path.isdir(q)), "")
    bad = ("no test file" if not path else "the path is a symlink: " + path if os.path.islink(full)
           else "the path is outside .lite/pass/: " + path if rel.split(os.sep)[0] == ".."
           else "no test file at " + path if not os.path.isfile(full)
           else "a file already exists at " + rel if os.path.lexists(os.path.join(tree, rel))
           else "a parent of %s is a file or a symlink: %s" % (rel, parent) if parent else "")
    if bad:
        return None, bad
    try:
        why = merge.run_tests(project, sha, test, tail=60, overlay=(base, [rel]))
    except OSError as e:
        return None, "the file could not be copied: %s" % e
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
    # the loop posts one `## Review, round N` comment per review; the fix rounds are one fewer
    return max(0, len({n for t in texts for n in re.findall(r"^## Review, round (\d+)", t, re.M)}) - 1)


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
    try:
        with common.scratch_tree(project, "origin/" + settings["Loop branch"]) as tree:
            _pass(project, settings, since_ref, tree, r)
    except Exception as e:  # the pass never raises; it reports
        r["errors"].append("pass stopped: %s" % e)
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
    issues = json.loads(gh(["issue", "list", "--state", "open", "--limit", "200", "--json",
                            "number,title,body,labels,comments"]) or "[]")
    tags = lambda i: {l["name"] for l in i.get("labels", [])}
    decisions = ["#%s %s: %s" % (i["number"], i["title"], ((i.get("body") or "").strip().split("\n") or [""])[0][:200])
                 for i in issues if tags(i) & {"inbox", "needs-user"} and not i["title"].startswith(FINDINGS)]
    reply = ask("confirm", "\nOpen decisions (a finding that touches one is held, not queued):\n"
                + "\n".join(decisions or ["none"]) + "\n\nFindings to judge:\n"
                + "\n".join("%s | %s | .lite/pass/%s" % c[:3] for c in candidates)) if candidates else ""
    said, held = [f[0] for f in findings(reply, "CONFIRMED")], {f[0]: f[1] for f in findings(reply, "HELD")}
    for c in candidates:
        if c[0] in held:
            r["held"].append((c[0], "%s\n\nHeld for an open decision: %s. Not queued as a defect." % (c[1], held[c[0]]), ""))
        else:
            r["confirmed" if c[0] in said else "rejected"].append(c if c[0] in said else (c[0], "not confirmed"))
    reply = ask("lessons", "\nMerged in this batch:\n" + "\n".join(r["batch"]) + "\n\nFindings so far:\n"
                + "\n".join(f[0] for f in r["drift"] + r["rubric"] + r["confirmed"]) + "\n")
    r["lessons"], r["guardrails"] = [f[0] for f in findings(reply, "LESSONS")], findings(reply, "GUARDRAILS")
    ready = "ready" if approves(plan, "confirmed defect") else "inbox"
    fence = lambda c: "`" * max([3] + [len(m) + 1 for m in re.findall(r"`+", c)])
    jobs = [(t, "%s\n\n## Failing test\n\nPath: %s\n\n%s\n%s\n%s\n" % (esc(d), p, fence(c), c.rstrip("\n"), fence(c)),
             ready) for t, d, p, c in r["confirmed"]]
    found = r["drift"] + r["rubric"] + r["held"] + r["guardrails"] + [("Add to PLAN.md ## Lessons", l, "") for l in r["lessons"]]
    line = lambda t, d: "- [ ] **%s**: %s" % (t, esc(d).replace("\n", "\n  "))
    open_ = next((i for i in issues if i["title"].startswith(FINDINGS) and "inbox" in tags(i)), None)
    if open_:  # one open findings issue: add only what it does not list yet
        listed = (open_.get("body") or "") + "".join(c.get("body") or "" for c in open_.get("comments", []))
        found = [f for f in found if "**%s**" % f[0] not in listed]
        if found:
            gh(["issue", "comment", str(open_["number"]), "--body-file", "-"], retry=False,
               input="\n".join(line(t, d) for t, d, _ in found) + "\n\n" + common.MARKER + "\n")
            r["issues"].append("#%s %d finding(s) added" % (open_["number"], len(found)))
    else:
        jobs += [("%s, %s, %s" % (FINDINGS, time.strftime("%Y-%m-%d"), sha[:7]),
                  "\n".join(line(t, d) for t, d, _ in found), "inbox")] * bool(found)
    for title, body, label in jobs:
        number = create(title, body, label)
        r["issues"] += ["#%s %s (%s)" % (number, title, label)] if number else []


def markdown(r):
    show = lambda v: "\n".join("- " + (": ".join(x[:2]) if isinstance(x, tuple) else x) for x in v) or "none"
    return "## End-of-loop pass (%d sessions)\n\n### Smoke\n\n%s\n\n" % (r["sessions"], r["smoke"]) + "\n\n".join(
        "### %s\n\n%s" % (title, show(r[key])) for key, title in TITLES)
