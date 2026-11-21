from kit.tests.test_guard import GuardCase
from kit.tests import test_codex_hooks


DATA = (
    "rg -n 'gh\\(|git push' kit",
    'grep "gh pr merge" README.md',
    "sed -n '/gh(/p; /git_push/p' kit/hooks/guard.py",
    'grep "say \\"gh pr merge\\"" README.md',
    "cat <<EOF\ngh pr merge\ngit push origin feature\nEOF",
    "cat <<'EOF'\ngh pr merge\ngit push origin feature\nEOF",
    'cat <<"EOF"\ngh pr merge\nEOF',
    "cat <<-EOF\n\tgh pr merge\n\tgit push origin feature\n\tEOF",
    "cat <<'FIRST' <<SECOND\ngh pr merge\nFIRST\ngit push\nSECOND",
    "cat <<END-NOTES\ngh pr merge\nEND-NOTES",
    "cat <<<'gh pr merge'",
    "cat <<EOF\n'\nEOF\ngrep 'gh pr merge' README.md",
)


class TestShellData(GuardCase):
    def test_quoted_arguments_and_heredoc_bodies_are_data_in_every_role(self):
        for role in ("builder", "test-writer", "reviewer", "pass"):
            for command in DATA:
                with self.subTest(role=role, command=command):
                    self.allowed(self.bash(command, role=role))

    def test_file_content_in_a_heredoc_is_data(self):
        for role, path in (("builder", "notes.md"), ("test-writer", "notes.md"),
                           ("reviewer", "/tmp/notes.md"), ("pass", ".loop/pass/notes.md")):
            with self.subTest(role=role):
                self.allowed(self.bash("cat > %s <<'EOF'\ngh pr merge\nEOF" % path, role=role))

    def test_commands_after_data_are_still_refused(self):
        for data in DATA:
            self.allowed(self.bash(data, role="builder"))
            for suffix in ("\ngh pr list", "\ngit push origin feature"):
                with self.subTest(data=data, suffix=suffix):
                    self.refused(self.bash(data + suffix, role="builder"), "role-git")

    def test_shells_and_command_runners_keep_their_input_executable(self):
        for role in ("builder", "test-writer", "reviewer", "pass"):
            self.allowed(self.bash("grep 'bash gh pr merge' README.md", role=role))
            for runner in ("sh", "bash", "zsh", "dash", "eval", "xargs", "env bash", "env -i /bin/sh", "FOO=x bash", "/bin/sh"):
                for command in (runner + " -c 'gh pr merge 1'",
                                runner + " <<EOF\ngit push origin feature\nEOF",
                                "cat <<EOF | " + runner + "\ngh pr merge 1\nEOF",
                                "echo 'gh pr merge 1' | " + runner):
                    with self.subTest(role=role, command=command):
                        self.refused(self.bash(command, role=role), "role-git")

    def test_command_substitution_inside_double_quotes_still_runs(self):
        for command in ('echo "$(gh pr merge 1)"', 'echo "`git push origin feature`"', 'x="a $(gh pr list)"'):
            with self.subTest(command=command):
                self.refused(self.bash(command, role="reviewer"), "role-git")
        self.allowed(self.bash("echo '$(gh pr merge 1)'", role="reviewer"))  # single quotes do not substitute

    def test_real_commands_outside_quotes_are_refused_in_every_role(self):
        for role in ("builder", "test-writer", "reviewer", "pass"):
            self.allowed(self.bash("grep 'gh pr merge' README.md", role=role))
            for prefix in ("", "echo ok && ", "echo ok; ", "echo ok | ", "echo $(", "true && \\\n"):
                for command in ("gh pr list", "git push origin feature"):
                    with self.subTest(role=role, prefix=prefix, command=command):
                        self.refused(self.bash(prefix + command + (")" if "$(" in prefix else ""), role=role), "role-git")


class TestCodexShellData(GuardCase):
    guard = test_codex_hooks.CodexGuardTest.guard

    def test_codex_shell_data_is_allowed_as_text_or_an_argument_list(self):
        for command in DATA:
            for payload in (command, ["/bin/bash", "-lc", command]):
                with self.subTest(payload=payload):
                    self.allowed(self.guard({"tool_name": "Bash", "tool_input": {"command": payload}}))
        for command in ("gh pr list", "git push origin feature", "bash -c 'gh pr merge 1'"):
            self.refused(self.guard({"tool_name": "Bash", "tool_input": {"command": ["/bin/bash", "-lc", command]}}), "role-git")
