"""Unit tests for loop/gates/claim.py and loop/research.py: the checks of move 4.

Every test starts from one ready piece that passes the claim, and spoils one
thing. Each check must refuse alone: exactly one fault, with a `next:` line. The
judge and the blocked-by links are stand-ins. The rest is real: a Git project
with a piece branch, the area map, the piece records and the spec parser.
`tests/claim-gate.sh` runs the real gate end to end.
"""

import json
import subprocess
import sys
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_ready  # type: ignore[import-not-found, unused-ignore]  # noqa: E402
from loop import evidence, fingerprint, github, moves, research, spec, states  # noqa: E402
from loop.cli import ExitCode  # noqa: E402
from loop.gates import CheckContext, CheckResult, claim, ready  # noqa: E402

TODAY = "2026-10-06"
git = test_ready.git
COMMAND = test_ready.COMMAND


def finding(source: str, checked: str, rests: str, text: str = "A fact the piece uses.") -> str:
    return f"{text} Source: {source}. Checked {checked}. Rests on: {rests}."


class Stand:
    """The stand-ins one test may change."""

    def __init__(self) -> None:
        self.judge = test_ready.judge_result()
        self.must_stay = test_ready.judge_result("passed", exit_code=0)
        self.blockers: dict[int, str] = {}
        self.versions: dict[str, str] = {"left-pad": "1.3.0"}
        self.judge_runs: list[tuple[str, str]] = []

    def run_judge(self, command: str, root: Path, ref: str, **_more: Any) -> dict[str, Any]:
        self.judge_runs.append((command, ref))
        found = self.judge if command == COMMAND else self.must_stay
        return {**found, "command": command, "ref": ref}

    def read_blockers(self, ctx: CheckContext) -> dict[int, str]:
        return dict(self.blockers)

    def version_of(self, root: Path, ref: str, name: str) -> str | None:
        return self.versions.get(name)

    def deps(self) -> claim.Deps:
        return claim.Deps(run_judge=self.run_judge, blockers=self.read_blockers,
                          today=lambda: TODAY, version_of=self.version_of)


