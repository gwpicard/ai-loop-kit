"""Unit tests for kit/scripts/loop/github.py: the gh wrapper, credential() and the push step.

These tests use the GitHub stand-in (tests/stand-ins/fake-github/gh) and a stand-in
App key made with openssl in a throwaway folder. Nothing reaches the real GitHub.
"""

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import cli, github  # noqa: E402
from loop.paths import Paths  # noqa: E402

STAND_IN = ROOT / "tests" / "stand-ins"
APP = json.loads((STAND_IN / "fake-app" / "app.json").read_text(encoding="utf-8"))


def make_key(folder: Path) -> Path:
    done = subprocess.run(
        [str(STAND_IN / "fake-app" / "make-key.sh"), str(folder)],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(done.stdout.strip())


_SHARED: list[bytes] = []


def place_key(folder: Path) -> Path:
    """The stand-in key in `folder`. One key is made per test run, since making one is slow."""
    if not _SHARED:
        _SHARED.append(make_key(Path(tempfile.mkdtemp())).read_bytes())
    folder.mkdir(parents=True, exist_ok=True)
    key = folder / "app-key.pem"
    descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_SHARED[0])
    return key


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True, env=GIT_ENV
    )
    return done.stdout.strip()


GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


class Project:
    """A throwaway project with a bare origin, the stand-in gh first on PATH and an App key."""

    def __init__(self, *, app: bool = True) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.root = self.base / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.base / "origin.git")],
                       check=True, env=GIT_ENV)
        git(self.base, "init", "-q", "-b", "main", str(self.root))
        git(self.root, "remote", "add", "origin", str(self.base / "origin.git"))
        (self.root / "README.md").write_text("start\n", encoding="utf-8")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-q", "-m", "start")
        git(self.root, "push", "-q", "origin", "main")
        self.paths = Paths.for_project(
            self.root, data_base=self.base / "data", kit_folder=ROOT / "kit"
        )
        self.bin = self.base / "bin"
        self.bin.mkdir()
        (self.bin / "gh").symlink_to(STAND_IN / "fake-github" / "gh")
        self.state = self.base / "gh-state.json"
        self.log = self.base / "gh.log"
        self.key = place_key(self.paths.app_key_file.parent)
        if app:
            self.write_settings()
        self.env = {
            **GIT_ENV,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "FAKE_GH_STATE": str(self.state),
            "FAKE_GH_LOG": str(self.log),
            "FAKE_APP_KEY": str(self.key),
        }
        self.env.pop("CLAUDECODE", None)

    def write_settings(self, **extra: Any) -> None:
        self.paths.local_settings.parent.mkdir(parents=True, exist_ok=True)
        app = {"app_id": APP["app_id"], "installation_id": APP["installation_id"],
               "slug": APP["slug"], **extra}
        self.paths.local_settings.write_text(
            json.dumps({"github_app": app}), encoding="utf-8"
        )

    def runner(self, record: list[dict[str, Any]] | None = None) -> Callable[..., Any]:
        """subprocess.run with this project's environment, recording each call."""

        def run(command: list[str], **kwargs: Any) -> Any:
            env = dict(self.env)
            env.update(kwargs.pop("env", None) or {})
            if record is not None:
                record.append({"command": list(command), "env": env})
            kwargs.setdefault("cwd", str(self.root))
            return subprocess.run(command, env=env, **kwargs)  # noqa: PLW1510

        return run

    def gh_calls(self) -> list[str]:
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text(encoding="utf-8").splitlines()
                if line.startswith("CALL")]

    def stand_in(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(self.state.read_text(encoding="utf-8"))
        return loaded


def b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


class Settings(unittest.TestCase):
    def test_no_settings_file_means_no_app(self) -> None:
        project = Project(app=False)
        self.assertIsNone(github.app_settings(project.paths))

    def test_the_key_path_defaults_to_the_one_paths_names(self) -> None:
        project = Project()
        settings = github.app_settings(project.paths)
        assert settings is not None
        self.assertEqual(settings.key_file, project.paths.app_key_file)
        self.assertEqual(settings.app_id, APP["app_id"])

    def test_the_settings_file_may_name_another_key_path(self) -> None:
        project = Project()
        other = make_key(project.base / "elsewhere")
        project.write_settings(key_file=str(other))
        settings = github.app_settings(project.paths)
        assert settings is not None
        self.assertEqual(settings.key_file, other)

    def test_a_settings_file_that_cannot_be_read_is_an_environment_fault(self) -> None:
        project = Project(app=False)
        project.paths.local_settings.parent.mkdir(parents=True, exist_ok=True)
        project.paths.local_settings.write_text("{not json", encoding="utf-8")
        with self.assertRaises(github.GitHubError) as caught:
            github.app_settings(project.paths)
        self.assertTrue(caught.exception.next_command)


class Token(unittest.TestCase):
    def test_the_jwt_is_rs256_signed_by_openssl_with_the_app_key(self) -> None:
        project = Project()
        calls: list[dict[str, Any]] = []
        jwt = github.make_jwt(APP["app_id"], project.key, now=1_700_000_000,
                              runner=project.runner(calls))
        header, payload, signature = jwt.split(".")
        self.assertEqual(json.loads(b64url_decode(header)), {"alg": "RS256", "typ": "JWT"})
        claims = json.loads(b64url_decode(payload))
        self.assertEqual(claims["iss"], str(APP["app_id"]))
        self.assertEqual(claims["iat"], 1_700_000_000 - 60)
        self.assertLessEqual(claims["exp"] - claims["iat"], 600)
        self.assertEqual(calls[0]["command"][:3], ["openssl", "dgst", "-sha256"])
        self.assertIn("-sign", calls[0]["command"])
        # The signature checks out against the public half of the key.
        public = project.base / "public.pem"
        subprocess.run(["openssl", "rsa", "-in", str(project.key), "-pubout", "-out",
                        str(public)], capture_output=True, check=True)
        sig_file = project.base / "sig.bin"
        sig_file.write_bytes(b64url_decode(signature))
        done = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(public), "-signature",
             str(sig_file)],
            input=f"{header}.{payload}".encode("ascii"),
            capture_output=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_credential_makes_a_short_lived_installation_token(self) -> None:
        project = Project()
        found = github.credential(project.paths, runner=project.runner(), env=project.env)
        assert found is not None
        self.assertEqual(found.kind, "app")
        self.assertTrue(found.token)
        self.assertEqual(found.actor, APP["slug"] + "[bot]")
        calls = project.gh_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn(f"app/installations/{APP['installation_id']}/access_tokens", calls[0])

    def test_the_token_is_kept_in_memory_only(self) -> None:
        project = Project()
        github.forget_tokens()
        found = github.credential(project.paths, runner=project.runner(), env=project.env)
        assert found is not None and found.token
        again = github.credential(project.paths, runner=project.runner(), env=project.env)
        assert again is not None
        self.assertEqual(again.token, found.token)
        self.assertEqual(len(project.gh_calls()), 1, "the second call reuses the token")
        for path in [*project.root.rglob("*"), *project.paths.data_dir.rglob("*")]:
            if path.is_file() and ".git" not in path.parts:
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self.assertNotIn(found.token, text, f"the token was written to {path}")

    def test_a_jwt_from_the_wrong_key_is_refused_by_the_stand_in(self) -> None:
        project = Project()
        github.forget_tokens()
        other = make_key(project.base / "wrong")
        project.write_settings(key_file=str(other))
        with self.assertRaises(github.GitHubError):
            github.credential(project.paths, runner=project.runner(), env=project.env)

    def test_a_missing_key_is_an_environment_fault_naming_setup(self) -> None:
        project = Project()
        github.forget_tokens()
        project.write_settings(key_file=str(project.base / "no-such-key.pem"))
        with self.assertRaises(github.GitHubError) as caught:
            github.credential(project.paths, runner=project.runner(), env=project.env)
        self.assertIn("/setup", caught.exception.next_command)

    def test_the_person_credential_is_refused_in_an_agent_session(self) -> None:
        project = Project()
        with self.assertRaises(github.GitHubError) as caught:
            github.credential(project.paths, as_person=True, env={"CLAUDECODE": "1"})
        self.assertIn("gate.py sync", caught.exception.next_command)
        person = github.credential(project.paths, as_person=True, env={})
        assert person is not None
        self.assertEqual(person.kind, "person")
        self.assertIsNone(person.token)


