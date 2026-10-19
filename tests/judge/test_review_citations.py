"""Keep approved review citations and account for every discarded finding."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import git
from review import parse_contract_findings, parse_standards_findings
from run_fixtures import RunFixture

BODY = """## Intent
Keep saved items.
Out of scope:
- Change the display.
## Contract
- D1: Adding an item retains saved items.
## Research
- R1: The API appends items (source: https://example.test/api, read: 2026-10-15)
## Approach
D99 and R99 are examples, not approved items.
"""
DIFF = "+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"


def verdict(findings, role="contract"):
    data = {"findings": findings}
    if role == "standards":
        data.update(follow_ups=[], changes="none")
    return "<verdict>" + json.dumps(data) + "</verdict>"


class ReviewCitationsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        git(self.root, "init", "--quiet")
        (self.root / "app.py").write_text("new\nunchanged\n")
        (self.root / "saved.py").write_text("saved = []\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "--quiet", "-m", "Judged files")
        self.judged = git(self.root, "rev-parse", "HEAD")

    def parse(self, findings, body=BODY):
        dropped = []
        kept = parse_contract_findings(verdict(findings), body, DIFF,
                                       folder=self.root, judged=self.judged, dropped=dropped)
        return kept, dropped

    def test_D1_keeps_research_from_the_approved_issue(self):
        finding = {"citation": "R1", "hunk": "app.py:1", "finding": "The API replaces items."}
        self.assertEqual(parse_contract_findings(verdict([finding]), BODY, DIFF),
                         ["R1 at app.py:1: The API replaces items."])
        kept, dropped = self.parse([finding])
        self.assertEqual(kept, ["R1 at app.py:1: The API replaces items."])
        self.assertEqual(dropped, [])

    def test_D2_drops_unknown_research_with_a_reason(self):
        finding = {"citation": "R99", "hunk": "app.py:1", "finding": "Unsupported claim."}
        kept, dropped = self.parse([finding])
        self.assertEqual(kept, [])
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["finding"], finding)
        self.assertIn("approved", dropped[0]["reason"])

    def test_D3_keeps_missing_behaviour_in_an_unchanged_file(self):
        kept, dropped = self.parse([{"citation": "D1", "kind": "missing",
                                    "hunk": "saved.py:1", "finding": "Saved items are lost."}])
        self.assertEqual(kept, ["D1 at saved.py:1: Saved items are lost."])
        self.assertEqual(dropped, [])

    def test_D3_missing_needs_an_approved_contract_item_and_description(self):
        for citation, detail in (("D99", "Missing save."), ("R1", "Missing save."),
                                 ("Change the display.", "Missing save."), ("D1", " ")):
            with self.subTest(citation=citation, detail=detail):
                kept, dropped = self.parse([{"citation": citation, "kind": "missing",
                                            "hunk": "saved.py:1", "finding": detail}])
                self.assertEqual(kept, [])
                self.assertEqual(len(dropped), 1)

    def test_D4_uses_the_judged_commit_even_if_the_working_copy_changes(self):
        (self.root / "saved.py").unlink()
        (self.root / "untracked.py").write_text("local only\n")
        (self.root / "later.py").write_text("added after judgement\n")
        git(self.root, "add", "later.py")
        git(self.root, "commit", "--quiet", "-m", "Later reviewer commit")
        kept, dropped = self.parse([{"citation": "D1", "kind": "missing", "hunk": path,
                                    "finding": "Missing save."} for path in
                                   ("saved.py:1", "untracked.py:1", "later.py:1")])
        self.assertEqual(kept, ["D1 at saved.py:1: Missing save."])
        self.assertEqual(len(dropped), 2)
        self.assertTrue(all("judged commit" in item["reason"] for item in dropped))

    def test_D4_drops_nonexistent_files_even_when_the_diff_mentions_them(self):
        (self.root / "app.py").unlink()
        git(self.root, "add", "app.py")
        git(self.root, "commit", "--quiet", "-m", "Remove app")
        self.judged = git(self.root, "rev-parse", "HEAD")
        kept, dropped = self.parse([
            {"citation": "D1", "hunk": "app.py:1", "finding": "Bad change."}])
        self.assertEqual(kept, [])
        self.assertIn("judged commit", dropped[0]["reason"])

    def test_D3_rejects_invalid_unchanged_locations(self):
        for hunk in ("saved.py:0", "saved.py:2", "saved.py:2-1", "saved.py:1-2",
                     "../saved.py:1", "saved.py", "saved.py:1 trailing text"):
            with self.subTest(hunk=hunk):
                kept, dropped = self.parse([{"citation": "D1", "kind": "missing",
                                            "hunk": hunk, "finding": "Missing save."}])
                self.assertEqual(kept, [])
                self.assertEqual(len(dropped), 1)

    def test_D5_changed_code_still_needs_a_changed_hunk(self):
        for kind in (None, "changed"):
            finding = {"citation": "D1", "hunk": "app.py:2", "finding": "Bad change."}
            if kind:
                finding["kind"] = kind
            self.assertEqual(parse_contract_findings(verdict([finding]), BODY, DIFF), [])

    def test_D5_logs_changed_code_without_a_changed_hunk(self):
        kept, dropped = self.parse([
            {"citation": "D1", "hunk": "app.py:2", "finding": "Bad change."}])
        self.assertEqual(kept, [])
        self.assertIn("changed hunk", dropped[0]["reason"])

    def test_approved_changed_code_and_out_of_scope_citations_stay(self):
        kept, dropped = self.parse([
            {"citation": "D1", "hunk": "app.py:1", "finding": "Bad change."},
            {"citation": "Change the display.", "hunk": "app.py:1", "finding": "Scope creep."}])
        self.assertEqual(kept, ["D1 at app.py:1: Bad change.",
                                "Change the display. at app.py:1: Scope creep."])
        self.assertEqual(dropped, [])

    def test_missing_behaviour_accepts_legacy_contract_and_valid_line_ranges(self):
        kept, dropped = self.parse([{"citation": "D1", "kind": "missing",
                                    "hunk": "app.py:1-2", "finding": "Missing save."}],
                                   body=BODY.replace("## Contract", "## Done when"))
        self.assertEqual(kept, ["D1 at app.py:1-2: Missing save."])
        self.assertEqual(dropped, [])

    def test_D6_collapses_the_same_citation_and_claim_only(self):
        first = {"citation": "D1", "hunk": "app.py:1", "finding": "Bad change."}
        padded = {key: " " + value + " " for key, value in first.items()}
        self.assertEqual(self.parse([padded]), (["D1 at app.py:1: Bad change."], []))
        other = {**first, "finding": "Another claim."}
        elsewhere = {**first, "kind": "missing", "hunk": "saved.py:1"}
        kept, dropped = self.parse([first, padded, other, elsewhere])
        self.assertEqual(kept, ["D1 at app.py:1: Bad change.",
                                "D1 at app.py:1: Another claim."])
        self.assertEqual(len(dropped), 2)
        self.assertTrue(all("duplicate" in item["reason"] for item in dropped))
        self.assertEqual(dropped[1]["finding"], elsewhere)

    def test_standards_rules_and_changed_hunks_still_apply(self):
        findings = [{"rule": "Duplicated Code", "kind": "missing", "hunk": "app.py:2",
                     "finding": "Use a helper."},
                    {"rule": "Unknown rule", "hunk": "app.py:1", "finding": "Bad rule."},
                    {"rule": "Duplicated Code", "hunk": "app.py:1", "finding": "Use a helper."}]
        dropped = []
        kept = parse_standards_findings(verdict(findings, "standards"), "", DIFF,
                                        dropped=dropped)
        self.assertEqual(kept, ["Duplicated Code at app.py:1: Use a helper."])
        self.assertEqual(len(dropped), 2)


class ReviewCitationRunTest(RunFixture, unittest.TestCase):
    def test_D2_D7_logs_dropped_findings_and_counts_them_in_the_pull_request(self):
        def session(folder, prompt, logfile, *args):
            if prompt.startswith("# Standards reviewer brief"):
                findings = [{"rule": "Unknown rule", "hunk": "habits.py:1",
                             "finding": "Unapproved standard."}]
                output = verdict(findings, "standards")
            else:
                self.assertIn('Missing behaviour uses `kind: "missing"`', prompt)
                self.assertIn("an existing judged-commit line", prompt)
                (folder / "local.py").write_text("untracked\n")
                findings = [
                    {"citation": "R99", "hunk": "habits.py:1", "finding": "Unknown research."},
                    {"citation": "D1", "kind": "missing", "hunk": "local.py:1",
                     "finding": "Untracked file."},
                    {"citation": "D1", "kind": "missing", "hunk": "README.md:1",
                     "finding": "Missing saved items."}]
                output = verdict([*findings, {**findings[-1], "hunk": "habits.py:1"}])
            logfile.write_text(output)
            return ""

        with patch("review._review_session", side_effect=session):
            n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("Dropped review findings: 4", body)
        self.assertEqual(body.count("Missing saved items."), 1)
        logs = self.p.root / ".loop/logs"
        for role, claims in (("standards", ("Unapproved standard.",)),
                             ("contract", ("Unknown research.", "Untracked file.",
                                           "Missing saved items."))):
            output = (logs / f"piece-{n}-{role}-review.log").read_text()
            records = [json.loads(line.removeprefix("Dropped finding: "))
                       for line in output.splitlines() if line.startswith("Dropped finding: ")]
            self.assertEqual(tuple(item["finding"]["finding"] for item in records), claims)
            self.assertTrue(all(item["reason"] for item in records))


if __name__ == "__main__":
    unittest.main()