class ClaimCase(test_ready.Case):  # type: ignore[misc, unused-ignore]
    """A ready piece. `make_ready` runs the real ready gate and records what it wrote."""

    record: list[dict[str, Any]]

    def setUp(self) -> None:
        super().setUp()
        self.stand = test_ready.Stand()
        self.claim_stand = Stand()
        self.options: dict[str, str] = {}
        (self.root / "src" / "api.py").write_text("API = 1\n", encoding="utf-8")
        (self.root / "package.json").write_text(
            json.dumps({"dependencies": {"left-pad": "^1.3.0"}}), encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "More project files")
        self.judge_branch_again({test_ready.TEST_FILE: test_ready.TEST_TEXT})
        self.items = [
            self.file_item("src/app.py"),
            finding("left-pad", "2026-10-01", "version 1.3.0"),
            finding("https://example.invalid/docs", "2026-10-02", "version 2026-09"),
        ]
        self.relies = "the app constant in src/api.py"
        self.piece = 1

    # --- making the piece ready ---------------------------------------------------------

    def file_item(self, path: str, checked: str = "2026-10-01") -> str:
        print_ = research.file_fingerprint(self.root, "main", path)
        assert print_ is not None
        return finding(path, checked, f"fingerprint {print_[:12]}")

    def make_ready(self) -> None:
        old = ("- The folder rename uses the same rule. Source: src/folders/rename.ts.\n"
               "  Checked 3 October 2026. Rests on: fingerprint 4c1e9a2.")
        self.respec(old, "\n".join(f"- {item}" for item in self.items))
        self.respec("Relies on: PATCH /api/reports/:id in src/api/reports.ts",
                    f"Relies on: {self.relies}")
        result = ready.run(super().context(), self.stand.deps())
        assert result.ok, (result.failures, result.next_command)
        self.body = str(result.data["body"])
        self.record += [
            {"kind": "body", "text": self.body},
            {"kind": "fingerprint", "fingerprint": dict(result.data["fingerprint"])},
            *[dict(entry) for entry in result.data["entries"]],
            {"kind": "move", "move": 2, "from": "shaping", "to": "ready"},
        ]

    def commit_main(self, name: str, text: str) -> None:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", f"Change {name}")

    def other_piece(self, number: int, *, touches: str, state: str = "building",
                    issue: int | None = None) -> None:
        body = ("<!-- spec:start version=1 -->\n## Goal\nAnother piece.\n\n"
                f"## Links\nTouches: {touches}\n<!-- spec:end -->\n")
        entries: list[dict[str, Any]] = [
            {"kind": "capture", "title": "Another", "type": "feature", "issue": issue},
            {"kind": "body", "text": body},
            {"kind": "move", "move": 2, "from": "shaping", "to": "ready"},
        ]
        if state == "building":
            entries.append({"kind": "move", "move": 4, "from": "ready", "to": "building"})
        evidence.append(self.paths, number, entries)

    def policy(self, **values: Any) -> None:
        self.paths.policy_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.policy_file.write_text(json.dumps(values), encoding="utf-8")

    # --- running the claim ----------------------------------------------------------------

    def context(self) -> CheckContext:
        try:
            parsed: dict[str, Any] | None = spec.parse(self.body).to_dict()
        except spec.SpecError:
            parsed = None
        return CheckContext(
            number=1, move=states.by_number(4), origin="ready", target="building", reason=None,
            title="Rename a report", body=self.body, spec=parsed, record=self.record,
            paths=self.paths, options=dict(self.options),
        )

    def run_gate(self) -> CheckResult:
        return claim.run(self.context(), self.claim_stand.deps())

    def passing(self) -> CheckResult:
        result = self.run_gate()
        self.assertTrue(result.ok, f"refused: {result.failures} next: {result.next_command}")
        return result

    def refuses_alone(self, needle: str, *, send_back: bool) -> CheckResult:
        result = self.run_gate()
        self.assertFalse(result.ok, "the claim passed, and it should have refused")
        self.assertEqual(len(result.failures), 1, result.failures)
        self.assertIn(needle, result.failures[0])
        self.assertTrue(result.next_command, "a refusal names the next command")
        if send_back:
            self.assertIn(needle, str(result.data.get("send_back")))
        else:
            self.assertNotIn("send_back", result.data)
        return result


class ThePassingClaim(ClaimCase):
    def test_a_ready_piece_passes(self) -> None:
        self.make_ready()
        result = self.passing()
        self.assertNotIn("send_back", result.data)

    def test_it_keeps_the_fingerprint_in_the_record(self) -> None:
        self.make_ready()
        data = self.passing().data
        old = next(e for e in reversed(self.record) if e["kind"] == "fingerprint")
        self.assertEqual(data["fingerprint"], old["fingerprint"])
        self.assertEqual(data["fingerprint"],
                         fingerprint.take(self.body, data["fingerprint"]["judge_commit"]))

    def test_it_writes_a_claim_entry(self) -> None:
        self.make_ready()
        entry = next(e for e in self.passing().data["entries"] if e["kind"] == "claim-check")
        self.assertEqual(entry["findings"], 3)
        self.assertEqual(entry["main"], git(self.root, "rev-parse", "main"))

    def test_the_judge_and_the_must_stay_check_run_on_main(self) -> None:
        self.make_ready()
        self.passing()
        self.assertEqual([c for c, _ in self.claim_stand.judge_runs],
                         [COMMAND, "pytest tests/test_old.py"])
        self.assertEqual(self.claim_stand.judge_runs[0][1], self.first)
        self.assertEqual(git(self.root, "status", "--porcelain"), "")

    def test_the_gate_made_lines_do_not_count_as_an_edit(self) -> None:
        self.make_ready()
        self.body = self.body.replace("(written by the gate)", "(written by the gate, again)")
        self.passing()

    def test_the_judge_files_on_a_moved_main(self) -> None:
        self.make_ready()
        self.commit_main("docs/notes.md", "A change elsewhere.\n")
        self.passing()
        ref = self.claim_stand.judge_runs[0][1]
        self.assertNotEqual(ref, self.first)
        self.assertEqual(git(self.root, "rev-parse", f"{ref}^"),
                         git(self.root, "rev-parse", "main"))
        self.assertIn(test_ready.TEST_FILE, git(self.root, "ls-tree", "-r", "--name-only", ref))
        self.assertIn("docs/notes.md", git(self.root, "ls-tree", "-r", "--name-only", ref))


