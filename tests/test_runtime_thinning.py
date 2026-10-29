"""Guard behaviour at the seams shared by the runtime modules."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))

import agents
import gate
import risk_checks
import run
import walkaway
from helpers import GOOD_CODE, Project, git
from loopkit import loop_settings, record_text


class RuntimeThinningTest(unittest.TestCase):
    def test_ready_freezes_one_settings_snapshot(self):
        for prepare in ("", "printf prepared"):
            with self.subTest(prepare=prepare):
                project = Project()
                self.addCleanup(project.close)
                project.loop_section("printf tested", prepare)
                agents_file = project.root / "AGENTS.md"
                agents_file.write_text(agents_file.read_text() +
                    "Keep: printf kept\nQuality: printf first\nQuality: printf second\n"
                    "Standards: STANDARDS.md\nProtected paths: src/private, src/auth\n"
                    "Idle limit: 7\nWaiting limit: 4\nKeep limit: 20\nAgent: CoDeX\n"
                    "Sandbox domains: registry.npmjs.org\nSecret paths: .env, keys\n")
                git(project.root, "add", "AGENTS.md")
                git(project.root, "commit", "--quiet", "-m", "Set loop inputs")
                git(project.root, "push", "--quiet", "origin", "main")
                number = project.piece()
                with patch.object(gate, "loop_settings", wraps=loop_settings) as read:
                    gate.move(project.gh, project.root, number, "ready")
                ready = gate.last_record(project.gh.comments(number), "ready")
                expected = {
                    "test": "printf tested", "prepare": prepare, "keep": "printf kept",
                    "quality": ["printf first", "printf second"],
                    "standards": "STANDARDS.md", "protected_paths": ["src/private", "src/auth"],
                    "idle_limit": "7", "waiting_limit": "4", "keep_limit": "20", "agent": "codex",
                }
                self.assertEqual({key: ready[key] for key in expected}, expected)
                read.assert_called_once_with(project.root)
                settings = loop_settings(project.root)
                self.assertEqual(settings["sandbox domains"], "registry.npmjs.org")
                self.assertEqual(settings["secret paths"], [".env", "keys"])
                folder = run.worktree(project.root, number)
                (folder / "AGENTS.md").write_text("## The loop\nAgent: claude\nKeep: false\n")
                git(folder, "add", "AGENTS.md")
                git(folder, "commit", "--quiet", "-m", "Change loop inputs")
                passed, output = gate.judge(folder, ready)
                self.assertFalse(passed)
                self.assertEqual(output, "the loop settings changed in AGENTS.md")
                self.assertEqual({key: ready[key] for key in expected}, expected)

    def test_ready_retains_setting_defaults(self):
        project = Project()
        self.addCleanup(project.close)
        number = project.piece()
        ready = gate.check_ready(project.gh, project.root, project.gh.issue(number))
        expected = {"test": "printf baseline", "prepare": "", "keep": "", "quality": [],
                    "standards": "",
                    "protected_paths": [], "idle_limit": "10", "waiting_limit": "3",
                    "keep_limit": "15", "agent": "claude"}
        self.assertEqual({key: ready[key] for key in expected}, expected)

    def test_typed_moves_are_reachable(self):
        self.assertLessEqual(gate.NEEDS_TYPE, set(gate.MOVES.values()))

    def test_session_and_gate_share_the_path_predicate(self):
        self.assertIs(getattr(agents, "path_mentioned", None), risk_checks.path_mentioned)

    def test_path_mentions_match_in_session_filtering_and_gate_judgement(self):
        project = Project()
        self.addCleanup(project.close)
        number = project.piece()
        gate.move(project.gh, project.root, number, "ready")
        ready = gate.last_record(project.gh.comments(number), "ready")
        folder = run.worktree(project.root, number)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Implement habits")
        cases = [
            ("habits.py", "habits.py", True),
            ("Change habits.py/child", "habits.py", True),
            ("Change habits.py.bak", "habits.py", False),
            ("Change old-habits.py", "habits.py", False),
            ("Change `habits.py`, please.", "habits.py", True),
            ("Change habits.py/", "habits.py/", True),
            ("Inside src/habits.py we add a habit.", "habits.py", True),
            ("Change habitsXpy", "habits.py", False),
            ("No protected file is named.", "habits.py", False),
        ]
        for text, path, mentioned in cases:
            with self.subTest(text=text, path=path):
                contract = {"D1": text}
                with patch.object(agents, "subprocess") as process:
                    agents.start_session("claude", "brief", folder, role="builder",
                                         protected_paths=[path], contract=contract)
                protected = process.Popen.call_args.kwargs["env"]["LOOP_PROTECTED_PATHS"]
                self.assertEqual(bool(protected), not mentioned)
                passed, output = gate.judge(folder, {
                    **ready, "contract": contract, "protected_paths": [path],
                })
                self.assertEqual(passed, mentioned, output)
                self.assertEqual(risk_checks.path_mentioned(text, path), mentioned)

    def test_report_counts_each_issue_once_across_label_results(self):
        gh = Mock()
        gh.issues_with_label.return_value = [{"number": 1}, {"number": 1}]
        gh.comments.return_value = [
            record_text({"move": "claim"}, "claim"),
            record_text({"move": "give-back", "type": "stopped", "cause": "stopped",
                         "reason": "person requested a stop"}, "give-back"),
        ]
        report = gate.report(gh)
        self.assertIn("stopped: 1\n", report)
        self.assertIn("stopped / stopped: 1\n", report)
        self.assertIn("pieces started: 1\n", report)
        gh.comments.assert_called_once_with(1)

    def test_walkaway_guard_availability_is_independent_of_manifest(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks = root / "kit" / "hooks"
            hooks.mkdir(parents=True)
            for has_guard in (False, True):
                for manifest in (None, '{}', '{"command":"guard.py"}'):
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
                        with patch.object(agents, "selected", return_value="claude"), \
                                patch.object(walkaway.subprocess, "run", return_value=
                                             SimpleNamespace(returncode=0, stdout="2.1.285")), \
                                patch.object(walkaway.sandbox, "excluded_commands",
                                             return_value=[]), \
                                patch.object(walkaway.sandbox, "probe",
                                             return_value=(True, "ok")), \
                                patch.object(walkaway.shutil, "disk_usage", return_value=
                                             SimpleNamespace(free=walkaway.MIN_FREE_BYTES)):
                            checks = walkaway.preflight(
                                Mock(issues_with_label=Mock(return_value=[])),
                                root, baseline_checked=True)
                        available = next(ok for ok, label, _ in checks
                                         if label == "the kit guard hook is available to sessions")
                        self.assertEqual(available, has_guard)
