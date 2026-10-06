"""Unit tests for loop/gates/ready.py: the checks of move 2, each refusing alone.

Every test starts from one piece that passes, and spoils one thing. The judge,
the two test-list sessions and the blocked-by links are stand-ins here. The
rest is real: a Git project with a piece branch, the area map, the held-out
store and the spec parser. `tests/ready-gate.sh` runs the real judge and the
session code end to end.
"""

import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import fingerprint, github, heldout, spec, states  # noqa: E402
from loop.gates import CheckContext, CheckResult, ready  # noqa: E402
from loop.paths import Paths  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "specs"
IDS = ["FL-1", "FL-2", "EC-1", "EC-2"]
COMMAND = "pytest tests/acceptance/test_rename.py"
TEST_FILE = "tests/acceptance/test_rename.py"
TEST_TEXT = "".join(
    f"def test_{name.lower().replace('-', '_')}():\n    assert False, \"{name}\"\n\n"
    for name in IDS
)
TODAY = "2026-10-06"
OLD_FAILS = (
    "Fails today: 4 of 4 tests fail on their assertion; main at a1b2c3d;\n"
    "5 October 2026 (written by the gate)\n"
)


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=T", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True,
    )
    return done.stdout.strip()


def judge_result(outcome: str = "failed", **more: Any) -> dict[str, Any]:
    failing = IDS if outcome == "failed" else []
    base: dict[str, Any] = {
        "outcome": outcome, "runner": "pytest", "command": COMMAND, "ref": "x", "commit": "c1",
        "exit_code": 1, "timed_out": False, "seconds": 0.1, "output_tail": "",
        "failures": [{"test": "t", "assertion": True, "detail": "d", "ids": [i], "kind": None}
                     for i in failing],
        "failing_ids": failing, "kind": None, "note": None,
    }
    base.update(more)
    return base


class Stand:
    """The stand-ins one test may change."""

    def __init__(self) -> None:
        self.judge: dict[str, Any] = judge_result()
        self.must_stay: dict[str, Any] = judge_result("passed", exit_code=0)
        self.lists: list[list[str]] = [list(IDS), list(IDS)]
        self.problems: list[str] = []
        self.judge_runs: list[tuple[str, str]] = []
        self.list_runs = 0

    def run_judge(self, command: str, root: Path, ref: str, **_more: Any) -> dict[str, Any]:
        self.judge_runs.append((command, ref))
        found = self.judge if command == COMMAND else self.must_stay
        return {**found, "command": command, "ref": ref}

    def run_lists(self, paths: Paths, number: int, block: str, ids: list[str]) -> dict[str, Any]:
        self.list_runs += 1
        return {"lists": self.lists, "labels": ["a", "b"]}

    def blockers(self, ctx: CheckContext) -> list[str]:
        return list(self.problems)

    def deps(self) -> ready.Deps:
        return ready.Deps(run_judge=self.run_judge, run_lists=self.run_lists,
                          blockers=self.blockers, today=lambda: TODAY)


def base_body() -> str:
    body = (FIXTURES / "ready.md").read_text(encoding="utf-8")
    assert OLD_FAILS in body
    old = "Opening a report still works (tests/reports.test.ts)."
    assert old in body
    return body.replace(OLD_FAILS, "").replace(
        old, "Opening a report still works.\nCheck: pytest tests/test_old.py"
    )


