"""Project admission races, crash recovery and run-record freshness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import cli  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import record  # noqa: E402

WORKER = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from loop.paths import Paths
from loop.run import record
paths = Paths.for_project(Path(sys.argv[2]), data_base=Path(sys.argv[2]) / 'data')
name = sys.argv[3]
print('ready', flush=True)
sys.stdin.readline()
try:
    lock = record.acquire_lock(paths, name)
except record.LockHeld:
    print('refused', flush=True)
else:
    try:
        if len(sys.argv) > 4:
            if record.RunRecord.exists(paths, name):
                run = record.RunRecord.load(paths, name)
            else:
                run = record.RunRecord.create(paths, name, [1], attended=True,
                                               merge_pre_approved=False)
                run.set_status(1, record.BUILT, branch='saved-work')
            print(json.dumps({'status': run.status(1), 'branch': run.piece(1)['branch']}),
                  flush=True)
        else:
            print('admitted', flush=True)
        sys.stdin.readline()
    finally:
        lock.release()
"""


CRASH_WRITER = """
import os, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from loop.paths import Paths
from loop.run import record
paths = Paths.for_project(Path(sys.argv[2]), data_base=Path(sys.argv[2]) / 'data')
name = sys.argv[3]
actual_open = os.open
def crash_open(path, *args, **kwargs):
    fd = actual_open(path, *args, **kwargs)
    target = Path(path)
    if target.parent == paths.run_dir(name) and target.name.startswith('lock'):
        os.kill(os.getpid(), signal.SIGKILL)
    return fd
os.open = crash_open
print('ready', flush=True)
sys.stdin.readline()
record.acquire_lock(paths, name)
"""


