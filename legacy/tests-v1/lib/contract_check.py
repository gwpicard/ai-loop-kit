"""Hold an agent script to design principle 8. Used by tests/script-contracts.sh.

Usage: contract_check.py SCRIPT...

A script is checked when it carries the line `# contract: agent` in its first
ten lines. The extra line `# contract: changes-state` adds the `--dry-run` rule.

For each script it checks, with no terminal and an empty standard input:

1. `--help` exits 0, prints text, names the exit codes, and (for a script that
   changes state) names `--dry-run`;
2. a run with no arguments ends in time, exits with a documented code, prints
   nothing or one JSON object on standard output, and, on a failure, prints a
   `next:` line on standard error;
3. a second run on the same input gives the same exit code and the same output;
4. `--dry-run` (for a script that changes state) leaves its folder as it was.

Set CONTRACT_TIMEOUT to change the 20 second limit for a run.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop.cli import ExitCode

TIMEOUT = float(os.environ.get("CONTRACT_TIMEOUT", "20"))
DOCUMENTED = {int(code) for code in ExitCode}


class Result:
    def __init__(self, code: int | None, out: str, err: str) -> None:
        self.code = code  # None means the run timed out
        self.out = out
        self.err = err


def execute(script: Path, args: list[str], cwd: Path) -> Result:
    """Run the script with no terminal and no input, and stop it if it hangs."""
    proc = subprocess.Popen(
        [str(script), *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return Result(None, "", "")
    return Result(proc.returncode, out, err)


def listing(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))


def markers(script: Path) -> set[str]:
    found: set[str] = set()
    with open(script, encoding="utf-8", errors="replace") as handle:
        for _ in range(10):
            line = handle.readline().strip()
            if line.startswith("# contract:"):
                found.add(line.removeprefix("# contract:").strip())
    return found


def json_object(text: str) -> bool:
    if not text.strip():
        return True
    try:
        return isinstance(json.loads(text), dict)
    except ValueError:
        return False


def check(script: Path) -> list[str]:
    problems: list[str] = []
    found = markers(script)
    if "agent" not in found:
        return [f"{script} is not marked '# contract: agent'"]
    changes_state = "changes-state" in found

    scratch = Path(tempfile.mkdtemp())

    # 1. --help
    helped = execute(script, ["--help"], scratch)
    if helped.code is None:
        problems.append("--help timed out")
    elif helped.code != 0:
        problems.append(f"--help exited {helped.code}, not 0")
    elif not helped.out.strip():
        problems.append("--help prints nothing on standard output")
    else:
        text = helped.out.lower()
        if "exit codes" not in text:
            problems.append("--help does not name the exit codes (write a line 'exit codes: ...')")
        if changes_state and "--dry-run" not in text:
            problems.append("--help does not name --dry-run, but the script changes state")

    # 2. no arguments, no terminal
    first = execute(script, [], scratch)
    if first.code is None:
        problems.append(
            f"no arguments: timed out after {TIMEOUT:g} seconds (does it wait for input?)"
        )
    else:
        if first.code not in DOCUMENTED:
            problems.append(
                f"no arguments: exit code {first.code} is not one of {sorted(DOCUMENTED)}"
            )
        if not json_object(first.out):
            problems.append("no arguments: standard output is not JSON")
        if first.code != 0 and "next:" not in first.err:
            problems.append(
                f"no arguments: exit {first.code} with no 'next:' line on standard error"
            )

    # 3. twice on the same input, in the same folder
    if first.code is not None:
        second = execute(script, [], scratch)
        if (second.code, second.out) != (first.code, first.out):
            problems.append("running twice on the same input gave a different result")

    # 4. --dry-run changes nothing
    if changes_state:
        fresh = Path(tempfile.mkdtemp())
        before = listing(fresh)
        dry = execute(script, ["--dry-run"], fresh)
        if dry.code is None:
            problems.append("--dry-run timed out")
        elif listing(fresh) != before:
            problems.append("--dry-run changed the folder it ran in")
        elif not json_object(dry.out):
            problems.append("--dry-run: standard output is not JSON")

    return problems


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write((__doc__ or "").strip() + "\n")
        return 0 if argv else 2
    failed = 0
    for name in argv:
        script = Path(name)
        if not script.is_file():
            print(f"FAIL {name}: no such file")
            failed += 1
            continue
        problems = check(script)
        for problem in problems:
            print(f"FAIL {name}: {problem}")
        if problems:
            failed += 1
        else:
            print(f"ok: {name} meets the script contract")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
