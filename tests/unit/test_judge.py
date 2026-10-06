"""Unit tests for kit/scripts/loop/judge.py.

The reports in tests/fixtures/runner-reports/ were recorded from pytest and the
Node runner, and written to the shape Vitest and Jest document. No test needs
the tools installed, except the ones that run `python3 -m pytest` itself.
"""

import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import judge, spec  # noqa: E402

REPORTS = ROOT / "tests" / "fixtures" / "runner-reports"
SUFFIX = {"pytest": "xml", "node": "xml", "vitest": "json", "jest": "json"}


def report(runner: str, case: str) -> Path:
    return REPORTS / f"{runner}-{case}.{SUFFIX[runner]}"


class ReadReports(unittest.TestCase):
    def test_assertion_failure_names_the_id(self) -> None:
        for runner in SUFFIX:
            with self.subTest(runner=runner):
                result = judge.interpret(runner, report(runner, "fail"), 1, "")
                self.assertEqual(result["outcome"], "failed")
                self.assertEqual(result["failing_ids"], ["FL-1"])
                self.assertTrue(all(f["assertion"] for f in result["failures"]))
                self.assertIsNone(result["note"])

    def test_import_error_is_an_error_not_a_failure(self) -> None:
        for runner in SUFFIX:
            with self.subTest(runner=runner):
                result = judge.interpret(runner, report(runner, "import"), 1, "")
                self.assertEqual(result["outcome"], "errored")
                self.assertEqual(result["failing_ids"], [])
                self.assertTrue(result["failures"])
                self.assertFalse(any(f["assertion"] for f in result["failures"]))

    def test_an_assertion_that_names_no_id_is_not_the_right_failure(self) -> None:
        for runner in SUFFIX:
            with self.subTest(runner=runner):
                source = report(runner, "fail")
                text = source.read_text(encoding="utf-8").replace("FL-1", "nothing")
                with tempfile.TemporaryDirectory() as folder:
                    copy = Path(folder) / source.name
                    copy.write_text(text, encoding="utf-8")
                    result = judge.interpret(runner, copy, 1, "")
                self.assertEqual(result["outcome"], "failed_no_id")
                self.assertEqual(result["failing_ids"], [])
                self.assertIn("FL-", result["note"])

    def test_the_outcome_list_names_failed_no_id(self) -> None:
        self.assertIn("failed_no_id", judge.__doc__ or "")
        self.assertIn("failed_no_id", judge.OUTCOMES)
        self.assertNotIn("failed_no_id", judge.RIGHT_FAILURES)

    def test_error_kind_is_named(self) -> None:
        for runner in ("pytest", "vitest", "jest"):
            with self.subTest(runner=runner):
                result = judge.interpret(runner, report(runner, "import"), 1, "")
                self.assertEqual(result["kind"], "a missing module")

    def test_pass(self) -> None:
        for runner in SUFFIX:
            with self.subTest(runner=runner):
                result = judge.interpret(runner, report(runner, "pass"), 0, "")
                self.assertEqual(result["outcome"], "passed")
                self.assertEqual(result["failures"], [])
                self.assertEqual(result["failing_ids"], [])

    def test_nonzero_exit_with_no_failure_in_the_report_is_an_error(self) -> None:
        result = judge.interpret("pytest", report("pytest", "pass"), 5, "")
        self.assertEqual(result["outcome"], "errored")
        self.assertIn("exit", result["note"])

    def test_missing_report_after_a_failed_run_is_an_error(self) -> None:
        result = judge.interpret("pytest", Path("/nonexistent/report.xml"), 2, "boom")
        self.assertEqual(result["outcome"], "errored")
        self.assertIn("report", result["note"])

    def test_unknown_runner_falls_back_to_the_exit_code_with_a_note(self) -> None:
        failed = judge.interpret(None, None, 1, "FAIL something")
        self.assertEqual(failed["outcome"], "failed")
        self.assertIn("exit code", failed["note"])
        passed = judge.interpret(None, None, 0, "")
        self.assertEqual(passed["outcome"], "passed")
        self.assertIn("exit code", passed["note"])

    def test_exit_code_runners_name_no_report(self) -> None:
        for runner in sorted(judge.EXIT_CODE_RUNNERS):
            with self.subTest(runner=runner):
                self.assertIsNone(judge.report_option(runner, "r"))


class DetectRunner(unittest.TestCase):
    def test_commands(self) -> None:
        cases = {
            "pytest tests/test_a.py": "pytest",
            "python3 -m pytest -q": "pytest",
            "npx vitest run": "vitest",
            "jest --ci": "jest",
            "node --test tests/": "node",
            "python3 -m unittest tests/unit/test_a.py": "unittest",
            "go test ./...": "go",
            "cargo test": "cargo",
            "sh tests/check.sh": "shell",
            "make check": None,
        }
        for command, runner in cases.items():
            with self.subTest(command=command):
                self.assertEqual(judge.detect_runner(command, "/nonexistent"), runner)

    def test_npm_script_is_read_through_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "package.json").write_text(
                '{"scripts": {"test": "vitest run", "other": "echo hi"}}', encoding="utf-8"
            )
            self.assertEqual(judge.detect_runner("npm test", folder), "vitest")
            self.assertEqual(judge.detect_runner("npm run test", folder), "vitest")
            self.assertEqual(judge.detect_runner("npm run other", folder), "npm")

    def test_report_option_is_added_after_the_double_dash_for_npm(self) -> None:
        text = judge.build_command("npm test", "vitest", "/r.json")
        self.assertEqual(text, ["npm", "test", "--", "--reporter=json", "--outputFile=/r.json"])
        text = judge.build_command("pytest tests/a.py", "pytest", "/r.xml")
        self.assertEqual(text, ["pytest", "tests/a.py", "--junitxml=/r.xml"])


