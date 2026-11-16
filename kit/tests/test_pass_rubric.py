from pathlib import Path

from kit.tests import test_pass as tp
from kit.tests.fake_claude import FakeClaudeGh
import flow

GOOD = "Swallowed error | kit/scripts/a.py:12 the exception is dropped |"
NOLINE = "Vague smell | the code feels long |"
RUBRIC = {"reply": "FINDINGS:\n%s\n%s" % (GOOD, NOLINE)}
ONE = {"reply": "FINDINGS:\n" + GOOD}
ACCEPT = {"reply": "RUBRIC CONFIRMED:\nSwallowed error\n\nRUBRIC REJECTED:\nnone\n\nCONFIRMED:\nnone\n\nHELD:\nnone\n\nREJECTED:\nnone"}
REJECT = {"reply": "RUBRIC CONFIRMED:\nnone\n\nRUBRIC REJECTED:\nSwallowed error | the code handles it\n\nCONFIRMED:\nnone\n\nHELD:\nnone\n\nREJECTED:\nnone"}


class RubricValidationTest(FakeClaudeGh):
    repo = tp.PassTest.repo
    gh = tp.PassTest.gh
    run_pass = tp.PassTest.run_pass
    created = tp.PassTest.created
    bodies = tp.PassTest.bodies

    def run_with(self, rubric, confirm, surfaces=(), redteam=None, count=0):
        self.repo(tp.plan(surfaces=surfaces))
        self.claude({"pass": [tp.NONE, rubric] + [redteam or tp.NONE] * count + [confirm, tp.LESSONS]})
        self.seen = self.bodies()
        return self.run_pass()

    def filed(self):
        return "\n".join(i or "" for _, i in self.seen)

    def test_an_accepted_rubric_finding_is_filed(self):
        r, md = self.run_with(ONE, ACCEPT)
        self.assertEqual([f[0] for f in r["rubric"]], ["Swallowed error"])
        self.assertIn("Swallowed error", self.filed())
        self.assertNotIn("not validated", self.filed())

    def test_a_rejected_rubric_finding_is_reported_with_its_reason_and_not_filed(self):
        r, md = self.run_with(ONE, REJECT)
        self.assertEqual(r["rubric"], [])
        self.assertNotIn("Swallowed error", self.filed())
        part = md.split("### Rubric: rejected")[1]
        self.assertIn("Swallowed error", part)
        self.assertIn("the code handles it", part)

    def test_a_rubric_finding_without_file_and_line_is_rejected_even_if_confirmed(self):
        said = {"reply": ACCEPT["reply"].replace("Swallowed error", "Swallowed error\nVague smell", 1)}
        r, md = self.run_with(RUBRIC, said)
        self.assertEqual([f[0] for f in r["rubric"]], ["Swallowed error"])
        self.assertNotIn("Vague smell", self.filed())
        self.assertIn("Vague smell", md.split("### Rubric: rejected")[1])

    def test_the_confirm_session_sees_the_rubric_findings(self):
        self.run_with(ONE, ACCEPT)
        prompt = self.claude_calls()[2]["prompt"]
        self.assertIn("Swallowed error", prompt)
        self.assertIn("kit/scripts/a.py:12", prompt)

    def test_the_confirm_session_runs_with_rubric_findings_and_no_red_team_candidates(self):
        r, _ = self.run_with(ONE, ACCEPT)
        self.assertEqual(r["sessions"], 5)  # drift, rubric, confirm, lessons, simplify

    def test_an_unreadable_reply_files_rubric_findings_as_not_validated(self):
        self.run_with(ONE, {"reply": "I could not tell."})
        self.assertIn("Swallowed error", self.filed())
        self.assertIn("not validated", self.filed())

    def test_an_unreadable_reply_still_queues_no_red_team_candidate(self):
        r, _ = self.run_with(ONE, {"reply": "I could not tell."}, surfaces=("the CLI",), redteam=tp.FIND, count=1)
        self.assertEqual(r["confirmed"], [])
        self.assertNotIn("Broken input", [t for t, _ in self.created()])
        self.assertIn("Swallowed error", self.filed())

    def test_the_session_limit_holds_with_rubric_findings(self):
        r, _ = self.run_with(ONE, ACCEPT, surfaces=["s%d" % i for i in range(6)], count=4)
        self.assertEqual(r["sessions"], 9)
        self.assertEqual(len(self.claude_calls()), 9)

    def test_the_brief_sets_the_acceptance_rule_for_rubric_findings(self):
        text = Path(flow.BRIEFS, "pass-confirm.md").read_text(encoding="utf-8")
        self.assertIn("RUBRIC CONFIRMED:", text)
        self.assertIn("RUBRIC REJECTED:", text)
        self.assertRegex(text, r"(?is)file:line.{0,200}reject|reject.{0,200}file:line")
        self.assertIn("loop branch", text)
