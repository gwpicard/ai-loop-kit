"""Checks for the spec, the gate, the guard and one whole run."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

from helpers import GOOD_CODE, JUDGE, KIT, SPEC, Project, git

import gate
import run
from loopkit import Refused, parse_spec


class SpecTest(unittest.TestCase):
    def test_reads_a_whole_spec(self):
        spec = parse_spec(SPEC)
        self.assertEqual(list(spec.done_when), ["D1", "D2"])
        self.assertEqual(spec.command, "python3 judge_add.py")
        self.assertEqual(spec.files, ["judge_add.py"])
        self.assertEqual(spec.kind, "test")

    def test_names_every_gap_at_once(self):
        with self.assertRaises(Refused) as r:
            parse_spec("## Goal\nSomething.\n")
        self.assertIn("Done when", r.exception.reason)
        self.assertIn("Judge", r.exception.reason)

    def test_refuses_a_twice_used_id_and_a_path_outside(self):
        body = SPEC.replace("- D2:", "- D1:").replace("- judge_add.py", "- ../x.py")
        with self.assertRaises(Refused) as r:
            parse_spec(body)
        self.assertIn("used twice", r.exception.reason)
        self.assertIn("inside the project", r.exception.reason)

    def test_scaffold_needs_no_files(self):
        body = "## Done when\n- D1: tests run.\n\n## Judge\nCommand: `true`\nKind: scaffold\n"
        self.assertEqual(parse_spec(body).kind, "scaffold")


class GateTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def ready(self, n):
        return gate.move(self.p.gh, self.p.root, n, "ready")

    def test_ready_fixes_the_bar(self):
        n = self.p.piece()
        self.ready(n)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
        rec = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual(len(rec["bar"]), 64)
        self.assertEqual(rec["command"], "python3 judge_add.py")

    def test_the_ready_note_never_claims_a_check_it_skipped(self):
        n = self.p.piece(spec=SPEC.replace("Command:", "Kind: scaffold\nCommand:"))
        self.ready(n)
        note = self.p.gh.comments(n)[-1]
        self.assertIn("does not apply", note)
        self.assertNotIn("fails on main as it should", note)

    def test_ready_refuses_a_judge_that_passes_on_main(self):
        n = self.p.piece(judge="print('test_D1 test_D2 ok')\n")
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("already passes", r.exception.reason)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])

    def test_ready_refuses_a_broken_judge(self):
        n = self.p.piece(judge="def oops(:\n")
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("wrong reason", r.exception.reason)

    def test_ready_refuses_a_judge_that_names_no_spec_id(self):
        n = self.p.piece(judge=JUDGE.replace("test_D1", "test_one").replace("test_D2", "test_two"))
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("names no spec ID", r.exception.reason)

    def test_ready_refuses_when_an_id_has_no_test(self):
        n = self.p.piece(judge=JUDGE.replace("test_D2", "test_two"))
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("D2", r.exception.reason)

    def test_ready_refuses_without_the_piece_branch(self):
        n = gate.capture(self.p.gh, "No branch", SPEC)
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("no branch", r.exception.reason)

    def test_only_listed_moves_are_allowed(self):
        n = self.p.piece()
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "approval")
        self.assertIn("no move from shaping to approval", r.exception.reason)

    def test_moves_back_need_a_reason(self):
        n = self.p.piece()
        with self.assertRaises(Refused):
            gate.move(self.p.gh, self.p.root, n, "dropped")
        gate.move(self.p.gh, self.p.root, n, "dropped", reason="not needed")
        self.assertEqual(self.p.gh.issue(n)["state"], "CLOSED")

    def test_claim_refuses_a_spec_changed_after_ready(self):
        n = self.p.piece()
        self.ready(n)
        self.p.gh.issues[n]["body"] += "\n- D3: a new wish.\n"
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "building")
        self.assertIn("spec changed", r.exception.reason)

    def test_judge_fails_when_the_bar_moves(self):
        n = self.p.piece()
        self.ready(n)
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        self.assertTrue(gate.judge(self.p.root, ready)[0])
        (self.p.root / "judge_add.py").write_text("print('all good')\n")
        passed, why = gate.judge(self.p.root, ready)
        self.assertFalse(passed)
        self.assertIn("differ", why)

    def test_submit_runs_the_judge_itself(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root, pr="u")
        self.assertIn("does not pass", r.exception.reason)
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root, pr="u")
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])

    def test_done_needs_a_merged_pull_request(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        self.p.gh.create_pr(f"piece/{n}", "t", "b")
        gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root, pr="u")
        with self.assertRaises(Refused):
            gate.move(self.p.gh, self.p.root, n, "done")
        self.p.gh.prs[f"piece/{n}"]["state"] = "MERGED"
        self.p.gh.issues[n]["state"] = "CLOSED"  # GitHub's closing words got there first
        self.assertEqual(len(gate.sync(self.p.gh, self.p.root)), 1)
        self.assertIn("state:done", self.p.gh.issue(n)["labels"])

    def test_keep_must_pass_on_main_and_still_pass_after_the_build(self):
        keep_spec = SPEC.replace("Files:", "Keep: `python3 keep_check.py`\nFiles:")
        n = self.p.piece(spec=keep_spec)
        with self.assertRaises(Refused) as r:  # no keep_check.py on main yet
            self.ready(n)
        self.assertIn("keep check already fails on main", r.exception.reason)
        (self.p.root / "keep_check.py").write_text("import pathlib, sys\nsys.exit(0 if pathlib.Path('README.md').exists() else 1)\n")
        git(self.p.root, "add", "keep_check.py")
        git(self.p.root, "commit", "--quiet", "-m", "Keep check")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        git(self.p.root, "merge", "--quiet", "--no-edit", "main")
        git(self.p.root, "switch", "--quiet", "main")
        self.ready(n)
        self.assertIn("keep check", self.p.gh.comments(n)[-1])
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        self.assertTrue(gate.judge(self.p.root, ready)[0])
        (self.p.root / "README.md").unlink()  # the build breaks what worked before
        passed, why = gate.judge(self.p.root, ready)
        self.assertFalse(passed)
        self.assertIn("keep check now fails", why)

    def test_the_loop_folder_stays_ignored_whatever_gitignore_says(self):
        (self.p.root / ".gitignore").write_text("__pycache__/\n")
        gate.ignore_loop_folder(self.p.root)
        (self.p.root / ".loop").mkdir()
        (self.p.root / ".loop" / "x.log").write_text("log")
        self.assertNotIn(".loop", git(self.p.root, "status", "--porcelain"))

    def test_a_piece_with_two_states_is_refused(self):
        n = self.p.piece()
        self.p.gh.issues[n]["labels"].append("state:ready")
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("2 state labels", r.exception.reason)


def guard(command=None, tool="Bash", builder=False, path=None):
    data = {"command": command} if command is not None else {"file_path": path}
    env = {**os.environ, "LOOP_BUILDER": "1" if builder else "0"}
    res = subprocess.run([sys.executable, str(KIT / "hooks" / "guard.py")],
                         input=json.dumps({"tool_name": tool, "tool_input": data}),
                         capture_output=True, text=True, env=env)
    return res.returncode


class GuardTest(unittest.TestCase):
    REFUSED = [
        "git push origin main", "git push origin HEAD:main", "git push --force origin piece/1",
        "git push -f", "rm -rf build", "rm -r src", "rm -fR x", "sudo rm --recursive x",
        "find . -name '*.pyc' -delete", "git clean -fdx", "git rm -r src",
        "gh pr merge 3 --squash", "gh issue edit 3 --add-label state:ready",
        "gh api repos/o/r/issues/3/labels -f labels[]=state:done",
        "echo hi && git push origin main", "FOO=1 git push origin main",
    ]
    ALLOWED = [
        "git push -u origin piece/4", "rm build/out.txt", "git status", "gh issue list",
        "gh issue edit 3 --add-label bug", "python3 gate.py move 3 ready", "ls -la",
    ]

    def test_refuses_the_hard_rules(self):
        for cmd in self.REFUSED:
            self.assertEqual(guard(cmd), 2, cmd)

    def test_allows_ordinary_work(self):
        for cmd in self.ALLOWED:
            self.assertEqual(guard(cmd), 0, cmd)

    def test_builders_never_push_or_use_gh_or_touch_settings(self):
        self.assertEqual(guard("git push -u origin piece/4", builder=True), 2)
        self.assertEqual(guard("gh issue list", builder=True), 2)
        self.assertEqual(guard(tool="Write", path="/p/.claude/settings.json", builder=True), 2)
        self.assertEqual(guard(tool="Write", path="/p/src/app.py", builder=True), 0)


FAKE_CLAUDE = textwrap.dedent('''\
    #!/bin/sh
    # A stand-in for claude -p. FAKE_MODE picks how it behaves.
    case "$FAKE_MODE" in
      good) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py ;;
      cheat) printf 'import sys\\nsys.exit(0)\\n' > judge_add.py ;;
      *) printf 'def add(items, name):\\n    return items\\n' > habits.py ;;
    esac
    git add -A && git commit --quiet -m "Build"
    echo "built"
    ''')


class RunTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        fake = Path(self.p.tmp.name) / "fake-claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["LOOP_CLAUDE"] = str(fake)
        self.addCleanup(os.environ.pop, "LOOP_CLAUDE", None)
        self.addCleanup(os.environ.pop, "FAKE_MODE", None)

    def build(self, mode, attempts=2):
        os.environ["FAKE_MODE"] = mode
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, attempts)
        return n, result

    def test_a_good_build_opens_a_pull_request(self):
        n, result = self.build("good")
        self.assertIn("pull request ready", result)
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])
        self.assertIn(f"piece/{n}", git(self.p.remote, "branch"))

    def test_a_failing_build_goes_back_to_shaping(self):
        n, result = self.build("bad")
        self.assertIn("back to shaping", result)
        labels = self.p.gh.issue(n)["labels"]
        self.assertIn("state:shaping", labels)
        self.assertIn("needs-you", labels)
        failed = [c for c in self.p.gh.comments(n) if "attempt" in c and "failed" in c]
        self.assertEqual(len(failed), 2)
        self.assertIn("The builder said:", failed[0])
        self.assertIn("built", failed[0])  # the stand-in's own words reach the issue

    def test_a_builder_that_changes_the_judge_does_not_pass(self):
        n, result = self.build("cheat")
        self.assertIn("back to shaping", result)
        self.assertEqual(self.p.gh.prs, {})


if __name__ == "__main__":
    unittest.main()
