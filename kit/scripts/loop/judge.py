"""Run a judge the same way everywhere, and tell an assertion failure from an error.

A judge is a test command from the spec's `Command:` line. This module runs it
in a temporary checkout of one ref, under a hard time limit, and reads the
runner's report. The answer is one of:

- `passed`: the command exited 0 and no failure was reported;
- `failed`: every reported failure was an assertion (the right way to be red);
- `failed_no_id`: every reported failure was an assertion, but none names a spec
  ID (`FL-` or `EC-`). It is not the right failure. Callers treat it like
  `errored`;
- `errored`: something other than an assertion broke, such as an import, or no
  report was written;
- `timeout`: the command ran past the limit and was stopped.

Only `passed` and `failed` give an answer a caller can use. `RIGHT_FAILURES`
holds the outcomes that count as failing for the right reason, and it holds only
`failed`.

pytest, Vitest, Jest and the Node runner write reports, and the report tells an
assertion from an error. Any other runner falls back to the exit code, with a
note that says so. The gate runs every judge itself and never trusts an
agent's word about one.

The command line is split into words and run without a shell. A command that
needs `&&` or a pipe goes in a script, and the spec names `sh script.sh`.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from loop import cli, spec
from loop.paths import PathError, find_project_root

TIME_LIMIT_ENV = "AI_LOOP_JUDGE_TIME_LIMIT"
DEFAULT_TIME_LIMIT = 600

# The runner names kit/spec-format.md lists. A test holds the two lists the same.
COMMAND_RUNNERS = (
    "pytest", "unittest", "npm", "pnpm", "yarn", "vitest", "jest", "go", "cargo", "shell",
)
# The runners whose report is read, and the option that writes it. `node` is
# found by `node --test` in a command, and the spec does not name it.
REPORT_RUNNERS: dict[str, list[str]] = {
    "pytest": ["--junitxml={report}"],
    "vitest": ["--reporter=json", "--outputFile={report}"],
    "jest": ["--json", "--outputFile={report}"],
    "node": ["--test-reporter=junit", "--test-reporter-destination={report}"],
}
# The runners that leave only the exit code.
EXIT_CODE_RUNNERS = frozenset(COMMAND_RUNNERS) - {"pytest", "vitest", "jest"}

# What a failure that is not an assertion turned out to be, by what it says.
ERROR_KINDS = (
    (
        r"ModuleNotFoundError|No module named|Cannot find module|ERR_MODULE_NOT_FOUND|"
        r"Failed to (load|resolve)",
        "a missing module",
    ),
    (r"ImportError|SyntaxError: .*import", "a failed import"),
    (r"SyntaxError", "a syntax error"),
    (
        r"NameError|ReferenceError|AttributeError|is not defined|has no attribute|"
        r"is not a function",
        "a name that does not exist",
    ),
    (r"collection failure", "a collection error"),
)
OTHER_ERROR = "an error that is not an assertion"
ASSERTION_HEAD = re.compile(r"^(AssertionError|Error: expect\(|expect\()")


class JudgeError(Exception):
    """The judge could not be run at all. Carries the next command."""

    def __init__(self, message: str, *, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


def default_time_limit() -> int:
    try:
        return max(1, int(os.environ.get(TIME_LIMIT_ENV, str(DEFAULT_TIME_LIMIT))))
    except ValueError:
        return DEFAULT_TIME_LIMIT


# --- which runner -------------------------------------------------------------------------


def _runner_in(text: str) -> str | None:
    """The runner a command line starts, by the words it holds."""
    words = shlex.split(text) if text.strip() else []
    if words and words[0] in ("sh", "bash"):
        return "shell"
    loose = set(re.split(r"[\s/]+", text))
    if "pytest" in loose or "py.test" in loose:
        return "pytest"
    if "vitest" in loose:
        return "vitest"
    if "jest" in loose:
        return "jest"
    if re.search(r"(^|\s)node(\s.*)?\s--test\b", text):
        return "node"
    if re.search(r"(^|\s)-m\s+unittest\b", text):
        return "unittest"
    if words[:2] == ["go", "test"]:
        return "go"
    if words[:2] == ["cargo", "test"]:
        return "cargo"
    return None


def _script_of(words: list[str]) -> str:
    rest = words[1:]
    if rest[:1] in (["run"], ["run-script"]):
        return rest[1] if len(rest) > 1 else "test"
    return rest[0] if rest else "test"


def detect_runner(command: str, folder: str) -> str | None:
    """The runner the command starts, read through package.json for npm, pnpm and yarn."""
    words = shlex.split(command)
    if words and words[0] in ("npm", "pnpm", "yarn"):
        try:
            with open(os.path.join(folder, "package.json"), encoding="utf-8") as handle:
                scripts = json.load(handle).get("scripts", {})
            inner = _runner_in(str(scripts.get(_script_of(words), "")))
        except (OSError, ValueError, AttributeError):
            inner = None
        return inner or words[0]
    return _runner_in(command)


def report_option(runner: str | None, report: str) -> list[str] | None:
    """The options that make `runner` write its report, or None when it cannot."""
    options = REPORT_RUNNERS.get(runner or "")
    return [option.format(report=report) for option in options] if options else None


def build_command(command: str, runner: str | None, report: str) -> list[str]:
    """The command's words with the report option added at the end."""
    words = shlex.split(command)
    options = report_option(runner, report)
    if not options:
        return words
    if words[0] in ("npm", "pnpm", "yarn"):
        return [*words, "--", *options]
    return [*words, *options]


