#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""Merge a settings template into a project's own settings file.

    merge-settings.py TEMPLATE TARGET [--set NAME=VALUE ...]

The kit's rules are added to the person's rules. Nothing the person wrote is
taken out or changed:

- an object is merged key by key;
- a list keeps the person's entries first, then adds each template entry the
  list lacks;
- for any other value, the person's value stays. When it differs from the
  kit's value, such as `sandbox.enabled: false`, the script reports it on
  stderr and in `overridden`, so a person's value never beats a guard unseen.

Each `--set NAME=VALUE` replaces `{{NAME}}` in the template's text before the
merge, such as `--set KIT_DIR=/path/to/kit`. A second run with the same
arguments changes nothing. A target that does not exist is made from the
template. A target that is not JSON is left as it is.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli


def merge(
    mine: Any,
    template: Any,
    added: list[str],
    where: str = "",
    overridden: list[str] | None = None,
) -> Any:
    """The person's value with the template's additions. `added` collects what changed.

    `overridden` collects each place where the person's own value differs from the kit's.
    """
    if isinstance(mine, dict) and isinstance(template, dict):
        out = dict(mine)
        for key, value in template.items():
            here = f"{where}.{key}" if where else key
            if key in out:
                out[key] = merge(out[key], value, added, here, overridden)
            else:
                out[key] = value
                added.append(here)
        return out
    if isinstance(mine, list) and isinstance(template, list):
        out_list = list(mine)
        for item in template:
            if item not in out_list:
                out_list.append(item)
                added.append(f"{where}: {json.dumps(item)[:80]}")
        return out_list
    if overridden is not None and mine != template:
        theirs, kits = json.dumps(mine)[:60], json.dumps(template)[:60]
        overridden.append(f"{where}: {theirs} (the kit's value is {kits})")
    return mine


def render(text: str, values: dict[str, str]) -> str:
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    return text


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("template", help="the settings template to merge in")
    parser.add_argument("target", help="the project's settings file")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                        help="replace {{NAME}} in the template with VALUE")


def handler(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, str] = {}
    for pair in args.set:
        name, sep, value = pair.partition("=")
        if not sep or not name:
            raise cli.Failure(
                f"{pair!r} is not NAME=VALUE",
                next_command="merge-settings.py --help",
                code=cli.ExitCode.USAGE,
            )
        if name == "KIT_DIR":
            if not Path(value).is_absolute():
                raise cli.Failure(
                    "KIT_DIR must be an absolute installed kit path",
                    next_command="give --set KIT_DIR=/absolute/path/to/kit",
                    code=cli.ExitCode.USAGE,
                )
            value = str(Path(value).resolve())
        values[name] = value
    template_path, target = Path(args.template), Path(args.target)
    try:
        template = json.loads(render(template_path.read_text(), values))
    except OSError as error:
        raise cli.Failure(f"cannot read the template: {error}",
                          next_command="merge-settings.py --help",
                          code=cli.ExitCode.ENVIRONMENT) from error
    except ValueError as error:
        raise cli.Failure(f"the template is not JSON once the values are set ({error})",
                          next_command="merge-settings.py --help") from error
    if target.exists():
        try:
            mine = json.loads(target.read_text())
        except ValueError as error:
            raise cli.Failure(
                f"{target} is not valid JSON ({error}), so it was left as it is",
                next_command=f"fix {target}, then run merge-settings.py again",
                code=cli.ExitCode.REFUSED) from error
        if not isinstance(mine, dict):
            raise cli.Failure(f"{target} is not a JSON object, so it was left as it is",
                              next_command=f"fix {target}, then run merge-settings.py again",
                              code=cli.ExitCode.REFUSED)
    else:
        mine = {}
    added: list[str] = []
    overridden: list[str] = []
    merged = merge(mine, template, added, overridden=overridden)
    for line in overridden:
        print(f"merge-settings.py: your value beats the kit's guard value at {line}",
              file=sys.stderr)
    if added and not args.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".merge-settings.")
        with os.fdopen(handle, "w") as stream:
            json.dump(merged, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        if target.exists():
            os.chmod(temporary, target.stat().st_mode & 0o777)
        else:
            os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    return {"target": str(target), "changed": bool(added), "added": added,
            "overridden": overridden}


def main(argv: list[str]) -> int:
    return cli.run(
        "merge-settings.py",
        "Merge a settings template into a project's settings file, keeping the person's rules.",
        setup,
        handler,
        argv,
        changes_state=True,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
