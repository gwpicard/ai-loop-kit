"""Exercise the default plugin with the optional files physically absent."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import git
from run_fixtures import RunFixture

ROOT = Path(__file__).resolve().parents[1]


class ExtrasTest(unittest.TestCase):
    def test_core_refuses_gauntlet_before_ready_claim_or_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "kit"
            shutil.copytree(ROOT / "kit", core, ignore=shutil.ignore_patterns("__pycache__"))
            script = r'''
import sys
from unittest.mock import patch
from helpers import Project, SPEC
sys.path.insert(0, sys.argv[1])
import gate
import run
import run_cli
from loopkit import Refused, last_record, record_text
p = Project()
try:
    n = p.piece()
    gate.move(p.gh, p.root, n, "ready")
    original = last_record(p.gh.comments(n), "ready")
    for optional in ({"kind": "gauntlet", "checks": []},
                     {"checks": [{"type": "critics", "capture": "render"}]},
                     {"checks": [original["checks"][0], {"type": "critics"}]}):
        ready = {**original, **optional}
        p.gh.comment(n, record_text(ready, "Frozen critics check"))
        before = run.sh(["git", "worktree", "list", "--porcelain"], p.root).stdout
        with patch.object(gate, "move") as move, patch.object(run, "build_claimed") as launch:
            try:
                run.build_piece(p.gh, p.root, n, attempts=1)
            except Refused as error:
                assert "gauntlet critics extra is not installed" in error.reason, error.reason
                assert "/plugin install ai-loop-kit-extras@ai-loop-kit" in error.next_step
                assert "AI_LOOP_KIT_EXTRAS_ROOT" in error.next_step
            else:
                raise AssertionError("missing gauntlet critics extra was not refused before claim")
            move.assert_not_called()
            launch.assert_not_called()
        assert before == run.sh(["git", "worktree", "list", "--porcelain"], p.root).stdout
        assert not run._run_metrics_path(p.root, n).exists()
        with patch.object(gate, "sh") as shell:
            try:
                gate.move(p.gh, p.root, n, "building")
            except Refused as error:
                assert "gauntlet critics extra is not installed" in error.reason
            else:
                raise AssertionError("direct claim accepted the missing critics extra")
            shell.assert_not_called()
        assert gate.state_of(p.gh.issue(n)) == "ready"
        with patch.object(run_cli, "repo_root", return_value=p.root), \
                patch.object(run_cli, "GitHub", return_value=p.gh), \
                patch.object(gate, "doctor") as doctor:
            assert run.main([str(n), "--walk-away"]) == 2
            doctor.assert_not_called()
    for judge in ("Kind: gauntlet\nCapture: render\nReference: ref.txt\n"
                  "Criteria:\n- Readable\nFiles:\n- render.py\n",
                  "## Exit\n### Critics\nCapture: render\nReference: ref.txt\n"
                  "Criteria:\n- Readable\nFiles:\n- render.py\n"):
        body = SPEC[:SPEC.index("## Judge")] + judge
        if judge.startswith("Kind:"):
            body = SPEC[:SPEC.index("## Judge")] + "## Judge\n" + judge
        number = p.piece(spec=body)
        with patch.object(gate, "sh") as shell:
            try:
                gate.check_ready(p.gh, p.root, p.gh.issue(number))
            except Refused as error:
                assert "gauntlet critics extra is not installed" in error.reason, error.reason
            else:
                raise AssertionError("ready accepted the missing critics extra")
            shell.assert_not_called()
    assert "critic" not in sys.modules
finally:
    p.close()
'''
            env = {**os.environ, "PYTHONPATH": str(ROOT / "tests")}
            env.pop("AI_LOOP_KIT_EXTRAS_ROOT", None)
            result = subprocess.run([sys.executable, "-c", script, str(core / "scripts")],
                                    capture_output=True, text=True, env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_core_refuses_mutation_before_ready_claim_or_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "kit"
            shutil.copytree(ROOT / "kit", core, ignore=shutil.ignore_patterns("__pycache__"))
            self.assertFalse((core.parent / "extras").exists())
            script = '''
import sys
from unittest.mock import patch
from helpers import Project
sys.path.insert(0, sys.argv[1])
import gate
import run
from loopkit import Refused, last_record, record_text
p = Project()
try:
    p.loop_section("true")
    n = p.piece()
    gate.move(p.gh, p.root, n, "ready")
    ready = last_record(p.gh.comments(n), "ready")
    ready["quality"] = ['python3 "$AI_LOOP_KIT_ROOT/quality/mutmut-check.py" origin/main']
    p.gh.comment(n, record_text(ready, "Frozen mutation check"))
    before = run.sh(["git", "worktree", "list", "--porcelain"], p.root).stdout
    with patch.object(gate, "move") as move, patch.object(run, "build_claimed") as launch:
        try:
            run.build_piece(p.gh, p.root, n, attempts=1)
        except Refused as error:
            assert "mutation extra is not installed" in error.reason, error.reason
            assert "/plugin install ai-loop-kit-extras@ai-loop-kit" in error.next_step
            assert "AI_LOOP_KIT_EXTRAS_ROOT" in error.next_step
        else:
            raise AssertionError("missing mutation extra was not refused before claim")
        move.assert_not_called()
        launch.assert_not_called()
    assert before == run.sh(["git", "worktree", "list", "--porcelain"], p.root).stdout
    assert not run._run_metrics_path(p.root, n).exists()
    with patch.object(gate, "sh") as shell:
        try:
            gate.move(p.gh, p.root, n, "building")
        except Refused as error:
            assert "mutation extra is not installed" in error.reason
        else:
            raise AssertionError("direct claim accepted the missing extra")
        shell.assert_not_called()
    assert gate.state_of(p.gh.issue(n)) == "ready"
    import run_cli
    with patch.object(run_cli, "repo_root", return_value=p.root), \
            patch.object(run_cli, "GitHub", return_value=p.gh), \
            patch.object(gate, "doctor") as doctor:
        assert run.main([str(n), "--walk-away"]) == 2
        doctor.assert_not_called()
    agents = p.root / "AGENTS.md"
    agents.write_text(agents.read_text() + "Quality: python3 mutmut-changed.py origin/main\\n")
    with patch.object(gate, "sh") as shell:
        try:
            gate.check_ready(p.gh, p.root, p.gh.issue(n))
        except Refused as error:
            assert "mutation extra is not installed" in error.reason
        else:
            raise AssertionError("ready accepted the missing extra")
        shell.assert_not_called()
    import extras
    legacy = {"kind": "goal", "command": "",
              "measure": "python3 mutmut-check.py origin/main"}
    try:
        extras.require_extras(legacy)
    except Refused as error:
        assert "mutation extra is not installed" in error.reason
    else:
        raise AssertionError("legacy goal record with a mutation measure was accepted")
finally:
    p.close()
'''
            env = {**os.environ, "PYTHONPATH": str(ROOT / "tests")}
            env.pop("AI_LOOP_KIT_EXTRAS_ROOT", None)
            result = subprocess.run([sys.executable, "-c", script, str(core / "scripts")],
                                    capture_output=True, text=True, env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(
                [sys.executable, str(core / "quality" / "mutmut-check.py"), "--help"],
                capture_output=True, text=True, env=env, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("mutation extra is not installed", result.stderr)
            self.assertIn("/plugin install ai-loop-kit-extras@ai-loop-kit", result.stderr)


class FullBundleTest(RunFixture, unittest.TestCase):
    def test_separate_critics_install_uses_its_own_code_and_brief(self):
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "kit"
            optional = Path(temporary) / "installed-extra"
            shutil.copytree(ROOT / "kit", core, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "extras", optional,
                            ignore=shutil.ignore_patterns("__pycache__", "tests"))
            script = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import gate
import run
from extras import critics, critics_root
from loopkit import Refused
root = Path(sys.argv[2])
critic = critics()
assert Path(critic.__file__) == critics_root() / "scripts/critic.py"
(root / "ours.txt").write_text("ours")
(root / "reference.txt").write_text("reference")
answers = []
def session(prompt):
    answers.append(prompt)
    return ('<verdict>{"winner":"A","reasons":{"Readable":'
            '{"winner":"A","reason":"clear"}}}</verdict>')
results = critic.judge(root, ["ours.txt"], "reference.txt", ["Readable"], session=session)
assert len(results) == len(answers) == 3
assert all("Readable" in prompt for prompt in answers)
assert all(result["winner"] in {"ours", "reference"} for result in results)
(critics_root() / "briefs/critic.md").unlink()
try:
    critics()
except Refused as error:
    assert "gauntlet critics extra is not installed" in error.reason
else:
    raise AssertionError("an incomplete critics extra was accepted")
'''
            env = {**os.environ, "AI_LOOP_KIT_EXTRAS_ROOT": str(optional)}
            result = subprocess.run([sys.executable, "-c", script, str(core / "scripts"),
                                     str(Path(temporary))], capture_output=True, text=True,
                                    env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_mutation_quality_keeps_the_existing_command_path(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() +
                          'Quality: python3 "$AI_LOOP_KIT_ROOT/quality/mutmut-check.py" --help\n')
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Configure mutation Quality")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("Validate mutmut and run the changed-function mutation check", body)

    def test_explicit_extra_path_works_for_separately_installed_plugins(self):
        from unittest.mock import patch

        import loopkit
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "core"
            optional = Path(temporary) / "installed-extra"
            shutil.copytree(ROOT / "kit", core, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "extras", optional)
            with patch.dict(os.environ, {"AI_LOOP_KIT_EXTRAS_ROOT": str(optional)}):
                code, output = loopkit.run_judge(
                    self.p.root, f'python3 "{core}/quality/mutmut-changed.py" --help')
                self.assertEqual(code, 0, output)
                self.assertIn("Run mutmut only for functions touched since a base ref", output)
            with patch.dict(os.environ, {"AI_LOOP_KIT_EXTRAS_ROOT": str(optional / "absent")}), \
                    self.assertRaisesRegex(loopkit.Refused, "mutation extra is not installed"):
                loopkit.run_judge(self.p.root, 'python3 mutmut-check.py --help')


if __name__ == "__main__":
    unittest.main()
