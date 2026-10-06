"""The gate's one way to GitHub: the `gh` wrapper, `credential()` and the push step.

Every GitHub call the gate makes goes through `GitHub._gh`, and every one asks
`credential()` first. Only `_run_gh` starts `gh`. A test checks both.

`credential()` acts as the gate's GitHub App:

- It reads the App's numbers from the machine-local settings file
  (`.agents/loop/local.json`, key `github_app`: `app_id`, `installation_id`,
  `slug`, and an optional `key_file`). The key path defaults to the one
  `loop/paths.py` names, outside the project.
- It signs a JWT with RS256 by calling `openssl dgst -sha256 -sign <key>`,
  because the standard library has no RSA signing.
- It trades the JWT for a short-lived installation token, which it keeps in
  memory only. Nothing writes the token to a file.

Every `gh` the gate starts gets the token in `GH_TOKEN` and an empty config
folder of its own in `GH_CONFIG_DIR`, so `gh` never reads the person's sign-in
or the keychain.

With no App settings there is no credential. Then `GitHub` starts no program at
all: every call raises `NoApp`, whose `next:` line names `gate.py sync`. Only
the person runs `gate.py sync`, with their own sign-in (`as_person=True`).
`credential()` refuses that in an agent session, and the guard hook refuses the
command too.

The push step runs `secret-scan.py --range` first and never pushes `main`.
"""

from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loop import cli
from loop.paths import Paths

Runner = Callable[..., Any]  # the shape of subprocess.run

