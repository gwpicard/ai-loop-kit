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
LIMIT = 200  # open issues read; a full page may be truncated
HELD = r"^[ \t*`]*HELD:[ \t*`]*(.*)$"
RUBRIC_BLOCK = r"^[\s*`]*RUBRIC (?:CONFIRMED|REJECTED):"
LOCATED = r"[\w./-]+:\d+"  # file:line
TITLES = (("drift", "Drift"), ("confirmed", "Red team: confirmed"), ("rejected", "Red team: rejected"),
          ("rubric", "Rubric"), ("rubric_rejected", "Rubric: rejected"), ("simplify", "Simplify and reconcile"), ("held", "Held for an open decision"), ("lessons", "Lessons"), ("guardrails", "Proposed guardrails"),
          ("issues", "Issues created"), ("batch", "Merged in this batch"), ("errors", "Problems"))


def esc(text):  # a finding cannot start a section of the issue
    return re.sub(r"(?m)^(\s*#)", r"\\\1", text)


def failing(project, sha, test, tree, path, prepare="", check="", files=""):
    # (path the Test command finds the file at, None) if it fails there once copied; else (None, why not)
    base, full = os.path.realpath(os.path.join(tree, ".loop", "pass")), os.path.join(tree, path)
    rel = os.path.relpath(os.path.realpath(full), base)
    parts = rel.split(os.sep)
    parent = next((q for q in (os.path.join(tree, *parts[:i]) for i in range(1, len(parts)))
                   if os.path.islink(q) or os.path.lexists(q) and not os.path.isdir(q)), "")
    bad = ("no test file" if not path else "the path is a symlink: " + path if os.path.islink(full)
           else "the path is outside .loop/pass/: " + path if rel.split(os.sep)[0] == ".."
           else "no test file at " + path if not os.path.isfile(full)
           else "a file already exists at " + rel if os.path.lexists(os.path.join(tree, rel))
           else "a parent of %s is a file or a symlink: %s" % (rel, parent) if parent else "")
    if bad:
        return None, bad
    try:
        command = common.files_command({"Test command": test, "Test files command": files}, [rel])
        why = merge.run_tests(project, sha, command, tail=60, overlay=(base, [rel]), prepare=prepare)
    except OSError as e:
        return None, "the file could not be copied: %s" % e
    if not why:
        return None, "the test passes under the Test command"
    if re.search(r"SyntaxError|IndentationError|ImportError|ModuleNotFound|NameError|errors? during collection|"
                 r"error collecting|cannot find module|timed out", why, re.I):
        return None, "the test errors (syntax or import) or times out"
    if check and (why := merge.run_tests(project, sha, "", tail=20, check=check, overlay=(base, [rel]), prepare=prepare)):
        return None, "the test fails the project's checks (lint, format): " + why
    return rel, None


def findings(text, name="FINDINGS"):  # (title, detail, path) per `title | detail | path` line
    rows = [(l.split("|", 2) + ["", ""])[:3] for l in flow.parse_block(text, name) if re.sub(r"[^a-z]", "", l.lower()) not in ("none", "nonefound", "nofindings")]
    return [(t.strip(), d.strip(), p.strip().strip("`").strip()) for t, d, p in rows]


def fix_rounds(texts):
    # the loop posts one `## Review, round N` comment per review; the fix rounds are one fewer
    return max(0, len({n for t in texts for n in re.findall(r"^## Review, round (\d+)", t, re.M)}) - 1)


def batch_lines(project, since, loop, notes=None):
    # one line per issue merged since `since`: build note title, fix rounds, parks, deviations;
    # `notes` collects each build note whole
    log = git(["log", "--format=%s", "%s..origin/%s" % (since, loop)], cwd=project, check=False)
    lines = []
    for n in sorted({int(m) for m in re.findall(r"^Issue (\d+)", log, re.M)}):
        info = json.loads(gh(["issue", "view", str(n), "--json", "title,body,comments"]))
        prs = json.loads(gh(["pr", "list", "--head", "issue/%d" % n, "--state", "all", "--json", "comments"]))
        texts = [c.get("body") or "" for c in info["comments"] + [c for p in prs for c in p["comments"]]]
        built = next((t for t in texts if t.startswith("## Built")), "\nno build note")
        if notes is not None:
            notes.append("#%d %s\n%s" % (n, info["title"], built.strip()[:2000]))
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
    with common.settings_environment(settings), common.timed("pass", project) as end:
        try:
            with common.scratch_tree(project, "origin/" + settings["Loop branch"]) as tree:
                _pass(project, settings, since_ref, tree, r)
        except Exception as e:  # the pass never raises; it reports
            r["errors"].append("pass stopped: %s" % e)
        end.update(outcome="failed" if r["errors"] else "done", sessions=r["sessions"],
                   confirmed=len(r["confirmed"]),
                   rejected=len(r["rejected"]),
                   issues=sum("finding(s) added" not in i for i in r["issues"]))
    return r, markdown(r)


