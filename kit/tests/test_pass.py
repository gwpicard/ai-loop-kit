import json
import os
import subprocess
import time
from pathlib import Path
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import pass_

AGENTS = "## Loop\nTest command: test ! -f tests/test_x.py\n"
APPROVAL = ("A confirmed defect with a failing test, found by the end-of-loop pass, may be queued as "
            "ready without the person's yes. Everything else goes to the inbox.")
BUILT = "## Built\n\nAdded the thing.\n\nDeviations: none\n"
FIND = {"files": {".loop/pass/tests/test_x.py": "fails\n"},
        "reply": "FINDINGS:\nBroken input | crashes on empty input | .loop/pass/tests/test_x.py"}
CONFIRM = {"reply": "CONFIRMED:\nBroken input\n\nHELD:\nnone\n\nREJECTED:\nnone"}
REJECT = {"reply": "CONFIRMED:\nnone\n\nHELD:\nnone\n\nREJECTED:\nBroken input"}
NONE = {"reply": "FINDINGS:\nnone"}
LESSONS = {"reply": "LESSONS:\nCheck empty input first.\n\nGUARDRAILS:\nBudget on input size | add a size budget |"}


def plan(approval=True, surfaces=("the CLI",)):
    return "# Plan\n\n## Standing approvals\n\n%s\n\n## Surfaces\n\n%s\n" % (
        APPROVAL if approval else "None.", "".join("- %s\n" % s for s in surfaces))


class PassTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()

    def repo(self, plan_text, extra=""):
        self.work, _ = make_repo(self.tmp, {"AGENTS.md": AGENTS + extra, "PLAN.md": plan_text})
        run_git(["checkout", "-b", "loop/main"], self.work)
        with open(os.path.join(self.work, "a.txt"), "w") as f:
            f.write("a\n")
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "Issue 3"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        self.settings = common.read_settings(self.work)
        self.gh()

    def gh(self, listed=(), built_body="Built by the loop.\n\n" + common.MARKER):
        self.scenario([
            {"match": "issue view 3", "responses": [{"stdout": json.dumps({
                "title": "Add it", "body": built_body, "comments": [{"body": BUILT}]})}]},
            {"match": "pr list", "responses": [{"stdout": json.dumps([{"comments": [
                {"body": "## Review, round 1\n\nVERDICT: CHANGES\nHEAD: x"}, {"body": "## Review, round 2\n\nVERDICT: APPROVE\nHEAD: y"}]}])}]},
            {"match": "issue list", "responses": [{"stdout": json.dumps([t if isinstance(t, dict) else {"title": t} for t in listed])}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue create", "responses": [{"stdout": "https://github.com/o/r/issues/41\n"}]}])

    def run_pass(self):
        return pass_.run_pass(self.work, self.settings, "origin/main")

    def created(self):
        out = []
        for c in self.calls():
            if c[:2] == ["issue", "create"]:
                out.append((c[c.index("--title") + 1], c[c.index("--label") + 1]))
        return out

    def bodies(self):
        seen, real = [], common.gh
        pass_.gh = lambda a, **k: (seen.append((a, k.get("input"))), real(a, **k))[1]
        self.addCleanup(setattr, pass_, "gh", real)
        return seen

    def steps(self, redteam, confirm=None, count=1):
        self.claude({"pass": [NONE, NONE] + [redteam] * count + ([confirm] if confirm else []) + [LESSONS]})

    def test_smoke_failure_is_a_finding(self):
        self.repo(plan(surfaces=()), "Smoke command: test -f NOSUCH\n")
        seen = self.bodies()
        r, md = self.run_pass()
        self.assertIn("Smoke command failed", r["smoke"])
        self.assertEqual([l for _, l in self.created()], ["inbox"])
        self.assertIn("- [ ] **Smoke command failed on the loop branch**: ", [i for a, i in seen if a[:2] == ["issue", "create"]][0])
        self.assertIn("failed", md)

    def test_passing_red_team_test_is_dropped(self):
        self.repo(plan())
        self.steps({"files": {".loop/pass/tests/ok.py": "x\n"},
                    "reply": "FINDINGS:\nWeak claim | maybe | .loop/pass/tests/ok.py"})
        r, _ = self.run_pass()
        self.assertEqual(r["sessions"], 5)  # no confirm session
        self.assertEqual(r["confirmed"], [])
        self.assertNotIn("Weak claim", [t for t, _ in self.created()])

    def test_confirmed_finding_is_ready_under_standing_approval(self):
        self.repo(plan())
        self.steps(FIND, CONFIRM)
        r, md = self.run_pass()
        self.assertIn(("Broken input", "ready"), self.created())
        create = [c for c in self.calls() if c[:2] == ["issue", "create"]][0]
        self.assertEqual(r["confirmed"][0][2], "tests/test_x.py")
        self.assertEqual(sorted(l for _, l in self.created()), ["inbox", "ready"])  # one findings issue
        self.assertIn("41 Broken input (ready)", md)
        self.assertNotIn("test_x.py", " ".join(create))  # body goes through stdin

    def test_failing_test_is_in_the_issue_body(self):
        self.repo(plan())
        self.steps(FIND, CONFIRM)
        seen = []
        real = common.gh
        pass_.gh = lambda a, **k: (seen.append((a, k.get("input"))), real(a, **k))[1]
        self.addCleanup(setattr, pass_, "gh", real)
        self.run_pass()
        body = [i for a, i in seen if a[:2] == ["issue", "create"] and "Broken input" in a][0]
        self.assertIn("## Failing test", body)
        self.assertIn("Path: tests/test_x.py", body)
        self.assertIn("fails", body)
        self.assertIn(common.MARKER, body)

    DECISION = {"number": 14, "title": "Decide how a byte-order mark is counted", "body": "Choose.\nMore.",
                "labels": [{"name": "inbox"}], "comments": []}
    HELD = {"reply": "CONFIRMED:\nBroken input\n\nHELD:\nBroken input | #%d" % 14}

    def test_a_finding_that_touches_an_open_decision_is_held_not_queued(self):
        self.repo(plan())
        self.gh(listed=[self.DECISION])
        self.steps(FIND, self.HELD)
        seen = self.bodies()
        r, md = self.run_pass()
        confirm = self.claude_calls()[3]["prompt"]
        self.assertIn("#%d Decide how a byte-order mark is counted: Choose." % 14, confirm)
        self.assertNotIn("More.", confirm)
        self.assertNotIn(("Broken input", "ready"), self.created())
        self.assertEqual(r["confirmed"], [])
        body = [i for a, i in seen if a[:2] == ["issue", "create"]][0]
        self.assertIn("**Broken input**", body)
        self.assertIn("Held for an open decision: #%d" % 14, body)
        self.assertIn("### Held for an open decision\n\n- Broken input", md)

    def held_run(self, reply, listed=None):
        self.repo(plan())
        self.gh(listed=listed if listed is not None else [self.DECISION])
        self.steps(FIND, {"reply": reply})
        r, md = self.run_pass()
        return r

    def test_a_confirm_reply_without_a_held_block_queues_nothing(self):
        r = self.held_run("CONFIRMED:\nBroken input\n")
        self.assertEqual(self.created(), [])
        self.assertIn("nothing queued: confirm reply unreadable", r["errors"])

    def readable(self, held):
        r = self.held_run("CONFIRMED:\nBroken input\n\n" + held)
        self.assertEqual(r["errors"], [])
        self.assertIn(("Broken input", "ready"), self.created())

    def test_held_none_on_the_same_line_is_readable(self):
        self.readable("HELD: none")

    def test_held_in_bold_is_readable(self):
        self.readable("**HELD:**\nnone")

    def test_held_in_backticks_is_readable(self):
        self.readable("`HELD:`\nnone")

    def test_a_full_open_issue_listing_may_be_truncated_so_nothing_is_queued(self):
        full = [{"number": n, "title": "Other %d" % n, "labels": [], "body": ""} for n in range(pass_.LIMIT)]
        r = self.held_run("CONFIRMED:\nBroken input\n\nHELD:\nnone", listed=full)
        self.assertEqual(self.created(), [])
        self.assertIn("nothing queued: the open-issue list may be truncated", r["errors"])

    OPEN = {"number": 29, "title": "Pass findings, 2026-11-14, aaaaaaa", "labels": [{"name": "inbox"}],
            "body": "- [ ] **Budget on input size**: x", "comments": [{"body": "- [ ] **Check empty input first**: y"}]}

    def test_findings_go_to_the_one_open_pass_findings_issue(self):
        self.repo(plan())
        self.gh(listed=[self.OPEN])
        self.steps(NONE)
        seen = self.bodies()
        r, _ = self.run_pass()
        self.assertEqual(self.created(), [])
        comments = [(a, i) for a, i in seen if a[:2] == ["issue", "comment"]]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0][0][2], "29")
        self.assertNotIn("Budget on input size", comments[0][1])
        self.assertIn("Add to PLAN.md ## Lessons", comments[0][1])
        self.assertIn(common.MARKER, comments[0][1])
        self.assertIn("#%d 1 finding(s) added" % 29, r["issues"])

    def test_nothing_is_added_when_the_open_findings_issue_lists_it_all(self):
        self.repo(plan())
        self.gh(listed=[dict(self.OPEN, body=self.OPEN["body"] + "\n- [ ] **Add to PLAN.md ## Lessons**: z")])
        self.steps(NONE)
        self.run_pass()
        self.assertFalse(any(c[:2] == ["issue", "comment"] for c in self.calls()))

    def test_confirmed_finding_is_inbox_without_approval(self):
        self.repo(plan(approval=False))
        self.steps(FIND, CONFIRM)
        self.run_pass()
        self.assertIn(("Broken input", "inbox"), self.created())

    def test_rejected_finding_creates_nothing(self):
        self.repo(plan())
        self.steps(FIND, REJECT)
        r, md = self.run_pass()
        self.assertNotIn("Broken input", [t for t, _ in self.created()])
        self.assertEqual(r["rejected"], [("Broken input", "not confirmed")])
        self.assertIn("Red team: rejected\n\n- Broken input", md)

    SIMPLIFY = {"reply": "SIMPLIFY:\nShare one verdict parser | flow.py and merge.py each read the verdict; keep merge.parse_verdict | flow.py\n"
                         "Close the workaround | the builder worked around the cache in app.py; remove it once the cache is fixed |"}

    def test_one_session_files_one_simplify_and_reconcile_issue(self):
        self.repo(plan(surfaces=()))
        self.claude({"pass": [NONE, NONE, LESSONS, self.SIMPLIFY]})
        seen = self.bodies()
        r, md = self.run_pass()
        title = "Simplify and reconcile, %s, %s" % (time.strftime("%Y-%m-%d"), common.git(
            ["rev-parse", "--short=7", "origin/loop/main"], cwd=self.work))
        self.assertEqual([t for t, _ in self.created()].count(title), 1)  # one issue, not one per finding
        self.assertEqual(sum(t.startswith("Simplify") for t, _ in self.created()), 1)
        body = [i for a, i in seen if a[:2] == ["issue", "create"] and title in a][0]
        self.assertIn("- [ ] **Share one verdict parser**: flow.py and merge.py each read the verdict", body)
        self.assertIn("- [ ] **Close the workaround**", body)
        self.assertEqual(r["sessions"], 4)
        self.assertIn("### Simplify and reconcile\n\n- Share one verdict parser", md)
        prompt = self.claude_calls()[3]["prompt"]
        self.assertIn("Added the thing.", prompt)  # the batch's build note, with its deviations
        self.assertIn("Merged in this batch", prompt)
        self.assertIn("git diff origin/main...HEAD", prompt)
        brief = Path(pass_.flow.BRIEFS, "pass-simplify.md").read_text(encoding="utf-8")
        for text in ("behaviour-preserving", "not exercised", "workarounds", "Edit nothing"):
            self.assertIn(text, brief)

    def test_a_defect_round_is_one_pass_that_queued_a_ready_defect(self):
        self.repo(plan())
        self.steps(FIND, CONFIRM)
        r, _ = pass_.run_pass(self.work, self.settings, "origin/main", rounds=0)
        self.assertEqual(r["rounds"], 1)
        self.assertIn(("Broken input", "ready"), self.created())
        self.steps(NONE)
        r, _ = pass_.run_pass(self.work, self.settings, "origin/main", rounds=1)
        self.assertEqual(r["rounds"], 1)  # nothing queued: not a round

    def test_defects_are_filed_as_inbox_once_the_rounds_limit_is_reached(self):
        self.repo(plan(), "Defect rounds: 2\n")
        self.steps(FIND, CONFIRM)
        seen = self.bodies()
        r, md = pass_.run_pass(self.work, self.settings, "origin/main", rounds=2)
        self.assertIn(("Broken input", "inbox"), self.created())
        self.assertNotIn(("Broken input", "ready"), self.created())
        body = [i for a, i in seen if a[:2] == ["issue", "create"] and "Broken input" in a][0]
        self.assertIn("## Failing test", body)
        self.assertEqual(r["rounds"], 2)
        self.assertTrue(r["capped"])
        self.assertIn("Defect rounds limit (2) reached", md)

    def test_an_unreadable_round_count_queues_nothing_as_ready_and_says_so(self):
        self.repo(plan())
        self.steps(FIND, CONFIRM)
        r, md = pass_.run_pass(self.work, self.settings, "origin/main", rounds=None)
        self.assertIn(("Broken input", "inbox"), self.created())
        self.assertNotIn(("Broken input", "ready"), self.created())
        self.assertIn("could not be read", md)
        self.assertEqual(r["rounds"], 2)

    def test_a_merged_issue_the_person_labelled_resets_the_count(self):
        self.repo(plan(), "Defect rounds: 2\n")
        self.gh(built_body="Added by hand.")  # no loop marker: the person queued it
        self.steps(FIND, CONFIRM)
        r, _ = pass_.run_pass(self.work, self.settings, "origin/main", rounds=2)
        self.assertIn(("Broken input", "ready"), self.created())
        self.assertEqual(r["rounds"], 1)
        self.assertFalse(r.get("capped"))

    def test_a_red_team_test_that_fails_the_check_command_is_rejected(self):
        self.repo(plan(), "Check command: ! grep -rq badlint tests\n")
        self.steps({"files": {".loop/pass/tests/test_x.py": "badlint\n"},
                    "reply": FIND["reply"]})
        r, _ = self.run_pass()
        self.assertEqual(r["sessions"], 5)  # no confirm session
        self.assertEqual(r["confirmed"], [])
        self.assertIn("Check command", r["rejected"][0][1])

    def test_a_red_team_test_that_passes_the_check_command_is_kept(self):
        self.repo(plan(), "Check command: ! grep -rq badlint tests\n")
        self.steps(FIND, CONFIRM)
        r, _ = self.run_pass()
        self.assertEqual(len(r["confirmed"]), 1)

    def test_a_later_pass_adds_to_the_one_open_simplify_issue(self):
        self.repo(plan(surfaces=()))
        self.gh(listed=[{"number": 31, "title": "Simplify and reconcile, 2026-11-14, aaaaaaa", "labels": [{"name": "inbox"}],
                         "body": "- [ ] **Share one verdict parser**: x", "comments": []}])
        self.claude({"pass": [NONE, NONE, LESSONS, self.SIMPLIFY]})
        seen = self.bodies()
        r, _ = self.run_pass()
        self.assertFalse(any(t.startswith("Simplify") for t, _ in self.created()))
        comments = [(a, i) for a, i in seen if a[:3] == ["issue", "comment", "31"]]
        self.assertEqual(len(comments), 1)
        self.assertIn("**Close the workaround**", comments[0][1])
        self.assertNotIn("Share one verdict parser", comments[0][1])
        self.assertIn(common.MARKER, comments[0][1])

    def test_at_most_nine_sessions_and_four_surfaces(self):
        self.repo(plan(surfaces=["s%d" % i for i in range(6)]))
        self.steps(NONE, count=6)
        r, _ = self.run_pass()
        self.assertEqual(r["sessions"], 8)  # drift, rubric, four surfaces, lessons, simplify
        self.assertEqual(len(self.claude_calls()), 8)
        self.assertEqual(sum("Surface:" in c["prompt"] for c in self.claude_calls()), 4)
        self.assertTrue(all(c["role"] == "pass" for c in self.claude_calls()))

    def test_second_run_creates_nothing_new(self):
        self.repo(plan())
        self.steps(FIND, CONFIRM)
        self.run_pass()
        first = self.created()
        self.assertTrue(first)
        self.gh(listed=[t for t, _ in first])
        self.steps(FIND, CONFIRM)
        self.run_pass()
        self.assertEqual(self.created(), [])

    def test_report_has_every_section_and_the_worktree_is_gone(self):
        self.repo(plan(), "Smoke command: true\n")
        self.steps(FIND, CONFIRM)
        r, md = self.run_pass()
        for heading in ("Smoke", "Drift", "Red team", "Rubric", "Lessons", "Issues created",
                        "Merged in this batch"):
            self.assertIn("### " + heading, md)
        self.assertIn("3 Add it: Added the thing. (fix rounds 1, parks 0, deviations: none)", md)
        self.assertIn("passed", md)
        out = subprocess.run(["git", "worktree", "list"], cwd=self.work, capture_output=True, text=True).stdout
        self.assertEqual(len(out.strip().splitlines()), 1)

    def test_issue_text_cannot_inject_sections_and_is_fenced(self):
        self.repo(plan())
        evil = {"files": {".loop/pass/tests/test_x.py": "# heading\nx = '''```'''\n```\n"},
                "reply": "FINDINGS:\nBroken input | fine\n## Injected | .loop/pass/tests/test_x.py"}
        evil["reply"] = "FINDINGS:\nBroken input | line one ## not a heading | .loop/pass/tests/test_x.py"
        self.steps(evil, CONFIRM)
        seen = []
        real = common.gh
        pass_.gh = lambda a, **k: (seen.append((a, k.get("input"))), real(a, **k))[1]
        self.addCleanup(setattr, pass_, "gh", real)
        self.run_pass()
        body = [i for a, i in seen if a[:2] == ["issue", "create"] and "Broken input" in a][0]
        self.assertIn("\n````\n# heading", body)
        self.assertEqual(pass_.merge.allowed_paths(body), set())
        self.assertTrue(body.split(common.MARKER)[0].endswith("````\n\n\n"))
        self.assertEqual(pass_.esc("a\n## b\n  # c"), "a\n\\## b\n\\  # c")

    def test_confirmation_needs_the_exact_title(self):
        self.repo(plan())
        self.steps(FIND, {"reply": "CONFIRMED:\nBroken input and more\n\nREJECTED:\nnone"})
        r, _ = self.run_pass()
        self.assertEqual(r["confirmed"], [])
        self.assertNotIn("Broken input", [t for t, _ in self.created()])

    def test_approval_fails_closed(self):
        yes = "A confirmed defect may be queued as ready."
        self.assertTrue(pass_.approves("## Standing approvals\n\n" + yes + "\n\n## X", "confirmed defect"))
        for text in ["A confirmed defect may not be queued as ready.", "A confirmed defect can't be queued as ready.",
                     "A confirmed defect may be queued as ready only after the person agrees.",
                     "A confirmed defect may be queued as ready unless it touches data.",
                     "Never: a confirmed defect may be queued as ready.", "A confirmed defect is ready.",
                     "No standing approvals.", "A confirmed defect\nmay be queued as ready.\nNone otherwise."]:
            self.assertFalse(pass_.approves("## Standing approvals\n\n" + text + "\n", "confirmed defect"), text)
        self.assertFalse(pass_.approves("## Decisions\n\n" + yes + "\n", "confirmed defect"))

    def test_errors_are_reported_not_raised_and_earlier_issues_are_kept(self):
        self.repo(plan(), "Smoke command: false\n")
        self.settings["Loop branch"] = "no-such"
        r, md = self.run_pass()
        self.assertIn("pass stopped", md)

    def test_a_failed_create_keeps_the_earlier_issues(self):
        self.repo(plan())
        self.steps(FIND, CONFIRM)
        with open(self.scenario_path) as f:
            rules = json.load(f)["rules"]
        rules[-1] = {"match": "issue create", "responses": [
            {"stdout": "https://github.com/o/r/issues/41\n"}, {"code": 1, "stderr": "boom"}]}
        self.scenario(rules)
        r, md = self.run_pass()
        self.assertEqual(len(r["issues"]), 1)
        self.assertIn("Broken input", r["issues"][0])
        self.assertIn("pass stopped", md)

    def test_titles_are_deduped_against_all_issues(self):
        self.repo(plan(surfaces=()))
        self.claude({"pass": [{"reply": "FINDINGS:\nOne | a |"}]})
        self.run_pass()
        lists = [c for c in self.calls() if c[:2] == ["issue", "list"]]
        self.assertTrue(any("all" in c for c in lists))

    def test_fix_rounds_count_distinct_round_numbers(self):
        review = lambda n: "## Review, round %d\n\nVERDICT: CHANGES" % n
        self.assertEqual(pass_.fix_rounds([review(1), review(1), review(2)]), 1)  # a repost of round 1 is not a round
        self.assertEqual(pass_.fix_rounds([review(1), review(1)]), 0)

    def test_fix_rounds_come_from_the_review_comments(self):
        review = lambda n: "## Review, round %d\n\nVERDICT: CHANGES\nHEAD: x" % n
        self.assertEqual(pass_.fix_rounds([]), 0)
        self.assertEqual(pass_.fix_rounds([review(1), "VERDICT: APPROVE\nHEAD: x"]), 0)  # the pull request's copy does not count
        self.assertEqual(pass_.fix_rounds([review(1), review(2)]), 1)
        self.assertEqual(pass_.fix_rounds(["Done", review(1), review(2), review(3)]), 2)

    def test_the_red_team_file_runs_under_a_discovery_command_in_tests(self):
        self.work, _ = make_repo(self.tmp, {
            "AGENTS.md": "## Loop\nTest command: python3 -m unittest discover -s tests -q\n", "PLAN.md": plan(),
            "tests/test_base.py": "import unittest\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"})
        run_git(["checkout", "-b", "loop/main"], self.work)
        run_git(["commit", "--allow-empty", "-m", "Issue 3"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        self.settings = common.read_settings(self.work)
        self.gh()
        bad = "import unittest\n\nclass T(unittest.TestCase):\n    def test_bom(self):\n        self.assertEqual(1, 2)\n"
        self.steps({"files": {".loop/pass/tests/test_bom.py": bad},
                    "reply": "FINDINGS:\nBOM | counted | .loop/pass/tests/test_bom.py"},
                    {"reply": "CONFIRMED:\nBOM"})
        r, _ = self.run_pass()
        self.assertEqual(r["rejected"], [])
        self.assertEqual(r["confirmed"][0][2], "tests/test_bom.py")

    def test_rejection_reasons_are_specific(self):
        tree = os.path.join(self.tmp, "tree")
        for d in ("tests", ".loop/pass/tests"):
            os.makedirs(os.path.join(tree, d))
        for name in (".loop/pass/tests/a.py", ".loop/pass/tests/dup.py", "tests/dup.py", "outside.py"):
            with open(os.path.join(tree, name), "w") as f:
                f.write("x\n")
        os.symlink("/etc/hosts", os.path.join(tree, ".loop/pass/tests/link.py"))
        os.symlink(os.path.join(tree, ".loop/pass/tests/a.py"), os.path.join(tree, ".loop/pass/tests/alias.py"))
        os.makedirs(os.path.join(tree, ".loop/pass/README.md"))
        os.makedirs(os.path.join(tree, ".loop/pass/.git"))
        for name in (".loop/pass/README.md/x.py", ".loop/pass/.git/x.py"):
            with open(os.path.join(tree, name), "w") as f:
                f.write("x\n")
        for name in ("README.md", ".git"):
            with open(os.path.join(tree, name), "w") as f:
                f.write("a file\n")
        reasons = iter(["failed: SyntaxError: bad", "the Test command timed out", None, "failed: AssertionError: 1 != 2"])
        orig = pass_.merge.run_tests
        calls = []
        pass_.merge.run_tests = lambda *a, **k: (calls.append(k["overlay"]), next(reasons))[1]
        self.addCleanup(setattr, pass_.merge, "run_tests", orig)
        ask = lambda p: pass_.failing(".", "sha", "t", tree, p)
        self.assertEqual(ask(""), (None, "no test file"))
        self.assertEqual(ask(".loop/pass/tests/none.py")[1], "no test file at .loop/pass/tests/none.py")
        self.assertIn("symlink", ask(".loop/pass/tests/link.py")[1])
        self.assertIn("symlink", ask(".loop/pass/tests/alias.py")[1])
        for outside in ("../x.py", "/etc/hosts", "outside.py", "tests/dup.py"):
            self.assertIn("outside .loop/pass/", ask(outside)[1], outside)
        self.assertEqual(ask(".loop/pass/tests/dup.py"), (None, "a file already exists at tests/dup.py"))
        for name in ("README.md", ".git"):
            self.assertIn("a parent of %s/x.py is a file or a symlink" % name, ask(".loop/pass/%s/x.py" % name)[1])
        self.assertEqual(calls, [])  # refused before any test run
        self.assertIn("errors (syntax or import)", ask(".loop/pass/tests/a.py")[1])
        self.assertIn("times out", ask(".loop/pass/tests/a.py")[1])
        self.assertEqual(ask(".loop/pass/tests/a.py"), (None, "the test passes under the Test command"))
        self.assertEqual(ask(".loop/pass/tests/a.py"), ("tests/a.py", None))
        self.assertEqual(calls[-1], (os.path.realpath(os.path.join(tree, ".loop/pass")), ["tests/a.py"]))
        pass_.merge.run_tests = mock.Mock(side_effect=OSError("disk full"))
        self.assertEqual(ask(".loop/pass/tests/a.py"), (None, "the file could not be copied: disk full"))

    def test_findings_go_in_one_inbox_issue_with_checkboxes(self):
        self.repo(plan(surfaces=()), "Smoke command: false\n")
        self.claude({"pass": [{"reply": "FINDINGS:\nOne | a\nmore |\nTwo | b |\n\nSURFACES:\nnone"},
                              {"reply": "FINDINGS:\nThree | kit/scripts/a.py:3 c |"},
                              {"reply": "RUBRIC CONFIRMED:\nThree\n\nRUBRIC REJECTED:\nnone\n\nCONFIRMED:\nnone\n\nHELD:\nnone\n\nREJECTED:\nnone"},
                              {"reply": LESSONS["reply"]}]})
        seen = self.bodies()
        r, _ = self.run_pass()
        made = [(a, i) for a, i in seen if a[:2] == ["issue", "create"]]
        self.assertEqual(len(made), 1)
        args, body = made[0]
        self.assertRegex(args[args.index("--title") + 1], r"^Pass findings, \d{4}-\d\d-\d\d, [0-9a-f]{7}$")
        self.assertEqual(args[args.index("--label") + 1], "inbox")
        for line in ("- [ ] **Smoke command failed on the loop branch**: ", "- [ ] **One**: a", "- [ ] **Two**: b",
                     "- [ ] **Three**: kit/scripts/a.py:3 c", "- [ ] **Budget on input size**: add a size budget",
                     "- [ ] **Add to PLAN.md ## Lessons**: Check empty input first."):
            self.assertIn(line, body)
        self.assertEqual(len(r["issues"]), 1)

    def test_no_findings_creates_no_inbox_issue(self):
        self.repo(plan(surfaces=()))
        self.claude({"pass": [NONE, NONE, {"reply": "LESSONS:\nnone\n\nGUARDRAILS:\nnone"}]})
        self.run_pass()
        self.assertEqual(self.created(), [])
