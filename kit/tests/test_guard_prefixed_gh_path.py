from kit.tests.test_guard import GuardCase


class TestPrefixedGhPath(GuardCase):
    def test_loop_roles_refuse_a_path_to_gh_after_a_prefix(self):
        for role in ("builder", "test-writer", "reviewer", "pass"):
            for prefix in ("env ", "sudo ", "VAR=value "):
                for path in ("/usr/bin/gh", "./bin/gh"):
                    with self.subTest(role=role, prefix=prefix, path=path):
                        self.allowed(self.bash("cat " + path, role=role))
                        self.refused(self.bash(prefix + path + " pr list",
                                               role=role), "role-git")