SCRIPTS = Path(__file__).resolve().parents[1]
GATE_PY = SCRIPTS / "gate.py"
SECRET_SCAN = SCRIPTS / "secret-scan.py"
AGENT_SESSION = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")
OTHER_TOKENS = ("GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
SETUP_NEXT = "run the second half of /setup again to install the App key, then run this again"
TOKEN_MARGIN = 120  # seconds; a token closer than this to its end is made again


class GitHubError(Exception):
    """A GitHub step that failed or was refused. Carries the exit code and the next command."""

    def __init__(
        self, message: str, *, next_command: str, code: cli.ExitCode = cli.ExitCode.ENVIRONMENT
    ) -> None:
        super().__init__(message)
        self.message = message
        self.next_command = next_command
        self.code = code


class NoApp(GitHubError):
    """No App credential: the gate does not act on GitHub, and the person syncs later."""

    def __init__(self, root: Path) -> None:
        super().__init__(
            "the gate's GitHub App is not set up yet, so the gate does not act on GitHub",
            next_command=sync_command(root),
            code=cli.ExitCode.REFUSED,
        )


class ReadTwiceError(GitHubError):
    """The piece changed between the gate's two reads."""

    def __init__(self, number: int) -> None:
        super().__init__(
            f"issue {number} moved between the gate's two reads, so another session or the "
            "person changed it",
            next_command="run gate.py report, then the same command again",
            code=cli.ExitCode.REFUSED,
        )


def sync_command(root: Path) -> str:
    """The exact command for the person to send the queued GitHub writes."""
    return (
        "tell the person to run, in their own terminal: "
        f"cd {shlex.quote(str(root))} && python3 {shlex.quote(str(GATE_PY))} sync"
    )


def in_agent_session(env: Mapping[str, str]) -> bool:
    return any(env.get(name) for name in AGENT_SESSION)


# --- the App's settings and its token ---------------------------------------------


@dataclass(frozen=True)
class AppSettings:
    app_id: int
    installation_id: int
    slug: str
    key_file: Path


def app_settings(paths: Paths) -> AppSettings | None:
    """The App's settings from the machine-local file, or None when there is no App yet."""
    path = paths.local_settings
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GitHubError(
            f"the machine-local settings file {path} cannot be read ({error})",
            next_command=SETUP_NEXT,
        ) from error
    app = data.get("github_app") if isinstance(data, dict) else None
    if app is None:
        return None
    try:
        key = app.get("key_file")
        return AppSettings(
            app_id=int(app["app_id"]),
            installation_id=int(app["installation_id"]),
            slug=str(app.get("slug") or "the-app"),
            key_file=Path(key) if key else paths.app_key_file,
        )
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise GitHubError(
            f"github_app in {path} needs app_id and installation_id as numbers",
            next_command=SETUP_NEXT,
        ) from error


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_jwt(
    app_id: int, key_file: Path, *, now: int | None = None, runner: Runner = subprocess.run
) -> str:
    """A JWT for the App, signed RS256 by openssl. It lives under ten minutes."""
    issued = int(time.time() if now is None else now) - 60
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {"iat": issued, "exp": issued + 540, "iss": str(app_id)}
    payload = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    try:
        done = runner(
            ["openssl", "dgst", "-sha256", "-sign", str(key_file)],
            input=signing_input,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise GitHubError(
            f"openssl could not be started ({error})",
            next_command="install openssl, then run this again",
        ) from error
    if done.returncode != 0 or not done.stdout:
        raise GitHubError(
            "openssl could not sign with the App key", next_command=SETUP_NEXT
        )
    signature: bytes = done.stdout
    return f"{header}.{payload}.{_b64url(signature)}"


@dataclass(frozen=True)
class Credential:
    kind: str  # "app" or "person"
    token: str | None  # None: the person's own sign-in, in their own terminal
    actor: str


_TOKENS: dict[tuple[int, int], tuple[str, float]] = {}


def forget_tokens() -> None:
    """Drop the tokens held in memory, so the next call makes a new one."""
    _TOKENS.clear()


def _gh_env(paths: Paths, token: str | None, env: Mapping[str, str]) -> dict[str, str]:
    out = dict(env)
    if token is None:
        return out
    for name in OTHER_TOKENS:
        out.pop(name, None)
    config = paths.data_dir / "gh-app-config"
    os.makedirs(config, mode=0o700, exist_ok=True)
    out.update(
        {
            "GH_TOKEN": token,
            "GH_CONFIG_DIR": str(config),
            "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1",
        }
    )
    return out


def _run_gh(
    paths: Paths,
    args: Sequence[str],
    token: str | None,
    *,
    runner: Runner,
    env: Mapping[str, str],
    stdin: str | None = None,
) -> Any:
    """The one place that starts gh."""
    try:
        return runner(
            ["gh", *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            env=_gh_env(paths, token, env),
            cwd=str(paths.root),
        )
    except OSError as error:
        raise GitHubError(
            f"the GitHub command-line tool could not be started ({error})",
            next_command="install gh from https://cli.github.com, then run this again",
        ) from error


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "no message")


def credential(
    paths: Paths,
    *,
    as_person: bool = False,
    runner: Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
) -> Credential | None:
    """The credential for a GitHub call: the App's token, the person's sign-in, or None.

    None means there is no App yet, and the caller must not act on GitHub.
    """
    env = os.environ if env is None else env
    if as_person:
        if in_agent_session(env):
            raise GitHubError(
                "gate.py sync acts with the person's own sign-in, and only the person runs it",
                next_command=sync_command(paths.root),
                code=cli.ExitCode.REFUSED,
            )
        return Credential("person", None, "the person")
    settings = app_settings(paths)
    if settings is None:
        return None
    actor = f"{settings.slug}[bot]"
    held = _TOKENS.get((settings.app_id, settings.installation_id))
    if held and held[1] - TOKEN_MARGIN > time.time():
        return Credential("app", held[0], actor)
    if not settings.key_file.is_file():
        raise GitHubError(f"the App key is missing at {settings.key_file}", next_command=SETUP_NEXT)
    jwt = make_jwt(settings.app_id, settings.key_file, runner=runner)
    done = _run_gh(
        paths,
        [
            "api",
            "--method",
            "POST",
            f"app/installations/{settings.installation_id}/access_tokens",
            "-H",
            f"Authorization: Bearer {jwt}",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        jwt,
        runner=runner,
        env=env,
    )
    if done.returncode != 0:
        raise GitHubError(
            f"GitHub refused the App's token request ({_first_line(done.stderr)})",
            next_command=SETUP_NEXT,
        )
    try:
        answer = json.loads(done.stdout)
        token = str(answer["token"])
    except (ValueError, KeyError, TypeError) as error:
        raise GitHubError(
            "GitHub's answer to the token request holds no token", next_command=SETUP_NEXT
        ) from error
    _TOKENS[(settings.app_id, settings.installation_id)] = (token, time.time() + 3300)
    return Credential("app", token, actor)


# --- the wrapper ------------------------------------------------------------------------


class GitHub:
    """GitHub as the gate sees it. Every call asks `credential()` first."""

    def __init__(
        self,
        paths: Paths,
        *,
        runner: Runner = subprocess.run,
        env: Mapping[str, str] | None = None,
        credential_fn: Callable[..., Credential | None] = credential,
        as_person: bool = False,
    ) -> None:
        self.paths = paths
        self.runner = runner
        self.env: Mapping[str, str] = os.environ if env is None else env
        self.credential_fn = credential_fn
        self.as_person = as_person

    @property
    def available(self) -> bool:
        """True when the gate may act on GitHub: with the App, or as the person in sync."""
        return self.as_person or app_settings(self.paths) is not None

    def _gh(self, args: Sequence[str], stdin: str | None = None) -> str:
        found = self.credential_fn(
            self.paths, as_person=self.as_person, runner=self.runner, env=self.env
        )
        if found is None:
            raise NoApp(self.paths.root)
        done = _run_gh(
            self.paths, args, found.token, runner=self.runner, env=self.env, stdin=stdin
        )
        if done.returncode != 0:
            raise GitHubError(
                f"GitHub did not answer, so nothing changed ({_first_line(done.stderr)})",
                next_command="check the network and the App's access, then run this again",
            )
        out: str = done.stdout
        return out

    def read_issue(self, number: int) -> dict[str, Any]:
        text = self._gh(["api", f"repos/{{owner}}/{{repo}}/issues/{number}"])
        try:
            data = json.loads(text)
        except ValueError as error:
            raise GitHubError(
                f"GitHub's answer for issue {number} is not JSON",
                next_command="run the same command again",
            ) from error
        if not isinstance(data, dict):
            raise GitHubError(
                f"GitHub's answer for issue {number} is not an issue",
                next_command="run the same command again",
            )
        if data.get("pull_request"):
            raise GitHubError(
                f"{number} is a pull request, not a piece",
                next_command="gate.py report",
                code=cli.ExitCode.REFUSED,
            )
        labels = [
            str(item["name"] if isinstance(item, dict) else item)
            for item in data.get("labels") or []
        ]
        return {
            "number": int(data.get("number", number)),
            "title": str(data.get("title") or ""),
            "body": str(data.get("body") or ""),
            "labels": labels,
            "state": str(data.get("state") or "open").lower(),
        }

    def read_again(self, number: int, first: Mapping[str, Any]) -> dict[str, Any]:
        """The second read, just before a write. Refuses when the issue changed."""
        now = self.read_issue(number)
        if (
            sorted(now["labels"]) != sorted(first["labels"])
            or now["body"] != first["body"]
            or now["state"] != first["state"]
        ):
            raise ReadTwiceError(number)
        return now

    def create_issue(self, title: str, body: str, labels: Sequence[str]) -> int:
        args = ["issue", "create", "--title", title, "--body-file", "-"]
        if labels:
            args += ["--label", ",".join(labels)]
        address = self._gh(args, stdin=body).strip().splitlines()[-1:]
        try:
            return int(address[0].rstrip("/").rsplit("/", 1)[-1])
        except (IndexError, ValueError) as error:
            raise GitHubError(
                "GitHub made the issue but gave no address for it",
                next_command="gate.py report",
            ) from error

    def edit_labels(self, number: int, *, add: Sequence[str], remove: Sequence[str]) -> None:
        if not add and not remove:
            return
        args = ["issue", "edit", str(number)]
        if add:
            args += ["--add-label", ",".join(add)]
        if remove:
            args += ["--remove-label", ",".join(remove)]
        self._gh(args)

    def set_body(self, number: int, body: str) -> None:
        self._gh(["issue", "edit", str(number), "--body-file", "-"], stdin=body)

    def comment(self, number: int, body: str) -> None:
        self._gh(["issue", "comment", str(number), "--body-file", "-"], stdin=body)

    def close(self, number: int, reason: str) -> None:
        self._gh(["issue", "close", str(number), "--reason", reason])

    def reopen(self, number: int) -> None:
        self._gh(["issue", "reopen", str(number)])

    def list_labels(self) -> list[str]:
        text = self._gh(["label", "list", "--json", "name", "--limit", "500"])
        try:
            return [str(item["name"]) for item in json.loads(text)]
        except (ValueError, KeyError, TypeError) as error:
            raise GitHubError(
                "GitHub's list of labels cannot be read", next_command="run this again"
            ) from error

    def create_label(self, name: str, colour: str, description: str) -> None:
        self._gh(["label", "create", name, "--color", colour, "--description", description])


# --- the push step ----------------------------------------------------------------------


def _git(root: Path, args: Sequence[str], runner: Runner, env: Mapping[str, str]) -> Any:
    return runner(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
        env=dict(env),
    )


def push(
    paths: Paths,
    branch: str,
    *,
    remote: str = "origin",
    runner: Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Push one piece branch: the secret scan first, never `main`, never with force.

    A push to GitHub needs the App, and acts as the App. Without it, `NoApp`.
    """
    env = dict(os.environ if env is None else env)
    root = paths.root
    if branch in ("main", "refs/heads/main") or branch.startswith("-"):
        raise GitHubError(
            f"the gate never pushes {branch}",
            next_command="push a piece branch; main changes only through a merge",
            code=cli.ExitCode.REFUSED,
        )
    found = _git(root, ["remote", "get-url", remote], runner, env)
    if found.returncode != 0:
        raise GitHubError(f"there is no remote called {remote}", next_command="git remote -v")
    url = found.stdout.strip()
    push_env = dict(env, GIT_TERMINAL_PROMPT="0")
    if "github.com" in url:
        held = credential(paths, runner=runner, env=env)
        if held is None or held.token is None:
            raise NoApp(root)
        basic = base64.b64encode(f"x-access-token:{held.token}".encode()).decode("ascii")
        push_env.update(
            {
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}",
                "GIT_CONFIG_KEY_1": "credential.helper",
                "GIT_CONFIG_VALUE_1": "",
            }
        )
    has_remote_main = _git(
        root, ["rev-parse", "--verify", "-q", f"refs/remotes/{remote}/main"], runner, env
    )
    base = f"{remote}/main" if has_remote_main.returncode == 0 else "main"
    span = f"{base}..{branch}"
    counted = _git(root, ["rev-list", "--count", span], runner, env)
    if counted.returncode != 0:
        raise GitHubError(
            f"the branch {branch} cannot be compared with {base}",
            next_command=f"git -C {shlex.quote(str(root))} branch --list {branch}",
        )
    scanned: str | None = None
    if counted.stdout.strip() not in ("", "0"):
        scan = runner(
            [sys.executable, str(SECRET_SCAN), "--range", span, "--json"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=str(root),
        )
        if scan.returncode != 0:
            raise GitHubError(
                f"the secret scan refused the push of {branch} ({_first_line(scan.stderr)})",
                next_command="remove the secret from the branch's commits, then push again",
                code=cli.ExitCode.REFUSED,
            )
        scanned = span
    done = runner(
        ["git", "-C", str(root), "push", remote, f"{branch}:refs/heads/{branch}"],
        capture_output=True,
        text=True,
        check=False,
        env=push_env,
    )
    if done.returncode != 0:
        raise GitHubError(
            f"git push of {branch} failed ({_first_line(done.stderr)})",
            next_command="bring the branch up to date with a merge, then push again",
        )
    return {"pushed": branch, "remote": remote, "scanned": scanned}
