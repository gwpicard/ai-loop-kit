"""The walk-away preflight looks for the guard hook where sessions load it."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

import agents
import sandbox
import walkaway

LABEL = "the kit guard hook is available to sessions"


def _guard_check(root: Path, guard: Path):
    assert hasattr(sandbox, "guard_path"), "sandbox.guard_path must exist"
    with patch.object(sandbox, "guard_path", return_value=guard), \
            patch.object(agents, "selected", return_value="claude"), \
            patch.object(walkaway.subprocess, "run", return_value=
                         SimpleNamespace(returncode=0, stdout="2.1.285")), \
            patch.object(walkaway.sandbox, "excluded_commands", return_value=[]), \
            patch.object(walkaway.sandbox, "probe", return_value=(True, "ok")), \
            patch.object(walkaway.shutil, "disk_usage", return_value=
                         SimpleNamespace(free=walkaway.MIN_FREE_BYTES)):
        checks = walkaway.preflight(Mock(issues_with_label=Mock(return_value=[])),
                                    root, baseline_checked=True)
    return next(check for check in checks if check[1] == LABEL)


class GuardPathTest(unittest.TestCase):
    def test_D1_guard_at_the_helper_path_passes_without_a_kit_folder(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            guard = Path(temporary) / "plugin" / "hooks" / "guard.py"
            guard.parent.mkdir(parents=True)
            guard.write_text("# guard\n")
            self.assertFalse((root / "kit").exists())
            ok, label, _ = _guard_check(root, guard)
            self.assertEqual(label, LABEL)
            self.assertTrue(ok)

    def test_D1_the_default_guard_path_is_the_hook_beside_the_scripts(self):
        self.assertTrue(hasattr(sandbox, "guard_path"), "sandbox.guard_path must exist")
        expected = Path(sandbox.__file__).resolve().parents[1] / "hooks" / "guard.py"
        self.assertEqual(sandbox.guard_path(), expected)

    def test_D2_missing_guard_fails_and_names_reinstalling_the_plugin(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            ok, _, step = _guard_check(root, Path(temporary) / "plugin" / "hooks" / "guard.py")
            self.assertFalse(ok)
            self.assertIn("reinstall the ai-loop-kit plugin", step)
            self.assertNotIn("kit/hooks/guard.py", step)

    def test_D2_a_guard_in_the_project_kit_folder_does_not_satisfy_the_check(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            (root / "kit" / "hooks").mkdir(parents=True)
            (root / "kit" / "hooks" / "guard.py").write_text("# guard\n")
            ok, _, _ = _guard_check(root, Path(temporary) / "plugin" / "hooks" / "guard.py")
            self.assertFalse(ok)

    def test_D3_session_settings_use_the_helper_path_in_the_hook_command(self):
        self.assertTrue(hasattr(sandbox, "guard_path"), "sandbox.guard_path must exist")
        with TemporaryDirectory() as temporary:
            marker = Path(temporary) / "elsewhere" / "marker-guard.py"
            with patch.object(sandbox, "guard_path", return_value=marker):
                settings = sandbox.session_settings(Path(temporary), walk_away=False)
        commands = [hook["command"] for entry in settings["hooks"]["PreToolUse"]
                    for hook in entry["hooks"]]
        self.assertEqual(len(commands), 1)
        self.assertIn(f'"{marker}"', commands[0])

    def test_D4_result_does_not_depend_on_hooks_json(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            hooks = Path(temporary) / "plugin" / "hooks"
            hooks.mkdir(parents=True)
            for has_guard in (False, True):
                for manifest in (None, "{}", json.dumps({"command": "guard.py"})):
                    with self.subTest(guard=has_guard, manifest=manifest):
                        guard = hooks / "guard.py"
                        config = hooks / "hooks.json"
                        if has_guard:
                            guard.write_text("# guard\n")
                        else:
                            guard.unlink(missing_ok=True)
                        if manifest is None:
                            config.unlink(missing_ok=True)
                        else:
                            config.write_text(manifest)
                        ok, _, _ = _guard_check(root, guard)
                        self.assertEqual(ok, has_guard)


if __name__ == "__main__":
    unittest.main()
