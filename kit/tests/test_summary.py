"""The final pull request opens with Summary, Evidence and Merge danger, written by one read-only session."""
import os
import unittest
from unittest import mock

from kit.tests import test_loop
from kit.tests.helpers import copy_repo
import common
import flow
import loop
import merge
import pass_
import session

setUpModule, tearDownModule = test_loop.setUpModule, test_loop.tearDownModule

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SECTIONS = ("## Summary", "## Evidence", "## Merge danger")
REPLY = ("## Summary\n\nSUMMARY-TEXT the list now loads.\n\n## Evidence\n\nEVIDENCE-TEXT test_list_loads failed, now passes.\n\n"
         "## Merge danger\n\nTwo-way door. MERGE-DANGER-TEXT")


def brief():
    with open(os.path.join(ROOT, "briefs", "pr-summary.md"), encoding="utf-8") as f:
        return f.read()


class Brief(unittest.TestCase):
    def test_it_asks_for_the_three_sections_in_order(self):
        text = brief()
        places = [text.index(s) for s in SECTIONS]
        self.assertEqual(places, sorted(places))

    def test_it_asks_for_visuals_evidence_by_name_and_the_door_type(self):
        text = brief().lower()
        for word in ("mermaid", "file tree", "call tree", "diff", "before", "by name", "tests pass",
                     "two-way", "one-way", "blast radius", "migration", "published interface"):
            self.assertIn(word, text)
        self.assertIn("unsure", text)

    def test_it_follows_the_writing_rules_and_claims_only_what_is_supported(self):
        text = flow.brief("pr-summary").lower()
        self.assertIn("writing rules", text)
        self.assertIn("build notes", text)
        self.assertIn("test results", text)

    def test_it_has_no_em_dash(self):
        self.assertNotIn("—", brief())


class Drain(test_loop.Base):
    commit, land = test_loop.GitTest.commit, test_loop.GitTest.land

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(test_loop.TEMPLATE.name, self._tmp.name)
        mock.patch.object(merge, "run_tests", return_value=None).start()
        mock.patch.object(pass_, "run_pass", return_value=({}, "## End-of-loop pass\n\nPASS-REPORT\n")).start()
        self.replies = [(REPLY, "s1")]
        self.asked = mock.patch.object(session, "run", side_effect=self.answer).start()

    def answer(self, *args, **kw):
        r = self.replies[min(self.asked.call_count - 1, len(self.replies) - 1)]
        if isinstance(r, Exception):
            raise r
        return r

    def drain(self, prs=()):
        self.world([], prs=prs)
        self.run_loop()
        found = [i for c, i in self.inputs if c.startswith(("pr create", "pr edit"))]
        self.assertTrue(found)
        return found[-1]

    def summary_calls(self):
        return [c for c in self.asked.call_args_list if "Summary" in str(c) and "Merge danger" in str(c)]

    def test_the_sections_come_first_then_hands_on_decisions_landed_and_the_pass_report(self):
        self.land()
        body = self.drain()
        order = ["SUMMARY-TEXT", "EVIDENCE-TEXT", "MERGE-DANGER-TEXT", "## Hands-on checks",
                 "## Decisions to confirm", "## Landed", "PASS-REPORT"]
        places = [body.index(s) for s in order]
        self.assertEqual(places, sorted(places))
        self.assertLess(body.index("## Summary"), body.index("## Evidence"))
        self.assertLess(body.index("## Evidence"), body.index("## Merge danger"))
        self.assertTrue(body.lstrip().startswith("## Summary") or body.index("## Summary") < body.index("## Hands-on checks"))

    def test_summary_prompt_starts_with_the_preamble_once(self):
        self.land()
        self.drain()
        prompt = self.summary_calls()[0].args[1]
        with open(os.path.join(flow.BRIEFS, "preamble.md")) as f:
            preamble = f.read().strip()
        self.assertTrue(prompt.startswith(preamble + "\n\n"))
        self.assertEqual(prompt.count(preamble), 1)

    def test_one_session_runs_on_the_reviewer_model(self):
        self.land()
        self.drain()
        self.assertEqual(len(self.summary_calls()), 1)
        call = self.summary_calls()[0]
        self.assertIn(common.read_settings(self.work)["Reviewer model"], list(call.args) + list(call.kwargs.values()))

    def test_a_refresh_without_new_merges_reuses_the_saved_summary(self):
        self.land()
        self.drain()
        body = self.drain(prs=[{"number": 9, "url": "https://example/pull/9"}])
        self.assertEqual(len(self.summary_calls()), 1)
        for s in SECTIONS + ("SUMMARY-TEXT", "EVIDENCE-TEXT", "MERGE-DANGER-TEXT"):
            self.assertEqual(body.count(s), 1, s)

    def test_new_merges_run_the_session_again(self):
        self.land()
        self.drain()
        self.commit("loop/main", "z.txt", "z\n", "Issue 3")
        self.drain(prs=[{"number": 9, "url": "https://example/pull/9"}])
        self.assertEqual(len(self.summary_calls()), 2)

    def check_fallback(self, body):
        self.assertIn("summary did not run", body.lower())
        self.assertNotIn("## Evidence", body)
        for s in ("## Hands-on checks", "## Decisions to confirm", "## Landed", "PASS-REPORT"):
            self.assertIn(s, body)

    def test_a_failed_session_falls_back_to_the_old_body_with_one_line(self):
        self.land()
        self.replies = [session.SessionError("claude exploded")]
        body = self.drain()
        self.check_fallback(body)
        self.assertEqual(body.lower().count("summary did not run"), 1)
        self.assertEqual(self.writes("needs-user"), [])

    def test_a_reply_missing_a_section_falls_back(self):
        self.land()
        self.replies = [("## Summary\n\nonly this\n\n## Evidence\n\nand this\n", "s1")]
        self.check_fallback(self.drain())

    def test_a_reply_with_the_sections_out_of_order_or_absent_falls_back(self):
        self.land()
        self.replies = [("I could not read the diff.", "s1")]
        self.check_fallback(self.drain())


if __name__ == "__main__":
    unittest.main()