class RunnerList(unittest.TestCase):
    def test_spec_format_list_matches_the_runners_judge_reads(self) -> None:
        text = (ROOT / "kit" / "spec-format.md").read_text(encoding="utf-8")
        table = text.split("### Supported test runners", 1)[1].split("\n## ", 1)[0]
        named: set[str] = set()
        for line in table.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 2 and cells[0].startswith("`"):
                named.update(re.findall(r"`([a-z]+)`", cells[1]))
        self.assertTrue(named)
        self.assertEqual(named, set(judge.COMMAND_RUNNERS))
        self.assertEqual(named, {name for _, name in spec.RUNNERS})
        self.assertTrue(set(judge.REPORT_RUNNERS) <= set(judge.COMMAND_RUNNERS) | {"node"})


class RunInCheckout(unittest.TestCase):
    def make_project(self, test_body: str) -> Path:
        base = Path(tempfile.mkdtemp())
        root = base / "project"
        root.mkdir()
        env = {
            "GIT_CONFIG_GLOBAL": str(base / "gitconfig"),
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "T",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        }
        (base / "gitconfig").write_text("", encoding="utf-8")
        (root / "check.sh").write_text(test_body, encoding="utf-8")
        for args in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "x"]):
            subprocess.run(["git", "-C", str(root), *args], env=env, check=True)
        self.env = env
        return root

    def test_a_check_past_the_limit_is_stopped_and_reported(self) -> None:
        root = self.make_project("sleep 30\n")
        result = judge.run("sh check.sh", root, "main", time_limit=1)
        self.assertEqual(result["outcome"], "timeout")
        self.assertTrue(result["timed_out"])
        self.assertIn("1 second", result["note"])

    def _reap(self, pid: int) -> None:
        if not self._gone(pid):
            os.kill(pid, signal.SIGKILL)

    def _gone(self, pid: int) -> bool:
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.1)
        return False

    def test_the_time_limit_kills_a_grandchild_too(self) -> None:
        pids = Path(tempfile.mkdtemp()) / "pid"
        root = self.make_project(f"sleep 25 &\necho $! > {pids}\nwait\n")
        started = time.monotonic()
        result = judge.run("sh check.sh", root, "main", time_limit=1)
        took = time.monotonic() - started
        pid = int(pids.read_text(encoding="utf-8"))
        self.addCleanup(self._reap, pid)
        self.assertEqual(result["outcome"], "timeout")
        self.assertLess(took, 8)
        self.assertTrue(self._gone(pid), "the grandchild outlived the time limit")

    def test_a_process_that_left_the_group_cannot_hold_the_run(self) -> None:
        pids = Path(tempfile.mkdtemp()) / "pid"
        script = (
            "python3 -c \"import os,time; os.setsid(); open('" + str(pids) + "','w')"
            ".write(str(os.getpid())); time.sleep(25)\" &\nwait\n"
        )
        root = self.make_project(script)
        started = time.monotonic()
        result = judge.run("sh check.sh", root, "main", time_limit=1)
        took = time.monotonic() - started
        pid = int(pids.read_text(encoding="utf-8"))
        self.addCleanup(self._reap, pid)
        self.assertEqual(result["outcome"], "timeout")
        self.assertLess(took, 10)

    def test_exit_code_fallback_for_a_shell_check(self) -> None:
        root = self.make_project("exit 1\n")
        result = judge.run("sh check.sh", root, "main", time_limit=30)
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["runner"], "shell")
        self.assertIn("exit code", result["note"])

    def test_the_checkout_is_removed(self) -> None:
        root = self.make_project("exit 0\n")
        result = judge.run("sh check.sh", root, "main", time_limit=30)
        self.assertEqual(result["outcome"], "passed")
        listed = subprocess.run(
            ["git", "-C", str(root), "worktree", "list"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(len(listed.strip().splitlines()), 1)

    def test_extra_files_are_written_into_the_checkout_and_never_into_git(self) -> None:
        root = self.make_project('test "$(cat held/case.txt)" = "secret-case-text"\n')
        result = judge.run(
            "sh check.sh", root, "main", time_limit=30,
            extra_files={"held/case.txt": "secret-case-text"},
        )
        self.assertEqual(result["outcome"], "passed")
        objects = subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch-all-objects", "--batch"],
            capture_output=True, check=True,
        ).stdout
        self.assertNotIn(b"secret-case-text", objects)
        plain = judge.run("sh check.sh", root, "main", time_limit=30)
        self.assertNotEqual(plain["outcome"], "passed")

    def test_an_extra_file_outside_the_checkout_is_refused(self) -> None:
        root = self.make_project("exit 0\n")
        with self.assertRaises(judge.JudgeError):
            judge.run("sh check.sh", root, "main", time_limit=30,
                      extra_files={"../outside.txt": "x"})

    def test_a_failed_install_is_an_error(self) -> None:
        root = self.make_project("exit 0\n")
        result = judge.run("sh check.sh", root, "main", install="sh -c 'exit 7'", time_limit=30)
        self.assertEqual(result["outcome"], "errored")
        self.assertIn("install", result["note"])

    def test_evidence_entry_holds_no_raw_output(self) -> None:
        root = self.make_project("echo secret-looking-output; exit 1\n")
        result = judge.run("sh check.sh", root, "main", time_limit=30)
        entry = judge.evidence_entry(result, fingerprint="abc")
        self.assertEqual(entry["kind"], "judge-run")
        self.assertEqual(entry["outcome"], "failed")
        self.assertEqual(entry["fingerprint"], "abc")
        self.assertNotIn("output", entry)


if __name__ == "__main__":
    unittest.main()