def run_module() -> Any:
    spec = importlib.util.spec_from_file_location("project_lock_run", ROOT / "kit/scripts/run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LockCase(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp(prefix="project-lock-test-"))
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data")
        self.children: list[subprocess.Popen[str]] = []
        self.addCleanup(self.stop_children)

    def stop_children(self) -> None:
        for child in self.children:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()

    def line(self, child: subprocess.Popen[str]) -> str:
        assert child.stdout is not None
        self.assertTrue(select.select([child.stdout], [], [], 10)[0], "worker timed out")
        return child.stdout.readline().strip()

    def send(self, child: subprocess.Popen[str]) -> None:
        assert child.stdin is not None
        child.stdin.write("go\n")
        child.stdin.flush()

    def start(self, name: str, *, saved: bool = False,
              crash_write: bool = False) -> subprocess.Popen[str]:
        child = subprocess.Popen(
            [sys.executable, "-c", CRASH_WRITER if crash_write else WORKER,
             str(ROOT / "kit/scripts"), str(self.folder), name,
             *(["saved"] if saved else [])], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        self.children.append(child)
        self.assertEqual(self.line(child), "ready")
        return child

class ProjectLockTest(LockCase):
    def race(self, names: tuple[str, str]) -> None:
        children = [self.start(name) for name in names]
        for child in children:
            self.send(child)
        results = [self.line(child) for child in children]
        self.assertEqual(sorted(results), ["admitted", "refused"],
                         "CR-17: different names must share one project admission")
        winner = children[results.index("admitted")]
        loser = children[results.index("refused")]
        loser.wait(timeout=10)
        project_lock = self.paths.runs_dir / ".project.lock"
        owner = json.loads(project_lock.read_text())
        self.assertEqual(owner["pid"], winner.pid)
        self.assertEqual(owner["run"], names[results.index("admitted")])
        self.assertEqual(owner["record"], str(self.paths.run_record(owner["run"])))
        before = project_lock.read_bytes()
        with self.assertRaises(record.LockHeld):
            record.acquire_lock(self.paths, "third-name")
        self.assertEqual(project_lock.read_bytes(), before,
                         "CR-17: a loser must leave the winner's metadata unchanged")
        self.send(winner)
        self.assertEqual(winner.wait(timeout=10), 0)

    def test_different_names_race_for_one_project(self) -> None:
        self.race(("alpha", "beta"))

    def test_crash_recovery_race_has_only_one_successor(self) -> None:
        child = self.start("crashed")
        self.send(child)
        self.assertEqual(self.line(child), "admitted")
        child.kill()
        child.wait(timeout=10)
        self.race(("restart-one", "restart-two"))

    def test_crash_before_pid_write_does_not_block_successors(self) -> None:
        child = self.start("crashed-write", crash_write=True)
        self.send(child)
        self.assertEqual(child.wait(timeout=10), -9)
        self.race(("restart-one", "restart-two"))

    def test_same_name_crash_restart_keeps_finished_work_and_project_inode(self) -> None:
        child = self.start("saved", saved=True)
        self.send(child)
        self.assertEqual(json.loads(self.line(child)),
                         {"status": record.BUILT, "branch": "saved-work"})
        project_lock = self.paths.runs_dir / ".project.lock"
        self.assertTrue(project_lock.exists(), "CR-17: admission must have a project lock")
        inode = project_lock.stat().st_ino
        child.kill()
        child.wait(timeout=10)
        again = self.start("saved", saved=True)
        self.send(again)
        self.assertEqual(json.loads(self.line(again)),
                         {"status": record.BUILT, "branch": "saved-work"})
        self.assertEqual(project_lock.stat().st_ino, inode)
        self.send(again)
        self.assertEqual(again.wait(timeout=10), 0)
        self.assertEqual(project_lock.stat().st_ino, inode)
        lock = record.acquire_lock(self.paths, "next")
        try:
            self.assertEqual(project_lock.stat().st_ino, inode)
        finally:
            lock.release()

    def test_release_twice_cannot_release_the_next_owner(self) -> None:
        first = record.acquire_lock(self.paths, "first")
        first.release()
        next_lock = record.acquire_lock(self.paths, "second")
        try:
            first.release()
            with self.assertRaises(record.LockHeld,
                                   msg="CR-17: old release cannot unlock successor"):
                record.acquire_lock(self.paths, "third")
        finally:
            next_lock.release()

    def test_owner_write_failure_releases_admission_and_its_mirror(self) -> None:
        original_sync = os.fsync

        def fail_owner_sync(fd: int) -> None:
            if os.fstat(fd).st_ino == self.paths.project_lock.stat().st_ino:
                raise OSError("owner write failed")
            original_sync(fd)

        with (patch.object(os, "fsync", side_effect=fail_owner_sync),
              self.assertRaises(record.LockHeld)):
            record.acquire_lock(self.paths, "failed-write")
        self.assertFalse(self.paths.lock_file("failed-write").exists(),
                         "CR-17: failed admission must not leave a live PID mirror")
        lock = record.acquire_lock(self.paths, "successor")
        lock.release()

    def test_different_projects_are_independent(self) -> None:
        other = Paths.for_project(self.folder / "other", data_base=self.folder / "data")
        first = record.acquire_lock(self.paths, "first")
        try:
            second = record.acquire_lock(other, "second")
            second.release()
        finally:
            first.release()

    def test_live_legacy_lock_under_another_name_refuses(self) -> None:
        path = self.paths.lock_file("legacy")
        path.parent.mkdir(parents=True)
        path.write_text(f"{os.getpid()}\n")
        with self.assertRaises(record.LockHeld,
                               msg="CR-17: live legacy owner must refuse admission"):
            record.acquire_lock(self.paths, "new")

    def test_malformed_legacy_lock_under_another_name_refuses(self) -> None:
        path = self.paths.lock_file("legacy")
        path.parent.mkdir(parents=True)
        path.write_text("unknown\n")
        with self.assertRaises(record.LockHeld, msg="CR-17: unknown legacy owner must refuse"):
            record.acquire_lock(self.paths, "new")
        self.assertEqual(path.read_text(), "unknown\n")


class RunAdmissionRecordTest(LockCase):
    def test_run_reloads_finished_state_after_admission(self) -> None:
        self.check_reload(already_exists=True)

    def test_run_created_during_preflight_is_resumed(self) -> None:
        self.check_reload(already_exists=False)

    def check_reload(self, *, already_exists: bool, changed_order: bool = False,
                     changed_infos: bool = False) -> None:
        module = run_module()
        if already_exists:
            record.RunRecord.create(self.paths, "saved", [1], attended=True,
                                    merge_pre_approved=False)

        def preflight(*args: Any) -> list[str]:
            fresh = (record.RunRecord.load(self.paths, "saved") if already_exists
                     else record.RunRecord.create(self.paths, "saved", [1], attended=True,
                                                  merge_pre_approved=False))
            fresh.set_status(1, record.BUILT, branch="saved-work")
            fresh.set_run_status(record.RUNNING, starts=7)
            if changed_order:
                fresh.data["order"] = [2]
                fresh.data["pieces"] = {"2": {"status": record.PENDING}}
                fresh.save()
            return []

        def engine_factory(*args: Any, **kwargs: Any) -> Any:
            self.assertFalse(changed_order,
                             "CR-17: changed run selection must refuse before engine")
            admitted = args[2]
            self.assertEqual(admitted.status(1), record.BUILT,
                             "CR-17: admission must reload finished-piece state")
            self.assertEqual(admitted.data["starts"], 8)
            if changed_infos:
                self.assertEqual(args[4][0].title, "fresh title",
                                 "CR-17: engine inputs must be refreshed under admission")
            return SimpleNamespace(run=lambda: SimpleNamespace(
                status=record.FINISHED, data={}, code=0, next_command="read summary"))

        parser = argparse.ArgumentParser()
        module.setup(parser)
        args = parser.parse_args(["--run", "saved"])
        args.dry_run = False
        info = SimpleNamespace(number=1, title="piece", issue="piece URL", areas={"code"})
        fresh_info = SimpleNamespace(number=1, title="fresh title", issue="piece URL",
                                     areas={"fresh area"})
        with (patch.object(module, "_paths", return_value=self.paths),
              patch.object(module, "_numbers", return_value=[1]),
              patch.object(module, "_policy", return_value={"min_free_memory_mb": 0,
                                                           "builder_cap": 1}),
              patch.object(module, "_pre_run_module", return_value=SimpleNamespace(
                  free_memory_mb=lambda: 100)),
              patch.object(module, "_caffeinate", return_value=(None, "stand-in awake")),
              patch.object(module, "_pre_run_check", side_effect=preflight),
              patch.object(module, "_first_command", return_value=["stand-in"]),
              patch.object(module.github, "GitHub"),
              patch.object(module.engine, "read_infos",
                           side_effect=[[info], [fresh_info]] if changed_infos else None,
                           return_value=[info]),
              patch.object(module.engine, "Engine", side_effect=engine_factory),
              patch.object(module.plan, "make_plan", return_value=SimpleNamespace(as_dict=dict))):
            if changed_order:
                with self.assertRaises(cli.Failure) as caught:
                    module.handler(args)
                self.assertIn("changed", str(caught.exception))
            else:
                module.handler(args)
        self.assertFalse(self.paths.lock_file("saved").exists())

    def test_changed_run_order_refuses_before_engine(self) -> None:
        self.check_reload(already_exists=True, changed_order=True)

    def test_run_refreshes_engine_inputs_under_admission(self) -> None:
        self.check_reload(already_exists=True, changed_infos=True)