class Fingerprint(ClaimCase):
    def test_a_spec_edited_by_hand(self) -> None:
        self.make_ready()
        self.respec("Names have at most 80 characters.", "Names have at most 90 characters.")
        self.refuses_alone("fingerprint", send_back=True)

    def test_a_judge_file_changed_after_ready(self) -> None:
        self.make_ready()
        git(self.root, "checkout", "-q", ready.branch_name(1))
        (self.root / test_ready.TEST_FILE).write_text(
            test_ready.TEST_TEXT + "\ndef test_more():\n    assert True\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Edit the judge")
        git(self.root, "checkout", "-q", "main")
        self.refuses_alone("judge file", send_back=True)

    def test_a_judge_commit_that_is_gone(self) -> None:
        self.make_ready()
        git(self.root, "branch", "-q", "-D", ready.branch_name(1))
        self.refuses_alone("piece branch", send_back=True)

    def test_a_record_with_no_fingerprint(self) -> None:
        self.make_ready()
        self.record = [e for e in self.record if e["kind"] != "fingerprint"]
        self.refuses_alone("no fingerprint", send_back=True)

    def test_a_spec_the_parser_refuses(self) -> None:
        self.make_ready()
        self.body = self.body.replace("<!-- spec:end -->", "")
        result = self.run_gate()
        self.assertFalse(result.ok)
        self.assertIn("spec", " ".join(result.failures))
        self.assertIn("send_back", result.data)


class Lint(ClaimCase):
    def test_a_rule_broken_on_main(self) -> None:
        self.make_ready()
        self.commit_main("docs/area-map", "docs/ menus\n")
        self.refuses_alone("reports", send_back=True)


class Judge(ClaimCase):
    def test_the_judge_now_passes_on_main(self) -> None:
        self.make_ready()
        self.claim_stand.judge = test_ready.judge_result("passed", exit_code=0)
        self.refuses_alone("passes on main", send_back=True)

    def test_the_judge_errors_on_main(self) -> None:
        self.make_ready()
        self.claim_stand.judge = test_ready.judge_result("errored", failing_ids=[], failures=[])
        self.refuses_alone("errored", send_back=True)

    def test_a_must_stay_the_same_check_now_fails(self) -> None:
        self.make_ready()
        self.claim_stand.must_stay = test_ready.judge_result("failed")
        result = self.refuses_alone("pytest tests/test_old.py", send_back=False)
        self.assertIn("main", result.next_command)

    def test_the_judge_is_not_run_when_a_cheap_check_fails(self) -> None:
        self.make_ready()
        self.claim_stand.blockers = {7: "building"}
        self.run_gate()
        self.assertEqual(self.claim_stand.judge_runs, [])


class RelianceOnCode(ClaimCase):
    def test_a_relied_on_file_changed_since_ready(self) -> None:
        self.make_ready()
        self.commit_main("src/api.py", "API = 2\n")
        self.refuses_alone("src/api.py", send_back=True)

    def test_a_relied_on_file_removed_since_ready(self) -> None:
        self.make_ready()
        git(self.root, "rm", "-q", "src/api.py")
        git(self.root, "commit", "-q", "-m", "Remove the API")
        self.refuses_alone("src/api.py", send_back=True)

    def test_ready_recorded_the_relied_on_file_and_its_fingerprint(self) -> None:
        self.make_ready()
        entry = next(e for e in self.record if e["kind"] == "relied-on")
        self.assertEqual(list(entry["files"]), ["src/api.py"])
        self.assertEqual(entry["files"]["src/api.py"],
                         research.file_fingerprint(self.root, "main", "src/api.py"))

    def test_a_record_that_ready_wrote_without_the_entry(self) -> None:
        self.make_ready()
        self.record = [e for e in self.record if e["kind"] != "relied-on"]
        self.refuses_alone("relied-on", send_back=True)

    def test_a_service_by_name_is_not_a_file(self) -> None:
        self.relies = "the Stripe API, and PATCH /api/reports/:id"
        self.make_ready()
        entry = next(e for e in self.record if e["kind"] == "relied-on")
        self.assertEqual(entry["files"], {})
        self.passing()


