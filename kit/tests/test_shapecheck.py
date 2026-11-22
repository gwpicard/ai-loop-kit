"""Judge shaping checks through their command line and the build entry point."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, settings_json
from kit.tests import test_flow
import common
import flow
import merge


KIT = Path(__file__).resolve().parents[1]
SCRIPT = KIT / "scripts/shapecheck.py"


class ShapecheckTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)

    def run_check(self, work, body, issues=None):
        self.assertTrue(SCRIPT.is_file(), "The shaping check command is missing")
        draft = self.tmp / "draft.md"
        draft.write_text(body, encoding="utf-8")
        command = [sys.executable, str(SCRIPT), str(draft)]
        if issues is not None:
            fixture = self.tmp / "issues.json"
            fixture.write_text(json.dumps(issues), encoding="utf-8")
            command += ["--issues", str(fixture)]
        return subprocess.run(command, cwd=work, capture_output=True, text=True,
                              timeout=30)

    def test_lists_tracked_tests_support_and_named_stops_for_each_body_layout(self):
        files = {
            "loop.json": json.dumps({"Test command": "true",
                                     "Protected paths": ["private/"]}),
            "src/service.py": "class Invoice: pass\n",
            "tests/test_service.py": "# src/service.py\n",
            "tests/test_handler.py": "# service.handle\n",
            "nested/tests/helpers.py": "# service.handle\n",
            "tests/fake_invoice.py": "# Invoice\n",
            "tests/run.py": "# Invoice and service.handle\n",
            "tests/test_unrelated.py": "# unrelated\n",
            "tests/test_regex_decoy.py": "# serviceXhandle\n",
            "src/consumer.py": "# Invoice\n",
            "setup.py": "# package manifest\n",
            "package/pyproject.toml": "[project]\nname = 'fixture'\n",
            "package/setup.py": "# package manifest\n",
            "scripts/setup.py": "# ordinary script\n",
            ".github/workflows/check.yml": "name: check\n",
            "requirements-dev.txt": "# empty\n",
            "private/rules.txt": "protected\n",
            "config/settings.json": "{}\n",
        }
        work, _ = make_repo(str(self.tmp), files)
        Path(work, "tests/test_untracked.py").write_text("# Invoice\n")
        names = ["src/service.py", "service.handle", "Invoice", "setup.py",
                 "package/setup.py", "scripts/setup.py",
                 ".github/workflows/check.yml", "requirements-dev.txt",
                 "private/rules.txt", "config/settings.json"]
        expected = {"tests/test_service.py", "tests/test_handler.py",
                    "nested/tests/helpers.py", "tests/fake_invoice.py", "tests/run.py",
                    "setup.py", "package/setup.py", ".github/workflows/check.yml",
                    "requirements-dev.txt", "private/rules.txt", "config/settings.json"}
        bodies = ["Change " + ", ".join("`" + n + "`" for n in names) + ".\n",
                  "## Goal\n" + "\n".join("- `" + n + "`" for n in reversed(names))
                  + "\nMention `Invoice` and `service.handle` again.\n"]
        for body in bodies:
            with self.subTest(body=body):
                result = self.run_check(work, body)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                lines = result.stdout.splitlines()
                self.assertEqual(set(lines), expected)
                self.assertEqual(len(lines), len(expected), "List each path only once")

    def test_warns_and_refuses_only_above_the_named_existing_file_limit(self):
        self.assertTrue(SCRIPT.is_file(), "The shaping check command is missing")
        spec = importlib.util.spec_from_file_location("shapecheck_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        limit = getattr(module, "MAX_FILES", None)
        self.assertIsInstance(limit, int, "Expose the existing-file limit as MAX_FILES")
        self.assertGreater(limit, 0)
        files = {"tests/test_%d.py" % n: "# SharedName\n" for n in range(limit)}
        work, _ = make_repo(str(self.tmp), files)
        body = "Change `SharedName`.\n"
        at_limit = self.run_check(work, body)
        self.assertEqual(at_limit.returncode, 0, at_limit.stdout + at_limit.stderr)
        self.assertEqual(set(at_limit.stdout.splitlines()), set(files))
        extra = "tests/helpers.py"
        Path(work, extra).write_text("# SharedName\n")
        run_git(["add", extra], work)
        run_git(["commit", "-qm", "add shared helper"], work)
        above_limit = self.run_check(work, body)
        self.assertNotEqual(above_limit.returncode, 0)
        self.assertRegex(above_limit.stdout + above_limit.stderr, r"(?i)warn")
        self.assertRegex(above_limit.stdout + above_limit.stderr, r"(?i)split")
        self.assertTrue((set(files) | {extra}).issubset(above_limit.stdout.splitlines()))

    def test_dependency_warnings_distinguish_both_limits_and_ignore_json_order(self):
        work, _ = make_repo(str(self.tmp))

        def issue(number, dependencies=()):
            refs = ", ".join(chr(35) + str(n) for n in dependencies) or "none"
            return {"number": number, "body": "Depends on: " + refs + "\n"}

        cases = [
            ("two dependants", [issue(1), issue(2, [1]), issue(3, [1])], False),
            ("three dependants", [issue(1), issue(2, [1]), issue(3, [1]),
                                  issue(4, [1])], True),
            ("three links", [issue(1), issue(2, [1]), issue(3, [2]),
                             issue(4, [3])], False),
            ("four links", [issue(1), issue(2, [1]), issue(3, [2]),
                            issue(4, [3]), issue(5, [4])], True),
        ]
        for label, issues, warning in cases:
            for ordered in (issues, list(reversed(issues))):
                with self.subTest(case=label, order=[i["number"] for i in ordered]):
                    result = self.run_check(work, "Change `AbsentName`.\n", ordered)
                    output = result.stdout + result.stderr
                    self.assertNotIn("Traceback", output)
                    if warning:
                        self.assertRegex(output, r"(?i)warn")
                        self.assertRegex(output, r"(?i)depend|chain|depth")
                    else:
                        self.assertEqual(result.returncode, 0, output)
                        self.assertNotRegex(output, r"(?i)warn")

    def test_shape_skill_runs_the_script_on_drafts_and_records_its_output(self):
        text = (KIT / "skills/shape/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("shapecheck.py", text)
        self.assertIn("## Protected paths this issue may change", text)


class BuildShapecheckTest(FakeClaudeGh):
    issue_view = test_flow.FlowTest.issue_view
    build = test_flow.FlowTest.build
    build_scenario = test_flow.FlowTest.build_scenario
    spy_gh = test_flow.FlowTest.spy_gh

    def setUp(self):
        super().setUp()
        self.work, self.origin = make_repo(
            self.tmp, {"loop.json": settings_json(test_flow.AGENTS)})
        run_git(["push", "origin", "main:loop/main"], self.work)
        patch = mock.patch.object(merge, "merge", return_value=test_flow.MERGED)
        self.merge = patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(merge, "find_pr", return_value={"number": 9})
        patch.start()
        self.addCleanup(patch.stop)

    def late_test(self):
        body = ("Change `InvoiceHandler`.\n\n"
                "## Protected paths this issue may change\nnone\n")
        self.issue_view(body=body)
        # Another piece lands after shaping; the supervisor still has its old tree.
        other = str(Path(self.tmp, "other-piece"))
        run_git(["clone", self.origin, other], self.tmp)
        run_git(["config", "user.name", "Test"], other)
        run_git(["config", "user.email", "t@example.com"], other)
        path = "tests/test_later.py"
        Path(other, "tests").mkdir()
        Path(other, path).write_text("# InvoiceHandler\n")
        run_git(["add", path], other)
        run_git(["commit", "-qm", "add handler coverage"], other)
        run_git(["push", "origin", "HEAD:loop/main"], other)
        self.assertFalse(Path(self.work, path).exists())
        return path

    def test_reports_current_loop_tests_at_start_and_in_build_note(self):
        path = self.late_test()
        sent = self.spy_gh()
        self.build_scenario()
        real_run = flow.session.run

        def run(*args, **kwargs):
            if args[0] == "builder":
                self.assertNotIn(path, kwargs.get("allowed", ()))
                notes = [text for command, text in sent
                         if command[:2] == ["issue", "comment"] and text]
                self.assertTrue(any(path in note for note in notes),
                                "Report the new loop-branch test before building")
            return real_run(*args, **kwargs)

        with mock.patch.object(flow.session, "run", side_effect=run):
            self.assertEqual(self.build().status, "merged")
        notes = [text for command, text in sent
                 if command[:2] == ["issue", "comment"] and text
                 and text.startswith("## Built")]
        self.assertTrue(any(path in note for note in notes),
                        "Keep the build-time shaping check in the build note")
        builder = next(c for c in self.claude_calls() if c["role"] == "builder")
        self.assertNotIn(path, builder["env"]["LOOP_ALLOWED"].splitlines())
        self.assertFalse(any(command[:2] == ["issue", "edit"] and "--body-file" in command
                             for command, _ in sent), "Reporting must not grant a path")

    def test_leaves_late_test_unapproved_and_names_it_when_merge_parks(self):
        path = self.late_test()
        sent = self.spy_gh()
        self.merge.side_effect = test_flow.REAL_MERGE
        self.build_scenario(builder=[{"files": {"app.py": "1\n",
                                               path: "# InvoiceHandler changed\n"}}])
        with mock.patch.object(common, "park", wraps=common.park) as park:
            result = self.build()
        self.assertEqual(result.status, "parked")
        self.assertIn(path, park.call_args.args[1])
        builder = next(c for c in self.claude_calls() if c["role"] == "builder")
        self.assertNotIn(path, builder["env"]["LOOP_ALLOWED"].splitlines())
        notes = [text for command, text in sent
                 if command[:2] == ["issue", "comment"] and text
                 and not text.startswith("TESTS:") and not text.startswith("## Review")]
        self.assertTrue(any(path in note for note in notes),
                        "Preserve the shaping check report even when the build parks")


if __name__ == "__main__":
    unittest.main()
