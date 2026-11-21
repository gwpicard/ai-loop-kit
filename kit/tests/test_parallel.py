"""Parallel builds: the supervisor starts worker processes; merges queue behind one lock."""
import json
import os
import re
import sys
import threading
import time
import unittest
from unittest import mock

from kit.tests.helpers import run_git, write_settings
from kit.tests.test_loop import AGENTS, Base, FACTORY, issue, setUpModule, tearDownModule  # noqa: F401
from kit.tests import test_loop
import common
import flow
import loop
import merge

REAL_SLEEP = time.sleep
SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")

# A stand-in for worker.py: logs its start and end, shows a step, sleeps, then merges (a file) or dies.
FAKE_WORKER = '''
import json, os, sys, time
sys.path.insert(0, %r)
import common
project, number = sys.argv[1], int(sys.argv[2])
cfg = json.load(open(os.path.join(project, ".loop", "fake.json")))
def log(what):
    with open(os.path.join(project, ".loop", "fake.log"), "a") as f:
        f.write("%%d %%s %%.3f\\n" %% (number, what, time.time()))
log("start")
common.event("step", project, issue=number, step="builder")
if number == cfg.get("stop_at"):
    open(os.path.join(project, ".loop", "stop"), "w").close()
time.sleep(cfg.get("sleep", 0.5))
if number in cfg.get("crash", []):
    log("crash")
    os._exit(3)
open(os.path.join(project, ".loop", "merged", str(number)), "w").close()
log("end")
os.makedirs(os.path.join(project, ".loop", "builds"), exist_ok=True)
json.dump({"last": "#%%d merged: done" %% number}, open(common.build_file(project, number, "result"), "w"))
''' % SCRIPTS


