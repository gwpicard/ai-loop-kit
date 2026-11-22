import json
from pathlib import Path
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
import common
import merge


class LoopSettingsProtectionTest(unittest.TestCase):
    def test_custom_protected_paths_cannot_remove_root_settings_protection(self):
        for name in ("loop.json", "loop.local.json"):
            with self.subTest(path=name), tempfile.TemporaryDirectory() as folder:
                config = {"Test command": "true", "Protected paths": ["secrets/"]}
                files = {"loop.json": json.dumps(config), "loop.local.json": '{"Parallel": 1}'}
                work, _ = make_repo(folder, files)
                protected = common.read_settings(work)["Protected paths"]
                self.assertIsNone(merge.stop_reason("sub/" + name, protected))
                base = common.git(["rev-parse", "HEAD"], cwd=work)
                changed = dict(config, Parallel=2) if name == "loop.json" else {"Parallel": 2}
                Path(work, name).write_text(json.dumps(changed), encoding="utf-8")
                run_git(["add", name], work)
                run_git(["commit", "-m", "Change loop settings"], work)
                head = common.git(["rev-parse", "HEAD"], cwd=work)
                allowed = merge.allowed_paths("## Protected paths this issue may change\n" + name + "\n")
                self.assertIsNone(merge.check_diff(work, base, head, protected, allowed, []))
                self.assertIsNotNone(merge.stop_reason(name, protected),
                                     name + " must remain protected with a custom list")
                other = "loop.local.json" if name == "loop.json" else "loop.json"
                allowed = merge.allowed_paths("## Protected paths this issue may change\n" + other + "\n")
                reason = merge.check_diff(work, base, head, protected, allowed, [])
                self.assertIsNotNone(reason, "permission for the other settings file must not suffice")
                self.assertIn(name, reason)


if __name__ == "__main__":
    unittest.main()