class EveryCallGoesThroughCredential(unittest.TestCase):
    def test_every_gh_call_carries_the_app_token_from_credential(self) -> None:
        project = Project()
        github.forget_tokens()
        spawned: list[dict[str, Any]] = []
        asked: list[bool] = []
        real = github.credential

        def counting(paths: Paths, **kwargs: Any) -> Any:
            asked.append(True)
            return real(paths, **kwargs)

        hub = github.GitHub(project.paths, runner=project.runner(spawned), env=project.env,
                            credential_fn=counting)
        self.assertTrue(hub.available)
        number = hub.create_issue("A piece", "body text", ["state:shaping", "type:feature"])
        hub.edit_labels(number, add=["needs-you"], remove=[])
        hub.set_body(number, "new body")
        hub.comment(number, "a comment")
        hub.read_issue(number)
        hub.close(number, "not planned")
        hub.reopen(number)
        hub.create_label("state:review", "5319E7", "In review")
        hub.list_labels()
        gh_runs = [c for c in spawned if c["command"][0] == "gh"]
        token_runs = [c for c in gh_runs if "access_tokens" in " ".join(c["command"])]
        work_runs = [c for c in gh_runs if c not in token_runs]
        self.assertEqual(len(work_runs), 9)
        self.assertGreaterEqual(len(asked), 9, "credential() is asked before every call")
        token = real(project.paths, runner=project.runner(), env=project.env)
        assert token is not None
        for call in work_runs:
            self.assertEqual(call["env"].get("GH_TOKEN"), token.token)
            config = call["env"].get("GH_CONFIG_DIR", "")
            self.assertTrue(config.startswith(str(project.paths.data_dir)),
                            "gh never reads the person's own config folder")
        state = project.stand_in()
        issue = state["issues"][0]
        self.assertEqual({e["actor"] for e in issue["events"]}, {APP["slug"] + "[bot]"})
        self.assertEqual(issue["comments"][0]["author"], APP["slug"] + "[bot]")

    def test_no_kit_script_or_hook_starts_gh_itself(self) -> None:
        """Every agent script reaches GitHub through loop/github.py, so through credential()."""
        # Borrowed files that a later piece adapts. Each is named with that piece.
        later = {
            # It only reads `gh auth status` and `gh repo view`, to report
            # readiness. pre-run-check.py (an agent script) also calls it, with
            # --for-run, before a run. That call is open for the maintainer to judge.
            "kit/scripts/check-tooling.sh",
        }
        python_spawn = re.compile(r"""[\[(]\s*["']gh["']""")
        shell_spawn = re.compile(r"""(^|[;&|(`]|\$\(|\bthen|\bdo)\s*gh\s+[a-z]""", re.MULTILINE)
        found = []
        for folder in (ROOT / "kit" / "scripts", ROOT / "kit" / "hooks"):
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                name = str(path.relative_to(ROOT))
                if name == "kit/scripts/loop/github.py" or name in later:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                code = "\n".join(line for line in text.splitlines()
                                 if not line.lstrip().startswith("#"))
                first = text.split("\n", 1)[0]
                shell = path.suffix == ".sh" or ("sh" in first and first.startswith("#!")
                                                 and "python" not in first)
                if (shell_spawn if shell else python_spawn).search(code):
                    found.append(name)
        self.assertEqual(found, [], "only loop/github.py starts gh, through credential()")

    def test_the_wrapper_starts_gh_in_one_place(self) -> None:
        text = (ROOT / "kit" / "scripts" / "loop" / "github.py").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"""\[\s*["']gh["']""", text)), 1)


