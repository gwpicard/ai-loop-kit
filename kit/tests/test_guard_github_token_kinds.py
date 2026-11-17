from kit.tests.test_guard import GuardCase


class TestGithubTokenKinds(GuardCase):
    def test_other_github_token_prefixes_refused(self):
        for prefix in ["gh" + "s_", "gh" + "o_", "gh" + "u_", "gh" + "r_"]:
            token = prefix + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
            with self.subTest(prefix=prefix):
                r = self.call("Write", {"file_path": "docs/n.md", "content": "t=" + token + "\n"})
                self.refused(r, "secret")
