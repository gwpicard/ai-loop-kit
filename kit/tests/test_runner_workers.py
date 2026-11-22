"""The runner's command honours the worker budget and conservative defaults."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from kit.tests.helpers import HERE


ROOT = Path(HERE).parent.parent
PROBE = '''
import concurrent.futures, json, os, runpy, sys
from unittest import mock
class ProbePool(concurrent.futures.ThreadPoolExecutor):
    def __init__(self, *args, **kwargs):
        print("WORKERS=" + str(args[0] if args else kwargs["max_workers"]), flush=True)
        super().__init__(*args, **kwargs)
    def map(self, function, jobs):
        return [(module, 0, 0, "") for module, ids in jobs]
cpus = json.loads(sys.argv.pop(1))
sys.argv.pop(0)
with mock.patch("os.cpu_count", return_value=cpus), \\
        mock.patch("concurrent.futures.ThreadPoolExecutor", ProbePool):
    runpy.run_path(sys.argv[0], run_name="__main__")
'''


class RunnerWorkersTest(unittest.TestCase):
    def check_workers(self, cpus, override, expected):
        env = dict(os.environ)
        env.pop("LOOP_TEST_WORKERS", None)
        if override is not None:
            env["LOOP_TEST_WORKERS"] = str(override)
        # Discover enough jobs to observe the cap; the probe records scheduling without running them.
        files = sorted(Path(HERE).glob("test_parse_block*.py")) + [Path(HERE, name) for name in (
            "test_guard_gh_newline.py", "test_guard_github_token_kinds.py",
            "test_guard_pgp_private_key.py", "test_guard_slack_token_kinds.py")]
        self.assertGreaterEqual(len(files), 8)
        result = subprocess.run([sys.executable, "-c", PROBE, json.dumps(cpus),
                                 str(Path(HERE, "run.py")), *map(str, files)],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        counts = [int(line.split("=", 1)[1]) for line in result.stdout.splitlines()
                  if line.startswith("WORKERS=")]
        self.assertEqual(counts, [expected], result.stdout)

    def test_environment_sets_the_worker_count(self):
        for cpus, override in ((16, 1), (16, 3), (2, 4), (2, 9)):
            with self.subTest(cpus=cpus, override=override):
                self.check_workers(cpus, override, override)

    def test_default_is_half_the_processors_bounded_by_two_and_eight(self):
        for cpus, expected in ((1, 2), (2, 2), (7, 3), (12, 6), (32, 8), (None, 2)):
            with self.subTest(cpus=cpus):
                self.check_workers(cpus, None, expected)