def _pass(project, settings, since, tree, r):
    sha, test = git(["rev-parse", "HEAD"], cwd=tree), settings["Test command"]
    check = settings.get("Check command")
    context = "\n\nLoop branch: %s\nTest command: %s\nRed-team surfaces: %s\n%sBatch diff: git diff %s...HEAD\n" % (
        settings["Loop branch"], test, json.dumps(settings.get("Red-team surfaces", [])),
        "Check command: %s\n" % check if check else "", since)
    def ask(name, extra=""):  # at most 9 calls: drift, rubric, four red teams, confirm, lessons, simplify
        r["sessions"] += 1
        try:
            return session.run("pass", flow.brief("pass-%s" % name) + context + extra,
                               tree, settings["Pass"][1], project, "pass", agent=settings["Pass"][0])[0]
        except common.LoopError as e:
            r["errors"].append("%s session: %s" % (name, e))
            return ""
    if settings.get("Smoke command"):
        bad = merge.run_tests(project, sha, settings["Smoke command"], tail=5, prepare=settings["Prepare command"])
        r["smoke"] = bad.replace("the Test command", "the Smoke command") if bad else "passed"
        r["drift"] += [("Smoke command failed on the loop branch", r["smoke"], "")] if bad else []
    notes = []
    try:
        r["batch"] = batch_lines(project, since, settings["Loop branch"], notes)
    except Exception as e:
        r["errors"].append("batch notes: %s" % e)
    drift = ask("drift")
    r["drift"] += findings(drift)
    rubric = findings(ask("rubric"))
    surfaces = settings.get("Red-team surfaces", [])[:4]
    if findings(drift, "SURFACES") and not surfaces:
        r["drift"].append(("Set Red-team surfaces in loop.json", "Proposed Red-team surfaces:\n- "
                           + "\n- ".join(f[0] for f in findings(drift, "SURFACES")[:4]), ""))
    candidates = []
    for surface in surfaces:
        for title, detail, path in findings(ask("redteam", "\nSurface: %s\n" % surface)):
            rel, why = failing(project, sha, test, tree, path, settings["Prepare command"], settings["Check command"],
                               settings["Test files command"])
            if rel:
                candidates.append((title, detail, rel, Path(tree, path).read_text(encoding="utf-8")))
            else:
                r["rejected"].append((title, why))
    issues = json.loads(gh(["issue", "list", "--state", "open", "--limit", str(LIMIT), "--json",
                            "number,title,body,labels,comments"]) or "[]")
    tags = lambda i: {l["name"] for l in i.get("labels", [])}
    decisions = ["#%s %s: %s" % (i["number"], i["title"], ((i.get("body") or "").strip().split("\n") or [""])[0][:200])
                 for i in issues if tags(i) & {"inbox", "needs-user"} and not i["title"].startswith(FINDINGS)]
    reply = ask("confirm", "\nOpen decisions (a finding that touches one is held, not queued):\n"
                + "\n".join(decisions or ["none"]) + ("\n\nFindings to judge:\n"
                + "\n".join("%s | %s | .loop/pass/%s" % c[:3] for c in candidates) if candidates else "")
                + ("\n\nRubric findings to judge:\n" + "\n".join("%s | %s" % f[:2] for f in rubric) if rubric else "")
                ) if candidates or rubric else ""
    blocked = "the open-issue list may be truncated" if len(issues) >= LIMIT else ""
    if candidates and not re.search(HELD, reply, re.M):
        blocked = "confirm reply unreadable"
    unvalidated = bool(rubric) and not re.search(RUBRIC_BLOCK, reply, re.M)
    reply = re.sub(HELD, lambda m: "HELD:\n" + m.group(1) if m.group(1) else "HELD:", reply, flags=re.M)
    said, held = [f[0] for f in findings(reply, "CONFIRMED")], {f[0]: f[1] for f in findings(reply, "HELD")}
    for c in candidates:
        if c[0] in held:
            r["held"].append((c[0], "%s\n\nHeld for an open decision: %s. Not queued as a defect." % (c[1], held[c[0]]), ""))
        else:
            r["confirmed" if c[0] in said else "rejected"].append(c if c[0] in said else (c[0], "not confirmed"))
    accepted = [f[0] for f in findings(reply, "RUBRIC CONFIRMED")]
    why = {f[0]: f[1] for f in findings(reply, "RUBRIC REJECTED")}
    for f in rubric:
        if unvalidated:  # the reply cannot be read: file the finding, marked
            r["rubric"].append((f[0], f[1] + " (not validated)", f[2]))
        elif not re.search(LOCATED, f[1]):
            r["rubric_rejected"].append((f[0], "no file:line"))
        elif f[0] in accepted:
            r["rubric"].append(f)
        else:
            r["rubric_rejected"].append((f[0], why.get(f[0]) or "not confirmed"))
    reply = ask("lessons", "\nMerged in this batch:\n" + "\n".join(r["batch"]) + "\n\nFindings so far:\n"
                + "\n".join(f[0] for f in r["drift"] + r["rubric"] + r["confirmed"]) + "\n")
    r["lessons"], r["guardrails"] = findings(reply, "LESSONS"), findings(reply, "GUARDRAILS")
    r["simplify"] = findings(ask("simplify", "\nMerged in this batch:\n" + "\n".join(r["batch"]) + "\n\nBuild notes:\n"
                                 + "\n\n".join(notes) + "\n"), "SIMPLIFY")
    if blocked:  # open decisions cannot be checked: queue only the rubric findings
        r["errors"].append("nothing queued: " + blocked)
    queued = lambda items: [] if blocked else items
    fence = lambda c: "`" * max([3] + [len(m) + 1 for m in re.findall(r"`+", c)])
    jobs = [(t, "%s\n\n## Failing test\n\nPath: %s\n\n%s\n%s\n%s\n" % (esc(d), p, fence(c), c.rstrip("\n"), fence(c)),
             "inbox") for t, d, p, c in queued(r["confirmed"])]
    jobs += [(t, d, "inbox") for t, d, _ in queued(r["lessons"])]
    found = queued(r["drift"]) + r["rubric"] + queued(r["held"] + r["guardrails"])
    line = lambda t, d: "- [ ] **%s**: %s" % (t, esc(d).replace("\n", "\n  "))
    def file(prefix, items):  # one open inbox issue per kind: add only what it does not list yet
        open_ = next((i for i in issues if i["title"].startswith(prefix) and "inbox" in tags(i)), None)
        if open_:
            listed = (open_.get("body") or "") + "".join(c.get("body") or "" for c in open_.get("comments", []))
            items = [f for f in items if "**%s**" % f[0] not in listed]
            if items:
                gh(["issue", "comment", str(open_["number"]), "--body-file", "-"], retry=False,
                   input="\n".join(line(t, d) for t, d, _ in items) + "\n\n" + common.MARKER + "\n")
                r["issues"].append("#%s %d finding(s) added" % (open_["number"], len(items)))
        elif items:
            jobs.append(("%s, %s, %s" % (prefix, time.strftime("%Y-%m-%d"), sha[:7]), "\n".join(line(t, d) for t, d, _ in items), "inbox"))
    file(FINDINGS, found)
    file("Simplify and reconcile", queued(r["simplify"]))
    for title, body, label in jobs:
        number = create(title, body, label)
        r["issues"] += ["#%s %s (%s)" % (number, title, label)] if number else []


def markdown(r):
    show = lambda v: "\n".join("- " + (": ".join(x[:2]) if isinstance(x, tuple) else x) for x in v) or "none"
    return "## End-of-loop pass (%d sessions)\n\n### Smoke\n\n%s\n\n" % (r["sessions"], r["smoke"]) + "\n\n".join(
        "### %s\n\n%s" % (title, show(r[key])) for key, title in TITLES)
