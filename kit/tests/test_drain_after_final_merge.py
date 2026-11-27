"""Judge final pull request races through the loop run command."""
import json
from pathlib import Path
import shlex
import subprocess
import sys

from kit.tests.helpers import FakeGh, make_repo, run_git


KIT = Path(__file__).resolve().parents[1]
TEST_COMMAND = """import json
from pathlib import Path
import subprocess
import sys

project, origin, base, advance = sys.argv[1:]
runtime = Path(project, '.loop')

def git(*args, cwd=project):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()

head = git('rev-parse', 'origin/loop/main')
before = git('rev-parse', 'refs/heads/' + base, cwd=origin)
observed = dict(local_before=git('rev-parse', 'origin/' + base),
                remote_before=before, head=head)
if advance == 'yes':
    subprocess.run(['git', 'merge-base', '--is-ancestor', before, head],
                   cwd=origin, check=True)
    subprocess.run(['git', 'update-ref', 'refs/heads/' + base, head, before],
                   cwd=origin, check=True)
observed['remote_after'] = git('rev-parse', 'refs/heads/' + base, cwd=origin)
(runtime / 'test-observation.json').write_text(json.dumps(observed))
(runtime / 'stop').touch()
print('drain Test command ran')
"""


class DrainAfterFinalMergeTest(FakeGh):
    def fixture(self, base="main", files=("feature.txt",), advance=False):
        self.work, self.origin = make_repo(self.tmp, {"drain_test.py": TEST_COMMAND})
        if base != "main":
            run_git(["branch", base, "main"], self.origin)
            run_git(["fetch", "--no-prune", "origin"], self.work)
        run_git(["symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/" + base],
                self.work)
        self.base = base
        self.runtime = Path(self.work, ".loop")
        self.runtime.mkdir()
        command = shlex.join([sys.executable, "drain_test.py", self.work, self.origin,
                              base, "yes" if advance else "no"])
        Path(self.work, "loop.json").write_text(json.dumps({
            "Test command": command, "Idle hours": 0,
        }))
        run_git(["add", "loop.json"], self.work)
        run_git(["commit", "-qm", "Configure the fixture drain"], self.work)
        for name in files:
            path = Path(self.work, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("landed change\n")
            run_git(["add", "--", name], self.work)
            run_git(["commit", "-qm", "Add " + name], self.work)
        run_git(["push", "origin", "HEAD:loop/main"], self.work)

    def drive(self, refusal=None):
        factory = dict(number=1, title="Factory", body="", labels=[])
        create = {"stdout": "https://example.test/pull/9\n"}
        if refusal is not None:
            create = {"code": 1, "stderr": refusal}
        self.scenario([
            {"match": "label list", "responses": [{"stdout": json.dumps([
                dict(name=name) for name in ("inbox", "shaping", "ready", "building", "needs-user")])}]},
            {"match": "issue list --state open", "responses": [{"stdout": json.dumps([factory])}]},
            {"match": "issue list --state closed", "responses": [{"stdout": "[]"}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "pr create", "responses": [create]},
            {"match": "api repos/{owner}/{repo} --jq .delete_branch_on_merge",
             "responses": [{"stdout": "false"}]},
        ])
        output = self.runtime / "loop.out"
        with output.open("w") as stream:
            result = subprocess.run([str(KIT / "bin/loop"), "run"], cwd=self.work,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=30)
        self.output = output.read_text()
        self.assertEqual(result.returncode, 0, self.output)
        observation = self.runtime / "test-observation.json"
        self.assertTrue(observation.is_file(), self.output)
        observed = json.loads(observation.read_text())
        self.assertEqual(observed["local_before"], observed["remote_before"])
        self.assertNotEqual(observed["remote_before"], observed["head"])
        events = [json.loads(line) for line in (self.runtime / "events.jsonl").read_text().splitlines()]
        self.ends = [e for e in events if e["kind"] == "drain" and e.get("phase") == "end"]
        self.assertEqual(len(self.ends), 1, events)
        self.creates = [call for call in self.calls() if call[:2] == ["pr", "create"]]
        return observed

    def assert_pass(self):
        with self.subTest(surface="drain event"):
            self.assertEqual(self.ends[0]["outcome"], "pass", self.ends[0])
        with self.subTest(surface="loop.out"):
            self.assertFalse([line for line in self.output.splitlines() if "problem" in line],
                             self.output)

    def test_default_branch_gaining_all_landed_commits_during_tests_creates_no_pull_request(self):
        examples = (("main", ("feature.txt",)),
                    ("trunk", ("folder/a file.txt", "other.txt")))
        for base, files in examples:
            with self.subTest(base=base, files=files):
                self.fixture(base, files, advance=True)
                observed = self.drive()
                self.assertEqual(observed["remote_after"], observed["head"])
                with self.subTest(surface="pull request"):
                    self.assertEqual(self.creates, [], "the default branch already contains every landed commit")
                with self.subTest(surface="fetch"):
                    current = subprocess.check_output(
                        ["git", "rev-parse", "origin/" + base], cwd=self.work, text=True).strip()
                    self.assertEqual(current, observed["head"], "refresh the default branch after the Test command")
                self.assert_pass()

    def test_no_commits_refusal_records_a_pass_without_a_problem_line(self):
        self.fixture()
        self.drive("pull request create failed: GraphQL: No commits between main and loop/main (createPullRequest)\n")
        self.assertEqual(len(self.creates), 1, self.calls())
        self.assert_pass()

    def test_new_landed_commits_without_an_open_pull_request_still_create_one(self):
        self.fixture()
        observed = self.drive()
        self.assertEqual(observed["remote_after"], observed["remote_before"])
        self.assertEqual(len(self.creates), 1, self.calls())
        create = self.creates[0]
        self.assertEqual(create[create.index("--base") + 1], self.base)
        self.assertEqual(create[create.index("--head") + 1], "loop/main")
        self.assert_pass()