class ParallelTest(Base):
    def setUp(self):
        super().setUp()
        loop.time.sleep.side_effect = REAL_SLEEP
        for name in ("sync_default", "drain"):
            mock.patch.object(loop, name).start()
        mock.patch.object(loop, "BUSY_POLL", 0.05).start()
        self.headroom = mock.patch.object(loop, "headroom", return_value=None).start()
        os.makedirs(os.path.join(self.work, ".loop", "merged"))
        write_settings(os.path.join(self.work, "loop.json"), AGENTS + "Parallel: 3\n")
        self.script = os.path.join(self.work, ".loop", "fake_worker.py")
        with open(self.script, "w") as f:
            f.write(FAKE_WORKER)
        mock.patch.object(loop, "worker_command", lambda p, n, r, previous=0: [sys.executable, self.script, p, str(n)]).start()
        self.issues, self.labels = {}, {}
        self.configure()

    def configure(self, **cfg):
        with open(os.path.join(self.work, ".loop", "fake.json"), "w") as f:
            json.dump(cfg, f)

    def world_of(self, *issues):
        self.issues = {i["number"]: i for i in issues}
        self.labels = {i["number"]: {l["name"] for l in i["labels"]} for i in issues}

    def merged(self):
        return {int(n) for n in os.listdir(os.path.join(self.work, ".loop", "merged"))}

    def fake_gh(self, args, input=None):
        text = " ".join(args)
        self.calls.append(text)
        self.inputs.append((text, input))
        if text.startswith("issue list --state open"):
            rows = [dict(i, labels=[{"name": l} for l in sorted(self.labels[n])])
                    for n, i in self.issues.items() if n not in self.merged()]
            return 0, json.dumps([FACTORY] + rows), ""
        if text.startswith("issue list --state closed"):
            return 0, json.dumps([{"number": n} for n in self.merged()]), ""
        m = re.match(r"issue edit (\d+) --(add|remove)-label (\S+)", text)
        if m:
            (self.labels[int(m[1])].add if m[2] == "add" else self.labels[int(m[1])].discard)(m[3])
        if "--json comments" in text:
            return 0, json.dumps({"comments": []}), ""
        if text.startswith("api") and "permission" in text:
            return 0, json.dumps({"permission": "write"}), ""
        return 0, "[]" if "pr list" in text else "", ""

    def events(self):
        """(issue, what, time) from the fake workers' log, in order."""
        with open(os.path.join(self.work, ".loop", "fake.log")) as f:
            return [(int(a), b, float(c)) for a, b, c in (l.split() for l in f)]

    def at(self, number, what):
        return [t for n, w, t in self.events() if (n, w) == (number, what)][0]

    def run_it(self):
        self.assertEqual(self.run_loop(), 0)

    def test_three_independent_issues_build_at_the_same_time(self):
        self.world_of(issue(2), issue(3), issue(4))
        self.run_it()
        self.assertEqual(self.merged(), {2, 3, 4})
        first_end = min(self.at(n, "end") for n in (2, 3, 4))
        self.assertTrue(all(self.at(n, "start") < first_end for n in (2, 3, 4)))
        self.assertEqual(len(self.writes("--add-label building")), 3)
        self.assertTrue(any("#2, builder, since" in b and "#3, builder, since" in b for b in self.board_inputs()))

    def test_parallel_is_a_ceiling(self):
        write_settings(os.path.join(self.work, "loop.json"), AGENTS + "Parallel: 2\n")
        self.world_of(issue(2), issue(3), issue(4))
        self.run_it()
        self.assertEqual(self.merged(), {2, 3, 4})
        self.assertGreaterEqual(self.at(4, "start"), min(self.at(2, "end"), self.at(3, "end")))

    def test_a_dependant_waits_for_the_merge_of_its_blocker(self):
        self.world_of(issue(2), issue(3, body="Depends on: #2"), issue(4))
        self.run_it()
        self.assertEqual(self.merged(), {2, 3, 4})
        self.assertGreaterEqual(self.at(3, "start"), self.at(2, "end"))
        self.assertLess(self.at(4, "start"), self.at(2, "end"))

    def test_stop_lets_running_builds_finish_and_starts_none(self):
        write_settings(os.path.join(self.work, "loop.json"), AGENTS + "Parallel: 2\n")
        self.configure(stop_at=2, sleep=0.4)
        self.world_of(issue(2), issue(3), issue(4), issue(5))
        self.run_it()
        self.assertEqual(self.merged(), {2, 3})  # both running builds ended; 4 and 5 never started
        self.assertEqual({n for n, w, _ in self.events() if w == "start"}, {2, 3})
        self.assertIn("exiting: stop requested", [c[0][0] for c in self.say.call_args_list])
        self.assertFalse(os.path.exists(os.path.join(self.work, ".loop", "stop")))

    def test_one_crash_leaves_the_others_running_and_is_retried_then_parked(self):
        self.configure(crash=[3], sleep=0.3)
        self.world_of(issue(2), issue(3), issue(4))
        self.run_it()
        self.assertEqual(self.merged(), {2, 4})
        self.assertEqual([w for n, w, _ in self.events() if n == 3], ["start", "crash", "start", "crash"])
        self.assertEqual(len(self.writes("issue comment 3")), 2)  # the retry note, then the park
        self.assertEqual(len(self.writes("issue edit 3 --add-label needs-user")), 1)
        self.assertEqual(self.labels[3], {"needs-user"})
        with open(os.path.join(self.work, ".loop", "events.jsonl")) as f:
            crashes = [e for e in map(json.loads, f) if e["kind"] == "crashed"]
        self.assertEqual([(e["issue"], e["attempt"]) for e in crashes], [(3, 1), (3, 2)])
        self.assertTrue(all("exit code" in e["reason"] for e in crashes))

    def test_a_second_build_waits_while_the_machine_is_busy(self):
        self.headroom.return_value = "load average 9.0 is not below the 8 CPUs"
        self.world_of(issue(2), issue(3), issue(4))
        self.run_it()
        self.assertEqual(self.merged(), {2, 3, 4})
        for a, b in ((2, 3), (3, 4)):  # one at a time
            self.assertGreaterEqual(self.at(b, "start"), self.at(a, "end"))
        said = [c[0][0] for c in self.say.call_args_list if c[0][0].startswith("deferring")]
        self.assertTrue(said and "load average 9.0" in said[0])
        self.assertEqual(len(said), len(set(said)))  # said once per reason, not at every poll

    def test_parallel_one_builds_in_the_loop_process(self):
        write_settings(os.path.join(self.work, "loop.json"), AGENTS)
        self.world_of(issue(2))
        with self.fake_build() as build, mock.patch.object(loop, "worker_command") as command:
            self.run_it()
        self.assertEqual(build.call_count, 1)
        command.assert_not_called()

    def test_a_worker_process_leaves_a_result_the_loop_reads(self):
        cmd = [sys.executable, "-c", (
            "import sys; sys.path.insert(0, %r); import flow, worker; "
            "flow.build = lambda *a: flow.Result('parked', 'a question'); "
            "sys.exit(worker.main(sys.argv[1:]))" % SCRIPTS), self.work, "2", "[]"]
        proc = loop.subprocess.Popen(cmd)
        proc.wait()
        st = loop.new_state()
        st["building"][2] = ("10:00", proc)
        loop.reap(self.work, st)
        self.assertEqual((st["building"], st["last"]), ({}, "#2 parked: a question"))
        self.assertFalse(os.path.exists(common.build_file(self.work, 2, "result")))


    def test_a_running_issue_is_not_picked_from_a_stale_snapshot(self):
        self.world_of(issue(2))
        st = loop.new_state()
        loop.snapshot(st)
        st["building"][2] = ("10:00", None)
        with mock.patch.object(common, "ready_is_trusted", return_value=True):
            self.assertIsNone(loop.pick(st))

    def test_deferral_is_logged_when_the_kind_of_reason_changes(self):
        reasons = iter(["load average 9.0 is not below the 8 CPUs", "load average 9.5 is not below the 8 CPUs",
                        "memory pressure is warning"])
        self.headroom.side_effect = lambda: next(reasons, "memory pressure is warning")
        self.configure(sleep=0.6)
        self.world_of(issue(2), issue(3))
        self.run_it()
        said = [c[0][0] for c in self.say.call_args_list if c[0][0].startswith("deferring")]
        self.assertEqual([("load" in s) for s in said], [True, False])

    def test_a_worker_over_the_cap_is_killed_and_counts_as_a_death(self):
        self.configure(sleep=30)
        self.world_of(issue(2))
        st = loop.new_state()
        proc = loop.subprocess.Popen([sys.executable, self.script, self.work, "2"], start_new_session=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        st["building"][2], st["started"][2] = ("10:00", proc), time.time() - 100
        loop.reap(self.work, st, cap=50)
        self.assertEqual((st["building"], st["deaths"]), ({}, {2: 1}))
        self.assertIsNotNone(proc.poll())

    def test_the_pid_is_recorded_and_a_live_stray_worker_refuses_the_start(self):
        self.configure(sleep=0.3)
        self.world_of(issue(2))
        self.run_it()
        self.assertFalse(os.path.exists(common.build_file(self.work, 2, "pid")))  # cleared when reaped
        stray = loop.subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(stray.kill)
        os.makedirs(os.path.join(self.work, ".loop", "builds"), exist_ok=True)
        with open(common.build_file(self.work, 9, "pid"), "w") as f:
            f.write(str(stray.pid))
        self.calls.clear()
        self.assertEqual(self.run_loop(), 1)
        self.assertIn("refused: build processes of an earlier loop", " ".join(c[0][0] for c in self.say.call_args_list))
        self.assertTrue(os.path.exists(common.build_file(self.work, 9, "pid")))
        self.assertEqual(self.writes("--add-label building"), [])
        self.assertFalse(os.path.exists(os.path.join(self.work, ".loop", "loop.pid")))


class HeadroomTest(unittest.TestCase):
    def test_load_at_the_cpu_count_is_busy(self):
        with mock.patch.object(loop.os, "getloadavg", return_value=(4.0, 1, 1)), \
                mock.patch.object(loop.os, "cpu_count", return_value=4):
            self.assertIn("load average 4.0", loop.headroom())
        with mock.patch.object(loop.os, "getloadavg", return_value=(3.9, 1, 1)), \
                mock.patch.object(loop.os, "cpu_count", return_value=4), mock.patch.object(loop.sys, "platform", "linux"):
            self.assertIsNone(loop.headroom())


def tree(work, name, files=None):
    path = os.path.join(os.path.dirname(work), "trees", name)
    run_git(["fetch", "-q", "origin"], work)
    run_git(["worktree", "add", "-q", "-B", "issue/" + name, path, "origin/loop/main"], work)
    return path


class LandTest(Base):
    """flow.land with a real repository: the merge lock and the catch-up."""
    SETTINGS = {"Loop branch": "loop/main"}

    def setUp(self):
        super().setUp()
        from kit.tests.helpers import copy_repo
        self.work, self.origin = copy_repo(test_loop.TEMPLATE.name, self._tmp.name)
        self.review = "VERDICT: APPROVE\nHEAD: %s\n"

    def commit(self, where, name, text="x\n", push=None):
        with open(os.path.join(where, name), "w") as f:
            f.write(text)
        run_git(["add", "-A"], where)
        run_git(["commit", "-qm", name], where)
        if push:
            run_git(["push", "-q", "origin", push], where)
        return common.git(["rev-parse", "HEAD"], cwd=where)

    def move_loop_branch(self, name):
        other = tree(self.work, "other-" + name)
        self.commit(other, name, push="HEAD:loop/main")

    def land(self, number, t, review=None):
        return flow.land(number, "issue/%s" % number, review or self.review, self.work, t, self.SETTINGS)

    def test_merges_never_overlap(self):
        trees = [tree(self.work, str(n)) for n in (1, 2, 3)]
        for n, t in enumerate(trees, 1):
            self.commit(t, "f%d.txt" % n, push="issue/%d" % n)
        live, worst = [0], [0]

        def merge_one(*args):
            live[0] += 1
            worst[0] = max(worst[0], live[0])
            time.sleep(0.15)
            live[0] -= 1
            return merge.Result(True, False, "merged", "abc")
        with mock.patch.object(merge, "merge", side_effect=merge_one) as m:
            threads = [threading.Thread(target=self.land, args=(n, t)) for n, t in enumerate(trees, 1)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual((m.call_count, worst[0]), (3, 1))

    def test_a_moved_loop_branch_is_caught_up_before_the_merge(self):
        t = tree(self.work, "1")
        old = self.commit(t, "mine.txt", push="issue/1")
        self.move_loop_branch("theirs.txt")
        seen = []
        with mock.patch.object(merge, "merge", side_effect=lambda *a: seen.append(a[2]) or merge.Result(True, False, "m", "c")):
            landed = self.land(1, t, self.review % old)
        self.assertNotEqual(landed.head, old)
        self.assertTrue(os.path.exists(os.path.join(t, "theirs.txt")))
        self.assertEqual(common.git(["rev-parse", "origin/issue/1"], cwd=self.work), landed.head)
        self.assertEqual(seen, ["VERDICT: APPROVE\nHEAD: %s\n" % landed.head])
        self.assertEqual(landed.files, ["mine.txt"])

    def test_an_unmoved_loop_branch_changes_nothing(self):
        t = tree(self.work, "1")
        old = self.commit(t, "mine.txt", push="issue/1")
        with mock.patch.object(merge, "merge", return_value=merge.Result(True, False, "m", "c")):
            landed = self.land(1, t, self.review % old)
        self.assertEqual((landed.head, landed.conflicts), (old, []))

    def test_a_refusal_after_the_loop_branch_moved_catches_up_once_more(self):
        t = tree(self.work, "1")
        old = self.commit(t, "mine.txt", push="issue/1")
        results = [merge.Result(False, False, "the branch moved", None), merge.Result(True, False, "m", "c")]

        def refuse_then_pass(*args):
            if len(results) == 2:
                self.move_loop_branch("later.txt")
            return results.pop(0)
        with mock.patch.object(merge, "merge", side_effect=refuse_then_pass) as m:
            landed = self.land(1, t, self.review % old)
        self.assertEqual(m.call_count, 2)
        self.assertTrue(landed.result.ok)
        self.assertTrue(os.path.exists(os.path.join(t, "later.txt")))

    def test_a_refusal_with_the_loop_branch_still_is_final(self):
        t = tree(self.work, "1")
        old = self.commit(t, "mine.txt", push="issue/1")
        with mock.patch.object(merge, "merge", return_value=merge.Result(False, False, "tests fail", None)) as m:
            landed = self.land(1, t, self.review % old)
        self.assertEqual((m.call_count, landed.result.reason), (1, "tests fail"))

    def test_a_conflicting_catch_up_stays_open_for_the_builder(self):
        t = tree(self.work, "1")
        old = self.commit(t, "same.txt", "mine\n", push="issue/1")
        other = tree(self.work, "other")
        self.commit(other, "same.txt", "theirs\n", push="HEAD:loop/main")
        with mock.patch.object(merge, "merge") as m:
            landed = self.land(1, t, self.review % old)
        m.assert_not_called()
        self.assertEqual(landed.conflicts, ["same.txt"])
        self.assertTrue(common.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=t, check=False))


if __name__ == "__main__":
    unittest.main()
