"""Test helpers: a fake gh on PATH driven by a scenario file, temp git repos."""
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

FAKE_GH = '''#!PYTHON
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


def write_exe(path, text):
    """Write a fake command. Its shebang runs this interpreter with -S (no site
    import), which starts about twice as fast and is all a stdlib-only fake needs."""
    shebang = "#!%s -S" % sys.executable if " " not in sys.executable else "#!/usr/bin/env python3"
    with open(path, "w") as f:
        f.write(text.replace("#!PYTHON", shebang, 1))
    os.chmod(path, 0o755)


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
        write_exe(script, FAKE_GH)
        # No real docker: the host's daemon is not what these tests check, and a
        # shell stub that fails starts much faster. A test can write its own.
        docker = os.path.join(bindir, "docker")
        with open(docker, "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(docker, 0o755)
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


def settings_json(text):
    """Convert the settings used by older fixtures into typed JSON."""
    import common
    found = {k: v for _, k, v in common.setting_lines(text)}
    for role, prefix in (("Builder", "Builder"), ("Test writer", "Builder"),
                         ("Reviewer", "Reviewer"), ("Pass", "Reviewer")):
        if found.get(prefix + " model") and not found.get(role):
            found[role] = "claude " + found[prefix + " model"]
    for key in ("Builder model", "Reviewer model", "Defect rounds"):
        found.pop(key, None)
    for key in found.keys() & common.NUMERIC_SETTINGS:
        found[key] = float(found[key])
    for key in found.keys() & common.LIST_SETTINGS:
        found[key] = [p.strip() for p in found[key].split(",") if p.strip()]
    return json.dumps(found)


def write_settings(path, text, append=False):
    """Write a JSON fixture, optionally extending its previous settings."""
    found = json.loads(settings_json("## Loop\n" + text))
    if append:
        with open(path) as f:
            found = dict(json.load(f), **found)
    with open(path, "w") as f:
        json.dump(found, f)


_TEMPLATES = {}
_TEMPLATE_DIR = []


def _template(files):
    """Build each distinct repository once per process and keep it for copying."""
    key = json.dumps(files, sort_keys=True)
    if key not in _TEMPLATES:
        if not _TEMPLATE_DIR:
            _TEMPLATE_DIR.append(tempfile.mkdtemp(prefix="loop-tests-"))
            atexit.register(shutil.rmtree, _TEMPLATE_DIR[0], True)
        parent = os.path.join(_TEMPLATE_DIR[0], str(len(_TEMPLATES)))
        os.mkdir(parent)
        _TEMPLATES[key] = (parent, _build_repo(parent, files))
    return _TEMPLATES[key][0]


def _build_repo(parent, files):
    origin = os.path.join(parent, "origin.git")
    work = os.path.join(parent, "work")
    # An empty template leaves out the sample hooks: fewer files to copy.
    run_git(["init", "--template=", "--bare", "-b", "main", origin], parent)
    run_git(["init", "--template=", "-b", "main", work], parent)
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


def make_repo(parent, files=None):
    """Create a work repo with a bare origin, one commit pushed to main.
    Return (work, origin) paths. The repository is built once per process and copied."""
    return copy_repo(_template(files), parent)


def copy_repo(template, parent):
    """Copy a make_repo result into parent and repoint origin. Return (work, origin)."""
    while os.path.exists(os.path.join(parent, "work")):  # a second repo in one folder gets its own subfolder
        parent = os.path.join(parent, "again")
        os.makedirs(parent, exist_ok=True)
    work, origin = (os.path.join(parent, n) for n in ("work", "origin.git"))
    shutil.copytree(os.path.join(template, "work"), work)
    shutil.copytree(os.path.join(template, "origin.git"), origin)
    # Point origin at the copy by editing the config file: no git process needed.
    config = os.path.join(work, ".git", "config")
    with open(config) as f:
        text = f.read()
    old = os.path.join(template, "origin.git")
    with open(config, "w") as f:
        f.write(text.replace("url = " + old, "url = " + origin))
    return work, origin
