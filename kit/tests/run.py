"""Run the test modules in parallel, each in its own process.

    python3 kit/tests/run.py

A module with many tests is split into shards (a shard is a process running a
share of that module's tests), so one slow module does not set the total time.
Prints one line per module and a summary. Exits non-zero if any test fails.
Standard library only.
"""
import atexit
import collections
import concurrent.futures
import os
import re
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHARD_SIZE = 10  # tests per process, at most
JOB_TIMEOUT = 1800  # seconds a test process may run
GROUPS = set()  # process groups of the running test processes


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
        name = "kit.tests." + f[:-3]
        ids = list(test_ids(unittest.defaultTestLoader.loadTestsFromName(name)))
        shards = max(1, -(-len(ids) // SHARD_SIZE))
        out += [(f[:-3], ids[i::shards]) for i in range(shards)]
    return sorted(out, key=lambda j: -len(j[1]))


def kill_group(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def stop_all():
    for pgid in list(GROUPS):
        kill_group(pgid)


def stop(signum, frame):
    stop_all()
    os._exit(128 + signum)


def run_job(job):
    module, ids = job
    # Test modules may import the kit's scripts without importing helpers first.
    # The path is set in the child only, so the hooks the tests start do not inherit it.
    code = ("import sys, unittest; sys.path.insert(0, %r); "
            "unittest.main(module=None, argv=['unittest'] + sys.argv[1:])"
            % os.path.join(ROOT, "kit", "scripts"))
    p = subprocess.Popen([sys.executable, "-c", code] + ids, cwd=ROOT, text=True, start_new_session=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    GROUPS.add(p.pid)
    try:
        out, err = p.communicate(timeout=JOB_TIMEOUT)
    except subprocess.TimeoutExpired:
        kill_group(p.pid)
        p.communicate()
        return module, 1, 0, "%s: a test process ran longer than %d seconds and was killed\n" % (module, JOB_TIMEOUT)
    finally:
        kill_group(p.pid)  # nothing the tests started outlives them
        GROUPS.discard(p.pid)
    ran = re.search(r"Ran (\d+) tests?", err)
    return module, p.returncode, int(ran.group(1)) if ran else 0, err


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    atexit.register(stop_all)
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
