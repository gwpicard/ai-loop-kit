#!/usr/bin/env sh
# Rehearse session-scoped GitHub credentials without an account or a network.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
python3 - "$ROOT" <<'PYTEST'
import json, os, pathlib, subprocess, sys, tempfile
root = pathlib.Path(sys.argv[1])
launcher = root / ".agents/skills/setup-ai-build-kit/scripts/codex-with-github.py"
if not launcher.is_file():
    sys.exit("FAIL: the installed skill has no portable Codex credential launcher")
failures = []
with tempfile.TemporaryDirectory() as folder:
    folder = pathlib.Path(folder)
    fixture = "synthetic-not-a-github-credential"
    gh = folder / "gh"
    gh.write_text("#!" + sys.executable + "\n" +
        'import os, sys\n'
        'assert sys.argv[1:] == ["auth", "token", "--hostname", "github.com"]\n'
        'mode = os.environ.get("FIXTURE_MODE", "success")\n'
        'if mode == "refuse": sys.exit(1)\n'
        'print(os.environ["FIXTURE_CREDENTIAL"])\n'
        'if mode == "multiline": print("extra line")\n'
        'if mode == "failure": sys.exit(1)\n')
    gh.chmod(0o700)
    codex = folder / "codex"
    codex.write_text("#!" + sys.executable + "\n" +
        'import json, os, sys\n'
        'credential = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")\n'
        'print(json.dumps({"authenticated": credential == os.environ["FIXTURE_CREDENTIAL"], '
        '"args": sys.argv[1:], "profile": os.environ.get("CODEX_PERMISSION_PROFILE"), '
        '"debug": "GH_DEBUG" in os.environ}))\n')
    codex.chmod(0o700)
    base = {k:v for k,v in os.environ.items() if k not in ["GH_TOKEN", "GITHUB_TOKEN"]}
    base.update(PATH=str(folder), FIXTURE_CREDENTIAL=fixture, CODEX_PERMISSION_PROFILE="workspace-network")
    def run(name, changes, success, args=None):
        env = dict(base); env.update(changes)
        result = subprocess.run([sys.executable, str(launcher), *(args or [])], env=env, capture_output=True, text=True)
        text = result.stdout + result.stderr
        ok = fixture not in text
        if success:
            try:
                data = json.loads(result.stdout)
                ok = ok and result.returncode == 0 and data["authenticated"]
                ok = ok and data["profile"] == "workspace-network" and not data["debug"]
                ok = ok and data["args"] == ["--no-daemon", "--disable", "shell_snapshot", *(args or [])]
            except (ValueError, KeyError): ok = False
        else: ok = ok and result.returncode != 0 and not result.stdout
        print(("ok: " if ok else "FAIL: ") + name)
        if not ok: failures.append(name)
    run("stored credential stays in memory and arguments survive", {"GH_DEBUG":"api"}, True, ["exec", "a prompt with 'quotes'"])
    run("existing GH_TOKEN needs no stored login", {"GH_TOKEN":fixture,"FIXTURE_MODE":"refuse"}, True)
    run("existing GITHUB_TOKEN needs no stored login", {"GITHUB_TOKEN":fixture,"FIXTURE_MODE":"refuse"}, True)
    run("failed credential read never launches Codex or prints its output", {"FIXTURE_MODE":"failure"}, False)
    run("malformed credential response never launches Codex", {"FIXTURE_MODE":"multiline"}, False)
    gh.unlink()
    run("missing GitHub CLI stops the launch", {}, False)
    codex.unlink()
    run("missing Codex stops the launch", {}, False)
if failures: sys.exit(1)
print("codex-github-auth.sh: all checks passed")
PYTEST