class Case(unittest.TestCase):
    """A project with a piece that passes. A test spoils one thing and reads the result."""

    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.root = self.base / "project"
        (self.root / "docs").mkdir(parents=True)
        git(self.base, "init", "-q", "-b", "main", str(self.root))
        (self.root / "README.md").write_text("# demo\n", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
        (self.root / "docs" / "area-map").write_text(
            "src/ reports\ndocs/ menus\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_old.py").write_text("def test_old():\n    pass\n",
                                                          encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Start")
        self.paths = Paths.for_project(self.root, data_base=self.base / "data",
                                       kit_folder=ROOT / "kit")
        self.stand = Stand()
        self.body = base_body()
        self.record: list[dict[str, Any]] = [
            {"kind": "capture", "title": "Rename a report", "type": "feature", "issue": None}
        ]
        self.cases = {"FL-1": "visible text of one hidden case", "EC-1": "another hidden case"}
        self.store_held_out()
        self.judge_branch()

    # --- the project ---------------------------------------------------------------

    def judge_branch(self, files: dict[str, str] | None = None) -> str:
        git(self.root, "checkout", "-q", "-b", ready.branch_name(1))
        for name, text in (files or {TEST_FILE: TEST_TEXT}).items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Judge files")
        self.first = git(self.root, "rev-parse", "HEAD")
        git(self.root, "checkout", "-q", "main")
        return self.first

    def judge_branch_again(self, files: dict[str, str]) -> None:
        git(self.root, "branch", "-q", "-D", ready.branch_name(1))
        self.judge_branch(files)

    def store_held_out(self) -> None:
        self.print_ = heldout.store(self.paths, 1, self.cases)["fingerprint"]
        self.body = base_body().replace(
            "Proves: FL-1, FL-2, EC-1, EC-2\n",
            f"Proves: FL-1, FL-2, EC-1, EC-2\nHeld-out cases: fingerprint {self.print_}\n",
        )

    def respec(self, old: str, new: str) -> None:
        assert old in self.body, old
        self.body = self.body.replace(old, new, 1)

    def context(self) -> CheckContext:
        try:
            parsed: dict[str, Any] | None = spec.parse(self.body).to_dict()
        except spec.SpecError:
            parsed = None
        return CheckContext(
            number=1, move=states.by_number(2), origin="shaping", target="ready", reason=None,
            title="Rename a report", body=self.body, spec=parsed, record=self.record,
            paths=self.paths,
        )

    def run_gate(self) -> CheckResult:
        return ready.run(self.context(), self.stand.deps())

    def refusal(self, *needles: str) -> CheckResult:
        result = self.run_gate()
        self.assertFalse(result.ok, "the gate passed, and it should have refused")
        said = " ".join(result.failures)
        for needle in needles:
            self.assertIn(needle, said)
        self.assertTrue(result.next_command, "a refusal names the next command")
        return result

    def passing(self) -> CheckResult:
        result = self.run_gate()
        self.assertTrue(
            result.ok, f"the gate refused: {result.failures} next: {result.next_command}"
        )
        return result


class ThePassingPiece(Case):
    def test_the_piece_passes(self) -> None:
        result = self.passing()
        self.assertEqual(result.data["must_look"], [])

    def test_the_judge_ran_on_the_first_commit_and_main_stayed_clean(self) -> None:
        self.passing()
        self.assertEqual(self.stand.judge_runs[0], (COMMAND, self.first))
        self.assertEqual(git(self.root, "status", "--porcelain"), "")

    def test_the_gate_writes_the_fails_today_line_into_the_spec(self) -> None:
        body = self.passing().data["body"]
        judge = spec.parse(body).to_dict()["judge"]
        self.assertTrue(judge["fails_today"])
        self.assertIn("(written by the gate)", judge["fails_today"])
        for name in IDS:
            self.assertIn(name, judge["fails_today"])
        self.assertEqual(spec.parse(body).to_dict()["judge"]["held_out"].split()[-1], self.print_)

    def test_the_fingerprint_is_of_the_new_body_and_the_first_commit(self) -> None:
        data = self.passing().data
        again = fingerprint.take(data["body"], self.first)
        self.assertEqual(data["fingerprint"], again)

    def test_the_written_spec_has_no_need_left(self) -> None:
        from loop import needs

        body = self.passing().data["body"]
        self.assertEqual(needs.needs_from_body(body, issue_type="feature"), [])

    def test_the_record_gets_the_judge_run_and_the_test_lists(self) -> None:
        kinds = [e["kind"] for e in self.passing().data["entries"]]
        self.assertIn("judge-run", kinds)
        self.assertIn("test-lists", kinds)
        lists = next(e for e in self.passing().data["entries"] if e["kind"] == "test-lists")
        self.assertEqual(lists["lists"], [IDS, IDS])

    def test_the_module_loads_through_the_gate_name(self) -> None:
        from loop import moves

        self.assertIs(moves.load_checks("ready").__module__.endswith("ready"), True)


class TheNeedsList(Case):
    def test_a_need_that_is_not_empty_refuses(self) -> None:
        self.respec("## Open questions\nNone.", "## Open questions\n- Should it be undoable?")
        self.refusal("Open question")

    def test_a_lint_fault_refuses(self) -> None:
        self.respec("Names have at most 80 characters.", "Names have at most 80 characters, TBD.")
        self.refusal("TBD")

    def test_a_missing_core_field_refuses(self) -> None:
        self.respec("## Goal\nA user can rename a saved report from its menu.\n", "")
        self.refusal("Goal")

    def test_a_spec_the_parser_refuses_is_refused(self) -> None:
        self.body = self.body.replace("<!-- spec:end -->", "")
        self.refusal("spec")

    def test_the_judge_is_not_asked_when_the_lint_fails(self) -> None:
        self.respec("Names have at most 80 characters.", "Names have at most 80 characters, TBD.")
        self.refusal()
        self.assertEqual(self.stand.judge_runs, [])
        self.assertEqual(self.stand.list_runs, 0)

    def test_an_id_without_a_test_refuses(self) -> None:
        self.judge_branch_again({TEST_FILE: TEST_TEXT.replace("EC-2", "EC-9")})
        self.refusal("EC-2")


class TheTestLists(Case):
    def test_lists_that_differ_by_id_refuse_and_name_the_ids(self) -> None:
        self.stand.lists = [list(IDS), ["FL-1", "FL-2", "EC-1"]]
        result = self.refusal("EC-2")
        self.assertIn("differ", " ".join(result.failures))

    def test_lists_in_another_order_are_the_same(self) -> None:
        self.stand.lists = [list(IDS), list(reversed(IDS))]
        self.passing()

    def test_many_differences_say_to_split_the_piece(self) -> None:
        self.stand.lists = [["FL-1", "FL-2"], ["EC-1", "EC-2"]]
        self.refusal("split")

    def test_the_sessions_run_once_the_lint_passes_and_not_before(self) -> None:
        self.passing()
        self.assertEqual(self.stand.list_runs, 1)


class TheJudgeFiles(Case):
    def test_a_missing_piece_branch_refuses(self) -> None:
        git(self.root, "branch", "-q", "-D", ready.branch_name(1))
        result = self.refusal("piece-1")
        self.assertIn("gate.py branch", result.next_command)

    def test_a_branch_cut_from_an_older_main_refuses(self) -> None:
        (self.root / "src" / "later.py").write_text("Z = 3\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Main moves on")
        result = self.refusal("cut from an older main")
        self.assertIn("git rebase main piece-1", result.next_command)
        self.assertEqual(self.stand.judge_runs, [])

    def test_a_branch_cut_from_todays_main_is_fine(self) -> None:
        self.passing()

    def test_a_branch_with_no_commit_refuses(self) -> None:
        git(self.root, "branch", "-q", "-D", ready.branch_name(1))
        git(self.root, "branch", ready.branch_name(1), "main")
        self.refusal("first commit")

    def test_judge_files_that_are_not_the_first_commit_refuse(self) -> None:
        git(self.root, "branch", "-q", "-D", ready.branch_name(1))
        git(self.root, "checkout", "-q", "-b", ready.branch_name(1))
        (self.root / "src" / "other.py").write_text("Y = 2\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Code first")
        (self.root / TEST_FILE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / TEST_FILE).write_text(TEST_TEXT, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Tests second")
        git(self.root, "checkout", "-q", "main")
        self.refusal("src/other.py", "first commit")

    def test_a_judge_file_changed_after_the_first_commit_refuses(self) -> None:
        git(self.root, "checkout", "-q", ready.branch_name(1))
        (self.root / TEST_FILE).write_text(TEST_TEXT + "\n# loosened\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Edit the judge")
        git(self.root, "checkout", "-q", "main")
        self.refusal(TEST_FILE, "after the first commit")

    def test_a_later_commit_that_leaves_the_judge_files_alone_is_fine(self) -> None:
        git(self.root, "checkout", "-q", ready.branch_name(1))
        (self.root / "src" / "later.py").write_text("Z = 3\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Build")
        git(self.root, "checkout", "-q", "main")
        self.passing()

    def test_a_first_commit_with_no_test_file_refuses(self) -> None:
        self.judge_branch_again({"src/only.py": "A = 1\n"})
        self.refusal("src/only.py")


class TheJudgeOnMain(Case):
    def test_a_judge_that_passes_on_main_refuses(self) -> None:
        self.stand.judge = judge_result("passed", exit_code=0)
        self.refusal("passes")

    def test_a_judge_that_errors_instead_of_failing_refuses(self) -> None:
        self.stand.judge = judge_result("errored", kind="a failed import",
                                        note="no report was written")
        result = self.refusal("error", "assertion")
        self.assertIn("import", " ".join(result.failures))

    def test_a_failure_that_names_no_id_refuses(self) -> None:
        self.stand.judge = judge_result("failed_no_id", note="names no spec ID")
        self.refusal("assertion")

    def test_a_timeout_refuses(self) -> None:
        self.stand.judge = judge_result("timeout", timed_out=True)
        self.refusal("time")

    def test_a_failure_from_a_runner_with_no_report_is_not_proven(self) -> None:
        self.stand.judge = judge_result("failed", runner="shell", failing_ids=[], failures=[],
                                        note="only the exit code was read")
        self.refusal("not proven")

    def test_a_failure_that_names_an_id_the_spec_lacks_refuses(self) -> None:
        self.stand.judge = judge_result("failed", failing_ids=["FL-9"])
        self.refusal("FL-9")


class MustStayTheSame(Case):
    def checked(self) -> None:
        self.assertIn("Check: pytest tests/test_old.py", self.body)

    def test_a_check_that_passes_on_main_passes(self) -> None:
        self.checked()
        self.passing()
        self.assertIn(("pytest tests/test_old.py", "main"), self.stand.judge_runs)

    def test_a_check_that_fails_on_main_refuses(self) -> None:
        self.checked()
        self.stand.must_stay = judge_result("failed", exit_code=1)
        result = self.refusal("tests/test_old.py", "main")
        self.assertIn("already", " ".join(result.failures) + result.next_command)

    def test_a_check_that_errors_on_main_refuses(self) -> None:
        self.checked()
        self.stand.must_stay = judge_result("errored")
        self.refusal("tests/test_old.py")

    def test_a_spec_with_no_check_line_refuses(self) -> None:
        self.respec("\nCheck: pytest tests/test_old.py", "")
        result = self.refusal("Must stay the same holds no Check: line")
        self.assertIn("Check: <command>", result.next_command)
        self.assertEqual(self.stand.judge_runs, [])
        self.assertEqual(self.stand.list_runs, 0)


class HeldOut(Case):
    def test_cases_missing_from_the_store_refuse(self) -> None:
        folder = heldout.folder(self.paths, 1)
        for item in folder.iterdir():
            item.unlink()
        result = self.refusal("held-out")
        self.assertIn("heldout", result.next_command)

    def test_a_fingerprint_missing_from_the_spec_refuses(self) -> None:
        self.body = base_body()
        self.refusal("has no Held-out cases: line")

    def test_a_different_fingerprint_refuses(self) -> None:
        self.respec(self.print_, "0" * 64)
        self.refusal("differs")

    def test_a_case_stored_after_the_spec_was_written_refuses(self) -> None:
        heldout.store(self.paths, 1, {"EC-2": "a third hidden case"})
        self.refusal("differs")

    def test_a_case_text_never_reaches_the_result(self) -> None:
        result = self.passing()
        self.assertNotIn("visible text of one hidden case", repr(result))


class SensitiveAreas(Case):
    ITEM = "- the refund button moves money."

    def test_a_sensitive_area_with_no_acceptance_refuses(self) -> None:
        self.respec("## Sensitive areas\nNone.", f"## Sensitive areas\n{self.ITEM}")
        self.refusal("sensitive", "Accepted")

    def test_an_acceptance_with_no_quote_or_no_date_refuses(self) -> None:
        for tail in (' Accepted: "go ahead".', " Accepted: yes, 2026-10-01."):
            with self.subTest(tail=tail):
                self.body = base_body()
                self.store_held_out()
                self.respec("## Sensitive areas\nNone.", f"## Sensitive areas\n{self.ITEM}{tail}")
                self.refusal("Accepted")

    def test_an_accepted_sensitive_area_passes_and_marks_the_piece(self) -> None:
        self.respec("## Sensitive areas\nNone.",
                    f'## Sensitive areas\n{self.ITEM} Accepted: "I accept this risk" 2026-10-01.')
        self.assertEqual(self.passing().data["must_look"], [ready.SENSITIVE])


class Dependencies(Case):
    def test_a_blocked_by_link_to_nothing_refuses(self) -> None:
        self.stand.problems = ["issue 41 does not exist"]
        result = self.refusal("issue 41")
        self.assertIn("dependency", " ".join(result.failures))

    def test_a_cycle_refuses(self) -> None:
        self.stand.problems = ["blocked-by cycle: 1 -> 2 -> 1"]
        self.refusal("cycle")

    def fetch_from(self, table: dict[int, Any]) -> Callable[[int], dict[str, Any] | None]:
        return lambda number: table.get(number)

    def test_dependency_problems_finds_a_missing_issue(self) -> None:
        table = {1: {"labels": ["state:shaping"], "blocked_by": [2]}}
        found = ready.dependency_problems(1, self.fetch_from(table))
        self.assertEqual(len(found), 1)
        self.assertIn("2", found[0])
        self.assertIn("does not exist", found[0])

    def test_dependency_problems_finds_a_cycle(self) -> None:
        table = {
            1: {"labels": ["state:shaping"], "blocked_by": [2]},
            2: {"labels": ["state:ready"], "blocked_by": [3]},
            3: {"labels": ["state:ready"], "blocked_by": [1]},
        }
        found = ready.dependency_problems(1, self.fetch_from(table))
        self.assertTrue(any("cycle" in f and "1 -> 2 -> 3 -> 1" in f for f in found), found)

    def test_dependency_problems_finds_a_link_to_something_that_is_not_a_piece(self) -> None:
        table = {1: {"labels": [], "blocked_by": [2]}, 2: {"labels": ["bug"], "blocked_by": []}}
        found = ready.dependency_problems(1, self.fetch_from(table))
        self.assertIn("not a piece", found[0])

    def test_dependency_problems_finds_a_dropped_blocker(self) -> None:
        table = {1: {"labels": [], "blocked_by": [2]},
                 2: {"labels": ["state:dropped"], "blocked_by": []}}
        self.assertIn("dropped", ready.dependency_problems(1, self.fetch_from(table))[0])

    def test_a_clean_chain_has_no_problem(self) -> None:
        table = {
            1: {"labels": [], "blocked_by": [2, 3]},
            2: {"labels": ["state:ready"], "blocked_by": [3]},
            3: {"labels": ["state:done"], "blocked_by": []},
        }
        self.assertEqual(ready.dependency_problems(1, self.fetch_from(table)), [])


class FakeHub:
    """A stand-in for loop.github.GitHub, for the real blocked-by reader."""

    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.issues: dict[int, dict[str, Any]] = {
            1: {"labels": ["state:shaping"]},
        }
        self.links: dict[int, Any] = {1: []}
        self.reads: list[int] = []

    def read_issue(self, number: int) -> dict[str, Any]:
        self.reads.append(number)
        if number not in self.issues:
            raise github.GitHubError("no such issue", next_command="x", not_found=True)
        return self.issues[number]

    def api_json(self, path: str) -> Any:
        number = int(path.split("/issues/")[1].split("/")[0])
        found = self.links.get(number)
        if found is None:
            raise github.GitHubError("not found", next_command="x", not_found=True)
        return found


class TheRealBlockedByReader(Case):
    def blockers(self, hub: FakeHub, issue: int | None = 1) -> list[str]:
        if issue is not None:
            self.record.append({"kind": "synced", "issue": issue})
        return ready._github_blockers(self.context(), hub=hub)

    def test_no_app_and_an_issue_refuses(self) -> None:
        with self.assertRaises(github.GitHubError) as caught:
            self.blockers(FakeHub(available=False))
        self.assertIn("second half of /setup", caught.exception.next_command)
        self.assertIn("sync", caught.exception.next_command)

    def test_the_gate_turns_that_into_a_refusal(self) -> None:
        self.record.append({"kind": "synced", "issue": 1})
        hub = FakeHub(available=False)
        original = ready._github_blockers
        deps = ready.Deps(
            run_judge=self.stand.run_judge, run_lists=self.stand.run_lists,
            blockers=lambda ctx: original(ctx, hub=hub), today=lambda: TODAY,
        )
        result = ready.run(self.context(), deps)
        self.assertFalse(result.ok)
        self.assertIn("blocked-by links cannot be read", " ".join(result.failures))
        self.assertIn("second half of /setup", result.next_command)

    def test_no_app_and_no_issue_ever_made_passes(self) -> None:
        self.assertEqual(self.blockers(FakeHub(available=False), issue=None), [])

    def test_a_missing_start_issue_refuses(self) -> None:
        hub = FakeHub()
        del hub.issues[1]
        found = self.blockers(hub)
        self.assertEqual(len(found), 1)
        self.assertIn("issue 1 does not exist", found[0])

    def test_a_not_found_dependencies_answer_refuses(self) -> None:
        hub = FakeHub()
        del hub.links[1]
        with self.assertRaises(github.GitHubError):
            self.blockers(hub)

    def test_a_clean_issue_passes(self) -> None:
        self.assertEqual(self.blockers(FakeHub()), [])

    def test_a_blocker_that_does_not_exist_is_found(self) -> None:
        hub = FakeHub()
        hub.links[1] = [{"number": 2}]
        found = self.blockers(hub)
        self.assertIn("issue 2 does not exist", found[0])


class Areas(Case):
    def test_an_area_missing_from_the_map_refuses(self) -> None:
        self.respec("Touches: reports, menus", "Touches: reports, billing")
        result = self.refusal("billing")
        self.assertIn("docs/area-map", result.next_command)

    def test_a_new_area_named_in_the_spec_is_allowed(self) -> None:
        self.respec("Touches: reports, menus", "Touches: reports, report-menu")
        self.passing()

    def test_a_project_with_no_map_refuses_an_area_it_does_not_name_as_new(self) -> None:
        (self.root / "docs" / "area-map").unlink()
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "No map")
        self.refusal("reports")


class LaterPieces(Case):
    def test_a_measurement_judge_names_l7(self) -> None:
        self.respec("Kind: acceptance tests,", "Kind: metric,")
        result = self.refusal("L7")
        self.assertIn("L7", result.next_command)

    def test_a_reference_judge_names_l8(self) -> None:
        self.respec("Kind: acceptance tests,", "Kind: reference comparison,")
        result = self.refusal("L8")
        self.assertIn("L8", result.next_command)

    def test_a_route_open_mark_names_l7(self) -> None:
        self.respec("Proves: FL-1", "Route: open\nProves: FL-1")
        result = self.refusal("route open")
        self.assertIn("L7", result.next_command)

    def test_nothing_runs_before_the_refusal(self) -> None:
        self.respec("Kind: acceptance tests,", "Kind: metric,")
        self.refusal()
        self.assertEqual((self.stand.judge_runs, self.stand.list_runs), ([], 0))


class MustLook(Case):
    def test_each_reason_marks_the_piece_alone(self) -> None:
        marks = {
            ready.IRREVERSIBLE: ("Added:", "Not reversible: old names are overwritten.\nAdded:"),
            ready.NEW_DEPENDENCY: ("Added:", "New dependency: left-pad 1.3.0.\nAdded:"),
            ready.SECURITY: ("Added:", "Security: the menu checks the owner.\nAdded:"),
        }
        for reason, (old, new) in marks.items():
            with self.subTest(reason=reason):
                self.store_held_out()
                self.respec(old, new)
                self.assertEqual(self.passing().data["must_look"], [reason])

    def test_the_persons_own_mark_in_decisions_marks_the_piece(self) -> None:
        self.respec("## Decisions\n", "## Decisions\n- must-look: I want to read this one.\n")
        self.assertEqual(self.passing().data["must_look"], [ready.PERSON])

    def test_the_mark_is_found_in_other_spellings(self) -> None:
        for text in ("Must look: yes", "MUST-LOOK because money"):
            with self.subTest(text=text):
                self.store_held_out()
                self.respec("## Decisions\n", f"## Decisions\n- {text}\n")
                self.assertEqual(self.passing().data["must_look"], [ready.PERSON])

    def test_a_mark_that_says_no_marks_nothing(self) -> None:
        self.respec("Added:", "New dependency: none.\nSecurity: no\nAdded:")
        self.assertEqual(self.passing().data["must_look"], [])

    def test_several_reasons_come_in_a_fixed_order(self) -> None:
        self.respec("Added:", "Security: yes, a new login check.\nNot reversible: yes.\nAdded:")
        self.respec("## Decisions\n", "## Decisions\n- must-look: yes\n")
        self.assertEqual(self.passing().data["must_look"],
                         [ready.IRREVERSIBLE, ready.SECURITY, ready.PERSON])

    def test_there_are_exactly_five_reasons(self) -> None:
        self.assertEqual(len(ready.REASONS), 5)
        self.assertEqual(len(set(ready.REASONS)), 5)


class QuickPath(Case):
    def quick_body(self) -> str:
        return (FIXTURES / "quick.md").read_text(encoding="utf-8")

    def test_the_quick_fixture_reads_as_quick(self) -> None:
        self.assertEqual(spec.parse(self.quick_body()).path, "quick")

    def test_a_quick_piece_that_touches_two_areas_refuses(self) -> None:
        self.body = self.quick_body()
        parsed = spec.parse(self.body).to_dict()
        self.assertTrue(parsed["found"])
        self.respec_quick("Touches:", "Touches: reports, menus")
        self.refusal("names 2 areas")

    def respec_quick(self, marker: str, text: str) -> None:
        lines = self.body.splitlines()
        for number, line in enumerate(lines):
            if line.strip().startswith(marker):
                lines[number] = text
                break
        else:
            raise AssertionError(marker)
        self.body = "\n".join(lines) + "\n"


class NoTestRunner(Case):
    def empty_project(self) -> None:
        for path in ("tests/test_old.py", "src/app.py"):
            git(self.root, "rm", "-q", path)
        git(self.root, "commit", "-q", "-m", "Empty the project")

    def scaffold_body(self) -> str:
        return (
            "A tool that runs.\n\n<!-- spec:start version=1 -->\nPath: quick\n\n"
            "## Goal\nThe project has a test command that runs.\n\n"
            "## Expected flow\nFL-1 Running the test command exits with code 0.\n\n"
            "## Edge cases\nEC-1 When no test exists, then the command exits with code 0 and "
            "says 0 tests.\n\n"
            "## Must stay the same\nNothing exists yet. None.\n\n"
            "## Judge\nKind: scaffold, the test command runs\nCommand: sh scripts/test.sh\n"
            "Proves: FL-1, EC-1\n\n"
            "## Changes to current behaviour\nNew area: tooling\n\n"
            "## Links\nTouches: tooling\n"
            "<!-- spec:end -->\n"
        )

    def test_the_empty_project_has_no_runner(self) -> None:
        self.empty_project()
        self.assertFalse(ready.has_test_runner(self.root, "main"))

    def test_a_git_error_is_not_read_as_no_test_runner(self) -> None:
        with self.assertRaises(ready.GitError):
            ready.has_test_runner(self.root, "no-such-ref")

    def test_a_git_error_refuses_the_piece(self) -> None:
        def broken(*_args: Any, **_more: Any) -> bool:
            raise ready.GitError("git could not list main")

        with mock.patch.object(ready, "has_test_runner", broken):
            self.refusal("git could not list main")

    def test_a_project_with_tests_has_a_runner(self) -> None:
        self.assertTrue(ready.has_test_runner(self.root, "main"))

    def test_a_quick_scaffold_piece_passes_with_no_runner(self) -> None:
        self.empty_project()
        git(self.root, "branch", "-q", "-D", ready.branch_name(1))
        self.body = self.scaffold_body()
        result = self.passing()
        self.assertEqual(self.stand.list_runs, 0)
        self.assertEqual(self.stand.judge_runs, [])
        self.assertEqual(result.data["fingerprint"]["judge_commit"],
                         git(self.root, "rev-parse", "main"))
        self.assertTrue(spec.parse(result.data["body"]).judge["fails_today"])

    def test_any_other_piece_is_refused_with_no_runner(self) -> None:
        self.empty_project()
        result = self.refusal("test runner")
        self.assertIn("scaffold", result.next_command)

    def test_a_scaffold_piece_that_is_not_quick_is_refused(self) -> None:
        self.empty_project()
        self.body = self.scaffold_body().replace("Path: quick\n\n", "")
        self.refusal("quick")

    def test_a_scaffold_piece_is_judged_as_any_other_when_a_runner_exists(self) -> None:
        self.body = self.scaffold_body()
        self.refusal("single test")
        self.assertEqual(self.stand.judge_runs, [])


if __name__ == "__main__":
    unittest.main()
