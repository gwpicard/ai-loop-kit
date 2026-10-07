"""Start a non-interactive `claude -p` session, and read how it ended.

Every session the loop starts goes through here: a builder, a test-list writer,
the trim pass and a reviewer. This module holds the rules that must not differ
between them:

- the command line is exact and short (design principle 14). The brief goes by
  file, the settings by `--settings`, the mode is `dontAsk`, and there is no
  `--bare`, no `--resume` and no `--continue`. A cost cap is added only when the
  caller gives one;
- the working folder is the piece's worktree;
- the environment is scrubbed of every GitHub credential, so a builder holds none;
- text from outside (an issue, a comment, a web page, the spec, the attempt log)
  reaches a session only inside a marked data block, and a lint refuses a brief
  template that puts it anywhere else;
- the builder settings are rendered with absolute paths and no placeholder left. A builder
  attempt also passes the files of the frozen bar, and its own settings file then denies a
  write to each of them, by a deny rule and by a sandbox write block (`bar_rules`);
- a session ends with one hand-off file, which this module reads and checks.

The hand-off file is written by `kit/scripts/handoff.py`. It holds one of five
outcomes. `OUTCOMES` and `validate_handoff` are the one definition of them.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from loop.paths import Paths

CLAUDE = "claude"
RUN_ENV = "AI_LOOP_KIT_RUN"
HANDOFF_ENV = "AI_LOOP_KIT_HANDOFF_FILE"
AUTO_MEMORY_ENV = "CLAUDE_CODE_DISABLE_AUTO_MEMORY"

# Environment names a builder never inherits. A name that starts with GH_ or
# GITHUB_ is dropped, so a new GitHub variable is covered before anybody lists it.
SCRUBBED_PREFIXES = ("GH_", "GITHUB_")
SCRUBBED_NAMES = frozenset({"GIT_ASKPASS", "SSH_ASKPASS", "SSH_AUTH_SOCK"})

_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_BLOCK_LABEL = re.compile(r"^[a-z][a-z0-9_-]*$")
_PLACEHOLDER = re.compile(r"\{\{(data:)?([A-Za-z_][A-Za-z0-9_]*)\}\}")
_ANY_PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}")

# The names of text that comes from outside the kit. A brief holds each only as
# `{{data:<name>}}`, which becomes a marked data block.
OUTSIDE_FIELDS = frozenset(
    {
        "spec",
        "attempt_log",
        "hypothesis",
        "issue",
        "comments",
        "web",
        "pr_text",
        "diff",
        "findings",
    }
)

OUTCOMES = ("done", "bar-is-wrong", "needs-the-person", "blocked-by-environment", "gave-up")
# The one field each outcome must carry. "done" may also carry `decisions`.
HANDOFF_FIELD = {
    "done": "summary",
    "bar-is-wrong": "evidence",
    "needs-the-person": "question",
    "blocked-by-environment": "reason",
    "gave-up": "reason",
}
HANDOFF_NEXT = "run the hand-off script with --help, then write the hand-off again"


class SessionError(Exception):
    """A refusal. Carries the next command."""

    def __init__(self, message: str, *, next_command: str = HANDOFF_NEXT) -> None:
        super().__init__(message)
        self.next_command = next_command


# --- the command line and the environment --------------------------------------


def build_command(settings_file: Path, *, max_budget_usd: float | None = None) -> list[str]:
    """The exact `claude -p` command line. The brief is not on it: it is the input."""
    command = [
        CLAUDE,
        "-p",
        "--settings",
        str(settings_file),
        "--permission-mode",
        "dontAsk",
        "--output-format",
        "json",
        # Nobody can answer a prompt in an unattended run, so it is a denial.
        "--permission-prompts",
        "none",
    ]
    if max_budget_usd is not None:
        if max_budget_usd <= 0:
            raise SessionError(
                f"a cost cap must be more than zero, and {max_budget_usd} is not",
                next_command="pass a positive amount, or no cap at all",
            )
        command += ["--max-budget-usd", f"{max_budget_usd:.4f}".rstrip("0").rstrip(".")]
    return command


def scrub_env(env: Mapping[str, str]) -> dict[str, str]:
    """A copy of `env` with every GitHub credential taken out."""
    return {
        name: value
        for name, value in env.items()
        if name not in SCRUBBED_NAMES and not name.startswith(SCRUBBED_PREFIXES)
    }


def handoff_command(kit_dir: Path) -> str:
    """The command a builder runs to hand back. The builder settings allow exactly this."""
    return f"python3 {kit_dir}/scripts/handoff.py"


# --- rendering ------------------------------------------------------------------


def render(text: str, values: Mapping[str, str]) -> str:
    """Replace each `{{NAME}}` with its value. A name with no value is a refusal."""

    def put(match: re.Match[str]) -> str:
        name = match.group(0)[2:-2]
        if name not in values:
            raise SessionError(
                f"the template holds {{{{{name}}}}} and no value was given for it",
                next_command="give the value, or take the placeholder out of the template",
            )
        return values[name]

    return _ANY_PLACEHOLDER.sub(put, text)


def _render_json(node: Any, values: Mapping[str, str]) -> Any:
    if isinstance(node, str):
        return render(node, values)
    if isinstance(node, list):
        return [_render_json(item, values) for item in node]
    if isinstance(node, dict):
        return {key: _render_json(item, values) for key, item in node.items()}
    return node


def bar_rules(worktree: Path, bar_paths: Sequence[str]) -> tuple[list[str], list[str]]:
    """The deny rules and the sandbox write blocks for the paths of the frozen bar.

    The first layer of the frozen bar (the gate's byte-for-byte check is the second). Each
    path is relative to the worktree and names one file, so a wildcard is refused. A rule
    that stands for more than the bar lists would stop a builder from adding new tests.
    """
    rules: list[str] = []
    blocks: list[str] = []
    for name in bar_paths:
        pure = PurePosixPath(name)
        if not name or pure.is_absolute() or ".." in pure.parts or any(c in name for c in "*?[]{}"):
            raise SessionError(
                f"the bar path {name!r} is not one file relative to the worktree",
                next_command="list each bar file by its path from the worktree root, "
                "with no wildcard and no '..'",
            )
        absolute = str(worktree / pure)
        rules.append(f"Edit(/{absolute})")
        blocks.append(absolute)
    if bar_paths:
        # A new conftest.py can turn every failing test green, and a list of files cannot name
        # a file that does not exist yet, so one rule covers each conftest.py in the worktree.
        rules.append(f"Edit(/{worktree}/**/conftest.py)")
    return rules, blocks


def render_settings(
    template: Path,
    *,
    paths: Paths,
    worktree: Path,
    handoff_file: Path,
    bar_paths: Sequence[str] = (),
    extra_values: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The builder settings for one session, as a dictionary with no placeholder left.

    `bar_paths` are the files of the frozen bar (`loop.bar.paths`). The settings then deny a
    write to each: a deny rule for the edit tools and a write block in the sandbox.
    `extra_values` fills placeholders only a special template holds, such as the reviewer's
    `FINDINGS_FILE`. A value must be an absolute path.
    """
    values = {
        "KIT_DIR": str(paths.kit_dir),
        "PROJECT_ROOT": str(paths.root),
        "WORKTREE": str(worktree),
        "DATA_DIR": str(paths.data_dir),
        "HANDOFF_FILE": str(handoff_file),
        **{name: str(value) for name, value in (extra_values or {}).items()},
    }
    for name, value in values.items():
        if not os.path.isabs(value):
            raise SessionError(
                f"{name} is {value!r}, which is not an absolute path",
                next_command="start the session from a project found by an absolute path",
            )
    loaded = json.loads(template.read_text(encoding="utf-8"))
    rendered: dict[str, Any] = _render_json(loaded, values)
    rules, blocks = bar_rules(worktree, bar_paths)
    deny = rendered.setdefault("permissions", {}).setdefault("deny", [])
    deny.extend(rule for rule in rules if rule not in deny)
    write_blocks = rendered.setdefault("sandbox", {}).setdefault("filesystem", {}).setdefault(
        "denyWrite", []
    )
    write_blocks.extend(block for block in blocks if block not in write_blocks)
    return rendered


# --- data blocks ----------------------------------------------------------------


def data_block(label: str, text: str, *, nonce: str | None = None) -> str:
    """Wrap outside text in a marked block that the text cannot close by itself.

    The markers carry a random nonce. The text is refused if it holds the nonce,
    so no text can write the line that ends its own block.
    """
    if not _BLOCK_LABEL.match(label):
        raise SessionError(
            f"{label!r} is not a valid block label",
            next_command="use lower-case letters, digits, '_' and '-' only",
        )
    if nonce is None:
        nonce = secrets.token_hex(8)
        while nonce in text:
            nonce = secrets.token_hex(8)
    elif nonce in text:
        raise SessionError(
            "the text holds the nonce of its own data block",
            next_command="use a different nonce, or leave it out",
        )
    return f"<<<DATA BEGIN {label} nonce={nonce}>>>\n{text}\n<<<DATA END {label} nonce={nonce}>>>"


_BLOCK = re.compile(
    r"^<<<DATA BEGIN (?P<label>\S+) nonce=(?P<nonce>[0-9A-Za-z]+)>>>\n"
    r"(?P<body>.*?)\n"
    r"<<<DATA END (?P=label) nonce=(?P=nonce)>>>$",
    re.MULTILINE | re.DOTALL,
)


def parse_blocks(text: str) -> list[tuple[str, str]]:
    """Each data block in `text`, as (label, body)."""
    return [(m.group("label"), m.group("body")) for m in _BLOCK.finditer(text)]


def outside_the_blocks(text: str) -> str:
    """`text` with every data block taken out."""
    return _BLOCK.sub("", text)


@dataclass(frozen=True)
class Fields:
    trusted: list[str]
    outside: list[str]


def template_fields(template: str) -> Fields:
    """The names a template holds: kit values, and outside text as data blocks."""
    trusted: list[str] = []
    outside: list[str] = []
    for match in _PLACEHOLDER.finditer(template):
        bucket = outside if match.group(1) else trusted
        if match.group(2) not in bucket:
            bucket.append(match.group(2))
    return Fields(trusted=trusted, outside=outside)


def check_template(template: str) -> list[str]:
    """What is wrong with a brief template. An empty list means it is fine.

    Outside text may appear only as `{{data:<name>}}`. A plain `{{<name>}}` for
    one of those names would put it in the brief unmarked.
    """
    problems: list[str] = []
    for match in _PLACEHOLDER.finditer(template):
        is_data, name = bool(match.group(1)), match.group(2)
        if is_data and name not in OUTSIDE_FIELDS:
            problems.append(
                f"{{{{data:{name}}}}} names no kind of outside text the kit knows. "
                f"Use one of: {', '.join(sorted(OUTSIDE_FIELDS))}"
            )
        if not is_data and name.lower() in OUTSIDE_FIELDS:
            problems.append(
                f"{{{{{name}}}}} would put outside text in the brief with no data block. "
                f"Write {{{{data:{name.lower()}}}}} instead"
            )
    leftovers = _ANY_PLACEHOLDER.findall(_PLACEHOLDER.sub("", template))
    problems += [f"{item} is not a placeholder the kit can fill" for item in leftovers]
    return problems


def render_brief(
    template: str, *, trusted: Mapping[str, str], outside: Mapping[str, str]
) -> str:
    """Fill a brief template. Outside text goes into data blocks, in one pass."""
    problems = check_template(template)
    if problems:
        raise SessionError(
            "the brief template breaks the data-block rule: " + "; ".join(problems),
            next_command="fix the template, then run tests/unit.sh",
        )
    fields = template_fields(template)
    missing = [n for n in fields.trusted if n not in trusted] + [
        f"data:{n}" for n in fields.outside if n not in outside
    ]
    if missing:
        raise SessionError(
            "no value was given for " + ", ".join(missing),
            next_command="give every value the template names",
        )

    def put(match: re.Match[str]) -> str:
        name = match.group(2)
        if match.group(1):
            return data_block(name.replace("_", "-"), outside[name])
        return trusted[name]

    return _PLACEHOLDER.sub(put, template)


# --- the hand-off file ----------------------------------------------------------


def validate_handoff(data: Any) -> dict[str, Any]:
    """Check a hand-off. Returns it, or raises with what is wrong."""
    if not isinstance(data, dict):
        raise SessionError("the hand-off is not a JSON object")
    outcome = data.get("outcome")
    if outcome not in OUTCOMES:
        raise SessionError(
            f"the hand-off outcome {outcome!r} is not one of {', '.join(OUTCOMES)}"
        )
    field = HANDOFF_FIELD[outcome]
    allowed = {"outcome", field} | ({"decisions"} if outcome == "done" else set())
    extra = sorted(set(data) - allowed)
    if extra:
        raise SessionError(f"a {outcome} hand-off holds {', '.join(extra)}, which it may not")
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SessionError(f"a {outcome} hand-off needs a {field}, and it has none")
    decisions = data.get("decisions", [])
    if not isinstance(decisions, list) or not all(
        isinstance(item, str) and item.strip() for item in decisions
    ):
        raise SessionError("decisions must be a list of text, one for each decision")
    return data


def read_handoff(path: Path) -> dict[str, Any] | None:
    """The hand-off at `path`, checked. None when the session left none."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise SessionError(f"the hand-off file is not JSON: {exc}") from exc
    return validate_handoff(data)


# --- sessions -------------------------------------------------------------------


@dataclass(frozen=True)
class Session:
    """One planned session. Planning writes the settings file and the brief file."""

    run: str
    label: str
    command: list[str]
    cwd: Path
    env: dict[str, str]
    brief_file: Path
    settings_file: Path
    handoff_file: Path


@dataclass(frozen=True)
class Result:
    exit_code: int
    stdout: str
    stderr: str
    output: dict[str, Any] | None  # the JSON `claude -p` printed, when it printed JSON
    handoff: dict[str, Any] | None  # None when the session left none
    handoff_error: str = ""  # why a hand-off that exists could not be read
    moved_aside: Path | None = None  # an earlier session's hand-off, kept under a dated name


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def plan(
    paths: Paths,
    *,
    run: str,
    label: str,
    worktree: Path,
    brief: str,
    max_budget_usd: float | None = None,
    env: Mapping[str, str] | None = None,
    settings_template: Path | None = None,
    bar_paths: Sequence[str] = (),
    extra_values: Mapping[str, str] | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> Session:
    """Plan one session and write its settings file and brief file in the run folder.

    A builder attempt passes its own `label` (such as `p7-a2`) and `bar_paths`, so each attempt
    gets its own settings file with the deny rules and write blocks of the frozen bar. The
    reviewer passes `extra_values` for its template and `extra_env` for the one variable that
    names its findings file. The environment is scrubbed of GitHub credentials first, so
    `extra_env` is the only way a name gets in after the scrub.
    """
    if not _LABEL.match(label) or ".." in label:
        raise SessionError(
            f"{label!r} is not a valid session label",
            next_command="use letters, digits, '.', '_' and '-' only, such as p7-a1",
        )
    run_dir = paths.run_dir(run)  # raises PathError for a bad run name
    folder = worktree.resolve()
    if paths.worktrees_dir.resolve() not in folder.parents or not folder.is_dir():
        raise SessionError(
            f"{worktree} is not a worktree under {paths.worktrees_dir}",
            next_command="open the piece's worktree with: sh kit/scripts/worktree.sh open "
            "<number>-<name> <branch> <base>",
        )
    handoff_file = run_dir / f"handoff-{label}.json"
    settings_file = run_dir / f"settings-{label}.json"
    brief_file = run_dir / f"brief-{label}.md"
    template = settings_template or paths.kit_dir / "templates" / "builder-settings.json"
    settings = render_settings(
        template, paths=paths, worktree=worktree, handoff_file=handoff_file, bar_paths=bar_paths,
        extra_values=extra_values,
    )
    command = build_command(settings_file, max_budget_usd=max_budget_usd)
    session_env = scrub_env(os.environ if env is None else env)
    session_env[RUN_ENV] = run
    session_env[HANDOFF_ENV] = str(handoff_file)
    # Second layer beside `autoMemoryEnabled: false` in the builder settings.
    session_env[AUTO_MEMORY_ENV] = "1"
    for name, value in (extra_env or {}).items():
        if name.startswith(SCRUBBED_PREFIXES) or name in SCRUBBED_NAMES:
            raise SessionError(
                f"the session may not be given the variable {name}, which names a credential",
                next_command="give the session no GitHub credential",
            )
        session_env[name] = str(value)
    _write_private(settings_file, json.dumps(settings, indent=2, sort_keys=True) + "\n")
    _write_private(brief_file, brief)
    return Session(
        run=run,
        label=label,
        command=command,
        cwd=worktree,
        env=session_env,
        brief_file=brief_file,
        settings_file=settings_file,
        handoff_file=handoff_file,
    )


def _move_aside(path: Path) -> Path | None:
    """Rename an existing file to `<name>.<UTC date and time>[-n]`. None when there is none."""
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for count in range(1000):
        target = path.with_name(f"{path.name}.{stamp}" + (f"-{count}" if count else ""))
        try:
            os.link(path, target)  # fails when the name is taken, so nothing is overwritten
        except FileExistsError:
            continue
        path.unlink()
        return target
    raise SessionError(
        f"too many earlier hand-offs sit beside {path}",
        next_command="look at them, then keep the ones you need",
    )


Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def start(session: Session, *, runner: Runner = subprocess.run) -> Result:
    """Run the session and wait for it. The brief file is its input.

    A hand-off left by an earlier session of the same label is moved aside to a
    dated name first, so it cannot be taken for this one's and is not lost. The
    result names it in `moved_aside`.
    """
    moved_aside = _move_aside(session.handoff_file)
    try:
        with session.brief_file.open("r", encoding="utf-8") as brief:
            done = runner(
                session.command,
                cwd=str(session.cwd),
                env=session.env,
                stdin=brief,
                capture_output=True,
                text=True,
                check=False,
            )
    except FileNotFoundError as exc:
        raise SessionError(
            f"{CLAUDE} is not on the PATH: {exc}",
            next_command="install Claude Code, then start the session again",
        ) from exc
    output: dict[str, Any] | None = None
    try:
        parsed = json.loads(done.stdout)
        if isinstance(parsed, dict):
            output = parsed
    except ValueError:
        output = None
    handoff: dict[str, Any] | None = None
    problem = ""
    try:
        handoff = read_handoff(session.handoff_file)
    except SessionError as exc:
        problem = str(exc)
    return Result(
        exit_code=done.returncode,
        stdout=done.stdout,
        stderr=done.stderr,
        output=output,
        handoff=handoff,
        handoff_error=problem,
        moved_aside=moved_aside,
    )
