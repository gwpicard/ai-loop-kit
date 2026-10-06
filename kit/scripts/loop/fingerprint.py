"""The fingerprint of a piece's judge: a hash of the spec block and the judge commit.

The gate stores the fingerprint when a piece becomes ready. A later run takes it
again. A different fingerprint means that the spec or the judge changed, and the
gate refuses to trust the old evidence.

Two parts go in:

- the spec block, read through the one parser (`loop.spec`), cut to the text
  between the markers, with blanks collapsed and the lines the gate writes
  itself (`Fails today:`) left out;
- the commit that last touched the judge files.

Text outside the block, such as the issue title or a comment, does not count.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loop import cli, spec

GATE_KEYS = ("fails today",)
_KEY = re.compile(r"^([A-Za-z][A-Za-z -]*?):")


class FingerprintError(Exception):
    """A fingerprint that cannot be taken. Carries the next command."""

    def __init__(self, message: str, *, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalise(block: str) -> str:
    """The block with blanks collapsed and the gate's own lines removed."""
    kept: list[str] = []
    skipping = False
    for raw in block.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        match = _KEY.match(line)
        if match:
            skipping = match.group(1).lower() in GATE_KEYS
        elif line.startswith("#"):
            skipping = False
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


def take(body: str, judge_commit: str) -> dict[str, str]:
    """The fingerprint of the spec block in `body` and the judge commit.

    Raises `spec.SpecError` for a block the parser refuses, and
    `FingerprintError` when the body holds no spec block.
    """
    parsed = spec.parse(body)
    if not parsed.found:
        raise FingerprintError(
            "the text holds no spec block, so there is nothing to fingerprint",
            next_command="add the spec block as kit/spec-format.md says, then run it again",
        )
    spec_hash = _sha(normalise(parsed.block))
    return {
        "spec": spec_hash,
        "judge_commit": judge_commit,
        "fingerprint": _sha(f"{spec_hash}\n{judge_commit}"),
    }


def judge_commit(root: Path, ref: str, files: Sequence[str]) -> str:
    """The last commit on `ref` that touched any of the judge files."""
    if not files:
        raise FingerprintError(
            "no judge file was named", next_command="name the judge files and run it again"
        )
    done = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%H", ref, "--", *files],
        capture_output=True,
        text=True,
        check=False,
    )
    commit = done.stdout.strip()
    if done.returncode != 0 or not commit:
        raise FingerprintError(
            f"no commit on {ref} touches {', '.join(files)}",
            next_command=f"commit the judge files to {ref}, then run it again",
        )
    return commit


# --- command line ---------------------------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--file", required=True, help="a file that holds the spec block")
    parser.add_argument("--judge-commit", required=True, help="the commit of the judge files")


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        body = Path(args.file).read_text(encoding="utf-8")
    except OSError as error:
        raise cli.Failure(
            f"the file {args.file} could not be read ({error.strerror})",
            next_command="fingerprint --help",
            code=cli.ExitCode.USAGE,
        ) from error
    try:
        return dict(take(body, args.judge_commit))
    except spec.SpecError as error:
        raise cli.Failure(
            str(error),
            next_command=error.next_command,
            code=cli.ExitCode.REFUSED if error.refused else cli.ExitCode.FAILURE,
        ) from error
    except FingerprintError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.REFUSED
        ) from error


def main(argv: list[str]) -> int:
    return cli.run(
        "fingerprint",
        "Take the fingerprint of a spec block and a judge commit.",
        _setup,
        _handle,
        argv,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
