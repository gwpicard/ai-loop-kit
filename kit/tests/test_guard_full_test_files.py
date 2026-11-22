from kit.tests.test_guard import GuardCase


class TestFullTestFiles(GuardCase):
    def test_listing_every_test_module_gets_the_bare_full_test_refusal(self):
        files = "python3 kit/tests/run.py {files}"
        modules = ("tests/test_app.py", "web/a.spec.js", "lib/util_test.go")
        for role in ("builder", "reviewer", "test-writer", "pass"):
            baseline = self.bash("tests/run-all.sh", role=role,
                                 test="tests/run-all.sh", files=files)
            self.refused(baseline)
            self.assertIn("rule: full-test", baseline.stderr.splitlines())
            for selected in (modules, tuple(reversed(modules))):
                command = files.format(files=" ".join(selected))
                with self.subTest(role=role, command=command):
                    self.allowed(self.bash(command, role=role, test="tests/run-all.sh"))
                    for omitted in range(len(selected)):
                        partial = selected[:omitted] + selected[omitted + 1:]
                        self.allowed(self.bash(files.format(files=" ".join(partial)),
                                               role=role, test="tests/run-all.sh", files=files))
                    result = self.bash(command, role=role, test="tests/run-all.sh", files=files)
                    self.refused(result)
                    self.assertEqual(result.stderr, baseline.stderr)

    def test_test_files_command_without_files_is_a_full_test(self):
        files = "python3 kit/tests/run.py {files}"
        commands = ("python3 kit/tests/run.py", "  python3 kit/tests/run.py  ",
                    "true && python3 kit/tests/run.py", "false || python3 kit/tests/run.py",
                    "python3 kit/tests/run.py; true", "python3 kit/tests/run.py | cat",
                    "true\npython3 kit/tests/run.py")
        for role in ("builder", "reviewer", "test-writer", "pass"):
            for command in commands:
                with self.subTest(role=role, command=command):
                    self.allowed(self.bash(command, role=role, test="tests/run-all.sh"))
                    result = self.bash(command, role=role, test="tests/run-all.sh", files=files)
                    self.refused(result)
                    self.assertIn("rule: full-test", result.stderr.splitlines())
