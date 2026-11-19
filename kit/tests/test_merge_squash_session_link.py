import os
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
import common
import merge

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"
# Built at run time so that no tracked file holds a literal session link.
LINK = "https://claude.ai/code/" + "session_01AbCdEf"
FOOTER = "\U0001F916 Generated with [Claude Code](https://claude.com/claude-code)"


class SquashSessionLinkTest(unittest.TestCase):
    def test_session_link_and_generated_footer_are_not_in_the_squash_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _ = make_repo(tmp, {"AGENTS.md": AGENTS, "app.py": "x = 1\n"})
            run_git(["push", "origin", "main:loop/main"], work)
            run_git(["checkout", "-b", "issue/1", "main"], work)
            with open(os.path.join(work, "app.py"), "w") as f:
                f.write("x = 2\n")
            run_git(["add", "-A"], work)
            run_git(["commit", "-m", "real change\n\n" + FOOTER + "\n\n" + LINK], work)
            sha = common.git(["rev-parse", "HEAD"], cwd=work)
            body = merge.squash_body(work, "loop/main", sha)
        self.assertIn("real change", body)
        self.assertNotIn("claude.ai/code/session_", body)
        self.assertNotIn("Generated with", body)


if __name__ == "__main__":
    unittest.main()
