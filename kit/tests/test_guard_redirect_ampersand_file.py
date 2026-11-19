from kit.tests.test_guard import GuardCase


class TestRedirectAmpersandFile(GuardCase):
    """`>& file` sends stdout and stderr to a file, as `&> file` does."""

    def test_reviewer_cannot_write_through_a_redirect_to_a_file_with_ampersand(self):
        self.refused(self.bash("echo x >& README.md", role="reviewer"))

    def test_pass_role_cannot_write_outside_its_folder_with_ampersand_redirect(self):
        self.refused(self.bash("echo x >& src/app.py", role="pass"))

    def test_descriptor_duplication_is_still_allowed(self):
        self.assertEqual(self.bash("echo x >&2", role="reviewer").returncode, 0)
