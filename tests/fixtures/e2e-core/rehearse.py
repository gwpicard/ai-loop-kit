"""Rehearse the core with stand-ins, or the App path in an explicit manual smoke run."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent


def checked(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class Rehearsal:
    def __init__(self, app: bool, real: Path | None = None, kit: Path | None = None) -> None:
        self.app = app
        self.real = real is not None
        self.env = dict(os.environ)
        for key in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SIMPLE",
                    "ANTHROPIC_API_KEY", "GH_TOKEN", "GITHUB_TOKEN", "FAKE_CLAUDE_SCRIPT"):
            self.env.pop(key, None)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        if real is None:
            name = "core-app" if app else "core-local"
            source = shlex.quote(str(ROOT / "tests/lib/throwaway-project.sh"))
            script = f'. {source}; tp_new {name}; export TP_BIN; python3 -c ' + shlex.quote(
                "import os,json; print(json.dumps({k:v for k,v in os.environ.items() "
                "if k.startswith(('TP_', 'FAKE_', 'GIT_', 'AI_LOOP_')) or k == 'PATH'}))")
            made = subprocess.run(["sh", "-c", script], env={**self.env, "ROOT": str(ROOT)},
                                  capture_output=True, text=True, check=True)
            self.env.update(json.loads(made.stdout))
            self.project = Path(self.env["TP_ROOT"])
            self.base = Path(self.env["TP_BASE"])
            if not app:
                unused_key = Path(self.env["TP_APP_KEY"])
                unused_key.rename(unused_key.with_suffix(".unused"))
            self.kit = self.base / "plugin"
            shutil.copytree(ROOT / "kit", self.kit)
            self.env["PATH"] = (self.env["TP_BIN"] + ":" +
                                str(ROOT / "tests/stand-ins/fake-computer") + ":" +
                                self.env["PATH"])
            checked(shutil.which("claude", path=self.env["PATH"]) ==
                    str(Path(self.env["TP_BIN"]) / "claude"), "E2E-ISOLATION Claude stand-in")
            checked(shutil.which("gh", path=self.env["PATH"]) ==
                    str(Path(self.env["TP_BIN"]) / "gh"), "E2E-ISOLATION GitHub stand-in")
        else:
            self.project = real.resolve()
            self.base = self.project / ".agents/smoke"
            self.base.mkdir(parents=True, exist_ok=True)
            self.kit = (kit or ROOT / "kit").resolve()
            checked(self.project != ROOT.resolve(), "E2E-ISOLATION use a separate test project")
        self.env["CLAUDE_PLUGIN_ROOT"] = str(self.kit)
        self.env["PYTHONPATH"] = str(self.kit / "scripts")
        self.gate = str(self.kit / "scripts/gate.py")
        self.runner = str(self.kit / "scripts/run.py")
        self.fixture: dict[str, Any] = json.loads((FIXTURES / "project.json").read_text())
        self.fake = self.base / "sessions"
        if not self.real:
            self.fake.mkdir()
            self.env["FAKE_CLAUDE_DIR"] = str(self.fake)
            handoff = str(self.kit / "scripts/handoff.py")
            review_or_list = (
                "import os,json,subprocess,sys; "
                "target=os.environ.get('AI_LOOP_KIT_FINDINGS_FILE'); "
                "open(target,'w').write(json.dumps({'findings':[]})) if target else "
                "subprocess.run([sys.executable,sys.argv[1],'done','--summary',"
                "'FL-1: flow test\\nEC-1: edge test'],check=True)")
            self.script("default", {"runs": [["python3", "-c", review_or_list, handoff]]})
            self.script("trim", {"runs": [["python3", handoff, "done", "--summary",
                                           "Nothing to trim."]]})

    def call(self, *args: str, person: bool = False, codes: tuple[int, ...] = (0,),
             env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        command = list(args)
        if person:
            checked(not self.real, "E2E-ISOLATION terminal stand-in is test-only")
            command = ["python3", str(ROOT / "tests/lib/as-person.py"), *command]
        result = subprocess.run(command, cwd=self.project, env=env or self.env,
                                capture_output=True, text=True, check=False,
                                timeout=None if self.real else 240)
        with (self.base / "commands.log").open("a") as out:
            out.write(json.dumps({"command": command, "code": result.returncode,
                                  "stdout": result.stdout, "stderr": result.stderr}) + "\n")
        checked(result.returncode in codes,
                f"E2E-COMMAND {Path(args[0]).name} exited {result.returncode}; "
                f"read {self.base / 'commands.log'}")
        return result

    def data(self, *args: str, person: bool = False) -> dict[str, Any]:
        result = self.call(*args, person=person)
        value: dict[str, Any] = json.loads(result.stdout)
        return value

    def script(self, name: str, body: dict[str, Any]) -> None:
        (self.fake / f"{name}.json").write_text(json.dumps(body))

    def builder(self, number: int, kind: str) -> None:
        if self.real:
            return
        files = self.fixture[kind]
        self.script(str(number), {"files": files,
                                 "commits": [{"message": "Build " + kind, "paths": list(files)}],
                                 "runs": [["python3", str(self.kit / "scripts/handoff.py"),
                                           "done", "--summary", "Built " + kind + "."]]})

    def queue_sync(self) -> None:
        before = self.data("python3", self.gate, "sync", "--dry-run", "--json")
        checked(bool(before["digest"]), "E2E-MANUAL queue has a digest")
        self.data("python3", self.gate, "sync", "--confirm", before["digest"], "--json",
                  person=True)
        report = self.data("python3", self.gate, "report", "--brief", "--json")
        checked(not report["waiting_for_sync"], "E2E-MANUAL the queue was sent")

    def record(self, name: str) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(
            (self.project / ".agents/runs" / name / "run.json").read_text())
        return value

    def state(self, number: int) -> str:
        return str(self.data("python3", self.gate, "report", str(number), "--brief", "--json")
                   ["pieces"][0]["state"])

    def github_calls(self) -> str:
        target = Path(self.env["FAKE_GH_LOG"])
        return target.read_text() if target.exists() else ""

    def found(self) -> None:
        if self.real:
            tracked = self.call("git", "ls-files").stdout.splitlines()
            checked(tracked == ["README.md"], "E2E-EMPTY use a tiny repository with only README.md")
            checked(not self.call("git", "status", "--porcelain", "--untracked-files=no").stdout,
                    "E2E-REAL the test repository must be clean")
            extra = self.call("git", "ls-files", "--others", "--exclude-standard").stdout
            checked(all(name == ".agents/loop/local.json" or name.startswith(".agents/smoke/")
                        for name in extra.splitlines()),
                    "E2E-REAL only machine-local App settings may be untracked")
            checked(self.call("git", "branch", "--show-current").stdout.strip() == "main",
                    "E2E-REAL start on main")
            remote = self.call("git", "remote", "get-url", "origin").stdout
            checked("github.com" in remote, "E2E-REAL origin must be the test GitHub repository")
            local = self.project / ".agents/loop/local.json"
            checked(local.is_file() and json.loads(local.read_text()).get("github_app"),
                    "E2E-REAL configure the installed test App first")
        result = self.data("python3", str(self.kit / "scripts/setup.py"), "found",
                           "--language", "python", "--billing-mode", "subscription",
                           "--repo-visibility", "private", "--plan", "free", "--kit-ref", "main",
                           "--json")
        if not self.real:
            checked("gate.py sync" in result["labels"]["next"], "E2E-SETUP label next command")
        policy = self.project / ".agents/loop/policy.json"
        checked(not json.loads(policy.read_text())["test_command"],
                "E2E-EMPTY founding does not pretend a runner exists")
        with (self.project / "docs/area-map").open("a") as out:
            out.write("tests/ project-records\n")
        self.call("git", "add", "-A")
        self.call("git", "commit", "-m", "Found the tiny project")
        self.call("git", "push", "origin", "main")
        if self.app:
            if not self.real:
                app: dict[str, Any] = json.loads(
                    (ROOT / "tests/stand-ins/fake-app/app.json").read_text())
                (self.project / ".agents/loop/local.json").write_text(json.dumps({
                    "github_app": {k: app[k] for k in ("app_id", "installation_id", "slug")}}))
                self.env["FAKE_APP_KEY"] = self.env["TP_APP_KEY"]
            self.data("python3", self.gate, "labels", "--create", "--json")
        else:
            checked(not (self.project / ".agents/loop/local.json").exists(),
                    "E2E-LOCAL no App credential")
            checked(not self.github_calls(), "E2E-LOCAL founding made no GitHub call")

    def scaffold(self) -> int:
        result = self.data("python3", str(self.kit / "scripts/setup.py"), "first-piece",
                           "--test-command", "python3 -m pytest -q", "--json")
        number = int(result["piece"])
        body = result["gate"].get("body")
        if body is None:
            body = (self.kit / "templates/first-piece.md").read_text().replace(
                "{{TEST_COMMAND}}", "python3 -m pytest -q")
        body = str(body).replace(
            "The project has a structure to build in and one command that runs its tests.",
            "The project has a test runner and tests/test_scaffold.py. Its sample bug.py "
            "module has total(items): non-empty integer lists sum correctly; an empty list "
            "currently returns None. This known bug is the later reproducing-test piece.")
        spec = self.base / "scaffold.md"
        spec.write_text(body)
        self.data("python3", self.gate, "spec", str(number), "--body-file", str(spec), "--json")
        self.data("python3", self.gate, "branch", str(number), "--json")
        self.data("python3", self.gate, "move", str(number), "ready", "--json")
        self.builder(number, "scaffold")
        return number

    def shape(self, kind: str) -> int:
        body = (FIXTURES / f"{kind}.md").read_text().replace(
            "Held-out cases: fingerprint {{HELD}}\n", "")
        spec = self.base / f"{kind}.md"
        spec.write_text(body)
        captured = self.data("python3", self.gate, "capture", "--title", kind.capitalize(),
                             "--body-file", str(spec), "--type", kind, "--json")
        number = int(captured["piece"])
        self.data("python3", self.gate, "branch", str(number), "--json")
        self.call("git", "checkout", "piece-" + str(number))
        judge = "tests/test_" + kind + ".py"
        (self.project / judge).write_text(self.fixture["judges"][kind])
        self.call("git", "add", judge)
        self.call("git", "commit", "-m", "Judge " + kind + " first")
        red = self.call("python3", "-m", "pytest", judge, "-q", codes=(1,))
        checked("FL-1" in red.stdout, "E2E-JUDGE " + kind + " fails for its expected flow")
        self.call("git", "checkout", "main")
        cases = []
        for spec_id, text in self.fixture["held"][kind].items():
            case = self.base / f"hidden-{kind}-{spec_id}.txt"
            target = f"tests/held_out/test_hidden_{kind}_{spec_id.replace('-', '')}.py"
            case.write_text("# held-out-path: " + target + "\n" + text)
            cases.extend(["--case", spec_id + "=" + str(case)])
        held = self.data("python3", "-m", "loop.heldout", "store", "--piece", str(number),
                         *cases, "--json")
        spec.write_text((FIXTURES / f"{kind}.md").read_text().replace(
            "{{HELD}}", held["fingerprint"]))
        self.data("python3", self.gate, "spec", str(number), "--body-file", str(spec), "--json")
        self.data("python3", self.gate, "move", str(number), "ready", "--json")
        checked(self.state(number) == "ready", "E2E-READY " + kind)
        self.builder(number, kind)
        return number

    def build_and_merge(self, name: str, pieces: list[int]) -> None:
        before = self.github_calls() if not self.real else ""
        flags = ["--unattended"] if self.app else []
        self.data("python3", self.runner, "--run", name, "--pieces",
                  ",".join(map(str, pieces)), *flags, "--json")
        run = self.record(name)
        checked(run["status"] == "finished", "E2E-RUN finished")
        final = run["integration"]["final"]
        checked(final.get("main", {}).get("status") == "green",
                "E2E-JOIN green; actual run: " + json.dumps(run))
        checked(run["review"]["tracks"]["main"]["status"] == "clean", "E2E-REVIEW clean")
        entry = run["pull_requests"]["main"]
        checked(run["review"]["tracks"]["main"]["reviewed"] == final["main"]["head"] ==
                entry["head"], "E2E-HEAD review and judges cover the pull request head")
        if len(pieces) == 2:
            checked(final["main"]["checked"]["checks"] == 8 and
                    final["main"]["checked"]["held_out"] == 4,
                    "E2E-JUDGE both pieces and all four held-out cases ran")
        checked(not run["merge_pre_approved"], "E2E-MERGE person decides")
        if not self.app:
            checked(self.github_calls() == before, "E2E-LOCAL the run made no GitHub call")
            checked(entry["state"] == "waiting" and not entry["pull_request"],
                    "E2E-LOCAL the pull request waits")
            checked("gate.py sync" in entry["next"], "E2E-LOCAL exact queue command")
            self.queue_sync()
            # Today's waiting entry remains unchanged after sync. The person can still
            # push and open a pull request themselves, outside the kit's completion path.
            opened = self.data("python3", "-m", "loop.run.pull_request", "open",
                               "--run", name, "--json")
            checked(opened["opened"][0]["status"] == "already",
                    "E2E-LOCAL waiting entry is retained after sync")
            self.call("git", "push", "origin", entry["branch"], person=True)
            body = "Manual rehearsal merge.\n" + "\n".join(
                "Closes " + "#" + str(n) for n in pieces)
            made = self.call("gh", "pr", "create", "--base", "main", "--head", entry["branch"],
                             "--title", "Manual " + name, "--body", body, person=True)
            pr = made.stdout.strip().rsplit("/", 1)[-1]
        else:
            for number in pieces:
                checked(self.state(number) == "approval", "E2E-APPROVAL local piece")
            pr = str(entry["pull_request"])
        if self.real:
            input(f"Merge pull request {pr} on GitHub, then press Return: ")
        else:
            self.call("gh", "pr", "merge", pr, "--merge", "--match-head-commit", entry["head"])
        if self.app:
            self.data("python3", self.gate, "check-main", "--json")
        else:
            calls = self.github_calls()
            result = self.data("python3", self.gate, "check-main", "--json")
            checked(not result["merges"] and self.github_calls() == calls,
                    "E2E-LOCAL check-main records no manual merge without the App")
            remaining = self.record(name)["pull_requests"]["main"]
            checked(remaining["state"] == "waiting" and remaining["pull_request"] == 0,
                    "E2E-LOCAL manual merge is not adopted")
        self.call("git", "fetch", "origin", "main")
        self.call("git", "merge", "--ff-only", "origin/main")
        for number in pieces:
            checked(self.state(number) == ("done" if self.app else "review"),
                    "E2E-DONE local piece, or the recorded before-App gap")
        if not self.real:
            state: dict[str, Any] = json.loads(Path(self.env["FAKE_GH_STATE"]).read_text())
            issues = [i for i in state["issues"] if i["number"] in pieces]
            checked(len(issues) == len(pieces), "E2E-DONE issues exist")
            checked(all(i["state"] == "closed" and
                        ("state:done" if self.app else "state:review") in i["labels"]
                        for i in issues),
                    "E2E-DONE GitHub issues and labels")
            if self.app:
                checked(all(any(str(e["actor"]).endswith("[bot]") for e in i["events"])
                            for i in issues), "E2E-APP App writes the labels")
            else:
                checked(all(e["actor"] == "replay-person" for i in issues for e in i["events"]),
                        "E2E-LOCAL only the person wrote GitHub")
        self.data("python3", str(self.kit / "scripts/records-check.py"),
                  *[arg for n in pieces for arg in ("--closing", str(n))], "--json")

    def run(self) -> None:
        self.found()
        scaffold = self.scaffold()
        if not self.app:
            for flag in ("--unattended", "--merge-pre-approved"):
                result = self.call("python3", self.runner, "--run", "refuse-app",
                                   "--pieces", str(scaffold), flag, "--json", codes=(3,))
                checked("second half" in result.stderr and "next:" in result.stderr,
                        "E2E-LOCAL " + flag + " names the missing setup half")
        self.build_and_merge("core-scaffold", [scaffold])
        print("  ok: scaffold built and merged; " +
              ("recorded done" if self.app else "manual completion gap reproduced"), flush=True)
        # A person configures the runner now that it exists. This is preparation
        # for the later pieces, not a claim that the kit updates the policy itself.
        policy_path = self.project / ".agents/loop/policy.json"
        if self.real:
            input("Set test_command in .agents/loop/policy.json to python3 -m pytest -q, "
                  "commit that change, then press Return: ")
        else:
            configured = json.loads(policy_path.read_text())
            configured["test_command"] = "python3 -m pytest -q"
            policy_path.write_text(json.dumps(configured, indent=2) + "\n")
            self.call("git", "add", ".agents/loop/policy.json", person=True)
            self.call("git", "commit", "-m", "Set the project's test command", person=True)
        checked(json.loads(policy_path.read_text())["test_command"] == "python3 -m pytest -q",
                "E2E-PERSON test command configured")
        feature, bug = self.shape("feature"), self.shape("bug")
        self.build_and_merge("core-pieces", [feature, bug])
        changelog = (self.project / "CHANGELOG.md").read_text()
        for number in (scaffold, feature, bug):
            checked(len(re.findall(r"\bpiece " + str(number) + r"\b", changelog)) == 1,
                    "E2E-CHANGELOG one entry per merged piece")
        checked("### Added" in changelog and "### Fixed" in changelog, "E2E-CHANGELOG types")
        self.call("python3", "-m", "pytest", "-q")
        print("  ok: feature and bug " + ("done" if self.app else "waiting after manual merge") +
              ", two new changelog entries and records green", flush=True)
        print("  scratch: " + str(self.base), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("local", "app", "both"), default="both")
    parser.add_argument("--real", type=Path, help="manual App smoke project")
    parser.add_argument("--kit-dir", type=Path)
    args = parser.parse_args()
    if args.real:
        checked(os.environ.get("AI_LOOP_KIT_REAL_SMOKE") == "1" and sys.stdin.isatty()
                and sys.stdout.isatty(), "E2E-REAL manual smoke needs opt-in and a terminal")
        checked(args.case == "app", "E2E-REAL the manual smoke covers the App path")
        checked(not any(key.startswith("FAKE_") for key in os.environ),
                "E2E-REAL leave the stand-in environment before the manual smoke")
        for tool in ("claude", "gh"):
            location = shutil.which(tool)
            checked(location is not None and "tests/stand-ins" not in str(Path(location).resolve()),
                    "E2E-REAL use the real " + tool + " command")
    for app in ((False, True) if args.case == "both" else (args.case == "app",)):
        print("Core rehearsal: " + ("App" if app else "before the App"), flush=True)
        Rehearsal(app, args.real, args.kit_dir).run()
    print("Core end-to-end checks passed.")


if __name__ == "__main__":
    main()