class ResearchFindings(ClaimCase):
    def test_a_file_finding_whose_file_changed(self) -> None:
        self.make_ready()
        self.commit_main("src/app.py", "X = 2\n")
        self.refuses_alone("src/app.py", send_back=True)

    def test_a_file_finding_whose_file_is_gone(self) -> None:
        self.make_ready()
        git(self.root, "rm", "-q", "src/app.py")
        git(self.root, "commit", "-q", "-m", "Remove app")
        self.refuses_alone("src/app.py", send_back=True)

    def test_an_outside_finding_past_the_age_limit(self) -> None:
        self.items[1] = finding("left-pad", "2026-08-01", "version 1.3.0")
        self.make_ready()
        self.refuses_alone("left-pad", send_back=True)

    def test_a_page_finding_past_the_age_limit(self) -> None:
        self.items[2] = finding("https://example.invalid/docs", "2026-08-01", "version 2026-09")
        self.make_ready()
        self.refuses_alone("example.invalid", send_back=True)

    def test_the_age_limit_comes_from_the_policy(self) -> None:
        self.items[1] = finding("left-pad", "2026-08-01", "version 1.3.0")
        self.make_ready()
        self.policy(research_age_days=90)
        self.passing()

    def test_an_outside_finding_on_a_changed_version(self) -> None:
        self.make_ready()
        self.claim_stand.versions["left-pad"] = "1.3.1"
        result = self.refuses_alone("1.3.1", send_back=True)
        self.assertIn("left-pad", result.failures[0])

    def test_a_package_the_project_does_not_name_cannot_be_confirmed(self) -> None:
        self.make_ready()
        del self.claim_stand.versions["left-pad"]
        self.refuses_alone("cannot confirm", send_back=True)

    def test_a_finding_with_no_source_date_or_basis(self) -> None:
        self.items[1] = "A fact with nothing behind it."
        self.make_ready_without_the_gate()
        self.refuses_alone("source", send_back=True)

    def make_ready_without_the_gate(self) -> None:
        # The ready gate refuses such a finding, so the record is built by hand.
        self.respec(
            "- The folder rename uses the same rule. Source: src/folders/rename.ts.\n"
            "  Checked 3 October 2026. Rests on: fingerprint 4c1e9a2.",
            "\n".join(f"- {item}" for item in self.items))
        taken = fingerprint.take(self.body, self.first)
        self.record += [
            {"kind": "body", "text": self.body}, {"kind": "fingerprint", "fingerprint": taken},
            {"kind": "relied-on", "files": {}, "main": git(self.root, "rev-parse", "main")},
        ]

    def test_the_research_check_needs_no_network(self) -> None:
        self.make_ready()
        self.passing()


