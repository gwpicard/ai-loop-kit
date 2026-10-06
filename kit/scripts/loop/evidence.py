"""The piece record: a keyed, hash-chained file of what the gate saw, in `.agents/pieces/<n>/`.

Only the gate writes it. No agent calls `append`: an agent's word is never
evidence. A test greps `kit/` for callers outside the gate's own modules.

Each line holds one entry and a `mac`. The `mac` is an HMAC-SHA256 of the
entry and the token of the line before it. The key lives in the per-project data
folder (`evidence.key`, mode 0600), outside the project, so a builder that can
write the record cannot compute a valid `mac`. A small head record
(`evidence-heads/<n>.json`, with its own `mac`) sits beside the key. It holds the
entry count and the last token. A record shorter than the head says, or one
whose last token differs, is refused. So is a record with a bad `mac`, and a
record whose key or head went missing.

The gate's older format has an unkeyed `chain` on each line instead of a `mac`.
`read` still reads it, but only as a prefix before keyed lines, and `inspect`
(and so `show`) counts those lines as unkeyed. They prove nothing against
someone who can write the file.

A last line with no trailing newline is an interrupted write. `append` moves it
to a sibling file (`evidence.jsonl.interrupted-<n>`), reports it and never
erases it. If the head counts that line, the record is shorter than the head
says and `append` refuses instead.
"""

from __future__ import annotations

import argparse
import hmac
import importlib
import json
import os
import secrets
from hashlib import sha256
from pathlib import Path
from typing import Any

from gate import chain_of

from loop import cli
from loop.paths import PathError, Paths, find_project_root

EVIDENCE = "evidence.jsonl"
RESERVED = ("mac", "chain")
STOP = "stop and tell the person; only they move that file aside, then run the same command again"


class EvidenceError(Exception):
    """A record that cannot be trusted. Carries the next command."""

    def __init__(self, message: str, *, next_command: str = STOP) -> None:
        super().__init__(message)
        self.next_command = next_command


def record_path(paths: Paths, number: int) -> Path:
    return paths.piece_dir(number) / EVIDENCE


def key_path(paths: Paths) -> Path:
    return paths.data_dir / "evidence.key"


def head_path(paths: Paths, number: int) -> Path:
    paths.piece_dir(number)  # checks the number
    return paths.data_dir / "evidence-heads" / f"{number}.json"


def _mac(key: bytes, text: str) -> str:
    return hmac.new(key, text.encode("utf-8"), sha256).hexdigest()


def _line_mac(key: bytes, previous: str, entry: dict[str, Any]) -> str:
    return _mac(key, previous + "\n" + json.dumps(entry, sort_keys=True))


