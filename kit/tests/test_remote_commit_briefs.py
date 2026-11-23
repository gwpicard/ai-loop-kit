"""Session guidance preserves pushed history and explains squash messages."""
from pathlib import Path
import unittest


BRIEFS = Path(__file__).resolve().parents[1] / "briefs"


class RemoteCommitBriefTest(unittest.TestCase):
    def test_reviewer_does_not_request_issue_branch_message_or_signoff_changes(self):
        text = " ".join((BRIEFS / "reviewer.md").read_text().lower().split())
        self.assertRegex(text, r"squash[- ]merg")
        self.assertRegex(text, r"commit messages?[^.]*never[^.]*loop branch")
        self.assertRegex(text, r"squash commit[^.]*sign-off[^.]*attribution|"
                               r"squash commit[^.]*attribution[^.]*sign-off")
        self.assertRegex(text, r"(?:must not|never|do not)[^.]*ask[^.]*commit[- ]message")
        self.assertRegex(text, r"(?:must not|never|do not)[^.]*ask[^.]*sign-off")

    def test_preamble_forbids_rewriting_remote_commits_by_any_means(self):
        text = " ".join((BRIEFS / "preamble.md").read_text().lower().split())
        self.assertRegex(text, r"(?:never|must not|do not)[^.]*rewrit[^.]*amend[^.]*rebase")
        self.assertRegex(text, r"commits?[^.]*(?:remote|pushed)")
        self.assertRegex(text, r"by any means|through any means|regardless of (?:the )?(?:tool|method)")
