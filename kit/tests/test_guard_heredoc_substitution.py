from kit.tests.test_guard import GuardCase
from kit.tests import test_codex_hooks


class TestHeredocSubstitution(GuardCase):
    def test_unquoted_heredoc_commands_are_refused(self):
        for role in ("builder", "test-writer", "reviewer", "pass"):
            for expression in ("$(git switch feature)", "`git switch feature`"):
                with self.subTest(role=role, expression=expression):
                    self.refused(self.bash("cat <<EOF\n%s\nEOF" % expression,
                                           role=role), "role-git")

    def test_quoted_heredoc_substitutions_remain_literal(self):
        self.allowed(self.bash("cat <<'EOF'\n$(git switch feature)\nEOF",
                               role="builder"))


class TestCodexHeredocSubstitution(GuardCase):
    guard = test_codex_hooks.CodexGuardTest.guard

    def test_unquoted_heredoc_command_is_refused(self):
        command = "cat <<EOF\n$(git switch feature)\nEOF"
        for payload in (command, ["/bin/bash", "-lc", command]):
            with self.subTest(payload=payload):
                self.refused(self.guard({"tool_name": "Bash",
                                         "tool_input": {"command": payload}}), "role-git")
