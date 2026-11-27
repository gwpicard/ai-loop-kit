"""Exercise loop run startup without starting the supervisor's remote work."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from kit.tests.helpers import write_exe


KIT = Path(__file__).resolve().parents[1]

# bin/loop still selects the script and passes the command. The interpreter
# harness runs its real dispatcher, replacing only preflight and the supervisor
# boundary so that no GitHub calls or builds can escape the test.
INTERPRETER = '''#!PYTHON
import json, os, runpy, sys
from unittest import mock
sys.path.insert(0, os.path.dirname(sys.argv[1]))
namespace = runpy.run_path(sys.argv[1], run_name="loop_start_test")
import common, setup
def record(kind, value):
    with open(os.environ["START_EVENTS"], "a") as f:
        f.write(json.dumps([kind, value]) + "\\n")
def supervisor(project):
    record("started", os.getpid())
    return 0
def nice(amount):
    record("nice", amount)
    return 0
original_say = common.say
def say(message):
    record("log", str(message))
    return original_say(message)
namespace["main"].__globals__["run"] = supervisor
namespace["main"].__globals__["say"] = say
with mock.patch.object(common, "kit_version_refusal", return_value=None), \\
     mock.patch.object(common, "say", side_effect=say), \\
     mock.patch.object(common, "record_kit_version"), \\
     mock.patch.object(common, "read_settings", return_value={}), \\
     mock.patch.object(common, "codex_refusal", return_value=None), \\
     mock.patch.object(setup, "tidy", return_value=([], None)), \\
     mock.patch.object(setup, "missing", return_value=None), \\
     mock.patch.object(os, "nice", side_effect=nice):
    sys.platform = os.environ["START_PLATFORM"]
    sys.exit(namespace["main"](sys.argv[2:]))
'''

TASKPOLICY = '''#!PYTHON
import json, os, sys
with open(os.environ["START_EVENTS"], "a") as f:
    f.write(json.dumps(["taskpolicy", sys.argv[1:]]) + "\\n")
if os.environ["START_POLICY"] == "failed":
    print("fake taskpolicy: refused", file=sys.stderr)
    sys.exit(7)
'''


class LoopBackgroundPriorityTest(unittest.TestCase):
    def command(self, platform, policy="ok"):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bindir = root / "bin"
            bindir.mkdir()
            write_exe(str(bindir / "python3"), INTERPRETER)
            (bindir / "dirname").symlink_to("/usr/bin/dirname")
            if policy != "missing":
                write_exe(str(bindir / "taskpolicy"), TASKPOLICY)
            events = root / "events.jsonl"
            env = dict(os.environ, PATH=str(bindir), START_EVENTS=str(events),
                       START_PLATFORM=platform, START_POLICY=policy)
            result = subprocess.run([str(KIT / "bin" / "loop"), "run"],
                                    cwd=root, env=env, capture_output=True,
                                    text=True, timeout=15)
            recorded = [json.loads(line) for line in events.read_text().splitlines()] \
                if events.exists() else []
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return recorded, result.stdout + result.stderr

    def test_mac_keeps_supervisor_at_normal_priority(self):
        events, output = self.command("darwin")
        starts = [value for kind, value in events if kind == "started"]
        self.assertEqual(len(starts), 1, output)
        self.assertEqual(events, [["started", starts[0]]],
                         "Only session children change niceness")

    def test_other_systems_keep_supervisor_niceness(self):
        for platform in ("linux", "freebsd"):
            with self.subTest(platform=platform):
                events, output = self.command(platform)
                starts = [value for kind, value in events if kind == "started"]
                self.assertEqual(len(starts), 1, output)
                self.assertEqual(events, [["started", starts[0]]],
                                 "Only session children change niceness")

    def test_supervisor_does_not_need_taskpolicy(self):
        for policy in ("missing", "failed"):
            with self.subTest(policy=policy):
                events, output = self.command("darwin", policy)
                self.assertEqual(sum(kind == "started" for kind, _ in events), 1,
                                 "A priority failure must not prevent startup: " + output)
                lines = [value for kind, value in events if kind == "log"]
                self.assertEqual(lines, [], output)
                self.assertTrue(all(kind == "started" for kind, _ in events), events)

    def test_readme_explains_session_niceness_and_its_reason_in_one_sentence(self):
        text = " ".join((KIT / "README.md").read_text(encoding="utf-8").split())
        sentences = re.split(r"(?<=[.!?])\s+", text.lower())
        matches = [sentence for sentence in sentences
                   if "os.nice(10)" in sentence
                   and "loop" in sentence]
        self.assertTrue(matches, "Document that the loop starts sessions with raised niceness")
        self.assertTrue(any("responsive" in sentence for sentence in matches),
                        "Explain why in the same sentence")


if __name__ == "__main__":
    unittest.main()
