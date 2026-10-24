"""Control scripts refuse a Python older than the launcher's version.

The version lives in bin/kit-python only. Keep this file readable by old
Pythons, so it can say what is wrong instead of failing on new syntax.
"""
import re
import sys
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "bin" / "kit-python"


def required():
    found = re.search(r"^KIT_PYTHON=(\d+)\.(\d+)$", LAUNCHER.read_text(), re.M)
    return int(found.group(1)), int(found.group(2))


def require():
    need = required()
    if sys.version_info[:2] < need:
        print(f"refused: the kit needs Python {need[0]}.{need[1]}, "
              f"and this is {sys.version.split()[0]}", file=sys.stderr)
        print(f'next: start kit scripts with "{LAUNCHER}" <script>', file=sys.stderr)
        sys.exit(2)