# --- reading a report ------------------------------------------------------------------------


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _json_failures(report: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    data = json.loads(report.read_text(encoding="utf-8"))
    for result in data.get("testResults", []):
        failed = [a for a in result.get("assertionResults", []) if a.get("status") == "failed"]
        for item in failed:
            said = "\n".join(str(m) for m in item.get("failureMessages", []))
            head = _first_line(said)
            found.append(
                {
                    "test": item.get("fullName", ""),
                    "detail": said,
                    "assertion": bool(ASSERTION_HEAD.match(head)) or "[ERR_ASSERTION]" in head,
                }
            )
        message = str(result.get("message") or "")
        if result.get("status") == "failed" and not failed and message.strip():
            found.append({"test": result.get("name", ""), "detail": message, "assertion": False})
    return found


def _xml_failures(runner: str, report: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for case in ElementTree.parse(report).iter("testcase"):
        for tag in ("failure", "error"):
            for element in case.findall(tag):
                said = (element.get("message") or "") + "\n" + (element.text or "")
                lines = [line.strip() for line in said.splitlines() if line.strip()]
                if runner == "pytest":
                    assertion = (
                        tag == "failure"
                        and bool(lines)
                        and (
                            lines[0].startswith("AssertionError")
                            or lines[-1].endswith("AssertionError")
                        )
                    )
                else:
                    assertion = "AssertionError" in said or "ERR_ASSERTION" in said
                found.append(
                    {"test": case.get("name", ""), "detail": said.strip(), "assertion": assertion}
                )
    return found


def read_failures(runner: str, report: Path) -> list[dict[str, Any]]:
    """Each failure the report holds: the test, what it said and whether it was an assertion."""
    if runner in ("vitest", "jest"):
        return _json_failures(report)
    return _xml_failures(runner, report)


def _kind_of(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for pattern, kind in ERROR_KINDS:
        if any(re.search(pattern, line) for line in lines):
            return kind
    return OTHER_ERROR


OUTCOMES = ("passed", "failed", "failed_no_id", "errored", "timeout")
RIGHT_FAILURES = ("failed",)


def _ids_in(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for item in spec.ID.findall(text):
            if item not in found:
                found.append(item)
    return found


def interpret(
    runner: str | None, report: Path | None, exit_code: int, output: str
) -> dict[str, Any]:
    """Turn a runner's report and exit code into an answer. Nothing here runs a command."""
    result: dict[str, Any] = {
        "outcome": "errored",
        "runner": runner,
        "failures": [],
        "failing_ids": [],
        "kind": None,
        "note": None,
    }
    if runner not in REPORT_RUNNERS:
        why = "the runner is not known" if runner is None else f"{runner} writes no report here"
        result["outcome"] = "passed" if exit_code == 0 else "failed"
        result["note"] = f"{why}, so only the exit code was read (exit code {exit_code})"
        return result
    if report is None or not report.is_file():
        if exit_code == 0:
            result["outcome"] = "passed"
            result["note"] = "no report was written, so only the exit code was read"
        else:
            result["note"] = f"no report was written (exit code {exit_code}): {_first_line(output)}"
            result["kind"] = _kind_of(output)
        return result
    try:
        failures = read_failures(runner, report)
    except (OSError, ValueError, ElementTree.ParseError) as error:
        result["note"] = f"the report could not be read ({type(error).__name__}), exit {exit_code}"
        return result
    for failure in failures:
        failure["ids"] = _ids_in(failure["test"], failure["detail"])
        failure["kind"] = None if failure["assertion"] else _kind_of(failure["detail"])
        failure["detail"] = _first_line(failure["detail"])
    result["failures"] = failures
    if failures:
        if all(f["assertion"] for f in failures):
            result["failing_ids"] = _ids_in(*(i for f in failures for i in f["ids"]))
            if result["failing_ids"]:
                result["outcome"] = "failed"
            else:
                result["outcome"] = "failed_no_id"
                result["note"] = (
                    "the failure is an assertion, but it names no spec ID (FL- or EC-), "
                    "so it is not the right failure"
                )
        else:
            first = next(f for f in failures if not f["assertion"])
            result["kind"] = first["kind"]
        return result
    if exit_code == 0:
        result["outcome"] = "passed"
    else:
        result["note"] = f"the command exited with {exit_code} but the report holds no failure"
    return result


# --- running ------------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


class Checkout:
    """A detached checkout of one ref in a folder made by mkdtemp.

    The run leaves files behind, such as installed packages and reports. The
    removal counts every untracked file as ignored, so `git worktree remove`
    takes the folder away, and a tracked file the run changed still stops it.
    """

    def __init__(self, root: Path, ref: str) -> None:
        self.root = root
        self.ref = ref
        self.temp = ""
        self.path = ""
        self.added = False

    def open(self) -> None:
        self.temp = tempfile.mkdtemp(prefix="judge-")
        self.path = os.path.join(self.temp, "checkout")
        done = _git(self.root, "worktree", "add", "--quiet", "--detach", self.path, self.ref)
        if done.returncode != 0:
            self.clear()
            raise JudgeError(
                f"the temporary checkout of {self.ref} could not be made "
                f"({_first_line(done.stderr)})",
                next_command=f"check that {self.ref} exists in {self.root}, then run it again",
            )
        self.added = True

    def file(self, name: str) -> str:
        return os.path.join(self.temp, name)

    def clear(self) -> None:
        if self.added:
            everything = self.file("exclude-everything")
            Path(everything).write_text("*\n", encoding="utf-8")
            removed = _git(
                self.root, "-c", f"core.excludesFile={everything}", "worktree", "remove", self.path
            )
            if removed.returncode == 0:
                self.added = False
            else:
                self.note = (
                    f"the temporary checkout at {self.path} could not be removed "
                    f"({_first_line(removed.stderr)}); remove it with: git worktree remove "
                    f"{self.path}"
                )
        if self.temp and os.path.isdir(self.temp) and not self.added:
            for name in os.listdir(self.temp):
                full = os.path.join(self.temp, name)
                if os.path.isfile(full) or os.path.islink(full):
                    os.remove(full)
            with contextlib.suppress(OSError):
                os.rmdir(self.temp)
        _git(self.root, "worktree", "prune")

    note = ""


GRACE = 3  # seconds to collect output after the kill


def run_limited(argv: list[str], cwd: str, limit: int) -> tuple[int, str, bool]:
    """Run a command under the time limit, stopping everything it started when over."""
    env = dict(os.environ)
    env.update({"CI": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    except OSError as error:
        return 127, f"{argv[0]} could not be started ({error.strerror})", False
    try:
        output, _ = process.communicate(timeout=limit)
        return process.returncode, output or "", False
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
        try:
            output, _ = process.communicate(timeout=GRACE)
        except subprocess.TimeoutExpired:
            # A process that left the group still holds the pipe. Let go of it.
            output = ""
            if process.stdout is not None:
                with contextlib.suppress(OSError, ValueError):
                    process.stdout.close()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=GRACE)
        return -1, output or "", True


def run(
    command: str,
    root: Path,
    ref: str,
    *,
    install: str | None = None,
    time_limit: int | None = None,
) -> dict[str, Any]:
    """Run `command` in a temporary checkout of `ref` of the project at `root`."""
    limit = time_limit if time_limit is not None else default_time_limit()
    seconds_word = "second" if limit == 1 else "seconds"
    try:
        words = shlex.split(command)
    except ValueError as error:
        raise JudgeError(
            f"the command could not be read ({error})",
            next_command="fix the Command: line of the spec, then run it again",
        ) from error
    if not words:
        raise JudgeError(
            "the command is empty", next_command="fix the Command: line of the spec"
        )
    commit = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").stdout.strip()
    checkout = Checkout(root, ref)
    result: dict[str, Any] = {
        "command": command, "ref": ref, "commit": commit or None, "exit_code": None,
        "timed_out": False, "seconds": 0.0, "output_tail": "",
    }
    started = time.monotonic()
    try:
        checkout.open()
        if install:
            code, output, late = run_limited(shlex.split(install), checkout.path, limit)
            if late or code != 0:
                reason = (
                    f"ran past the limit of {limit} {seconds_word} and was stopped"
                    if late else f"failed with exit {code} ({_first_line(output[-2000:])})"
                )
                result.update(
                    interpret(None, None, 1, ""),
                    outcome="timeout" if late else "errored",
                    timed_out=late,
                    note=f"the install, `{install}`, {reason}",
                )
                return result
        runner = detect_runner(command, checkout.path)
        report = checkout.file("report.json" if runner in ("vitest", "jest") else "report.xml")
        argv = build_command(command, runner, report)
        code, output, late = run_limited(argv, checkout.path, limit)
        result["exit_code"] = code
        result["output_tail"] = output[-2000:]
        if late:
            result.update(
                interpret(runner, None, 1, ""),
                outcome="timeout",
                timed_out=True,
                note=f"the check ran past the limit of {limit} {seconds_word} and was stopped",
            )
        else:
            result.update(interpret(runner, Path(report), code, output))
    finally:
        checkout.clear()
        result["seconds"] = round(time.monotonic() - started, 2)
        if checkout.note:
            result["cleanup_note"] = checkout.note
    return result


def evidence_entry(result: dict[str, Any], *, fingerprint: str | None) -> dict[str, Any]:
    """The entry the gate writes to the piece record for one judge run.

    It holds the outcome and the IDs, and no raw output, so it holds no secret.
    """
    return {
        "kind": "judge-run",
        "outcome": result["outcome"],
        "runner": result["runner"],
        "command": result["command"],
        "ref": result["ref"],
        "commit": result["commit"],
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "failing_ids": result["failing_ids"],
        "failures": [
            {"test": f["test"], "assertion": f["assertion"], "ids": f["ids"]}
            for f in result["failures"]
        ],
        "kind_of_error": result["kind"],
        "note": result["note"],
        "fingerprint": fingerprint,
    }


# --- command line -------------------------------------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    sub = commands.add_parser("run", help="run a judge command in a temporary checkout")
    sub.add_argument("--command", required=True, help="the judge command (the spec's Command:)")
    sub.add_argument("--ref", default="main", help="the ref to check out (default: main)")
    sub.add_argument("--install", help="a command to run in the checkout first")
    sub.add_argument("--time-limit", type=int, help="seconds before the check is stopped")
    sub.add_argument("--root", help="the project folder (default: the one around here)")
    sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="print JSON")


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = Path(args.root) if args.root else find_project_root(Path.cwd())
        result = run(args.command, root, args.ref, install=args.install, time_limit=args.time_limit)
    except PathError as error:
        raise cli.Failure(
            str(error), next_command="judge run --help", code=cli.ExitCode.USAGE
        ) from error
    except JudgeError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.ENVIRONMENT
        ) from error
    outcome = result["outcome"]
    if outcome == "passed":
        return result
    if outcome == "failed":
        raise cli.Failure(
            "the judge failed"
            + (f" on an assertion naming {', '.join(result['failing_ids'])}"
               if result["failing_ids"] else f" ({result['note']})"),
            next_command="build until the judge passes, then run the same command again",
            code=cli.ExitCode.FAILURE,
            data=result,
        )
    raise cli.Failure(
        f"the judge gave no answer: {outcome}. {result['note'] or result['kind'] or ''}".strip(),
        next_command="fix the judge so that it fails on an assertion, then run it again",
        code=cli.ExitCode.ENVIRONMENT,
        data=result,
    )


def main(argv: list[str]) -> int:
    return cli.run(
        "judge",
        "Run a judge in a temporary checkout and say whether it passed, failed or errored.",
        _setup,
        _handle,
        argv,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
