"""The final pull request distinguishes a pending summary from a failed one."""
import json
from pathlib import Path
from unittest import mock

from kit.tests.fake_claude import FAKE_CLAUDE
from kit.tests.helpers import write_exe
from kit.tests.test_pass_background import BackgroundPassFixture
import loop
import report


SUMMARY = ("## Summary\n\nThe list loads.\n\n## Evidence\n\n"
           "test_list_loads passes.\n\n## Merge danger\n\nTwo-way door.\n")


class WorkerSummaryTest(BackgroundPassFixture):
    def setUp(self):
        super().setUp()
        self.body = ""
        self.summary_started = self.runtime / "summary-started"
        self.summary_gate = self.runtime / "release-summary"
        gate = ("\nif '## Summary' in prompt and '## Merge danger' in prompt:\n"
                "    from pathlib import Path\n"
                "    Path(%r).touch()\n"
                "    until = time.monotonic() + 20\n"
                "    while not Path(%r).exists() and time.monotonic() < until:\n"
                "        time.sleep(0.02)\n" % (str(self.summary_started), str(self.summary_gate)))
        write_exe(str(Path(self.tmp, "bin", "claude")),
                  FAKE_CLAUDE.replace("prompt = sys.stdin.read()", "prompt = sys.stdin.read()" + gate))
        self.claude({"pass": [{"reply": SUMMARY}]})
        mock.patch.object(loop.merge, "run_tests", return_value=None).start()

    def finish(self):
        self.summary_gate.touch()
        super().finish()

    def github(self, args, input=None):
        if args[:2] == ["pr", "view"]:
            self.inputs.append((args, input))
            return 0, json.dumps({"body": self.body}), ""
        if args[:2] in (["pr", "edit"], ["pr", "create"]):
            self.body = input
        return super().github(args, input)

    def drain_until_pending(self):
        done = self.begin_drain()
        self.wait_for(self.starts, "the worker did not reach the smoke command")
        self.assertTrue(done.wait(6), "the drain waited for the worker")
        self.assertEqual(self.errors, [])
        self.gate.touch()
        self.wait_for(self.summary_started.exists, "the worker did not start writing the summary", seconds=15)
        self.assertIsNone(self.workers[0].poll())
        return self.body

    def complete_worker(self):
        self.summary_gate.touch()
        for worker in self.workers:
            self.assertEqual(worker.wait(timeout=15), 0)
        self.collect(lambda: not self.st.get("pass"))
        return self.body

    def assert_pending(self, body):
        self.assertNotIn("The summary did not run.", body)
        self.assertRegex(body.lower(), r"summary[^\n]*(being written|in progress|pending)")

    def test_pending_body_becomes_the_summary_and_keeps_the_report(self):
        text = report.render(self.work, self.settings)
        pending = self.drain_until_pending()
        with self.subTest(stage="pending"):
            self.assert_pending(pending)
        body = self.complete_worker()
        with self.subTest(stage="completed"):
            self.assertIn(SUMMARY.strip(), body)
            self.assertNotIn("The summary did not run.", body)
            self.assertIn("## What changed\n\n```text\n" + text + "\n```", body)
            self.assertLess(body.index("## What changed"), body.index("## Hands-on checks"))
            for section in ("## Summary", "## Evidence", "## Merge danger", "## Hands-on checks",
                            "## Decisions to confirm", "## Landed", "## End-of-loop pass"):
                self.assertEqual(body.count(section), 1, section)

    def test_only_a_failed_summary_gets_the_failure_text(self):
        self.claude({"pass": [{"reply": "Summary unavailable."}]})
        pending = self.drain_until_pending()
        with self.subTest(stage="pending"):
            self.assert_pending(pending)
        body = self.complete_worker()
        with self.subTest(stage="failed"):
            self.assertEqual(body.count("The summary did not run."), 1)
            self.assertNotIn("## Summary", body)
            self.assertIn("## Landed", body)
            self.assertEqual(loop.cached_summary(self.work), {"head": self.head, "text": ""})

    def test_an_older_summary_is_not_presented_as_the_current_heads_summary(self):
        (self.runtime / "summary.json").write_text(json.dumps({
            "head": "0" * 40, "text": SUMMARY.replace("The list loads.", "OLD SUMMARY.")}))
        pending = self.drain_until_pending()
        with self.subTest(stage="pending"):
            self.assert_pending(pending)
            self.assertNotIn("OLD SUMMARY.", pending)
        body = self.complete_worker()
        with self.subTest(stage="completed"):
            self.assertIn(SUMMARY.strip(), body)
            self.assertNotIn("OLD SUMMARY.", body)