class TheOtherPieces(ClaimCase):
    def test_a_blocker_that_is_not_done(self) -> None:
        self.make_ready()
        self.claim_stand.blockers = {7: "building"}
        result = self.refuses_alone("issue 7", send_back=False)
        self.assertIn("building", result.failures[0])

    def test_a_blocker_that_is_done(self) -> None:
        self.make_ready()
        self.claim_stand.blockers = {7: "done"}
        self.passing()

    def test_a_blocker_built_earlier_in_this_run(self) -> None:
        self.make_ready()
        self.claim_stand.blockers = {7: "building", 8: "review"}
        self.options = {"built_earlier": "7, 8"}
        self.passing()

    def test_a_blocker_not_in_the_built_earlier_list(self) -> None:
        self.make_ready()
        self.claim_stand.blockers = {7: "building", 9: "ready"}
        self.options = {"built_earlier": "7"}
        self.refuses_alone("issue 9", send_back=False)

    def test_a_built_earlier_list_that_is_not_numbers(self) -> None:
        self.make_ready()
        self.options = {"built_earlier": "seven"}
        self.refuses_alone("built_earlier", send_back=False)

    def test_already_building(self) -> None:
        self.make_ready()
        self.record.append({"kind": "move", "move": 4, "from": "ready", "to": "building"})
        self.refuses_alone("already building", send_back=False)

    def test_the_same_issue_is_building_as_another_piece(self) -> None:
        self.record[0]["issue"] = 40
        self.make_ready()
        self.other_piece(2, touches="billing", issue=40)
        self.refuses_alone("already building", send_back=False)

    def test_an_area_in_use_by_a_running_piece(self) -> None:
        self.make_ready()
        self.other_piece(2, touches="menus, reports")
        result = self.refuses_alone("reports", send_back=False)
        self.assertIn("piece 2", result.failures[0])

    def test_a_running_piece_in_another_area(self) -> None:
        self.make_ready()
        self.other_piece(2, touches="billing")
        self.passing()

    def test_a_piece_that_is_not_building_holds_no_area(self) -> None:
        self.make_ready()
        self.other_piece(2, touches="reports", state="ready")
        self.passing()

    def test_no_free_slot(self) -> None:
        self.make_ready()
        for number in (2, 3, 4):
            self.other_piece(number, touches=f"area-{number}")
        result = self.refuses_alone("slot", send_back=False)
        self.assertIn("3", result.failures[0])

    def test_a_free_slot_is_left(self) -> None:
        self.make_ready()
        for number in (2, 3):
            self.other_piece(number, touches=f"area-{number}")
        self.passing()

    def test_the_slot_count_comes_from_the_policy(self) -> None:
        self.make_ready()
        self.policy(builder_cap=1)
        self.other_piece(2, touches="area-2")
        self.refuses_alone("slot", send_back=False)

    def test_an_unreadable_policy_refuses(self) -> None:
        self.make_ready()
        self.paths.policy_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.policy_file.write_text("{not json", encoding="utf-8")
        result = self.run_gate()
        self.assertFalse(result.ok)
        self.assertIn("policy", " ".join(result.failures))


class EveryFaultIsReported(ClaimCase):
    def test_two_faults_are_both_named(self) -> None:
        self.make_ready()
        self.claim_stand.blockers = {7: "building"}
        self.other_piece(2, touches="reports")
        result = self.run_gate()
        self.assertEqual(len(result.failures), 2)


class Blockers(ClaimCase):
    """The default reader of the blocked-by links keeps the no-App rule."""

    def test_an_issue_with_no_app_is_refused(self) -> None:
        self.record[0]["issue"] = 40
        self.make_ready()
        with self.assertRaises(github.GitHubError) as caught:
            claim.github_blockers(self.context(), hub=NoApp())
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertTrue(caught.exception.next_command)

    def test_the_check_turns_that_into_a_refusal(self) -> None:
        self.record[0]["issue"] = 40
        self.make_ready()

        def broken(ctx: CheckContext) -> dict[int, str]:
            return claim.github_blockers(ctx, hub=NoApp())

        deps = claim.Deps(run_judge=self.claim_stand.run_judge, blockers=broken,
                          today=lambda: TODAY, version_of=self.claim_stand.version_of)
        result = claim.run(self.context(), deps)
        self.assertFalse(result.ok)
        self.assertIn("blocked-by", result.failures[0])
        self.assertTrue(result.next_command)
        self.assertEqual(self.claim_stand.judge_runs, [])

    def test_a_piece_with_no_issue_has_no_link_to_read(self) -> None:
        self.make_ready()
        self.assertEqual(claim.github_blockers(self.context(), hub=NoApp()), {})

    def test_the_states_of_the_blockers_are_read(self) -> None:
        self.record[0]["issue"] = 40
        self.make_ready()
        hub = Linked({40: [7, 8, 9]}, {7: ["state:done"], 8: ["state:building", "type:bug"],
                                       9: ["bug"]})
        self.assertEqual(claim.github_blockers(self.context(), hub=hub),
                         {7: "done", 8: "building", 9: ""})


class NoApp:
    available = False


class Linked:
    available = True

    def __init__(self, links: Mapping[int, list[int]], labels: Mapping[int, list[str]]) -> None:
        self.links = links
        self.labels = labels

    def api_json(self, path: str) -> Any:
        number = int(path.split("/issues/")[1].split("/")[0])
        return [{"number": n} for n in self.links.get(number, [])]

    def read_issue(self, number: int) -> dict[str, Any]:
        return {"number": number, "labels": self.labels.get(number, []), "body": ""}