def _read_key(paths: Paths) -> bytes | None:
    try:
        return bytes.fromhex(key_path(paths).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None


def _make_key(paths: Paths) -> bytes:
    """The key, made with mode 0600 on first use."""
    path = key_path(paths)
    os.makedirs(path.parent, mode=0o700, exist_ok=True)
    key = secrets.token_bytes(32)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = _read_key(paths)
        if existing is None:
            raise EvidenceError(
                f"{path.name} exists but holds no key", next_command=STOP
            ) from None
        return existing
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(key.hex() + "\n")
    return key


def _read_head(paths: Paths, number: int, key: bytes | None) -> dict[str, Any] | None:
    path = head_path(paths, number)
    if not path.exists():
        return None
    try:
        head = json.loads(path.read_text(encoding="utf-8"))
        count, last, mac = int(head["count"]), str(head["last"]), str(head["mac"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise EvidenceError(f"the head record {path.name} cannot be read") from error
    if key is None or not hmac.compare_digest(mac, _mac(key, f"head\n{count}\n{last}")):
        raise EvidenceError(f"the head record {path.name} was not written by the gate")
    return {"count": count, "last": last}


def _write_head(paths: Paths, number: int, key: bytes, count: int, last: str) -> None:
    path = head_path(paths, number)
    os.makedirs(path.parent, mode=0o700, exist_ok=True)
    body = {"count": count, "last": last, "mac": _mac(key, f"head\n{count}\n{last}")}
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(body, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _scan(paths: Paths, number: int) -> dict[str, Any]:
    """Check the whole record. Returns the entries, counts, last token and any cut-off line."""
    path = record_path(paths, number)
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    parts = raw.split("\n")
    fragment = parts.pop()
    key = _read_key(paths)
    entries: list[dict[str, Any]] = []
    tokens: list[str] = []
    previous = ""
    keyed = 0
    for count, line in enumerate(parts, start=1):
        try:
            value = json.loads(line)
        except ValueError:
            value = None
        bad = EvidenceError(
            f"line {count} of {path.name} was not written by the gate: it does not "
            "follow from the line before it, so the record cannot be trusted"
        )
        if not isinstance(value, dict):
            raise bad
        mac = value.pop("mac", None)
        chain = value.pop("chain", None)
        if mac is not None:
            if chain is not None or key is None or not isinstance(mac, str):
                raise bad
            if not hmac.compare_digest(mac, _line_mac(key, previous, value)):
                raise bad
            previous = mac
            keyed += 1
        else:
            if keyed or chain != chain_of(previous, value):
                raise bad
            previous = str(chain)
        tokens.append(previous)
        entries.append(value)
    head = _read_head(paths, number, key)
    if keyed and head is None:
        raise EvidenceError(
            f"the head record for {path.name} is missing, so its length cannot be checked"
        )
    if keyed and key is None:
        raise EvidenceError("the key for the piece record is missing")
    if head is not None and head["count"]:
        if len(tokens) < head["count"]:
            raise EvidenceError(
                f"{path.name} is shorter than the head record says "
                f"({len(tokens)} entries, the head counts {head['count']}), so the record "
                "cannot be trusted"
            )
        if tokens[head["count"] - 1] != head["last"]:
            raise EvidenceError(
                f"{path.name} does not match the head record at entry {head['count']}, "
                "so the record cannot be trusted"
            )
    return {
        "entries": entries,
        "count": len(entries),
        "keyed": keyed,
        "unkeyed": len(entries) - keyed,
        "last": previous,
        "fragment": fragment,
        "key": key,
        "head": head,
    }


def read(paths: Paths, number: int) -> list[dict[str, Any]]:
    """Every entry of the piece record. Raises `EvidenceError` when it cannot be trusted."""
    entries: list[dict[str, Any]] = _scan(paths, number)["entries"]
    return entries


def inspect(paths: Paths, number: int) -> dict[str, Any]:
    """The entries with how many are keyed and unkeyed, and any interrupted write."""
    found = _scan(paths, number)
    report: dict[str, Any] = {
        "entries": found["entries"],
        "count": found["count"],
        "keyed": found["keyed"],
        "unkeyed": found["unkeyed"],
        "interrupted_bytes": len(found["fragment"].encode("utf-8")),
        "head_count": found["head"]["count"] if found["head"] else None,
    }
    if found["unkeyed"]:
        report["warning"] = (
            f"{found['unkeyed']} entries are unkeyed (the gate's older format): the chain "
            "alone does not stop a rewrite"
        )
    return report


def _set_aside(path: Path, fragment: str) -> Path:
    number = 1
    while (side := path.with_name(f"{path.name}.interrupted-{number}")).exists():
        number += 1
    descriptor = os.open(side, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(fragment)
        handle.flush()
        os.fsync(handle.fileno())
    return side


def append(
    paths: Paths, number: int, entries: list[dict[str, Any]], *, dry_run: bool = False
) -> list[str]:
    """Add each entry as one keyed line, under a lock on the piece's folder.

    Returns the notes to say, such as an interrupted write set aside. It refuses
    to extend a record that cannot be trusted.
    """
    for entry in entries:
        if any(name in entry for name in RESERVED):
            raise EvidenceError(
                f"an entry may not use the names {', '.join(RESERVED)}",
                next_command="rename the field and run the command again",
            )
    path = record_path(paths, number)
    found = _scan(paths, number)
    notes: list[str] = []
    if found["fragment"]:
        notes.append(
            f"an interrupted write had left a cut-off last line in {path.name}; "
            "it is set aside in a sibling file"
        )
    if dry_run:
        return notes
    path.parent.mkdir(parents=True, exist_ok=True)
    os.makedirs(paths.data_dir, mode=0o700, exist_ok=True)
    fcntl: Any
    try:
        fcntl = importlib.import_module("fcntl")
    except ImportError:  # not a POSIX system; the record goes unlocked
        fcntl = None
    with open(path.parent / ".lock", "a", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        found = _scan(paths, number)
        key = found["key"] or _make_key(paths)
        fragment: str = found["fragment"]
        if fragment:
            side = _set_aside(path, fragment)
            notes[0] = notes[0].replace("a sibling file", side.name)
            size = path.stat().st_size
            with open(path, "r+b") as handle:
                handle.truncate(size - len(fragment.encode("utf-8")))
        previous: str = found["last"]
        text = ""
        for entry in entries:
            mac = _line_mac(key, previous, entry)
            text += json.dumps(dict(entry, mac=mac), sort_keys=True) + "\n"
            previous = mac
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
        _write_head(paths, number, key, found["count"] + len(entries), previous)
    return notes


# --- command line ---------------------------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    show = commands.add_parser("show", help="read a piece record and check its keys and head")
    show.add_argument("--piece", type=int, required=True, help="the piece number")
    show.add_argument("--root", help="the project folder (default: the one around here)")
    show.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="print JSON"
    )


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = Path(args.root) if args.root else find_project_root(Path.cwd())
        paths = Paths.for_project(root)
        report = inspect(paths, args.piece)
    except PathError as error:
        raise cli.Failure(
            str(error), next_command="evidence show --help", code=cli.ExitCode.USAGE
        ) from error
    except EvidenceError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.REFUSED
        ) from error
    return {"piece": args.piece, **report}


def main(argv: list[str]) -> int:
    return cli.run(
        "evidence",
        "Read a piece record and check its hash chain. The gate alone writes the record.",
        _setup,
        _handle,
        argv,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
