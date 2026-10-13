#!/usr/bin/env python3
"""as-person.py: run a command as a person at a terminal would.

Usage: as-person.py COMMAND [ARGUMENT ...]

The command gets a pseudo-terminal for standard input and standard output, which is what the
gate reads as a person typing (`gate.py sync` and the person's merge check it). Standard error
stays as it is. What the command wrote to its terminal is printed, with the carriage returns
a terminal adds taken out, and the command's exit code is this script's exit code. A test
uses this to stand in for the person's own terminal. An agent session has no such terminal.
"""

import os
import pty
import sys


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("usage: as-person.py COMMAND [ARGUMENT ...]\n")
        return 2
    saved = os.dup(2)
    pid, master = pty.fork()
    if pid == 0:
        os.dup2(saved, 2)
        os.execvp(argv[0], argv)
    chunks: list[bytes] = []
    while True:
        try:
            data = os.read(master, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    _, status = os.waitpid(pid, 0)
    sys.stdout.write(b"".join(chunks).decode("utf-8", "replace").replace("\r\n", "\n"))
    sys.stdout.flush()
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