class TheFindingFormat(unittest.TestCase):
    def test_a_file_finding(self) -> None:
        found = spec.parse_finding(finding("src/app.py", "2026-10-01", "fingerprint 4c1e9a2b"))
        self.assertEqual((found["kind"], found["source"], found["fingerprint"], found["date"]),
                         ("file", "src/app.py", "4c1e9a2b", "2026-10-01"))

    def test_an_outside_finding_with_a_written_date(self) -> None:
        found = spec.parse_finding(
            "A fact. Source: left-pad. Checked 3 October 2026. Rests on: version 1.3.0.")
        self.assertEqual((found["kind"], found["source"], found["version"], found["date"]),
                         ("outside", "left-pad", "1.3.0", "2026-10-03"))

    def test_the_fixture_finding_reads(self) -> None:
        body = (test_ready.FIXTURES / "ready.md").read_text(encoding="utf-8")
        found = [spec.parse_finding(item) for item in spec.parse(body).research]
        self.assertEqual([f["kind"] for f in found], ["file"])
        self.assertEqual(found[0]["date"], "2026-10-03")

    def test_a_date_not_on_the_calendar_is_not_a_date(self) -> None:
        for text in ("Checked 31 February 2026.", "Checked 2026-02-30.", "Checked 31 Apr 2026."):
            found = spec.parse_finding(f"A fact. Source: a.py. {text} Rests on: version 1.")
            self.assertIsNone(found["date"], text)

    def test_the_date_after_checked_wins(self) -> None:
        found = spec.parse_finding(
            "A fact, true since 2020-01-01. Source: a.py. Checked 3 October 2026. "
            "Rests on: version 1.")
        self.assertEqual(found["date"], "2026-10-03")

    def test_what_is_missing_is_none(self) -> None:
        found = spec.parse_finding("A fact with nothing behind it.")
        self.assertEqual((found["kind"], found["source"], found["date"]), (None, None, None))

    def test_a_fingerprint_that_is_not_hex_is_not_a_basis(self) -> None:
        found = spec.parse_finding("A fact. Source: a.py. Checked 2026-10-01. "
                                   "Rests on: fingerprint nonsense.")
        self.assertIsNone(found["kind"])


