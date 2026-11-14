import json
import os
import subprocess

from lite.tests.fake_claude import FakeClaudeGh
from lite.tests.helpers import make_repo, run_git
import common
import pass_

AGENTS = "## Loop\nTest command: test ! -f .lite/pass/test_x.py\n"
APPROVAL = ("A confirmed defect with a failing test, found by the end-of-loop pass, may be queued as "
            "ready without the person's yes. Everything else goes to the inbox.")
BUILT = "## Built\n\nAdded the thing.\n\nDeviations: none\n"
FIND = {"files": {".lite/pass/test_x.py": "fails\n"},
        "reply": "FINDINGS:\nBroken input | crashes on empty input | .lite/pass/test_x.py"}
CONFIRM = {"reply": "CONFIRMED:\nBroken input\n\nREJECTED:\nnone"}
REJECT = {"reply": "CONFIRMED:\nnone\n\nREJECTED:\nBroken input"}
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

    def gh(self, listed=()):
        self.scenario([
            {"match": "issue view 3", "responses": [{"stdout": json.dumps({
                "title": "Add it", "comments": [{"body": BUILT}]})}]},
            {"match": "pr list", "responses": [{"stdout": json.dumps([{"comments": [
                {"body": "VERDICT: CHANGES\nHEAD: x"}]}])}]},
            {"match": "issue list", "responses": [{"stdout": json.dumps([{"title": t} for t in listed])}]},
            {"match": "issue create", "responses": [{"stdout": "https://github.com/o/r/issues/41\n"}]}])

    def run_pass(self):
        return pass_.run_pass(self.work, self.settings, "origin/main")

    def created(self):
        out = []
        for c in self.calls():
            if c[:2] == ["issue", "create"]:
                out.append((c[c.index("--title") + 1], c[c.index("--label") + 1]))
        return out

    def steps(self, redteam, confirm=None, count=1):
        self.claude({"pass": [NONE, NONE] + [redteam] * count + ([confirm] if confirm else []) + [LESSONS]})

    def test_smoke_failure_is_a_finding(self):
        self.repo(plan(surfaces=()), "Smoke command: test -f NOSUCH\n")
        r, md = self.run_pass()
        self.assertIn("Smoke command failed", r["smoke"])
        self.assertIn(("Smoke command failed on the loop branch", "inbox"), self.created())
        self.assertIn("failed", md)

    def test_passing_red_team_test_is_dropped(self):
        self.repo(plan())
        self.steps({"files": {".lite/pass/ok.py": "x\n"},
                    "reply": "FINDINGS:\nWeak claim | maybe | .lite/pass/ok.py"})
        r, _ = self.run_pass()
        self.assertEqual(r["sessions"], 4)  # no confirm session
        self.assertEqual(r["confirmed"], [])
        self.assertNotIn("Weak claim", [t for t, _ in self.created()])

    def test_confirmed_finding_is_ready_under_standing_approval(self):
        self.repo(plan())
        self.steps(FIND, CONFIRM)
        r, md = self.run_pass()
        self.assertIn(("Broken input", "ready"), self.created())
        create = [c for c in self.calls() if c[:2] == ["issue", "create"]][0]
        self.assertEqual(r["confirmed"][0][2], ".lite/pass/test_x.py")
        self.assertIn(("Add lessons from the latest batch to PLAN.md", "inbox"), self.created())
        self.assertIn(("Budget on input size", "inbox"), self.created())
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
        self.assertIn("Path: .lite/pass/test_x.py", body)
        self.assertIn("fails", body)
        self.assertIn(common.MARKER, body)

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

    def test_at_most_eight_sessions_and_four_surfaces(self):
        self.repo(plan(surfaces=["s%d" % i for i in range(6)]))
        self.steps(NONE, count=6)
        r, _ = self.run_pass()
        self.assertEqual(r["sessions"], 7)  # drift, rubric, four surfaces, lessons
        self.assertEqual(len(self.claude_calls()), 7)
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
        evil = {"files": {".lite/pass/test_x.py": "# heading\nx = '''```'''\n```\n"},
                "reply": "FINDINGS:\nBroken input | fine\n## Injected | .lite/pass/test_x.py"}
        evil["reply"] = "FINDINGS:\nBroken input | line one ## not a heading | .lite/pass/test_x.py"
        self.steps(evil, CONFIRM)
        seen = []
        real = common.gh
        pass_.gh = lambda a, **k: (seen.append((a, k.get("input"))), real(a, **k))[1]
        self.addCleanup(setattr, pass_, "gh", real)
        self.run_pass()
        body = [i for a, i in seen if a[:2] == ["issue", "create"] and "Broken input" in a][0]
        self.assertIn("\n````\n# heading", body)
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

    def test_only_an_assertion_failure_counts(self):
        tree = os.path.join(self.tmp, "tree")
        os.makedirs(os.path.join(tree, ".lite", "pass"))
        for name in ("a.py", "b.py"):
            with open(os.path.join(tree, ".lite", "pass", name), "w") as f:
                f.write("x\n")
        os.symlink("/etc/hosts", os.path.join(tree, ".lite", "pass", "link.py"))
        os.symlink(os.path.join(tree, ".lite", "pass", "a.py"), os.path.join(tree, ".lite", "pass", "alias.py"))
        reasons = iter(["failed: AssertionError: 1 != 2", "failed: SyntaxError: invalid syntax",
                        "failed: ImportError: no module", "the Test command timed out", None])
        orig = pass_.merge.run_tests
        pass_.merge.run_tests = lambda *a, **k: next(reasons)
        self.addCleanup(setattr, pass_.merge, "run_tests", orig)
        ok = lambda p: pass_.failing(".", "sha", "t", tree, p)
        self.assertTrue(ok(".lite/pass/a.py"))
        self.assertFalse(ok(".lite/pass/b.py"))
        self.assertFalse(ok(".lite/pass/b.py"))
        self.assertFalse(ok(".lite/pass/b.py"))
        self.assertFalse(ok(".lite/pass/b.py"))  # passes
        for bad in (".lite/pass/link.py", ".lite/pass/alias.py", "../x.py", "/etc/hosts", "src/a.py"):
            self.assertFalse(ok(bad), bad)  # refused before any test run

    def test_errors_are_reported_not_raised_and_earlier_issues_are_kept(self):
        self.repo(plan(), "Smoke command: false\n")
        self.settings["Loop branch"] = "no-such"
        r, md = self.run_pass()
        self.assertIn("pass stopped", md)

    def test_a_failed_create_keeps_the_earlier_issues(self):
        self.repo(plan(surfaces=()))
        self.claude({"pass": [{"reply": "FINDINGS:\nOne | a |\nTwo | b |"}]})
        with open(self.scenario_path) as f:
            rules = json.load(f)["rules"]
        rules[-1] = {"match": "issue create", "responses": [
            {"stdout": "https://github.com/o/r/issues/41\n"}, {"code": 1, "stderr": "boom"}]}
        self.scenario(rules)
        r, md = self.run_pass()
        self.assertEqual(len(r["issues"]), 1)
        self.assertIn("One", r["issues"][0])
        self.assertIn("pass stopped", md)

    def test_titles_are_deduped_against_all_issues(self):
        self.repo(plan(surfaces=()))
        self.claude({"pass": [{"reply": "FINDINGS:\nOne | a |"}]})
        self.run_pass()
        lists = [c for c in self.calls() if c[:2] == ["issue", "list"]]
        self.assertTrue(lists and all("all" in c for c in lists))
