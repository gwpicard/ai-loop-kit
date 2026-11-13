"""Test helpers: a fake gh on PATH driven by a scenario file, temp git repos."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys, time
path = os.environ["FAKE_GH_SCENARIO"]
args = " ".join(sys.argv[1:])
with open(path + ".calls", "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
rules = json.load(open(path))["rules"]
state_path = path + ".state"
state = json.load(open(state_path)) if os.path.exists(state_path) else {}
for i, rule in enumerate(rules):
    if rule["match"] in args:
        n = state.get(str(i), 0)
        state[str(i)] = n + 1
        json.dump(state, open(state_path, "w"))
        r = rule["responses"][min(n, len(rule["responses"]) - 1)]
        time.sleep(r.get("sleep", 0))
        sys.stdout.write(r.get("stdout", ""))
        sys.stderr.write(r.get("stderr", ""))
        sys.exit(r.get("code", 0))
sys.stderr.write("fake gh: no rule for " + args + "\\n")
sys.exit(1)
'''


class FakeGh(unittest.TestCase):
    """Base class. Call self.scenario(rules) to set what the fake gh answers.

    A rule is {"match": text found in the joined args, "responses": [...]},
    each response {"code", "stdout", "stderr"}. Responses are used in order
    and the last one repeats. The first matching rule wins.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        bindir = os.path.join(self.tmp, "bin")
        os.mkdir(bindir)
        script = os.path.join(bindir, "gh")
        with open(script, "w") as f:
            f.write(FAKE_GH)
        os.chmod(script, 0o755)
        self.scenario_path = os.path.join(self.tmp, "scenario.json")
        old = dict(os.environ)
        os.environ["PATH"] = bindir + os.pathsep + old["PATH"]
        os.environ["FAKE_GH_SCENARIO"] = self.scenario_path
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        self.scenario([])

    def scenario(self, rules):
        for ext in ("", ".calls", ".state"):
            if os.path.exists(self.scenario_path + ext):
                os.remove(self.scenario_path + ext)
        with open(self.scenario_path, "w") as f:
            json.dump({"rules": rules}, f)

    def calls(self):
        path = self.scenario_path + ".calls"
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]


def run_git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True,
                   text=True)


def make_repo(parent, files=None):
    """Create a work repo with a bare origin, one commit pushed to main.
    Return (work, origin) paths."""
    origin = os.path.join(parent, "origin.git")
    work = os.path.join(parent, "work")
    run_git(["init", "--bare", "-b", "main", origin], parent)
    run_git(["init", "-b", "main", work], parent)
    for k, v in (("user.name", "Test"), ("user.email", "t@example.com")):
        run_git(["config", k, v], work)
    run_git(["remote", "add", "origin", origin], work)
    for name, text in (files or {"README.md": "hello\n"}).items():
        path = os.path.join(work, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
    run_git(["add", "-A"], work)
    run_git(["commit", "-m", "first"], work)
    run_git(["push", "-u", "origin", "main"], work)
    return work, origin