class PullRequestState(unittest.TestCase):
    def test_with_the_app_the_state_is_read_as_the_app(self) -> None:
        project = Project()
        github.forget_tokens()
        state = {"repo": "someone/project", "next": 1, "issues": [], "pull_requests": [
            {"number": 1, "head": "piece-1", "state": "MERGED", "head_oid": "abc123"}]}
        project.state.write_text(json.dumps(state), encoding="utf-8")
        hub = github.GitHub(project.paths, runner=project.runner(), env=project.env)
        self.assertEqual(hub.pr_state("piece-1"), "merged abc123")
        self.assertEqual(hub.pr_state("piece-2"), "none")

    def test_without_the_app_the_state_is_not_read(self) -> None:
        project = Project(app=False)
        spawned: list[dict[str, Any]] = []
        hub = github.GitHub(project.paths, runner=project.runner(spawned), env=project.env)
        with self.assertRaises(github.NoApp):
            hub.pr_state("piece-1")
        self.assertEqual(spawned, [])


class NoApp(unittest.TestCase):
    def test_without_the_app_nothing_starts_gh_or_reads_the_keychain(self) -> None:
        project = Project(app=False)
        spawned: list[dict[str, Any]] = []
        hub = github.GitHub(project.paths, runner=project.runner(spawned), env=project.env)
        self.assertFalse(hub.available)
        writes: list[Callable[[], Any]] = [
            lambda: hub.create_issue("t", "b", []),
            lambda: hub.edit_labels(1, add=["state:ready"], remove=[]),
            lambda: hub.set_body(1, "b"),
            lambda: hub.comment(1, "c"),
            lambda: hub.read_issue(1),
            lambda: hub.close(1, "completed"),
            lambda: hub.reopen(1),
            lambda: hub.create_label("needs-you", "D93F0B", "x"),
        ]
        for write in writes:
            with self.assertRaises(github.NoApp) as caught:
                write()
            self.assertIn("gate.py sync", caught.exception.next_command)
        self.assertEqual(spawned, [], "no program ran at all")
        self.assertEqual(project.gh_calls(), [])


