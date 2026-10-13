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

The push step runs `secret-scan.py --range` first and never pushes `main`. It
pushes to GitHub only over https, to an address it builds from the owner and
name, with the App's token. It never uses the person's SSH key or credential
helper. A remote that is neither GitHub nor a folder on this computer is refused.

Other kit scripts read GitHub through this module too: `spec.py`,
`worktree.sh` (through `python3 -m loop.github pr-state <branch>`) and
`check-tooling.sh` (through `python3 -m loop.github repo-view`).
"""

from __future__ import annotations

import base64
import json
import os
import re
import selectors
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loop import cli
from loop.paths import PathError, Paths, find_project_root

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
        self,
        message: str,
        *,
        next_command: str,
        code: cli.ExitCode = cli.ExitCode.ENVIRONMENT,
        not_found: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.next_command = next_command
        self.code = code
        self.not_found = not_found


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


def gate_command(root: Path) -> str:
    """`cd <project> && python3 <gate.py>`, quoted for a shell."""
    return f"cd {shlex.quote(str(root))} && python3 {shlex.quote(str(GATE_PY))}"


def sync_command(root: Path) -> str:
    """The exact commands for the person: read every queued write first, then send them."""
    gate = f"python3 {shlex.quote(str(GATE_PY))}"
    return (
        "tell the person to run, in their own terminal: "
        f"cd {shlex.quote(str(root))} && {gate} sync --dry-run, read every write it lists, "
        f"then {gate} sync --confirm <the digest it printed> to post them in their own name"
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


def _gh_env(
    paths: Paths, token: str | None, env: Mapping[str, str], *, as_person: bool = False
) -> dict[str, str]:
    out = dict(env)
    if as_person:
        for name in ("GH_TOKEN", *OTHER_TOKENS):
            out.pop(name, None)
        owner, repo = origin_identity(paths)
        selectors = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
                     "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG",
                     "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GH_DEBUG"}
        for key in list(out):
            if key in selectors or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
                out.pop(key)
        out.update({"GH_HOST": "github.com", "GH_REPO": f"github.com/{owner}/{repo}"})
        return out
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
    as_person: bool = False,
) -> Any:
    """The one place that starts gh."""
    try:
        return runner(
            ["gh", *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            env=_gh_env(paths, token, env, as_person=as_person),
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


def literal_origin(paths: Paths) -> str:
    """Read only the literal URL in this project's config, ignoring routing overrides."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    try:
        done = subprocess.run(
            ["git", "-C", str(paths.root.resolve()), "config", "--local", "--get-all",
             "remote.origin.url"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=5, check=False, env=env,
        )
        urls = done.stdout.splitlines()
        if done.returncode or len(urls) != 1:
            raise ValueError("missing or ambiguous origin")
        return str(urls[0])
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise GitHubError("the actual project needs one literal GitHub origin",
                          next_command=sync_command(paths.root),
                          code=cli.ExitCode.REFUSED) from error


def origin_identity(paths: Paths, *, literal: str | None = None) -> tuple[str, str]:
    url = literal_origin(paths) if literal is None else literal
    match = re.fullmatch(
        r"(?:https://github\.com/|ssh://git@github\.com/|git@github\.com:)"
        r"([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*?)(?:\.git)?", url
    )
    if match is None or match[2] in (".", ".."):
        raise GitHubError("the actual project needs a canonical GitHub origin",
                          next_command=sync_command(paths.root), code=cli.ExitCode.REFUSED)
    return match[1].lower(), match[2].lower()


def bounded_person_process(command: list[str], *, timeout: float, **kwargs: Any) -> Any:
    """Reap our own finite GET process before releasing its response buffers."""
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=kwargs["cwd"], env=kwargs["env"],
                          start_new_session=True) as child:
        assert child.stdout is not None and child.stderr is not None
        try:
            with selectors.DefaultSelector() as selector:
                for name, stream in (("stdout", child.stdout), ("stderr", child.stderr)):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, name)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ValueError("person read timed out")
                    for key, _events in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        buffer = buffers[key.data]
                        buffer.extend(chunk)
                        limit = 8 * 1024 * 1024 if key.data == "stdout" else 16384
                        if len(buffer) > limit:
                            raise ValueError("person response exceeded its bound")
            child.wait(timeout=max(0.01, deadline - time.monotonic()))
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise GitHubError("person read exceeded its time or response bound",
                              next_command="run person sync again") from error
        return subprocess.CompletedProcess(command, child.returncode,
                                           buffers["stdout"].decode("utf-8", errors="replace"),
                                           buffers["stderr"].decode("utf-8", errors="replace"))


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
            self.paths, args, found.token, runner=self.runner, env=self.env, stdin=stdin,
            as_person=self.as_person
        )
        if done.returncode != 0:
            raise GitHubError(
                f"GitHub did not answer, so nothing changed ({_first_line(done.stderr)})",
                next_command="check the network and the App's access, then run this again",
                not_found="404" in done.stderr or "Not Found" in done.stderr,
            )
        out: str = done.stdout
        return out

    def api_json(self, path: str) -> Any:
        """A read of `gh api <path>`, as JSON."""
        text = self._gh(["api", path])
        try:
            return json.loads(text)
        except ValueError as error:
            raise GitHubError(
                "GitHub answered with something that is not JSON",
                next_command="run the same command again",
            ) from error

    def person_read(self, endpoint: str, *, timeout: float) -> Any:
        """Finite explicit-repository GETs, only inside confirmed person sync."""
        if not self.as_person or in_agent_session(self.env):
            raise GitHubError("person reads require external person sync",
                              next_command=sync_command(self.paths.root), code=cli.ExitCode.REFUSED)
        owner, repo = origin_identity(self.paths)
        prefix = f"repos/{owner}/{repo}"
        suffix = endpoint.removeprefix(prefix)
        if endpoint != prefix and not re.fullmatch(
            r"/issues(?:/[1-9][0-9]*(?:/dependencies/blocked_by|/comments)?)?"
            r"(?:\?(?:state=all&)?per_page=100&page=[1-9][0-9]*)?", suffix
        ):
            raise GitHubError("unsupported person read",
                              next_command=sync_command(self.paths.root))
        if not endpoint.startswith(prefix) or not 0 < timeout <= 30:
            raise GitHubError("invalid person read bound",
                              next_command=sync_command(self.paths.root))
        held = self.credential_fn(self.paths, as_person=True, runner=self.runner, env=self.env)
        if held is None or held.kind != "person":
            raise NoApp(self.paths.root)
        def bounded(command: list[str], **kwargs: Any) -> Any:
            return bounded_person_process(command, timeout=timeout, **kwargs)

        selected_runner = bounded if self.runner is subprocess.run else self.runner
        done = _run_gh(self.paths, ["api", "--method", "GET", endpoint], None,
                       runner=selected_runner, env=self.env, as_person=True)
        if done.returncode:
            raise GitHubError("person GitHub read failed",
                              next_command=sync_command(self.paths.root),
                              not_found="HTTP 404" in done.stderr)
        try:
            if len(done.stdout.encode("utf-8")) > 8 * 1024 * 1024:
                raise ValueError("oversized response")
            return json.loads(done.stdout)
        except (ValueError, TypeError) as error:
            raise GitHubError("person GitHub response is malformed or oversized",
                              next_command=sync_command(self.paths.root)) from error

    def pr_state(self, branch: str) -> str:
        """`open`, `merged <head commit>`, `closed` or `none` for the branch's pull requests."""
        text = self._gh(["pr", "list", "--head", branch, "--state", "all",
                         "--json", "state,headRefOid"])
        try:
            pulls = [dict(p) for p in json.loads(text)]
        except (ValueError, TypeError) as error:
            raise GitHubError(
                "GitHub's list of pull requests cannot be read",
                next_command="run the same command again",
            ) from error
        found = [str(p.get("state", "")) for p in pulls]
        if "OPEN" in found:
            return "open"
        if "MERGED" in found:
            head = next(str(p.get("headRefOid", "")) for p in pulls if p.get("state") == "MERGED")
            return f"merged {head}"
        return "closed" if "CLOSED" in found else "none"

    def repo_view(self) -> dict[str, Any]:
        """The repository's name, whether issues are on, and the access, read as the App."""
        text = self._gh(["repo", "view", "--json",
                         "nameWithOwner,hasIssuesEnabled,viewerPermission"])
        try:
            data = json.loads(text)
        except ValueError as error:
            raise GitHubError(
                "GitHub's answer about the repository is not JSON",
                next_command="run the same command again",
            ) from error
        if not isinstance(data, dict):
            raise GitHubError(
                "GitHub's answer about the repository cannot be read",
                next_command="run the same command again",
            )
        return {
            "nameWithOwner": str(data.get("nameWithOwner") or ""),
            "hasIssuesEnabled": bool(data.get("hasIssuesEnabled")),
            "viewerPermission": str(data.get("viewerPermission") or ""),
        }

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


