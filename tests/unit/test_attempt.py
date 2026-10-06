"""Unit tests for loop/gates/attempt.py and loop/attempt_log.py: the checks of move 5.

Every test starts from one claimed piece with one honest attempt that passes, and spoils
one thing. Each anti-gaming case must give a failed attempt, logged as possible gaming
where the design says so. A fault of the gate's own (git, a record, a store, a judge that
cannot run) must be a refusal that counts no attempt. The judge and `dependency-check.py`
are stand-ins. The rest is real: a Git project with a piece branch, the area map, the
held-out store, the policy file and the spec parser. `tests/attempt-gate.sh` runs the
real gate end to end, and `tests/unit/test_moves.py` runs the moves around it.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_claim  # type: ignore[import-not-found, unused-ignore]  # noqa: E402
import test_ready  # type: ignore[import-not-found, unused-ignore]  # noqa: E402
from loop import attempt_log, fingerprint, heldout, judge, moves, states  # noqa: E402
from loop.gates import CheckContext, CheckResult, attempt, ready  # noqa: E402
from loop.paths import Paths  # noqa: E402

git = test_ready.git
COMMAND = test_ready.COMMAND
TODAY = "2026-10-06"
AREA_MAP = "src/ reports\ntests/ reports\ndocs/ menus\nbilling/ billing\n"
HELD = "tests/held_out/test_{n}.py"


def case_text(n: int) -> str:
    return (f"# held-out-path: {HELD.format(n=n)}\n"
            f"def test_hidden_{n}():\n    assert rename('a') == 'a'\n")


def passed_run(**more: Any) -> dict[str, Any]:
    found: dict[str, Any] = test_ready.judge_result("passed", exit_code=0, **more)
    return found


class Stand:
    """The stand-ins of one test: the judge by command, and the dependency check."""

    def __init__(self) -> None:
        self.visible: dict[str, Any] = passed_run()
        self.held: dict[str, dict[str, Any]] = {}
        self.must_stay: dict[str, Any] = passed_run()
        self.runs: list[tuple[str, str]] = []
        self.extra: list[dict[str, str]] = []
        self.dependency: tuple[int, str] = (0, json.dumps({"ok": True, "added": []}))
        self.self_check: tuple[int, str] = (0, json.dumps({"ok": True, "added": []}))
        self.real_dependency_check = False
        self.self_checks = 0
        self.dependency_calls: list[dict[str, str]] = []
        self.judge_error: dict[str, judge.JudgeError] = {}

    def run_judge(self, command: str, root: Path, ref: str, **more: Any) -> dict[str, Any]:
        self.runs.append((command, ref))
        self.extra.append(dict(more.get("extra_files") or {}))
        if command in self.judge_error:
            raise self.judge_error[command]
        if command == COMMAND:
            found = self.visible
        elif command.startswith("pytest tests/held_out/"):
            found = self.held.get(command.split()[-1], passed_run())
        else:
            found = self.must_stay
        return {**found, "command": command, "ref": ref}

    def check_dependencies(self, argv: Any, env: Any) -> tuple[int, str]:
        if self.real_dependency_check:
            return attempt._run_dependency_check(argv, env)
        paths = dict(zip(argv[2::2], argv[3::2], strict=False))
        after = Path(paths["--lockfile"]).read_text(encoding="utf-8")
        before = Path(paths["--before"]).read_text(encoding="utf-8")
        if after == before:
            # The gate's first run of a lockfile against itself: no new packages, no registry call.
            self.self_checks += 1
            return self.self_check
        self.dependency_calls.append({"after": after, "before": before, "argv": " ".join(argv)})
        return self.dependency

    def deps(self) -> attempt.Deps:
        return attempt.Deps(run_judge=self.run_judge, dependency_check=self.check_dependencies,
                            today=lambda: TODAY)


class AttemptCase(test_claim.ClaimCase):  # type: ignore[misc, unused-ignore]
    """A claimed piece on its branch. `attempt` makes the builder's commit."""

    body: str
    print_: str
    record: list[dict[str, Any]]
    CASES = 2
    TOUCHES = "Touches: reports, menus"
    DEPENDENCY = False

    def prepare(self) -> None:
        """A subclass spoils the spec here, before ready."""

    def setUp(self) -> None:
        super().setUp()
        self.att = Stand()
        (self.root / "docs" / "area-map").write_text(AREA_MAP, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Map the tests and billing")
        self.judge_branch_again({test_ready.TEST_FILE: test_ready.TEST_TEXT})
        for stale in heldout.folder(self.paths, 1).iterdir():
            stale.unlink()
        self.cases = {f"FL-{n}": case_text(n) for n in range(1, self.CASES + 1)}
        old = self.print_
        self.print_ = heldout.store(self.paths, 1, self.cases, replace=True)["fingerprint"]
        self.body = self.body.replace(old, self.print_)
        self.respec("Touches: reports, menus", self.TOUCHES)
        if self.DEPENDENCY:
            self.respec("Added: a \"Rename\" item in the report menu.",
                        "Added: a \"Rename\" item in the report menu.\n"
                        "New dependency: left-pad, to trim names.")
        self.prepare()
        self.make_ready()
        latest = next(e for e in reversed(self.record) if e["kind"] == "fingerprint")
        self.record += [
            {"kind": "fingerprint", "fingerprint": dict(latest["fingerprint"]), "why": "move 4"},
            {"kind": "claim-check", "at": TODAY, "main": git(self.root, "rev-parse", "main"),
             "judge_ref": self.first, "findings": 3, "relied_on": 1},
            {"kind": "move", "move": 4, "from": "ready", "to": "building"},
        ]

    # --- the builder's work --------------------------------------------------------------

    def attempt(self, files: dict[str, str] | None = None, *, remove: tuple[str, ...] = (),
                message: str = "The attempt") -> str:
        git(self.root, "checkout", "-q", ready.branch_name(1))
        try:
            for name, text in (files or {}).items():
                target = self.root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            for name in remove:
                git(self.root, "rm", "-q", name)
            git(self.root, "add", "-A")
            git(self.root, "commit", "-q", "--allow-empty", "-m", message)
            head: str = git(self.root, "rev-parse", "HEAD")
            return head
        finally:
            git(self.root, "checkout", "-q", "main")

    def honest(self, **more: Any) -> str:
        files = {"src/rename.py": "def rename(name):\n    return name.strip() or None\n",
                 "tests/test_rename_extra.py": (
                     "from src.rename import rename\n\n\ndef test_a_name_is_trimmed():\n"
                     "    assert rename(' a ') == 'a'\n")}
        files.update(more.pop("files", {}))
        return self.attempt(files, **more)

    # --- running the gate ----------------------------------------------------------------

    def attempt_context(self) -> CheckContext:
        base = self.context()
        return CheckContext(
            number=1, move=states.by_number(5), origin="building", target="review", reason=None,
            title=base.title, body=self.body, spec=base.spec, record=self.record,
            paths=self.paths, options=dict(self.options),
        )

    def judge_attempt(self) -> CheckResult:
        return attempt.run(self.attempt_context(), self.att.deps())

    def passes(self) -> CheckResult:
        result = self.judge_attempt()
        self.assertTrue(result.ok, f"refused: {result.failures} next: {result.next_command}")
        return result

    def fails(self, check: str, *needles: str, gaming: bool) -> dict[str, Any]:
        """A failed attempt: refused, with an attempt entry, a next line and the right check."""
        result = self.judge_attempt()
        self.assertFalse(result.ok, "the attempt passed, and it should have failed")
        self.assertIn("attempt", result.data, f"a refusal of the gate's own: {result.failures}")
        item = result.data["attempt"]
        self.assertEqual(item["result"], "failed")
        self.assertEqual(item["possible_gaming"], gaming, item["findings"])
        self.assertIn(check, [f["check"] for f in item["findings"]], item["findings"])
        said = " ".join(result.failures)
        for needle in needles:
            self.assertIn(needle, said)
        if gaming:
            self.assertIn("possible gaming", said)
        self.assertTrue(result.next_command, "a refusal names the next command")
        return dict(item)

    def refuses(self, *needles: str) -> CheckResult:
        """The gate's own fault: refused, and no attempt is counted."""
        result = self.judge_attempt()
        self.assertFalse(result.ok, "the gate passed, and it should have refused")
        self.assertNotIn("attempt", result.data, "a refusal of the gate's own counts no attempt")
        self.assertNotIn("send_back", result.data)
        said = " ".join(result.failures)
        for needle in needles:
            self.assertIn(needle, said)
        self.assertTrue(result.next_command, "a refusal names the next command")
        return result


class ThePassingAttempt(AttemptCase):
    def test_an_honest_attempt_passes(self) -> None:
        self.honest()
        self.passes()

    def test_it_writes_an_attempt_entry_and_the_judge_runs(self) -> None:
        head = self.honest()
        entries = self.passes().data["entries"]
        first = entries[0]
        self.assertEqual((first["kind"], first["result"], first["n"], first["head"]),
                         ("attempt", "passed", 1, head))
        self.assertEqual(first["base"], git(self.root, "rev-parse", f"{self.first}^"))
        self.assertEqual([e["kind"] for e in entries[1:]], ["judge-run", "judge-run"])

    def test_the_visible_judge_and_the_check_run_on_the_head_commit(self) -> None:
        head = self.honest()
        self.passes()
        self.assertIn((COMMAND, head), self.att.runs)
        self.assertIn(("pytest tests/test_old.py", head), self.att.runs)

    def test_the_project_folder_and_the_branch_are_left_as_they_were(self) -> None:
        head = self.honest()
        self.passes()
        self.assertEqual(git(self.root, "status", "--porcelain"), "")
        self.assertEqual(git(self.root, "rev-parse", ready.branch_name(1)), head)

    def test_a_pass_after_failed_attempts_is_numbered_after_them(self) -> None:
        self.record.append(attempt_log.entry(number=1, result="failed", head="a" * 40,
                                             base="b" * 40, at=TODAY))
        self.honest()
        self.assertEqual(self.passes().data["entries"][0]["n"], 2)

    def test_the_module_loads_through_the_gate_name(self) -> None:
        self.assertTrue(moves.load_checks("attempt").__module__.endswith("attempt"))

    def test_the_visible_judge_is_not_asked_to_pass_a_changed_bar(self) -> None:
        self.honest(files={"tests/test_old.py": "def test_old():\n    assert True\n"})
        self.fails("frozen-bar", gaming=True)
        self.assertEqual(self.att.runs, [], "no judge runs against a bar that was changed")


class TheFrozenBar(AttemptCase):
    """Each way to lower the bar is a failed attempt, logged as possible gaming."""

    def bar_fails(self, needle: str) -> dict[str, Any]:
        item = self.fails("frozen-bar", needle, gaming=True)
        self.assertEqual(self.att.runs, [], "the judge ran against a changed bar")
        self.assertNotIn("send_back", self.judge_attempt().data)
        return item

    def test_a_changed_judge_file(self) -> None:
        self.honest(files={test_ready.TEST_FILE: test_ready.TEST_TEXT.replace(
            "assert False", "assert True")})
        self.bar_fails("acceptance-check")

    def test_a_deleted_judge_file(self) -> None:
        self.honest(remove=(test_ready.TEST_FILE,))
        self.bar_fails("acceptance-check")

    def test_a_removed_test(self) -> None:
        self.honest(remove=("tests/test_old.py",))
        self.bar_fails("existing-test")

    def test_a_skipped_test(self) -> None:
        self.honest(files={"tests/test_old.py":
                           "import pytest\n\n\n@pytest.mark.skip\ndef test_old():\n    pass\n"})
        item = self.bar_fails("skip-or-focus")
        self.assertIn("existing-test", " ".join(f["text"] for f in item["findings"]))

    def test_a_loosened_assertion(self) -> None:
        self.honest(files={"tests/test_old.py": "def test_old():\n    assert 1 or 0\n"})
        self.bar_fails("existing-test")

    def test_a_raised_timeout(self) -> None:
        self.honest(files={"pytest.ini": "[pytest]\ntimeout = 3600\n"})
        self.bar_fails("tool-settings")

    def test_a_retry_added(self) -> None:
        self.honest(files={"pytest.ini": "[pytest]\naddopts = --reruns 5\n"})
        self.bar_fails("tool-settings")

    def test_a_new_conftest_that_turns_failures_green(self) -> None:
        self.honest(files={"conftest.py": "collect_ignore_glob = ['tests/*']\n"})
        self.bar_fails("tool-settings")

    def test_a_hidden_dist_info_plugin_beside_a_root_module(self) -> None:
        self.honest(files={
            ".x-1.0.dist-info/METADATA": "Name: x\nVersion: 1.0\n",
            ".x-1.0.dist-info/entry_points.txt": "[pytest11]\ncheat = cheatmod\n",
            "cheatmod.py": "def pytest_runtest_makereport(item, call):\n    pass\n"})
        self.bar_fails("tool-settings")

    def test_a_vite_config_with_a_test_block(self) -> None:
        self.honest(files={"vite.config.ts": "export default { test: { retry: 5 } }\n"})
        self.bar_fails("tool-settings")

    def test_a_pytest_option_in_a_quoted_pyproject_table(self) -> None:
        self.honest(files={"pyproject.toml":
                           '[tool."pytest".ini_options]\naddopts = "-k not_slow"\n'})
        self.bar_fails("tool-settings")

    def test_a_test_script_changed_in_package_json(self) -> None:
        self.honest(files={"package.json": '{"scripts": {"test": "true"}}\n'})
        self.bar_fails("tool-settings")

    def test_a_suppression_added(self) -> None:
        self.honest(files={"src/app.py": "X = 1  # noqa\n"})
        self.bar_fails("suppression")

    def test_a_guarded_file_changed(self) -> None:
        self.honest(files={".githooks/pre-commit": "exit 0\n"})
        self.bar_fails("guarded-file")

    def test_a_rewritten_judge_commit(self) -> None:
        """The history was rewritten: the branch holds an edited copy as its first commit."""
        git(self.root, "checkout", "-q", "-B", ready.branch_name(1), f"{self.first}^")
        (self.root / test_ready.TEST_FILE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / test_ready.TEST_FILE).write_text(
            test_ready.TEST_TEXT.replace("assert False", "assert True"), encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Judge files, but kinder")
        git(self.root, "checkout", "-q", "main")
        item = self.bar_fails("first commit")
        self.assertEqual(item["findings"][0]["check"], "frozen-bar")

    def test_the_whole_list_is_in_the_attempt_log_entry(self) -> None:
        self.honest(files={test_ready.TEST_FILE: test_ready.TEST_TEXT + "\n",
                           "tests/test_old.py": "def test_old():\n    assert True\n"})
        item = self.fails("frozen-bar", gaming=True)
        texts = " ".join(f["text"] for f in item["findings"])
        self.assertIn("acceptance-check", texts)
        self.assertIn("existing-test", texts)


class TheFingerprint(AttemptCase):
    def test_a_fingerprint_changed_since_the_claim_is_a_failed_attempt(self) -> None:
        self.honest()
        self.respec("Names have at most 80 characters.", "Names have at most 90 characters.")
        item = self.fails("fingerprint", "since the claim", gaming=False)
        self.assertEqual([f["check"] for f in item["findings"]], ["fingerprint"])
        self.assertEqual(self.att.runs, [])

    def test_it_is_compared_with_the_fingerprint_the_claim_kept(self) -> None:
        """A gate-made change to the spec took a new fingerprint, which is the one kept."""
        self.honest()
        self.respec("Names have at most 80 characters.", "Names have at most 90 characters.")
        self.record.append({"kind": "fingerprint", "why": "gate-made change",
                            "fingerprint": fingerprint.take(self.body, self.first)})
        self.passes()

    def test_a_record_with_no_fingerprint_is_a_refusal(self) -> None:
        self.honest()
        self.record = [e for e in self.record if e["kind"] != "fingerprint"]
        self.refuses("no fingerprint")

    def test_a_record_with_no_claim_check_is_a_refusal(self) -> None:
        self.honest()
        self.record = [e for e in self.record if e["kind"] != "claim-check"]
        self.refuses("claim check")

    def test_a_spec_the_parser_refuses_is_a_refusal(self) -> None:
        self.honest()
        self.body = self.body.replace("<!-- spec:end -->", "")
        self.refuses("spec")


class TheVisibleJudge(AttemptCase):
    def test_a_visible_judge_that_fails_is_a_failed_attempt(self) -> None:
        self.honest()
        self.att.visible = test_ready.judge_result("failed")
        self.fails("visible-judge", "FL-1", gaming=False)

    def test_the_hidden_cases_are_not_run_when_the_visible_judge_fails(self) -> None:
        self.honest()
        self.att.visible = test_ready.judge_result("failed")
        self.judge_attempt()
        self.assertEqual([c for c, _ in self.att.runs if "held_out" in c], [])

    def test_a_visible_judge_that_errors_or_times_out(self) -> None:
        for outcome, word in (("errored", "errored"), ("timeout", "time limit"),
                              ("failed_no_id", "no spec ID")):
            with self.subTest(outcome=outcome):
                self.att.visible = test_ready.judge_result(outcome, failing_ids=[], failures=[])
                self.fails("visible-judge", word, gaming=False)

    def test_a_failure_from_a_runner_with_no_report_is_not_proven_and_still_failed(self) -> None:
        self.honest()
        self.att.visible = test_ready.judge_result("failed", runner=None, failing_ids=[])
        self.fails("visible-judge", "not proven", gaming=False)

    def test_a_judge_that_cannot_be_run_is_a_refusal(self) -> None:
        self.honest()
        self.att.judge_error[COMMAND] = judge.JudgeError("no checkout", next_command="look")
        self.refuses("could not be run")

    def test_a_spec_with_no_command_is_a_refusal(self) -> None:
        self.honest()
        self.body = self.body.replace(f"Command: {COMMAND}\n", "")
        self.record.append({"kind": "fingerprint", "why": "test",
                            "fingerprint": fingerprint.take(self.body, self.first)})
        self.refuses("no Command")


def stored_objects(root: Path) -> bytes:
    """Every object in the project's git object store, loose or packed, unreachable or not."""
    done = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch-all-objects", "--batch"],
        capture_output=True, check=True)
    return done.stdout


class TheHeldOutCases(AttemptCase):
    def test_no_hidden_case_text_ever_enters_the_object_store(self) -> None:
        self.honest()
        self.hidden(1)
        self.fails("held-out", gaming=True)
        objects = stored_objects(self.root)
        for n in (1, 2):
            self.assertNotIn(f"def test_hidden_{n}".encode(), objects)
        self.assertNotIn(b"held-out-path", objects)

    def test_the_cases_go_to_the_judge_as_extra_files_on_the_attempt_head(self) -> None:
        head = self.honest()
        self.passes()
        held = [(c, r, e) for (c, r), e in zip(self.att.runs, self.att.extra, strict=True)
                if "held_out" in c]
        self.assertEqual(len(held), 2)
        for command, ref, extra in held:
            self.assertEqual(ref, head)
            self.assertEqual(len(extra), 1)
            ((path, text),) = extra.items()
            self.assertIn(path, command)
            self.assertEqual(text, case_text(int(path.split("_")[-1][:-3])))
        visible = [e for (c, _r), e in zip(self.att.runs, self.att.extra, strict=True)
                   if c == COMMAND]
        self.assertEqual(visible, [{}])

    def hidden(self, *numbers: int) -> None:
        for number in numbers:
            self.att.held[HELD.format(n=number)] = test_ready.judge_result("failed")

    def test_a_result_much_worse_than_the_visible_one_is_gaming(self) -> None:
        self.honest()
        self.hidden(1)
        item = self.fails("held-out", "1 of 2 hidden cases", gaming=True)
        self.assertEqual(item["findings"][0]["gaming"], True)

    def test_the_log_never_holds_a_hidden_case_or_its_path(self) -> None:
        self.honest()
        self.hidden(1, 2)
        item = self.fails("held-out", gaming=True)
        text = json.dumps(item)
        for secret in ("held_out", "test_hidden", "rename('a')", "FL-1"):
            self.assertNotIn(secret, text)

    def test_a_case_that_errors_counts_as_failed(self) -> None:
        self.honest()
        self.att.held[HELD.format(n=2)] = test_ready.judge_result("errored", failing_ids=[])
        self.fails("held-out", "1 of 2", gaming=True)

    def test_hidden_cases_missing_from_the_store_are_a_refusal(self) -> None:
        self.honest()
        for item in heldout.folder(self.paths, 1).iterdir():
            item.unlink()
        self.refuses("no held-out cases")
        self.assertEqual([c for c, _ in self.att.runs if "held_out" in c], [])

    def test_a_store_that_changed_since_ready_is_a_refusal(self) -> None:
        self.honest()
        heldout.store(self.paths, 1, {"FL-1": case_text(1) + "# more\n"}, replace=True)
        self.refuses("differ from the fingerprint")

    def test_a_case_with_no_path_line_is_a_refusal(self) -> None:
        self.honest()
        text = "def test_hidden():\n    assert False\n"
        new = heldout.store(self.paths, 1, {"FL-1": text}, replace=True)["fingerprint"]
        self.body = self.body.replace(self.print_, new)
        self.record.append({"kind": "fingerprint", "why": "test",
                            "fingerprint": fingerprint.take(self.body, self.first)})
        self.refuses("held-out-path")

    def test_a_case_that_writes_outside_the_tree_is_a_refusal(self) -> None:
        self.honest()
        text = "# held-out-path: ../outside.py\ndef test_hidden():\n    assert False\n"
        new = heldout.store(self.paths, 1, {"FL-1": text}, replace=True)["fingerprint"]
        self.body = self.body.replace(self.print_, new)
        self.record.append({"kind": "fingerprint", "why": "test",
                            "fingerprint": fingerprint.take(self.body, self.first)})
        self.refuses("held-out-path")

    def test_a_hidden_case_that_cannot_be_run_is_a_refusal(self) -> None:
        self.honest()
        self.att.judge_error["pytest " + HELD.format(n=1)] = judge.JudgeError(
            "no checkout", next_command="look")
        self.refuses("held-out case could not be run")

    def test_a_command_that_names_no_judge_file_cannot_run_a_case_beside_it(self) -> None:
        with self.assertRaises(attempt.Refusal) as raised:
            attempt._held_command("pytest tests/acceptance", [test_ready.TEST_FILE],
                                  HELD.format(n=1), 1)
        self.assertIn("names no judge file", str(raised.exception))
        self.assertTrue(raised.exception.next_command)

    def test_the_command_swaps_the_judge_files_for_the_hidden_one(self) -> None:
        got = attempt._held_command("python3 -m pytest -q tests/acceptance/test_rename.py",
                                    [test_ready.TEST_FILE], HELD.format(n=1), 1)
        self.assertEqual(got, "python3 -m pytest -q tests/held_out/test_1.py")


class HeldOutGap(AttemptCase):
    CASES = 5

    def test_one_in_five_fails_the_attempt_but_is_not_flagged_as_gaming(self) -> None:
        self.honest()
        self.att.held[HELD.format(n=3)] = test_ready.judge_result("failed")
        self.fails("held-out", "1 of 5", gaming=False)

    def test_half_or_more_is_flagged(self) -> None:
        self.honest()
        for n in (1, 2, 3):
            self.att.held[HELD.format(n=n)] = test_ready.judge_result("failed")
        self.fails("held-out", "3 of 5", gaming=True)


class TheNewTestLint(AttemptCase):
    def test_a_new_test_with_nothing_asserted_fails_the_lint(self) -> None:
        self.honest(files={"tests/test_extra.py": "def test_nothing():\n    x = 1\n"})
        item = self.fails("new-test-lint", "no_assertion", gaming=False)
        self.assertIn("tests/test_extra.py", item["findings"][0]["text"])

    def test_a_new_test_that_asserts_true_fails_the_lint(self) -> None:
        self.honest(files={"tests/test_extra.py": "def test_always():\n    assert True\n"})
        self.fails("new-test-lint", "assert_true", gaming=False)

    def test_a_new_test_that_mocks_the_projects_own_code_fails_the_lint(self) -> None:
        self.honest(files={
            "tests/test_extra.py": "from unittest.mock import patch\n\n\n"
                                   "def test_it():\n    with patch('src.rename.rename') as m:\n"
                                   "        m.return_value = 1\n        assert m() == 1\n"})
        self.fails("new-test-lint", "own_module_mock", gaming=False)

    def test_a_clean_new_test_passes_the_lint(self) -> None:
        self.honest()
        self.passes()

    def test_the_lint_reads_only_what_the_attempt_added(self) -> None:
        """tests/test_old.py asserts nothing at the base. The attempt did not add that."""
        self.assertNotIn("assert", (self.root / "tests" / "test_old.py").read_text("utf-8"))
        self.honest()
        self.passes()

    def test_the_judge_files_are_not_linted(self) -> None:
        self.honest()
        self.passes()  # the judge file asserts False, which a new test never may


class TheMustStayTheSameChecks(AttemptCase):
    def test_a_check_gone_red_is_a_failed_attempt(self) -> None:
        self.honest()
        self.att.must_stay = test_ready.judge_result("failed")
        self.fails("must-stay-the-same", "pytest tests/test_old.py", gaming=False)

    def test_a_check_that_cannot_be_run_is_a_refusal(self) -> None:
        self.honest()
        self.att.judge_error["pytest tests/test_old.py"] = judge.JudgeError(
            "no checkout", next_command="look")
        self.refuses("could not be run")

    def test_every_fault_after_the_bar_is_reported_together(self) -> None:
        self.honest(files={"lib/util.py": "X = 1\n"})
        self.att.visible = test_ready.judge_result("failed")
        self.att.must_stay = test_ready.judge_result("failed")
        result = self.judge_attempt()
        checks = [f["check"] for f in result.data["attempt"]["findings"]]
        self.assertEqual(checks, ["visible-judge", "must-stay-the-same", "touches"])


class TheDeclaredTouches(AttemptCase):
    def test_a_diff_outside_the_declared_touches(self) -> None:
        self.honest(files={"billing/charge.py": "X = 1\n"})
        item = self.fails("touches", "billing/charge.py", "billing", gaming=False)
        self.assertIn("(menus, reports)", item["findings"][0]["text"])

    def test_a_path_in_no_area(self) -> None:
        self.honest(files={"lib/util.py": "X = 1\n"})
        self.fails("touches", "lib/util.py", "unclaimed", gaming=False)

    def test_a_root_file_and_a_changelog_are_inside_every_boundary(self) -> None:
        self.honest(files={"CHANGELOG.md": "A line.\n", "changes/note.md": "A note.\n"})
        self.passes()

    def test_a_path_in_a_declared_area_passes(self) -> None:
        self.honest(files={"docs/reports.md": "Docs.\n"})
        self.passes()

    def test_the_judge_files_are_not_part_of_the_diff_that_is_checked(self) -> None:
        self.honest()
        self.passes()

    def test_the_area_map_is_the_one_the_piece_was_cut_from_not_the_builders(self) -> None:
        """The builder claims lib/ for a declared area in its own copy of the map."""
        self.honest(files={"lib/util.py": "X = 1\n",
                           "docs/area-map": AREA_MAP + "lib/ reports\n"})
        self.fails("touches", "lib/util.py", gaming=False)

    def test_the_area_map_is_not_the_one_main_holds_now(self) -> None:
        self.honest(files={"lib/util.py": "X = 1\n"})
        git(self.root, "checkout", "-q", "main")
        (self.root / "docs" / "area-map").write_text(AREA_MAP + "lib/ reports\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Main moved on")
        self.fails("touches", "lib/util.py", gaming=False)

    def test_an_area_map_that_cannot_be_read_at_the_base_is_a_refusal(self) -> None:
        with self.assertRaises(attempt.Refusal):
            attempt._area_rules(self.root, "again", "no-such-ref")

    def test_the_map_is_read_with_git_show_never_from_the_folder(self) -> None:
        (self.root / "docs" / "area-map").write_text("garbage line with three words\n",
                                                     encoding="utf-8")
        self.honest(files={"docs/reports.md": "Docs.\n"})
        git(self.root, "checkout", "-q", "main", "--", "docs/area-map")
        self.passes()


class TheNewAreaOfAPiece(AttemptCase):
    TOUCHES = "Touches: reports, menus, report-menu"

    def test_a_new_area_the_piece_declares_may_be_mapped_by_the_piece(self) -> None:
        self.honest(files={"lib/menu.py": "X = 1\n",
                           "docs/area-map": AREA_MAP + "lib/ report-menu\n"})
        self.passes()

    def test_a_new_path_mapped_to_an_area_the_piece_did_not_declare_is_outside(self) -> None:
        self.honest(files={"lib/menu.py": "X = 1\n",
                           "docs/area-map": AREA_MAP + "lib/ billing\n"})
        self.fails("touches", "lib/menu.py", gaming=False)


class TheDependencies(AttemptCase):
    LOCK_BEFORE = '{"packages": {}}\n'
    LOCK_AFTER = '{"packages": {"node_modules/left-pad": {"version": "1.3.0"}}}\n'

    def lockfile(self) -> None:
        self.honest(files={"package-lock.json": self.LOCK_AFTER})

    def answer(self, code: int, **body: Any) -> None:
        self.att.dependency = (code, json.dumps(body))

    def test_an_unplanned_new_dependency_is_a_failed_attempt(self) -> None:
        self.lockfile()
        self.answer(0, ok=True, added=[{"name": "left-pad", "version": "1.3.0"}])
        self.fails("dependency", "left-pad", "New dependency", gaming=False)

    def test_the_check_reads_the_lockfile_before_and_after(self) -> None:
        self.lockfile()
        self.answer(0, ok=True, added=[])
        self.passes()
        call = self.att.dependency_calls[0]
        self.assertEqual(call["after"], self.LOCK_AFTER)
        self.assertEqual(call["before"], "")
        self.assertIn("--json", call["argv"])

    def test_the_before_lockfile_comes_from_the_base_commit(self) -> None:
        git(self.root, "checkout", "-q", "main")
        self.assertEqual(git(self.root, "ls-files", "package-lock.json"), "")
        self.lockfile()
        self.answer(0, ok=True, added=[])
        self.passes()

    def test_a_new_package_that_the_check_refuses_is_a_failed_attempt(self) -> None:
        self.lockfile()
        self.answer(3, ok=False, error="left-pad 1.3.0 is 2 days old, and the limit is 30",
                    next="wait", exit_code=3)
        self.fails("dependency", "2 days old", gaming=False)

    def test_exit_4_is_a_refusal_not_a_pass_and_counts_no_attempt(self) -> None:
        self.lockfile()
        self.answer(4, ok=False, error="the registry is unreachable", next="retry", exit_code=4)
        self.refuses("exit 4")

    def test_the_builders_lockfile_is_checked_against_itself_first(self) -> None:
        self.lockfile()
        self.answer(0, ok=True, added=[])
        self.passes()
        self.assertEqual(self.att.self_checks, 1)

    def test_exit_4_on_the_lockfile_against_itself_is_a_failed_attempt(self) -> None:
        self.lockfile()
        self.att.self_check = (
            4, json.dumps({"ok": False, "error": "cannot parse", "exit_code": 4}))
        self.answer(4, ok=False, error="the registry is unreachable", next="retry", exit_code=4)
        self.fails("dependency", "package-lock.json", "cannot be read", gaming=False)
        self.assertEqual(self.att.dependency_calls, [], "no registry call after a broken lockfile")

    def test_a_broken_package_lock_is_a_failed_attempt_that_counts(self) -> None:
        self.att.real_dependency_check = True
        self.honest(files={"package-lock.json": "{ this is not json"})
        item = self.fails("dependency", "package-lock.json", "cannot be read", gaming=False)
        self.assertEqual(item["n"], 1)

    def test_a_good_package_lock_with_no_new_package_passes_the_real_check(self) -> None:
        self.att.real_dependency_check = True
        self.honest(files={"package-lock.json": self.LOCK_BEFORE})
        self.passes()

    def test_a_self_check_that_gives_exit_1_or_3_is_a_failed_attempt(self) -> None:
        self.lockfile()
        for code in (1, 3):
            with self.subTest(code=code):
                self.att.self_check = (code, "")
                self.fails("dependency", "package-lock.json", "cannot be read", gaming=False)

    def test_a_self_check_that_gives_exit_2_is_a_refusal(self) -> None:
        self.lockfile()
        self.att.self_check = (2, "")
        self.refuses("exit 2")

    def test_a_lockfile_that_fails_the_registry_call_does_not_hide_a_failed_attempt(self) -> None:
        self.att.real_dependency_check = True
        registry = Path(tempfile.mkdtemp()) / "registry"
        registry.mkdir()
        self.options = {"registry": str(registry)}
        self.honest(files={"package-lock.json": json.dumps({
            "lockfileVersion": 3,
            "packages": {"": {"name": "p"},
                         "node_modules/x": {"name": "a\u0000b", "version": "1.0.0"}}}) + "\n"})
        self.att.visible = test_ready.judge_result("failed")
        item = self.fails("visible-judge", "FL-1", gaming=False)
        self.assertEqual(item["n"], 1)
        self.assertIn("note: the gate also refused", " ".join(self.judge_attempt().failures))

    def test_any_other_exit_or_an_unreadable_answer_is_a_refusal(self) -> None:
        self.lockfile()
        for code, text in ((1, ""), (2, "usage"), (0, "not json")):
            with self.subTest(code=code):
                self.att.dependency = (code, text)
                self.refuses(f"exit {code}")

    def test_a_manifest_the_check_cannot_read_is_noted_and_not_called_checked(self) -> None:
        for name in ("requirements.txt", "requirements-dev.txt", "yarn.lock", "poetry.lock"):
            with self.subTest(name=name):
                self.honest(files={name: "left-pad\n"})
                result = self.passes()
                self.assertIn(name, " ".join(result.data["notes"]))
                self.assertIn("does not read", " ".join(result.data["notes"]))
        self.assertEqual(self.att.dependency_calls, [])

    def test_no_lockfile_change_means_no_dependency_check(self) -> None:
        self.honest()
        self.passes()
        self.assertEqual(self.att.dependency_calls, [])


class APlannedDependency(TheDependencies):
    DEPENDENCY = True

    def test_an_unplanned_new_dependency_is_a_failed_attempt(self) -> None:
        self.lockfile()
        self.answer(0, ok=True, added=[{"name": "left-pad", "version": "1.3.0"}])
        self.passes()

    def test_the_options_reach_the_check(self) -> None:
        self.options = {"registry": "/some/registry", "now": "2026-10-06T00:00:00Z"}
        self.lockfile()
        self.answer(0, ok=True, added=[{"name": "left-pad", "version": "1.3.0"}])
        self.passes()
        self.assertIn("--registry /some/registry", self.att.dependency_calls[0]["argv"])
        self.assertIn("--now 2026-10-06T00:00:00Z", self.att.dependency_calls[0]["argv"])


class CountingAttempts(AttemptCase):
    def failed(self, n: int) -> dict[str, Any]:
        return attempt_log.entry(
            number=n, result="failed", head=f"{n}" * 40, base="b" * 40, at=TODAY,
            findings=[attempt_log.finding("visible-judge", f"fault {n}")])

    def setUp(self) -> None:
        super().setUp()
        self.honest()
        self.att.visible = test_ready.judge_result("failed")

    def test_the_first_failure_has_attempts_left_and_does_not_send_the_piece_back(self) -> None:
        result = self.judge_attempt()
        self.assertEqual(result.data["attempt"]["n"], 1)
        self.assertNotIn("send_back", result.data)
        self.assertIn("attempt 2 of 3", result.next_command)

    def test_the_third_failure_sends_the_piece_back_with_every_attempts_findings(self) -> None:
        self.record += [self.failed(1), self.failed(2)]
        result = self.judge_attempt()
        self.assertEqual(result.data["attempt"]["n"], 3)
        reason = result.data["send_back"]
        for needle in ("3 of 3", "fault 1", "fault 2", "visible-judge"):
            self.assertIn(needle, reason)
        self.assertIn("move 6", result.next_command)

    def test_the_limit_is_the_policy_limit(self) -> None:
        self.policy(attempt_limit=2)
        self.record += [self.failed(1)]
        self.assertIn("2 of 2", self.judge_attempt().data["send_back"])
        self.policy(attempt_limit=5)
        self.assertNotIn("send_back", self.judge_attempt().data)

    def test_attempts_before_the_piece_left_shaping_do_not_count(self) -> None:
        self.record += [self.failed(1), self.failed(2),
                        {"kind": "move", "move": 2, "from": "shaping", "to": "ready"}]
        result = self.judge_attempt()
        self.assertEqual(result.data["attempt"]["n"], 1)
        self.assertNotIn("send_back", result.data)

    def test_a_refusal_of_the_gate_counts_no_attempt(self) -> None:
        self.record += [self.failed(1), self.failed(2)]
        self.att.judge_error[COMMAND] = judge.JudgeError("no checkout", next_command="look")
        self.refuses("could not be run")

    def test_a_policy_file_that_cannot_be_read_is_a_refusal(self) -> None:
        self.paths.policy_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.policy_file.write_text("{not json", encoding="utf-8")
        self.refuses("policy file")


class WhatTheGateCannotRead(AttemptCase):
    """Never let a check pass when it did not run: each of these is a refusal with a next line."""

    def test_a_piece_branch_that_is_gone(self) -> None:
        git(self.root, "branch", "-q", "-D", ready.branch_name(1))
        self.refuses("piece branch")

    def test_a_judge_commit_git_cannot_find(self) -> None:
        self.honest()
        bad = "deadbeef" * 5
        self.record.append({"kind": "fingerprint", "why": "test",
                            "fingerprint": fingerprint.take(self.body, bad)})
        self.refuses("git rev-parse failed")

    def test_a_project_that_is_not_a_repository_has_no_branch_to_judge(self) -> None:
        self.honest()
        elsewhere = Path(tempfile.mkdtemp()) / "project"
        elsewhere.mkdir()
        self.paths = Paths.for_project(elsewhere, data_base=self.base / "data",
                                       kit_folder=ROOT / "kit")
        self.refuses("piece branch")

    def worktree_with_edit(self) -> None:
        folder = Path(tempfile.mkdtemp()) / "wt"
        git(self.root, "worktree", "add", "-q", str(folder), ready.branch_name(1))
        (folder / "src" / "rename.py").write_text("X = 2\n", encoding="utf-8")

    def test_a_worktree_with_a_change_nobody_committed_is_judged_on_its_commit(self) -> None:
        head = self.honest()
        self.worktree_with_edit()
        result = self.passes()
        self.assertEqual([r for _c, r in self.att.runs], [head] * len(self.att.runs))
        notes = " ".join(result.data["notes"])
        self.assertIn("nobody committed", notes)
        self.assertIn(head[:7], notes)

    def test_a_failed_attempt_with_a_change_nobody_committed_still_counts(self) -> None:
        self.honest(files={"tests/test_old.py": "def test_old():\n    assert 1 or 0\n"})
        self.worktree_with_edit()
        result = self.judge_attempt()
        self.assertFalse(result.ok)
        self.assertEqual(result.data["attempt"]["result"], "failed")
        self.assertIn("nobody committed", " ".join(result.failures))

    def test_a_worktree_the_gate_cannot_read_is_still_a_refusal(self) -> None:
        self.honest()
        folder = Path(tempfile.mkdtemp()) / "wt"
        git(self.root, "worktree", "add", "-q", str(folder), ready.branch_name(1))
        git(self.root, "worktree", "lock", str(folder))
        (folder / ".git").write_text("gitdir: /nowhere\n", encoding="utf-8")
        self.refuses("git status failed")

    def test_a_worktree_with_everything_committed_is_judged(self) -> None:
        self.honest()
        folder = Path(tempfile.mkdtemp()) / "wt"
        git(self.root, "worktree", "add", "-q", str(folder), ready.branch_name(1))
        (folder / "scratch.log").write_text("junk\n", encoding="utf-8")  # untracked: ignored
        self.passes()

    def test_a_spec_with_no_block(self) -> None:
        ctx = self.attempt_context()
        bare = CheckContext(
            number=ctx.number, move=ctx.move, origin=ctx.origin, target=ctx.target, reason=None,
            title=ctx.title, body="nothing", spec=None, record=ctx.record, paths=ctx.paths)
        result = attempt.run(bare, self.att.deps())
        self.assertFalse(result.ok)
        self.assertTrue(result.next_command)


class TheAttemptLog(unittest.TestCase):
    def test_a_finding_names_a_known_check(self) -> None:
        with self.assertRaises(ValueError):
            attempt_log.finding("invented", "text")

    def test_a_finding_is_clipped_and_flat(self) -> None:
        item = attempt_log.finding("touches", "a\nb  " + "x" * 1000)
        self.assertLessEqual(len(item["text"]), attempt_log.MAX_TEXT)
        self.assertNotIn("\n", item["text"])

    def test_an_entry_marks_possible_gaming_from_its_findings(self) -> None:
        plain = attempt_log.entry(number=1, result="failed", head="h", base="b", at=TODAY,
                                  findings=[attempt_log.finding("touches", "x")])
        gamed = attempt_log.entry(number=1, result="failed", head="h", base="b", at=TODAY,
                                  findings=[attempt_log.finding("frozen-bar", "x", gaming=True)])
        self.assertFalse(plain["possible_gaming"])
        self.assertTrue(gamed["possible_gaming"])

    def test_an_entry_result_is_passed_or_failed(self) -> None:
        with self.assertRaises(ValueError):
            attempt_log.entry(number=1, result="maybe", head="h", base="b", at=TODAY)

    def test_attempts_count_from_the_last_move_out_of_shaping(self) -> None:
        one = attempt_log.entry(number=1, result="failed", head="h", base="b", at=TODAY)
        record = [one, {"kind": "move", "from": "shaping", "to": "ready"}, one, one]
        self.assertEqual(attempt_log.used(record), 2)
        self.assertEqual(len(attempt_log.failed(record)), 2)

    def test_the_log_renders_for_a_brief(self) -> None:
        item = attempt_log.entry(
            number=1, result="failed", head="abcdef1234", base="b", at=TODAY,
            findings=[attempt_log.finding("frozen-bar", "a test was removed", gaming=True)])
        text = attempt_log.render([item])
        for needle in ("Attempt 1", "abcdef1", "failed", "possible gaming", "frozen-bar",
                       "a test was removed"):
            self.assertIn(needle, text)

    def test_an_empty_log_says_so(self) -> None:
        self.assertIn("No attempt", attempt_log.render([]))

    def test_the_entry_kind_is_not_one_the_gate_uses_for_its_own(self) -> None:
        own = {"capture", "move", "body", "needs", "fingerprint", "answer", "queue", "synced",
               "branch", "judge-run", "test-lists", "relied-on", "claim-check"}
        self.assertNotIn(attempt_log.KIND, own)

    def test_the_attempt_log_has_no_command_line_that_writes_it(self) -> None:
        text = (ROOT / "kit" / "scripts" / "loop" / "attempt_log.py").read_text(encoding="utf-8")
        self.assertNotIn("evidence.append", text)
        self.assertNotIn("open(", text)


if __name__ == "__main__":
    unittest.main()