class ReadTwice(unittest.TestCase):
    def test_a_change_between_the_two_reads_is_refused(self) -> None:
        project = Project()
        github.forget_tokens()
        hub = github.GitHub(project.paths, runner=project.runner(), env=project.env)
        number = hub.create_issue("A piece", "body", ["state:shaping"])
        first = hub.read_issue(number)
        state = project.stand_in()
        state.setdefault("faults", {})["race"] = {
            "number": number, "on_read": 1, "add": ["state:ready"]
        }
        project.state.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(github.ReadTwiceError):
            hub.read_again(number, first)

    def test_no_change_reads_clean(self) -> None:
        project = Project()
        github.forget_tokens()
        hub = github.GitHub(project.paths, runner=project.runner(), env=project.env)
        number = hub.create_issue("A piece", "body", ["state:shaping"])
        first = hub.read_issue(number)
        self.assertEqual(hub.read_again(number, first)["labels"], ["state:shaping"])


class Push(unittest.TestCase):
    def _branch(self, project: Project, name: str, text: str) -> None:
        git(project.root, "checkout", "-q", "-b", name)
        (project.root / "change.txt").write_text(text, encoding="utf-8")
        git(project.root, "add", "change.txt")
        git(project.root, "commit", "-q", "-m", "a change")
        git(project.root, "checkout", "-q", "main")

    def test_a_clean_branch_is_pushed_after_the_scan(self) -> None:
        project = Project(app=False)
        self._branch(project, "piece-1", "plain words\n")
        calls: list[dict[str, Any]] = []
        result = github.push(project.paths, "piece-1", runner=project.runner(calls),
                             env=project.env)
        self.assertEqual(result["pushed"], "piece-1")
        scan = [i for i, c in enumerate(calls) if "secret-scan.py" in " ".join(c["command"])]
        push = [i for i, c in enumerate(calls) if c["command"][:2] == ["git", "push"]
                or c["command"][1:4] == ["-C", str(project.root), "push"]]
        self.assertTrue(scan and push and scan[0] < push[0], "the scan runs before the push")
        heads = git(project.root, "ls-remote", "--heads", "origin")
        self.assertIn("refs/heads/piece-1", heads)

    def test_a_branch_with_a_secret_is_refused_and_not_pushed(self) -> None:
        project = Project(app=False)
        secret = "gh" + "p_" + "AbCdEf" * 6
        self._branch(project, "piece-2", f"token = {secret}\n")
        with self.assertRaises(github.GitHubError) as caught:
            github.push(project.paths, "piece-2", runner=project.runner(), env=project.env)
        self.assertNotIn(secret, str(caught.exception))
        heads = git(project.root, "ls-remote", "--heads", "origin")
        self.assertNotIn("piece-2", heads)

    def test_main_is_never_pushed(self) -> None:
        project = Project(app=False)
        with self.assertRaises(github.GitHubError):
            github.push(project.paths, "main", runner=project.runner(), env=project.env)

    def _fake_github(self, project: Project) -> Path:
        """A bare repository that git reaches for https://github.com/someone/project.git.

        The test's own git config rewrites that address to a local folder, so the
        push the gate builds runs for real and reaches no network.
        """
        hosted = project.base / "hosted" / "someone" / "project.git"
        hosted.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(hosted)],
                       check=True, env=GIT_ENV)
        git(project.root, "push", "-q", str(hosted), "main")
        config = project.base / "gitconfig"
        config.write_text(f'[url "file://{project.base}/hosted/"]\n'
                          "\tinsteadOf = https://github.com/\n", encoding="utf-8")
        project.env["GIT_CONFIG_GLOBAL"] = str(config)
        return hosted

    def _push_call(self, calls: list[dict[str, Any]]) -> dict[str, Any]:
        found = [c for c in calls if "push" in c["command"] and c["command"][0] == "git"]
        self.assertEqual(len(found), 1)
        return found[0]

    def _config(self, env: dict[str, str]) -> dict[str, str]:
        count = int(env.get("GIT_CONFIG_COUNT", "0"))
        return {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(count)}

    def test_an_ssh_remote_is_pushed_over_https_as_the_app(self) -> None:
        for remote in ("git@github.com:someone/project.git",
                       "ssh://git@github.com/someone/project.git",
                       "https://github.com/someone/project"):
            with self.subTest(remote=remote):
                project = Project()
                github.forget_tokens()
                hosted = self._fake_github(project)
                self._branch(project, "piece-4", "plain words\n")
                git(project.root, "remote", "set-url", "origin", remote)
                calls: list[dict[str, Any]] = []
                result = github.push(project.paths, "piece-4", runner=project.runner(calls),
                                     env=project.env)
                self.assertEqual(result["pushed"], "piece-4")
                call = self._push_call(calls)
                self.assertIn("https://github.com/someone/project.git", call["command"])
                self.assertNotIn(remote, call["command"])
                self.assertNotIn("origin", call["command"])
                env = call["env"]
                self.assertEqual(env.get("GIT_TERMINAL_PROMPT"), "0")
                config = self._config(env)
                self.assertEqual(config.get("credential.helper"), "")
                self.assertEqual(config.get("protocol.ssh.allow"), "never")
                self.assertIn("false", env.get("GIT_SSH_COMMAND", ""))
                token = github.credential(project.paths, runner=project.runner(),
                                          env=project.env)
                assert token is not None and token.token
                header = config.get("http.https://github.com/.extraheader", "")
                basic = base64.b64encode(f"x-access-token:{token.token}".encode()).decode()
                self.assertIn(basic, header, "the push carries the stand-in App's token")
                heads = git(project.root, "ls-remote", "--heads", str(hosted))
                self.assertIn("refs/heads/piece-4", heads)

    def test_a_remote_that_is_neither_github_nor_a_local_path_is_refused(self) -> None:
        for remote in ("git@gitlab.com:someone/project.git", "https://example.com/x/y.git",
                       "https://github.com.evil.example/someone/project.git"):
            with self.subTest(remote=remote):
                project = Project()
                self._branch(project, "piece-5", "plain\n")
                git(project.root, "remote", "set-url", "origin", remote)
                calls: list[dict[str, Any]] = []
                with self.assertRaises(github.GitHubError) as caught:
                    github.push(project.paths, "piece-5", runner=project.runner(calls),
                                env=project.env)
                self.assertEqual(caught.exception.code, cli.ExitCode.REFUSED)
                self.assertFalse([c for c in calls if "push" in c["command"]])

    def test_a_local_remote_never_uses_a_credential_helper_or_ssh(self) -> None:
        project = Project(app=False)
        self._branch(project, "piece-6", "plain\n")
        calls: list[dict[str, Any]] = []
        github.push(project.paths, "piece-6", runner=project.runner(calls), env=project.env)
        env = self._push_call(calls)["env"]
        self.assertEqual(env.get("GIT_TERMINAL_PROMPT"), "0")
        self.assertEqual(self._config(env).get("credential.helper"), "")
        self.assertIn("false", env.get("GIT_SSH_COMMAND", ""))

    def test_a_github_remote_without_the_app_waits_for_the_person(self) -> None:
        project = Project(app=False)
        self._branch(project, "piece-3", "plain\n")
        git(project.root, "remote", "set-url", "origin", "https://github.com/someone/project.git")
        calls: list[dict[str, Any]] = []
        with self.assertRaises(github.NoApp):
            github.push(project.paths, "piece-3", runner=project.runner(calls), env=project.env)
        self.assertFalse(any(c["command"][:2] == ["git", "push"] for c in calls))


if __name__ == "__main__":
    unittest.main()
