#!/usr/bin/env python3
"""Validate mutmut and run the changed-function mutation check."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from mutmut_support import validation_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="origin/main")
    base = parser.parse_args().base
    try:
        version = subprocess.run(["mutmut", "--version"], cwd=Path.cwd(),
                                 capture_output=True, text=True, check=False)
    except OSError as error:
        print(f"mutmut: could not check version: {error}", file=sys.stderr)
        return 2
    output = (version.stdout + version.stderr).strip()
    error = validation_error(Path.cwd(), output)
    if version.returncode:
        error = f"could not check mutmut version: {output or 'mutmut --version failed'}"
    if error:
        print(f"mutmut: {error}", file=sys.stderr)
        return 2
    helper = Path(__file__).with_name("mutmut-changed.py")
    return subprocess.run([sys.executable, str(helper), base], cwd=Path.cwd()).returncode


if __name__ == "__main__":
    raise SystemExit(main())
