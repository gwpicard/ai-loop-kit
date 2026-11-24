"""Collect a crashed pass after a registered group has lost its leader."""
import os
import signal

from kit.tests.helpers import write_exe
from kit.tests import test_pass_review_fixes as fixes
import common
import loop
import session


class PassOrphanCleanupTest(fixes.BackgroundPassFixture):
    agent = fixes.PassReviewFixesTest.agent
    end_agents = fixes.PassReviewFixesTest.end_agents
    assert_ended = fixes.PassReviewFixesTest.assert_ended

    def orphan(self, hook=False, completed=False):
        write_exe(os.path.join(self.tmp, "bin", "ps"), '#!/bin/sh\nexec /bin/ps "$@"\n', shared=False)
        command = ("import os, pathlib, subprocess, sys, time; "
                   "p = subprocess.Popen([sys.executable, '-c', "
                   "\"import time; time.sleep(30)\"], stdin=subprocess.DEVNULL, "
                   "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
                   "pathlib.Path(%r).write_text(str(p.pid)); "
                   "pathlib.Path(%r).write_text(str(os.getpid())); "
                   "%s" % (str(self.runtime / "hook-pid"), str(self.runtime / "leader-pid"),
                            "os._exit(0)" if completed else "time.sleep(30)"))
        self.agent(
            "sys.path.insert(0, %r)\nimport common, shlex\n"
            "(root / 'agent-pid').write_text(str(os.getpid()))\n"
            "command = [sys.executable, '-c', %r]\n" % (loop.HERE, command)
            + ("common.run_shell('exec ' + shlex.join(command), os.getcwd(), 60, record=os.environ['LOOP_GROUPS'])\n"
               "(root / 'hook-returned').touch()\ntime.sleep(30)\n"
               if hook else "os.execv(sys.executable, command)\n"))
        self.addCleanup(self.end_agents)
        done = self.begin_drain()
        self.wait_for(lambda: (self.runtime / "leader-pid").exists(), "the command did not start")
        self.assertTrue(done.wait(2))
        leader = int((self.runtime / "leader-pid").read_text())
        child = int((self.runtime / "hook-pid").read_text())
        self.assertEqual(os.getpgid(child), leader)
        self.workers[0].kill()
        self.workers[0].wait(timeout=5)
        if completed:
            self.wait_for(lambda: (self.runtime / "hook-returned").exists(), "the hook did not return")
        else:
            os.kill(leader, signal.SIGKILL)
        self.wait_for(lambda: leader not in loop.process_table()
                      or loop.process_table()[leader][1].startswith("Z"), "the group leader did not exit")
        return child

    def test_crashed_worker_collection_ends_an_agent_group_without_its_leader(self):
        child = self.orphan()
        loop.reap(self.work, self.st)
        self.assert_ended([child])
        self.assertIn("The pass failed:", loop.last_pass(self.work)["text"])

    def test_crashed_worker_collection_ends_a_hook_group_without_its_leader(self):
        child = self.orphan(hook=True)
        loop.reap(self.work, self.st)
        self.assert_ended([child])

    def test_crashed_worker_collection_keeps_ownership_after_a_hook_returns(self):
        child = self.orphan(hook=True, completed=True)
        loop.reap(self.work, self.st)
        self.assert_ended([child])

    def test_a_wrong_ownership_token_does_not_kill_a_surviving_group(self):
        child = self.orphan()
        path = common.build_file(self.work, "pass", "groups")
        pgid = os.getpgid(child)
        self.runtime.joinpath("wrong-groups").write_text("%d:wrong-token\n" % pgid)
        self.assertEqual(session.reap_groups(str(self.runtime / "wrong-groups"), self.st["pass"]["began"]), [])
        self.assertEqual(os.getpgid(child), pgid)
        self.assertTrue(os.path.exists(path))
        loop.reap(self.work, self.st)
        self.assert_ended([child])
