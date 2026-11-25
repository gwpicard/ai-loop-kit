from kit.tests import test_codex_hooks
from kit.tests.test_guard import GuardCase


class TestPrefixOptionArguments(GuardCase):
    guard = test_codex_hooks.CodexGuardTest.guard

    def test_prefix_options_with_separate_values_cannot_hide_gh(self):
        for agent in ("claude", "codex"):
            for role in ("builder", "test-writer", "reviewer", "pass"):
                for prefix in ("sudo -u root", "env -u UNUSED",
                               "sudo --user root", "env --unset UNUSED",
                               "env -u UNUSED sudo -u root"):
                    with self.subTest(agent=agent, role=role, prefix=prefix):
                        command = prefix + " /usr/bin/gh pr list"
                        self.refused(self.guard(
                            {"tool_name": "Bash", "tool_input": {"command": command}},
                            role=role, agent=agent), "role-git")

    def test_gh_path_as_an_argument_after_prefix_options_stays_data(self):
        for agent in ("claude", "codex"):
            for role in ("builder", "test-writer", "reviewer", "pass"):
                for prefix in ("sudo -u root", "env -u UNUSED"):
                    with self.subTest(agent=agent, role=role, prefix=prefix):
                        command = prefix + " cat /usr/bin/gh"
                        self.allowed(self.guard(
                            {"tool_name": "Bash", "tool_input": {"command": command}},
                            role=role, agent=agent))
