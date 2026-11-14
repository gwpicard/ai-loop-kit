"""Run the test modules in parallel, each in its own process.

    python3 lite/tests/run.py

A module with many tests is split into shards (a shard is a process running a
share of that module's tests), so one slow module does not set the total time.
Prints one line per module and a summary. Exits non-zero if any test fails.
Standard library only.
"""
import collections
import concurrent.futures
import os
import re
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHARD_SIZE = 10  # tests per process, at most


def test_ids(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from test_ids(t)
        else:
            yield t.id()


def jobs():
    """(module, [test ids]) for each process to run, the largest first."""
    sys.path.insert(0, ROOT)
    out = []
    for f in sorted(os.listdir(HERE)):
        if not (f.startswith("test_") and f.endswith(".py")):
            continue
        name = "lite.tests." + f[:-3]
        ids = list(test_ids(unittest.defaultTestLoader.loadTestsFromName(name)))
        shards = max(1, -(-len(ids) // SHARD_SIZE))
        out += [(f[:-3], ids[i::shards]) for i in range(shards)]
    return sorted(out, key=lambda j: -len(j[1]))


def run_job(job):
    module, ids = job
    p = subprocess.run([sys.executable, "-m", "unittest"] + ids, cwd=ROOT,
                       capture_output=True, text=True)
    ran = re.search(r"Ran (\d+) tests?", p.stderr)
    return module, p.returncode, int(ran.group(1)) if ran else 0, p.stderr


def main():
    work = jobs()
    workers = max(1, min(os.cpu_count() or 1, 8, len(work)))
    start = time.time()
    ran, bad, errors = collections.Counter(), set(), []
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for module, code, n, err in pool.map(run_job, work):
            ran[module] += n
            if code != 0:
                bad.add(module)
                errors.append(err)
    for module in sorted(ran):
        print("%-4s %-14s %3d tests" % ("FAIL" if module in bad else "ok", module, ran[module]))
    print("".join(errors), end="")
    print("%d tests in %d modules, %d failed, %.1fs"
          % (sum(ran.values()), len(ran), len(bad), time.time() - start))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
