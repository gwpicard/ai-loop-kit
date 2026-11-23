import json
from pathlib import Path
import subprocess
import unittest

from kit.tests.helpers import FakeGh, make_repo


KIT = Path(__file__).resolve().parents[1]


class StatusReadFailuresTest(FakeGh):
    def test_json_reports_only_local_throughput_without_github(self):
        work, _ = make_repo(self.tmp, {"loop.json": '{"Test command": "true"}'})
        result = subprocess.run([str(KIT / "bin/loop"), "status", "--json"],
                                cwd=work, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(set(json.loads(result.stdout)), {"throughput"})
        self.assertEqual(self.calls(), [])

    def test_failed_github_read_reports_unavailable_instead_of_no_parks(self):
        work, _ = make_repo(self.tmp, {"loop.json": '{"Test command": "true"}'})
        self.scenario([dict(match="issue list", responses=[dict(code=1, stderr="offline")])])
        result = subprocess.run([str(KIT / "bin/loop"), "status"],
                                cwd=work, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Open parks: unavailable", result.stdout)
        self.assertNotIn("Open parks: none", result.stdout)


class StartReadFailuresTest(unittest.TestCase):
    def test_start_guidance_reports_work_could_not_be_checked_if_a_source_is_unreadable(self):
        text = (KIT / "skills/loop/SKILL.md").read_text()
        instruction = text.split("After starting the loop,", 1)[1].split("\n\n", 1)[0]
        self.assertIn("If either source cannot be read", instruction)
        self.assertIn("outstanding work could not\nbe checked", instruction)
        self.assertNotIn("before claiming nothing", instruction)
