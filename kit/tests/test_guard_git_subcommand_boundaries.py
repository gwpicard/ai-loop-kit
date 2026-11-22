from kit.tests.test_guard import GuardCase


class TestGitSubcommandBoundaries(GuardCase):
    def test_read_only_names_at_the_end_of_the_command_are_allowed(self):
        for role in ("builder", "reviewer", "test-writer", "pass"):
            for command in ("git merge-base", "git merge-tree"):
                with self.subTest(role=role, command=command):
                    self.allowed(self.bash(command, role=role))

    def test_other_hyphenated_commands_keep_their_restrictions(self):
        for role in ("builder", "reviewer", "test-writer", "pass"):
            for command in ("git merge-file a b c", "git merge-index driver",
                            "git merge-recursive a -- b c", "git merge-ours a -- b c",
                            "git merge-subtree a -- b c", "git checkout-index file",
                            "git checkout--worker"):
                with self.subTest(role=role, command=command):
                    self.refused(self.bash(command, role=role), "rule: role-git\n")

    def test_shell_boundaries_keep_bare_merge_restricted(self):
        for role in ("builder", "reviewer", "test-writer", "pass"):
            for command in ("git merge; true", "git merge&&true", "git merge|head",
                            "(git merge)", "git diff $(git merge)"):
                with self.subTest(role=role, command=command):
                    self.refused(self.bash(command, role=role), "rule: role-git\n")
