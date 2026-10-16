"""Keep the shipped kit small and refuse the archived gauntlet preview."""
import unittest
from pathlib import Path

import gate
import loopkit
from helpers import KIT, SPEC


class KitSizeTest(unittest.TestCase):
    def test_python_total_is_below_the_release_baseline(self):
        total = sum(len(path.read_bytes().splitlines()) for path in KIT.rglob("*.py"))
        self.assertLess(total, 5500)

    def test_modules_leave_room_below_the_hard_limit(self):
        for folder in (KIT, KIT.parent / "tests"):
            for path in folder.rglob("*.py"):
                with self.subTest(path=path.relative_to(KIT.parent)):
                    self.assertLess(len(path.read_bytes().splitlines()), 900)

    def test_gauntlet_is_not_shipped(self):
        for name in ("scripts/critic.py", "briefs/critic.md"):
            self.assertFalse((KIT / name).exists(), name)

    def test_legacy_and_exit_specs_name_the_archive(self):
        specs = (
            SPEC + "Kind: gauntlet\nCapture: render\nReference: ref.png\n"
            "Criteria:\n- Readable\n",
            SPEC + "\n## Exit\n### Critics\nCapture: render\nReference: ref.png\n"
            "Criteria:\n- Readable\nFiles:\n- render.py\n",
            SPEC + "\n## Exit\n### Tests\nCommand: test\nFiles: judge.py\n"
            "### Critics\nCapture: render\nReference: ref.png\n"
            "Criteria:\n- Readable\nFiles:\n- render.py\n",
        )
        for body in specs:
            with self.subTest(body=body), self.assertRaisesRegex(
                    loopkit.Refused, "preview/gauntlet"):
                loopkit.parse_spec(body)

    def test_frozen_critic_checks_cannot_run_or_pass(self):
        for kind in ("critics", "critic", "unknown"):
            check = {"type": kind, "capture": "true", "reference": "ref.png",
                     "criteria": ["Readable"]}
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(loopkit.Refused, "unsupported exit check"):
                    loopkit.exit_ready(Path.cwd(), (check,), {"D1": "readable"}, ())
                with self.assertRaisesRegex(loopkit.Refused, "unsupported exit check"):
                    loopkit.exit_attempt(Path.cwd(), [check])

    def test_legacy_ready_record_cannot_pass_the_gate(self):
        passed, reason = gate.judge(Path.cwd(), {"kind": "gauntlet", "files": []})
        self.assertFalse(passed)
        self.assertIn("preview/gauntlet", reason)

    def test_frozen_gauntlet_is_refused_before_claim(self):
        issue = {"number": 1, "body": SPEC}
        for fields in ({"kind": "gauntlet"},
                       {"kind": "checks", "checks": [{"type": "critics"}]}):
            record = {"move": "ready", "spec": loopkit.spec_hash(SPEC), **fields}
            with self.subTest(fields=fields), self.assertRaisesRegex(
                    loopkit.Refused, "preview/gauntlet"):
                gate.check_frozen(issue, [loopkit.record_text(record, "ready")])


if __name__ == "__main__":
    unittest.main()
