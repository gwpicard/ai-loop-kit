from kit.tests.test_guard import GuardCase


class TestRmtreeText(GuardCase):
    def assert_searches_allowed(self, commands):
        for role in (None, "builder"):
            for command in commands:
                with self.subTest(role=role, command=command):
                    self.allowed(self.bash(command, role=role))

    def test_rg_patterns_are_allowed(self):
        self.assert_searches_allowed((
            "rg -n 'def scratch_tree|rmtree|TemporaryDirectory' kit/scripts/common.py",
            'rg -e "rmtree" -n kit/hooks/guard.py',
        ))

    def test_grep_patterns_are_allowed(self):
        self.assert_searches_allowed((
            "grep -n 'rmtree' kit/scripts/common.py",
            'grep -n -e "rmtree(" kit/hooks/guard.py',
        ))

    def test_git_grep_patterns_are_allowed(self):
        self.assert_searches_allowed((
            "git grep -n 'rmtree' -- kit/scripts",
            'git -C . grep -e "rmtree(" -- kit/hooks',
        ))

    def test_sed_read_only_arguments_are_allowed(self):
        self.assert_searches_allowed((
            "sed -n '/rmtree/p' kit/scripts/common.py",
            'sed -n -e "/def scratch_tree/,/rmtree/p" kit/scripts/common.py',
        ))

    def test_git_log_pickaxe_arguments_are_allowed(self):
        self.assert_searches_allowed((
            "git log -S'rmtree' -- kit/scripts/common.py",
            'git -C . log --oneline -S "rmtree(" -- kit/hooks/guard.py',
        ))

    def test_python_calls_are_still_refused(self):
        # These strings go to the hook as JSON; Python never executes their bodies.
        for interpreter in ("python3", "python"):
            for command in (
                interpreter + " -c 'import shutil; shutil.rmtree(\"x\")'",
                interpreter + " <<EOF\nimport shutil\nshutil.rmtree('x')\nEOF",
                interpreter + " - <<'EOF'\nfrom shutil import rmtree\nrmtree('x')\nEOF",
                "printf '%s\\n' 'import shutil; shutil.rmtree(\"x\")' | " + interpreter,
                "cat <<'EOF' | " + interpreter + " -\nimport shutil\nshutil.rmtree('x')\nEOF",
            ):
                for role in (None, "builder"):
                    with self.subTest(role=role, command=command):
                        self.refused(self.bash(command, role=role), "rule: recursive-delete\n")
