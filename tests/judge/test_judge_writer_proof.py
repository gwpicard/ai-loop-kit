"""The judge writer proves its judge on the base before it hands back to the shaper."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import GOOD_CODE, KIT, Project, git

# isort: split

import test_text_budgets
import errors
from loopkit import Refused, exit_ready

ROOT = Path(__file__).resolve().parents[2]
JUDGE = "judge_habits.py"
BODY = """## Intent
Add a habit.

Out of scope:
- Anything else.

## Contract
- D1: adding a habit appends it.

## Exit
### Tests
Command: `python3 judge_habits.py`
Files:
- judge_habits.py

## Risks
Protected paths: none
New dependency: none
Shared files: none
Needs services: none
Open choices: none
Depends on: {depends}
"""
# Fails by assertion naming D1, as a real judge does.
RIGHT = 'import sys\nprint("FAIL test_D1_add AssertionError add is missing")\nsys.exit(1)\n'
# Fails with an AttributeError, which the ready check refuses as the wrong reason.
WRONG = 'import sys\nprint("FAIL test_D1_add AttributeError no attribute add")\nsys.exit(1)\n'
FAKE_AGENT = """#!{python}
import json, os, pathlib, sys
state = pathlib.Path(os.environ['STATE'])
calls = state / 'calls'
number = (int(calls.read_text()) if calls.exists() else 0) + 1
calls.write_text(str(number))
(state / f'prompt-{{number}}.txt').write_text(sys.stdin.read())
rounds = json.loads(os.environ['ROUNDS'])
if number > len(rounds):
    sys.exit(1)
step = rounds[number - 1]
for name, text in step['writes'].items():
    path = pathlib.Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
verdict = {{'judge_files': step.get('files', ['judge_habits.py']),
           'tests_per_id': step.get('tests_per_id', True), 'notes': step['notes']}}
text = '<verdict>' + json.dumps(verdict) + '</verdict>'
print(json.dumps({{'type': 'assistant', 'message': {{'content': [{{'type': 'text', 'text': text}}]}}}}))
"""
FAKE_GH = """#!/bin/sh
# Answers `gh issue view <n> --json ...` from the files in $GHDATA.
if [ "$1" = issue ] && [ "$2" = view ] && [ -f "$GHDATA/issue-$3.json" ]; then
    cat "$GHDATA/issue-$3.json"
    exit 0
