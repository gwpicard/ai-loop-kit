"""The person's merge command must enforce checks and record its result."""
import json
import os
from pathlib import Path
import shlex
import subprocess

from kit.tests.helpers import FakeGh, make_repo, run_git, write_exe
import common


KIT = Path(__file__).resolve().parents[1]


REQUEST_GH = '''#!PYTHON
import json, os, sys
from pathlib import Path

path = os.environ["FAKE_GH_SCENARIO"]
args = sys.argv[1:]
with open(path + ".calls", "a") as stream:
    stream.write(json.dumps(args) + "\\n")
data = json.loads(Path(path).read_text())
info = data["info"]
merged = Path(path + ".merged").exists()
if merged:
    info.update(state="MERGED", mergeCommit={"oid": "a" * 40})
if args[:2] == ["pr", "view"]:
    print(json.dumps(info))
elif args[:2] == ["pr", "list"]:
    print(json.dumps([info]))
elif args[:2] == ["pr", "checks"]:
    print(json.dumps(data["checks"]))
    sys.exit(0 if data["green"] else 1)
elif args[:2] == ["pr", "merge"]:
    Path(path + ".merged").touch()
elif args[:2] == ["pr", "comment"]:
    pass
elif args[:2] == ["api", "user"]:
    print('{"login": "maintainer"}')
elif args[:1] == ["api"] and "repos/" in " ".join(args):
    print(json.dumps(dict(info, default_branch="main", delete_branch_on_merge=False,
                          merge_commit_sha="a" * 40 if merged else None)))
else:
    sys.stderr.write("Unexpected fake gh call: " + repr(args))
    sys.exit(1)
'''


class MergeByRequestTest(FakeGh):
    def project(self, base="main", check="SUCCESS", sign_off=False, failing_test=False):
        self.marker = Path(self.tmp, "full-test-ran")
        script = ("from pathlib import Path; "
                  "Path(%r).write_text('ran'); "
                  "assert Path('loop-only.txt').exists(); "
                  "assert Path('feature-only.txt').exists(); "
                  "assert %r" % (str(self.marker), not failing_test))
        settings = {"Test command": "python3 -c " + shlex.quote(script),
                    "Test files command": "false", "Sign-off": sign_off}
        self.work, _ = make_repo(self.tmp, {"loop.json": json.dumps(settings)})
        run_git(["checkout", "-b", "loop/main"], self.work)
        Path(self.work, "loop-only.txt").write_text("loop work\n")
        run_git(["add", "loop-only.txt"], self.work)
        run_git(["commit", "-m", "Loop work"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        run_git(["checkout", "-b", "fix", "main"], self.work)
        Path(self.work, "feature-only.txt").write_text("requested fix\n")
        run_git(["add", "feature-only.txt"], self.work)
        run_git(["commit", "-m", "Requested fix"], self.work)
        run_git(["push", "origin", "fix"], self.work)
        head = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["checkout", "main"], self.work)
        checks = [{"name": "required", "state": check, "status": "COMPLETED",
                   "conclusion": check, "bucket": "pass" if check == "SUCCESS" else "fail"}]
        info = dict(number=9, title="Requested fix", body="", state="OPEN",
                    baseRefName=base, headRefName="fix", headRefOid=head,
                    mergeable="MERGEABLE", mergeStateStatus="CLEAN",
                    statusCheckRollup=checks, mergeCommit=None)
        Path(self.scenario_path).write_text(json.dumps(dict(
            info=info, checks=checks, green=check == "SUCCESS")))
        write_exe(os.path.join(self.tmp, "bin/gh"), REQUEST_GH)

    def command(self):
        env = dict(os.environ)
        for name in ("LITE_ROLE", "LOOP_ROLE", "LOOP_BUILD_SETTINGS"):
            env.pop(name, None)
        result = subprocess.run([str(KIT / "bin/loop"), "merge", "9"], cwd=self.work,
                                env=env, capture_output=True, text=True, timeout=30)
        self.output = result.stdout + result.stderr
        self.assertNotIn("usage:", self.output.lower(), self.output)
        return result.returncode

    def merges(self):
        return [args for args in self.calls() if args[:2] == ["pr", "merge"]]

    def test_default_branch_refuses_a_failing_required_check(self):
        self.project(check="FAILURE")
        self.assertNotEqual(self.command(), 0, self.output)
        self.assertRegex(self.output.lower(), r"check|fail")
        self.assertEqual(self.merges(), [])

    def test_default_branch_merges_green_with_squash_sign_off_and_event(self):
        self.project(sign_off=True)
        self.assertEqual(self.command(), 0, self.output)
        calls = self.merges()
        self.assertEqual(len(calls), 1)
        self.assertIn("--squash", calls[0])
        self.assertNotIn("--delete-branch", calls[0])
        body = calls[0][calls[0].index("--body") + 1]
        self.assertIn("Signed-off-by: Test <t@example.com>", body)
        path = Path(self.work, ".loop/events.jsonl")
        self.assertTrue(path.exists(), "The requested merge must record an event")
        events = [json.loads(line) for line in path.read_text().splitlines()]
        requested = [event for event in events if event["kind"] == "merged-by-request"]
        self.assertEqual(len(requested), 1, events)
        self.assertTrue(any(value in (9, "9", "https://example/pull/9")
                            for value in requested[0].values()), requested[0])

    def test_loop_branch_runs_the_full_command_on_the_merged_result(self):
        self.project(base="loop/main", check="FAILURE")
        self.assertEqual(self.command(), 0, self.output)
        self.assertTrue(self.marker.exists(), "Run the full Test command, including both branches")
        self.assertEqual(len(self.merges()), 1)
        self.assertNotIn("Signed-off-by:", " ".join(self.merges()[0]))

    def test_loop_branch_refuses_when_the_full_command_fails(self):
        self.project(base="loop/main", failing_test=True)
        self.assertNotEqual(self.command(), 0, self.output)
        self.assertTrue(self.marker.exists(), "A green GitHub check cannot replace the full Test command")
        self.assertEqual(self.merges(), [])
