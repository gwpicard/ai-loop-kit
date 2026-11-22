"""List existing paths to approve before an issue enters the loop."""
import argparse
import collections
import json
from pathlib import Path
import re
import sys

import common
import merge

MAX_FILES = 20


def paths(body, project=".", protected=None, ref=None):
    """Find tracked tests referring to backticked names and named stop paths.

    A ref reads the loop branch rather than the supervisor's working tree.
    """
    names = sorted(set(re.findall(r"(?<!`)`([^`\n]+)`(?!`)", body)))
    tracked = set(common.git(
        ["ls-tree", "-rz", "--name-only", ref] if ref else ["ls-files", "-z"],
        cwd=project).split("\0")) - {""}
    if protected is None:
        protected = (common.read_settings(project)["Protected paths"]
                     if Path(project, "loop.json").exists()
                     else common.DEFAULTS["Protected paths"])
    found = set()
    if names:
        args = ["grep", "--full-name", "-zlF"]
        for name in names:
            args += ["-e", name]
        output = common.git(args + ([ref] if ref else []) + ["--"],
                            cwd=project, check=False)
        prefix = ref + ":" if ref else ""
        found.update(p.removeprefix(prefix) for p in output.split("\0") if p)
    named = {n.removeprefix("./") for n in names} | merge.allowed_paths(body)
    return sorted({p for p in found & tracked if merge.is_test_file(p)} | {
        p for p in named & tracked if merge.is_test_file(p)
        or merge.stop_reason(p, protected, project, ref)})


def warnings(files, issues=()):
    """Warn about large slices and dependency bottlenecks, counting links."""
    result = []
    if len(files) > MAX_FILES:
        result.append("Warning: %d existing files exceed MAX_FILES (%d); split the issue."
                      % (len(files), MAX_FILES))
    graph = {i["number"]: set(common.depends_on(i.get("body") or "")) for i in issues}
    dependants = collections.Counter(d for deps in graph.values() for d in deps)
    for number, count in sorted(dependants.items()):
        if count > 2:
            result.append("Warning: issue %s has %d dependants; split the dependency bottleneck."
                          % (number, count))

    def deep(number, seen):
        return any(d not in seen and (len(seen) >= 4 or deep(d, seen | {d}))
                   for d in graph.get(number, ()))

    if any(deep(n, {n}) for n in graph):
        result.append("Warning: dependency chain is deeper than three links; split the chain.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("body", help="draft issue body file")
    parser.add_argument("--issues", help="JSON array of issues with number and body")
    args = parser.parse_args()
    try:
        files = paths(Path(args.body).read_text(encoding="utf-8"))
        issues = json.loads(Path(args.issues).read_text(encoding="utf-8")) if args.issues else []
        for path in files:
            print(path)
        for warning in warnings(files, issues):
            print(warning, file=sys.stderr)
        return int(len(files) > MAX_FILES)
    except (OSError, ValueError, common.LoopError) as error:
        print("shapecheck: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