_GITHUB_REMOTE = re.compile(
    r"^(?:https://(?:[^@/]+@)?github\.com/|ssh://git@github\.com(?::22)?/|git@github\.com:)"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/(?P<name>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


def github_address(url: str) -> str | None:
    """`https://github.com/<owner>/<name>.git` for a GitHub remote, in any spelling, or None."""
    found = _GITHUB_REMOTE.match(url.strip())
    if found is None or found.group("name") in (".", ".."):
        return None
    return f"https://github.com/{found.group('owner')}/{found.group('name')}.git"


def is_local_path(url: str) -> bool:
    """True for a folder on this computer: a path or a file:// address."""
    if url.startswith("file://"):
        return True
    if "://" in url:
        return False
    # host:path is the scp spelling of an SSH address.
    return url.startswith(("/", ".")) or ":" not in url.split("/", 1)[0]


def _shown_url(url: str) -> str:
    """The address without any user name or password in it."""
    return re.sub(r"//[^@/]+@", "//", url)


GITHUB_HEADER = "http.https://github.com/.extraheader"


def _closed_env(env: Mapping[str, str], config: Sequence[tuple[str, str]]) -> dict[str, str]:
    """The push's environment: no prompt, no credential helper, no SSH at all.

    An empty value resets a list setting, so an empty credential helper drops
    the person's own helpers, and an empty GitHub extra header drops any header
    of their own before the App's is added.
    """
    out = dict(env)
    for name in [k for k in out if k.startswith("GIT_CONFIG_")]:
        out.pop(name)
    out.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="", SSH_ASKPASS="",
               GIT_SSH_COMMAND="false", GIT_SSH="false")
    settings = [("credential.helper", ""), ("protocol.ssh.allow", "never"),
                ("protocol.ext.allow", "never"), (GITHUB_HEADER, ""), *config]
    out["GIT_CONFIG_COUNT"] = str(len(settings))
    for index, (key, value) in enumerate(settings):
        out[f"GIT_CONFIG_KEY_{index}"] = key
        out[f"GIT_CONFIG_VALUE_{index}"] = value
    return out


def _remote(
    paths: Paths, remote: str, runner: Runner, env: Mapping[str, str], *, writing: bool
) -> tuple[str, dict[str, str]]:
    """The address to push to or fetch from, and the closed environment that goes with it.

    GitHub is reached over https with the App's token, to an address the gate builds itself. A
    folder on this computer is reached as it is. Any other remote is refused.
    """
    root = paths.root
    # The address as written in the config: `git remote get-url` would apply the
    # person's own insteadOf rewrites, and the gate builds its own address.
    found = _git(root, ["config", "--get", f"remote.{remote}.pushurl"], runner, env) \
        if writing else None
    if found is None or found.returncode != 0 or not found.stdout.strip():
        found = _git(root, ["config", "--get", f"remote.{remote}.url"], runner, env)
    if found.returncode != 0 or not found.stdout.strip():
        raise GitHubError(f"there is no remote called {remote}", next_command="git remote -v")
    url = found.stdout.strip().splitlines()[0]
    address = github_address(url)
    if address is not None:
        held = credential(paths, runner=runner, env=env)
        if held is None or held.token is None:
            raise NoApp(root)
        basic = base64.b64encode(f"x-access-token:{held.token}".encode()).decode("ascii")
        return address, _closed_env(env, [(GITHUB_HEADER, f"AUTHORIZATION: basic {basic}")])
    if is_local_path(url):
        return url, _closed_env(env, [])
    raise GitHubError(
        f"the remote {remote} is at {_shown_url(url)}, which is neither GitHub nor a folder "
        "on this computer; the gate reaches only GitHub, as its App",
        next_command="tell the person: the gate does not reach this remote; they push "
        "the branch themselves if they want it there",
        code=cli.ExitCode.REFUSED,
    )


def fetch(
    paths: Paths,
    branch: str = "main",
    *,
    remote: str = "origin",
    runner: Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Bring `refs/remotes/<remote>/<branch>` up to date. Never touches a local branch.

    The update is a fast-forward only, so a remote branch that was rewritten is a refusal.
    Without the App, a GitHub remote raises `NoApp`.
    """
    env = dict(os.environ if env is None else env)
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch) or branch.startswith("-"):
        raise GitHubError(f"{branch!r} is not a branch name", next_command="git branch --list")
    target, fetch_env = _remote(paths, remote, runner, env, writing=False)
    done = runner(
        ["git", "-C", str(paths.root), "fetch", "--quiet", target,
         f"refs/heads/{branch}:refs/remotes/{remote}/{branch}"],
        capture_output=True,
        text=True,
        check=False,
        env=fetch_env,
    )
    if done.returncode != 0:
        raise GitHubError(
            f"git fetch of {branch} failed ({_first_line(done.stderr)})",
            next_command=f"check the remote with git -C {shlex.quote(str(paths.root))} "
            "remote -v, then run this again",
        )
    return {"fetched": f"{remote}/{branch}", "from": _shown_url(target)}


def push(
    paths: Paths,
    branch: str,
    *,
    remote: str = "origin",
    runner: Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Push one piece branch: the secret scan first, never `main`, never with force.

    A push to GitHub needs the App, and acts as the App over https, to an address
    built from the owner and name. Without the App, `NoApp`. A folder on this
    computer (as tests use) takes a plain push. Any other remote is refused. No
    push ever uses a credential helper, a password prompt or SSH.
    """
    env = dict(os.environ if env is None else env)
    root = paths.root
    if branch in ("main", "refs/heads/main") or branch.startswith("-"):
        raise GitHubError(
            f"the gate never pushes {branch}",
            next_command="push a piece branch; main changes only through a merge",
            code=cli.ExitCode.REFUSED,
        )
    target, push_env = _remote(paths, remote, runner, env, writing=True)
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
        ["git", "-C", str(root), "push", target, f"{branch}:refs/heads/{branch}"],
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
    return {"pushed": branch, "remote": remote, "to": _shown_url(target), "scanned": scanned}


# --- a door for the shell scripts -------------------------------------------------------


USAGE = "usage: python3 -m loop.github (pr-state <branch> | repo-view)"


def main(argv: Sequence[str]) -> int:
    """A door for the shell scripts. Each read is made as the App.

    `pr-state <branch>`, for worktree.sh, prints the branch's pull request state.
    `repo-view`, for check-tooling.sh, prints the repository's name, whether
    issues are on and the access, as JSON. With no App either one starts no
    program and exits 3, with a `next:` line on standard error.
    """
    wanted = list(argv)
    if not (wanted[:1] == ["pr-state"] and len(wanted) == 2) and wanted != ["repo-view"]:
        print(USAGE, file=sys.stderr)
        return int(cli.ExitCode.USAGE)
    try:
        paths = Paths.for_project(find_project_root(Path.cwd()))
        hub = GitHub(paths)
        if wanted[0] == "pr-state":
            print(hub.pr_state(wanted[1]))
        else:
            print(json.dumps(hub.repo_view()))
    except PathError as error:
        print(f"{error}\nnext: cd <the project>, then run this again", file=sys.stderr)
        return int(cli.ExitCode.ENVIRONMENT)
    except GitHubError as error:
        print(f"{error.message}\nnext: {error.next_command}", file=sys.stderr)
        return int(error.code)
    return int(cli.ExitCode.OK)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