class TheResearchModule(unittest.TestCase):
    def test_the_fingerprint_of_a_file_is_a_prefix_match(self) -> None:
        problems = research.check(
            [spec.parse_finding(finding("a.py", "2026-10-01", "fingerprint abcdef1"))],
            today="2026-10-06", age_days=30,
            file_fingerprint=lambda path: "abcdef12" + "0" * 56,
            version_of=lambda name: None,
        )
        self.assertEqual(problems, [])

    def test_a_date_in_the_future_is_a_fault(self) -> None:
        problems = research.check(
            [spec.parse_finding(finding("left-pad", "2026-12-01", "version 1.0"))],
            today="2026-10-06", age_days=30, file_fingerprint=lambda path: None,
            version_of=lambda name: "1.0",
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("future", problems[0])

    def test_the_stamp_command_prints_the_fingerprint(self) -> None:
        done = subprocess.run(
            [sys.executable, "-m", "loop.research", "stamp", "--help"],
            capture_output=True, text=True, check=False, cwd=ROOT / "kit" / "scripts",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("stamp", done.stdout)


class GitSteps(ClaimCase):
    """A git step that fails is a refusal, never a pass."""

    def failing(self, word: str) -> Callable[..., tuple[int, str]]:
        real = claim._git

        def stand_in(root: Path, *args: str) -> tuple[int, str]:
            return (128, "") if args[0] == word else real(root, *args)

        return stand_in

    def test_a_failed_log_is_a_refusal_that_keeps_the_piece_ready(self) -> None:
        self.make_ready()
        with mock.patch.object(claim, "_git", self.failing("log")):
            result = self.refuses_alone("git log failed", send_back=False)
        self.assertIn("git", result.next_command)

    def test_a_failed_diff_tree_is_a_refusal(self) -> None:
        self.make_ready()
        with mock.patch.object(claim, "_git", self.failing("diff-tree")):
            self.refuses_alone("git diff-tree failed", send_back=False)

    def test_a_failed_show_is_a_refusal(self) -> None:
        self.make_ready()
        with mock.patch.object(claim, "_git", self.failing("show")):
            self.refuses_alone("git show failed", send_back=False)

    def test_a_failed_rev_list_is_a_refusal(self) -> None:
        self.make_ready()
        with mock.patch.object(claim, "_git", self.failing("rev-list")):
            self.refuses_alone("git rev-list failed", send_back=False)

    def test_two_failed_rev_parse_calls_are_a_refusal(self) -> None:
        self.make_ready()
        real = claim._git

        def stand_in(root: Path, *args: str) -> tuple[int, str]:
            if args[0] == "rev-parse" and "--verify" not in args:
                return 128, ""
            return real(root, *args)

        with mock.patch.object(claim, "_git", stand_in):
            self.refuses_alone("git rev-parse failed", send_back=False)

    def test_a_judge_commit_that_deletes_a_file(self) -> None:
        branch = ready.branch_name(1)
        git(self.root, "branch", "-q", "-D", branch)
        git(self.root, "checkout", "-q", "-b", branch)
        git(self.root, "rm", "-q", "tests/test_old.py")
        target = self.root / test_ready.TEST_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(test_ready.TEST_TEXT, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Judge files and a deletion")
        git(self.root, "checkout", "-q", "main")
        self.make_ready()
        self.commit_main("docs/notes.md", "A change elsewhere.\n")
        self.passing()
        ref = self.claim_stand.judge_runs[0][1]
        files = git(self.root, "ls-tree", "-r", "--name-only", ref)
        self.assertNotIn("tests/test_old.py", files)
        self.assertIn(test_ready.TEST_FILE, files)


class SendingBackThroughTheGate(ClaimCase):
    """A claim that sends the piece back does it by move 3, and writes the need."""

    def gate(self) -> moves.Gate:
        record = self.record
        evidence.append(self.paths, 1, [dict(e) for e in record])
        hub = github.GitHub(self.paths, runner=self.refuse_program, env={})
        return moves.Gate(
            self.paths, hub, today=lambda: TODAY,
            loader=self.loader,
        )

    def loader(self, name: str) -> Callable[[CheckContext], CheckResult]:
        if name == "claim":
            return self.claim_check
        return lambda ctx: CheckResult(ok=True)

    def refuse_program(self, command: list[str], **_k: Any) -> Any:
        raise AssertionError(f"a program ran with no App: {command}")

    def claim_check(self, ctx: CheckContext) -> CheckResult:
        return claim.run(ctx, self.claim_stand.deps())

    def test_a_changed_file_sends_the_piece_back_with_the_need(self) -> None:
        self.make_ready()
        self.commit_main("src/app.py", "X = 2\n")
        gate = self.gate()
        with self.assertRaises(moves.MoveError) as caught:
            gate.move(1, "building")
        self.assertIn("sent back to shaping", caught.exception.message)
        piece = gate.piece(1)
        self.assertEqual(piece.state, "shaping")
        last = piece.history[-1]
        self.assertEqual(last["move"], 3)
        self.assertIn("src/app.py", last["reason"])
        self.assertIn("src/app.py", " ".join(spec.parse(piece.body).open_questions))

    def test_a_dry_run_moves_nothing(self) -> None:
        self.make_ready()
        self.commit_main("src/app.py", "X = 2\n")
        gate = self.gate()
        with self.assertRaises(moves.MoveError):
            gate.move(1, "building", dry_run=True)
        self.assertEqual(gate.piece(1).state, "ready")

    def test_a_refusal_that_is_not_a_spec_fault_leaves_the_piece_ready(self) -> None:
        self.make_ready()
        self.claim_stand.blockers = {7: "building"}
        gate = self.gate()
        with self.assertRaises(moves.MoveError) as caught:
            gate.move(1, "building")
        self.assertNotIn("sent back", caught.exception.message)
        self.assertEqual(gate.piece(1).state, "ready")

    def test_a_passing_claim_makes_the_piece_building(self) -> None:
        self.make_ready()
        gate = self.gate()
        done = gate.move(1, "building")
        self.assertEqual((done["move"], done["to"]), (4, "building"))
        piece = gate.piece(1)
        self.assertEqual(piece.state, "building")
        self.assertFalse(piece.changed_outside)


if __name__ == "__main__":
    unittest.main()