fi
echo "unexpected gh call: $*" >&2
exit 1
"""


def step(judge, notes, **extra):
    return {"writes": {JUDGE: judge}, "notes": notes, **extra}


class JudgeProofTest(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)
        self.root = self.project.root
        self.base = self.root.parent
        self.project.loop_section("printf baseline")
        git(self.root, "switch", "--quiet", "-c", "piece/1")
        self.data = {"Intent": "Add a habit", "Approach": "",
                     "Contract": "D1: adding a habit appends it.", "Files": JUDGE}
        self.state = self.base / "state"
        self.state.mkdir()
        self.ghdata = self.base / "ghdata"
        self.ghdata.mkdir()
        self.fake_agent = self.base / "fake-agent"
        self.fake_agent.write_text(FAKE_AGENT.format(python=sys.executable))
        self.fake_agent.chmod(0o755)
        bindir = self.base / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.path = f"{bindir}:{os.environ['PATH']}"
        self.issue(1, BODY.format(depends="none"), "state:shaping")

    def issue(self, number, body, label):
        (self.ghdata / f"issue-{number}.json").write_text(json.dumps({
            "number": number, "title": f"Piece {number}", "body": body,
            "labels": [{"name": label}], "state": "OPEN"}))

    def launch(self, rounds, *flags):
        source = self.base / "input.json"
        source.write_text(json.dumps(self.data))
        output = self.base / "answer.txt"
        env = {**os.environ, "LOOP_CLAUDE": str(self.fake_agent), "PATH": self.path,
               "STATE": str(self.state), "GHDATA": str(self.ghdata),
               "ROUNDS": json.dumps(rounds)}
        result = subprocess.run(
            [sys.executable, str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", "claude", "--folder", str(self.root), "--input", str(source),
             "--output", str(output), *flags],
            env=env, capture_output=True, text=True, timeout=120, check=False)
        return result, output

    def calls(self):
        path = self.state / "calls"
        return int(path.read_text()) if path.exists() else 0

    def prompt(self, number):
        return (self.state / f"prompt-{number}.txt").read_text()

    def test_D1_a_wrong_reason_judge_is_sent_back_once_with_the_failure_text(self):
        result, output = self.launch(
            [step(WRONG, "first try"), step(RIGHT, "second try")], "--prove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), 2)
        self.assertNotIn("AttributeError", self.prompt(1))
        self.assertIn("AttributeError no attribute add", self.prompt(2))
        self.assertEqual(git(self.root, "show", f"HEAD:{JUDGE}") + "\n", RIGHT)
        self.assertEqual(git(self.root, "rev-list", "--count", "main..HEAD"), "2")
        self.assertTrue(output.exists())

    def test_D2_a_second_wrong_reason_is_refused_with_the_reason_and_the_notes(self):
        result, output = self.launch(
            [step(WRONG, "first try"), step(WRONG, "second try notes"), step(RIGHT, "third")],
            "--prove")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("refused:", result.stderr)
        self.assertIn("names no spec ID", result.stderr)
        self.assertIn("second try notes", result.stderr)
        self.assertNotIn("first try", result.stderr)
        self.assertIn("next:", result.stderr)
        self.assertEqual(self.calls(), 2)
        self.assertFalse(output.exists())

    def test_D2_another_refusal_is_reported_without_a_retry(self):
        agents = self.root / "AGENTS.md"  # an unknown agent: a plain Refused after the judge ran
        agents.write_text(agents.read_text() + "Agent: gemini\n")
        git(self.root, "commit", "--quiet", "-am", "Name an unknown agent")
        result, _ = self.launch([step(RIGHT, "only try")], "--prove")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Agent must be claude or codex", result.stderr)
        self.assertIn("only try", result.stderr)
        self.assertEqual(self.calls(), 1)

    def test_D3_a_verdict_with_tests_per_id_false_is_refused_with_the_notes(self):
        for flags in ((), ("--prove",)):
            with self.subTest(flags=flags):
                self.state_reset()
                result, output = self.launch(
                    [step(RIGHT, "D2 has no test", tests_per_id=False)], *flags)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("tests_per_id", result.stderr)
                self.assertIn("D2 has no test", result.stderr)
                self.assertEqual(self.calls(), 1)
                self.assertFalse(output.exists())

    def state_reset(self):
        for path in self.state.iterdir():
            path.unlink()
        git(self.root, "reset", "--quiet", "--hard", "main")
        (self.root / JUDGE).unlink(missing_ok=True)

    def test_D4_an_assertion_failure_on_the_base_needs_no_retry(self):
        result, output = self.launch([step(RIGHT, "fine")], "--prove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), 1)
        self.assertTrue(output.exists())
        self.assertNotIn("skipped", result.stdout)

    def test_D5_the_brief_tells_a_missing_subject_from_a_missing_dependency(self):
        brief = (KIT / "briefs/judge-writer.md").read_text()
        self.assertIn("error.name", brief)
        self.assertIn("ImportError", brief)
        self.assertIn("installed version's API", brief)
        example = re.findall(r"```python\n(.*?)```", brief, re.DOTALL)
        self.assertEqual(len(example), 1)
        cases = {"x = 1\n": "AssertionError",
                 "from habits_lib_missing import x\n": "ModuleNotFoundError"}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "judge.py").write_text(example[0] + "\ntest_D1_add()\n")
            for subject, error in cases.items():
                with self.subTest(error=error):
                    Path(tmp, "habits.py").write_text(subject)
                    run = subprocess.run([sys.executable, "judge.py"], cwd=tmp,
                                         capture_output=True, text=True, check=False)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn(error + ":", run.stderr)
            Path(tmp, "habits.py").write_text(GOOD_CODE)
            run = subprocess.run([sys.executable, "judge.py"], cwd=tmp,
                                 capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_D6_a_blocker_that_is_not_done_skips_the_proof_and_says_so(self):
        self.issue(7, "## Intent\nBlocker.\n", "state:building")
        self.issue(1, BODY.format(depends="7"), "state:shaping")
        result, _ = self.launch([step(WRONG, "wrong but unproved")], "--prove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("base proof skipped: pieces 7 are not done; "
                      "the base check runs when they are", result.stdout)
        self.assertEqual(self.calls(), 1)

    def test_D6_a_blocker_that_is_done_gets_the_proof(self):
        self.issue(7, "## Intent\nBlocker.\n", "state:done")
        self.issue(1, BODY.format(depends="7"), "state:shaping")
        result, _ = self.launch([step(WRONG, "first"), step(RIGHT, "second")], "--prove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), 2)
        self.assertNotIn("skipped", result.stdout)

    def test_D7_the_ceilings_rise_only_by_what_the_guidance_measures(self):
        sizes = {name: len((KIT / name).read_text().split())
                 for name in ("briefs/judge-writer.md", "skills/shape/SKILL.md")}
        for name, words in sizes.items():
            self.assertLessEqual(words, test_text_budgets.BUDGETS[name], name)
        paths = [*KIT.joinpath("skills").rglob("*.md"), *KIT.joinpath("briefs").rglob("*.md"),
                 *KIT.joinpath("agents").rglob("*.md"), KIT / "spec-format.md",
                 ROOT / "extras/briefs/critic.md"]
        measured = sum(len(path.read_text().split()) for path in paths)
        self.assertEqual(measured, test_text_budgets.TOTAL_BUDGET)
        self.assertEqual(test_text_budgets.BUDGETS["skills/shape/SKILL.md"],
                         sizes["skills/shape/SKILL.md"])

    def test_D7_the_shape_skill_ends_the_judge_writer_command_with_prove(self):
        skill = (KIT / "skills/shape/SKILL.md").read_text()
        self.assertRegex(skill, r"--role judge-writer [^`]*--folder \. --prove`")
        self.assertIn("skips", skill)

    def test_D8_without_prove_the_launcher_still_refuses_undeclared_writes(self):
        result, output = self.launch([{"writes": {JUDGE: RIGHT, "extra.py": "# extra\n"},
                                       "notes": "extra"}])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("outside the approved Exit Files", result.stderr)
        self.assertFalse(output.exists())

    def test_D8_without_prove_a_wrong_reason_judge_is_not_proved_or_retried(self):
        result, output = self.launch([step(WRONG, "unproved")])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), 1)
        self.assertTrue(output.exists())

    def test_ready_refusals_about_the_judge_carry_a_reason_type(self):
        self.assertTrue(hasattr(errors, "JudgeRefused"), "errors.JudgeRefused must exist")
        (self.root / "habits.py").write_text(GOOD_CODE)
        checks = ({"type": "tests", "command": "python3 -c pass", "files": []},)
        with self.assertRaises(errors.JudgeRefused) as raised:
            exit_ready(self.root, checks, {"D1": "add"}, ())
        self.assertEqual(raised.exception.reason_type, "spec-unclear")
        self.assertIsInstance(raised.exception, Refused)
        checks = ({"type": "tests", "command": "python3 -c 'import nothing_here_xyz'",
                   "files": []},)
        with self.assertRaises(errors.JudgeRefused) as raised:
            exit_ready(self.root, checks, {"D1": "add"}, ())
        self.assertEqual(raised.exception.reason_type, "bar-wrong")


if __name__ == "__main__":
    unittest.main()
