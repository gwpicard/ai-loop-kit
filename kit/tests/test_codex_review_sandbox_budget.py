"""A reviewer blocked by the sandbox has not found an issue defect."""
import json
import os
from pathlib import Path
import unittest

from kit.tests import test_flow
from kit.tests.fake_codex_check import FAKE, FakeCodexCheck
from kit.tests.helpers import run_git, write_exe


class ReviewSandboxBudgetTest(test_flow.FlowTest, FakeCodexCheck):
    def test_sandbox_refusal_does_not_use_up_review_rounds(self):
        settings = json.loads(Path(self.work, "loop.json").read_text())
        settings.update({"Reviewer": "codex gpt-6", "Max rounds": 2})
        Path(self.work, "loop.json").write_text(json.dumps(settings))
        run_git(["commit", "-qam", "configure Codex reviewer"], self.work)
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        fake = FAKE.replace('reply = step.get("reply", "ok")',
                            'reply = step.get("reply", "ok").replace("{HEAD}", '
                            'subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())')
        write_exe(os.path.join(self.tmp, "bin/codex"), fake)
        self.claude({"test-writer": [test_flow.WRITER],
                     "builder": [{"files": {"app.py": "1\n"}}]})
        self.codex([{"reply": "The sandbox blocked the focused test command: unable to make "
                               "temporary file: Operation not permitted. No code defect was verified.\n"
                               "VERDICT: CHANGES\nHEAD: {HEAD}\n\n"
                               "1. Unverified: the sandbox blocked the test command.\n"}])
        result = self.build()
        self.assertNotIn("did not pass review in", result.reason,
                         "a sandbox refusal must not exhaust the issue's round budget")
        self.assertIn("sandbox", result.reason.lower())
        self.assertIn(result.status, ("parked", "failed"))
        self.assertEqual([call["role"] for call in self.claude_calls()], ["test-writer", "builder"],
                         "do not send sandbox refusals to the builder as code fixes")
        self.merge.assert_not_called()


for _name in dir(ReviewSandboxBudgetTest):
    if _name.startswith("test_") and _name not in vars(ReviewSandboxBudgetTest):
        setattr(ReviewSandboxBudgetTest, _name, None)


if __name__ == "__main__":
    unittest.main()
