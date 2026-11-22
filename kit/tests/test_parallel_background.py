"""With Parallel set to one, a pass has an extra slot and replies still build."""
import json
import sys
import threading
from pathlib import Path
from unittest import mock

from kit.tests.test_pass_background import BackgroundPassFixture
import common
import loop


class BuildsBesidePassTest(BackgroundPassFixture):
    def github(self, args, input=None):
        if args[:4] == ["issue", "list", "--state", "open"]:
            rows = [{"number": 1, "title": "Factory", "body": ""}]
            if self.smokes.exists() and not (self.runtime / "build-start.json").exists():
                rows.append({"number": 2, "title": "Resume the piece", "body": "",
                             "labels": [{"name": name} for name in self.labels]})
            return 0, json.dumps(rows), ""
        if args[:3] == ["issue", "view", "2"] and args[-1] == "comments":
            self.reply_read.set()
            return 0, json.dumps({"comments": [
                {"body": "## Needs you\n\nChoose an input?\n\n" + common.MARKER},
                {"body": "Use the first input.", "author": {"login": "maintainer"}}]}), ""
        if args[:1] == ["api"] and "permission" in " ".join(args):
            return 0, '{"permission": "write"}', ""
        if args[:3] == ["issue", "edit", "2"]:
            if "--add-label" in args:
                self.labels.add(args[args.index("--add-label") + 1])
            if "--remove-label" in args:
                self.labels.discard(args[args.index("--remove-label") + 1])
        return super().github(args, input)

    def test_a_reply_starts_a_build_before_the_slow_pass_ends_with_parallel_one(self):
        self.labels = {"needs-user"}
        self.reply_read = threading.Event()
        script = self.runtime / "fake_build.py"
        script.write_text(
            "import json, pathlib, sys\n"
            "sys.path.insert(0, %r)\n"
            "import common\n"
            "root = pathlib.Path(sys.argv[1]) / '.loop'\n"
            "(root / 'build-start.json').write_text(json.dumps({\n"
            "    'replies': json.loads(sys.argv[3]),\n"
            "    'pass_ended': (root / 'smoke-ended').exists(),\n"
            "    'released': (root / 'release-smoke').exists()}))\n"
            "result = pathlib.Path(common.build_file(sys.argv[1], int(sys.argv[2]), 'result'))\n"
            "result.parent.mkdir(exist_ok=True)\n"
            "result.write_text(json.dumps({'last': '#2 merged: done'}))\n"
            "(root / 'stop').touch()\n" % loop.HERE)
        mock.patch.object(loop, "worker_command", side_effect=lambda p, n, r, previous=0: [
            sys.executable, str(script), p, str(n), json.dumps(r)]).start()
        mock.patch.object(loop, "headroom", return_value=None).start()
        mock.patch.object(loop, "sync_default", return_value=False).start()
        mock.patch.object(common, "ready_is_trusted", return_value=True).start()
        mock.patch.object(loop, "POLL", 0.05).start()
        mock.patch.object(loop, "BUSY_POLL", 0.05).start()
        result = []
        thread = threading.Thread(target=lambda: result.append(loop.run(self.work)))
        self.threads.append(thread)
        # The supervisor must finish even when the assertion exposes the inline pass.
        self.addCleanup(lambda: (self.runtime / "stop").touch())
        thread.start()
        self.wait_for(self.starts, "the drain did not start its pass")
        self.wait_for(lambda: (self.runtime / "build-start.json").exists(),
                      "Parallel: 1 did not start a build while the pass occupied its extra slot", seconds=2)
        started = json.loads((self.runtime / "build-start.json").read_text())
        self.assertTrue(self.reply_read.is_set(), "polling did not read the parked issue's reply")
        self.assertEqual(started["replies"], ["Use the first input."])
        self.assertFalse(started["pass_ended"], "the build started after the pass ended")
        self.assertFalse(started["released"], "the build waited for the pass gate")
        self.assertEqual(self.settings["Parallel"], 1)
        self.assertEqual(len(self.workers), 1)
        self.gate.touch()
        thread.join(timeout=8)
        self.assertFalse(thread.is_alive(), "the supervisor did not finish")
        self.assertEqual(result, [0])
