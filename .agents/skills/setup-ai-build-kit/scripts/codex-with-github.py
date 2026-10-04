#!/usr/bin/env python3
"""Start Codex from the person's terminal with session-scoped GitHub access."""
import os
import shutil
import subprocess
import sys


def main():
    gh = shutil.which("gh")
    codex = shutil.which("codex")
    if not gh or not codex:
        sys.exit("Install gh and Codex before starting this session.")

    env = os.environ.copy()
    # HTTP debugging can print credential-bearing headers. Do not carry it
    # into a session which deliberately receives a GitHub credential.
    for key in ("GH_DEBUG", "DEBUG"):
        env.pop(key, None)

    if not (env.get("GH_TOKEN") or env.get("GITHUB_TOKEN")):
        credential = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            env=env, capture_output=True, text=True,
        )
        if credential.returncode or not credential.stdout.strip():
            sys.exit("GitHub credential unavailable. Run gh auth status --hostname github.com in your terminal, then try again.")
        token = credential.stdout.strip()
        if "\n" in token or "\r" in token:
            sys.exit("Unexpected GitHub credential response; Codex was not started.")
        env["GH_TOKEN"] = token

    # The credential stays in process memory, never in argv or a settings file.
    # A dedicated process and disabled snapshots keep it out of a shared daemon
    # and the exported environment a shell snapshot saves on disk.
    argv = [codex, "--no-daemon", "--disable", "shell_snapshot", *sys.argv[1:]]
    os.execvpe(codex, argv, env)


if __name__ == "__main__":
    main()
