"""`loop pause` freezes the loop and everything it started; `loop resume` continues it.

A real loop runs on a fake gh and a fake Claude whose builder session starts a slow
Test command of its own. The tests pause through bin/loop and read states with ps.
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import HERE, copy_repo, make_repo, run_git, write_exe

ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "kit", "scripts")
LOOP = os.path.join(ROOT, "kit", "bin", "loop")
AGENTS = ("## Loop\nCheck command: test ! -f BAD\nTest command: seq 1 99; { test ! -f FAIL && "
          "{ test ! -f tests/test_new.py || test -f app.py; }; } || { echo AssertionError; false; }\n"
          "Loop branch: loop/main\nMax rounds: 2\n")
APPROVE = {"reply": "All good.\n\nVERDICT: APPROVE\nHEAD: {HEAD}\n\n1. none"}
WRITER = {"files": {"tests/test_new.py": "x\n"}, "reply": "Done.\nTESTS:\ntests/test_new.py"}
SLOW = "sleep 6.37"  # the slow Test command the fake builder session runs

# A supervisor with short polls and no end-of-loop work: the pause is what is judged.
RUNNER = ("import sys; sys.path.insert(0, %r); import loop; loop.BUSY_POLL = 0.3; loop.POLL = 10; "
          "loop.drain = lambda *a, **k: None; loop.sync_default = lambda *a, **k: False; "
          "sys.exit(loop.main(['run']))") % SCRIPTS

FAKE_GH = '''#!PYTHON
import json, os, sys
sys.path.insert(0, %r)
import setup
d = os.environ["FAKE_GH2"]
args = sys.argv[1:]
text = " ".join(args)
stdin = sys.stdin.read() if "--body-file" in args and "-" in args else ""
with open(os.path.join(d, "calls.jsonl"), "a") as f:
    f.write(json.dumps({"args": args, "input": stdin}) + "\\n")
def load(name, default):
    path = os.path.join(d, name)
    return json.load(open(path)) if os.path.exists(path) else default
def save(name, value):
    json.dump(value, open(os.path.join(d, name), "w"))
state = load("state.json", {"labels": ["ready"], "closed": False})
board = open(os.path.join(d, "board.txt")).read() if os.path.exists(os.path.join(d, "board.txt")) else ""
if text.startswith("label list"):
    print(json.dumps([{"name": n} for n in setup.LABELS]))
elif text.startswith("issue list --state open"):
    if "--search" in args:
        print(json.dumps([{"number": 1, "title": "Factory"}]))
    else:
        rows = [{"number": 1, "title": "Factory", "body": board, "labels": [], "updatedAt": "t", "milestone": None}]
        if not state["closed"]:
            rows.append({"number": 7, "title": "Piece 7", "body": "Do it.", "updatedAt": "t", "milestone": None,
                         "labels": [{"name": n} for n in state["labels"]]})
        print(json.dumps(rows))
elif text.startswith("issue list --state closed"):
    print(json.dumps([{"number": 7}] if state["closed"] else []))
elif text.startswith("issue list"):
    print("[]")
elif text.startswith("issue edit 1 ") and "--body-file" in args:
    open(os.path.join(d, "board.txt"), "w").write(stdin)
elif text.startswith("issue edit 7"):
    for i, a in enumerate(args):
        if a == "--add-label" and args[i + 1] not in state["labels"]:
            state["labels"].append(args[i + 1])
        if a == "--remove-label" and args[i + 1] in state["labels"]:
            state["labels"].remove(args[i + 1])
    save("state.json", state)
elif text.startswith("issue close 7"):
    state["closed"] = True
    save("state.json", state)
elif text.startswith("issue view 7"):
    print(json.dumps({"title": "Piece 7", "body": "Do it.", "comments": []}))
elif "timeline" in text:
    print(json.dumps([{"event": "labeled", "label": {"name": "ready"}, "actor": {"login": "me"}}]))
elif "permission" in text:
    print(json.dumps({"permission": "write"}))
elif text.startswith("pr list") and "--head" in args:  # a pull request that is already merged
    import subprocess
    sha = subprocess.run(["git", "rev-parse", "--verify", "origin/" + args[args.index("--head") + 1]],
                         capture_output=True, text=True).stdout.strip()
    print(json.dumps([{"number": 9, "state": "MERGED", "headRefOid": sha, "mergeCommit": {"oid": "abc"}}] if sha else []))
elif text.startswith("pr list") or "milestones" in text:
    print("[]")
''' % SCRIPTS

# Wraps the fake claude: a builder session first runs the slow Test command in a session of its own,
# as a Stop hook does, then answers as the plain fake does.
WRAPPER = '''#!PYTHON
import os, subprocess, sys
if os.environ.get("LOOP_ROLE") == "builder":
    marker = os.path.join(os.environ["LOOP_PROJECT"], ".loop", "slow-running")
    subprocess.Popen(["sh", "-c", "touch " + marker + "; %s"], start_new_session=True).wait()
os.execv(%%r, [%%r] + sys.argv[1:])
''' % SLOW


def table():
    """{pid: (ppid, state, command)} for every process."""
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,stat=,command="], capture_output=True, text=True).stdout
    rows = {}
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0].isdigit():
            rows[int(parts[0])] = (int(parts[1]), parts[2], parts[3])
    return rows


def tree(root):
    """{pid: (state, command)} of root and its descendants, zombies left out."""
    rows, found, todo = table(), {}, [root]
    while todo:
        pid = todo.pop()
        if pid in rows and pid not in found and not rows[pid][1].startswith("Z"):
            found[pid] = rows[pid][1:]
            todo += [p for p, r in rows.items() if r[0] == pid]
    return found


def states(pids):
    rows = table()
    return {p: rows[p][1] for p in pids if p in rows}


class PauseBase(FakeClaudeGh):
    PARALLEL = 1

    def setUp(self):
        super().setUp()
        self.addCleanup(self.cleanup_processes)
        template = tempfile.TemporaryDirectory()
        self.addCleanup(template.cleanup)
        work, _ = make_repo(template.name, {"AGENTS.md": AGENTS})
        run_git(["push", "origin", "main:loop/main"], work)
        self.work, self.origin = copy_repo(template.name, self.tmp)
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(AGENTS + "Parallel: %d\n" % self.PARALLEL)
        self.bin = os.path.join(self.tmp, "bin")
        self.gh_dir = os.path.join(self.tmp, "gh2")
        os.mkdir(self.gh_dir)
        os.environ["FAKE_GH2"] = self.gh_dir
        write_exe(os.path.join(self.bin, "gh"), FAKE_GH)
        plain = os.path.join(self.bin, "claude-plain")
        os.rename(os.path.join(self.bin, "claude"), plain)
        write_exe(os.path.join(self.bin, "claude"), WRAPPER % (plain, plain))
        self.claude({"test-writer": [WRITER], "builder": [{"files": {"app.py": "1\n"}}], "reviewer": [APPROVE]})
        self.supervisors = []

    def cleanup_processes(self):
        for pid in self.supervisors:
            for p in tree(pid):
                for sig in (signal.SIGCONT, signal.SIGKILL):
                    try:
                        os.kill(p, sig)
                    except OSError:
                        pass

    def loop_cmd(self, *args, **kw):
        return subprocess.run([LOOP, *args], cwd=self.work, capture_output=True, text=True, timeout=60, **kw)

    def start(self):
        out = open(os.path.join(self.work, ".loop", "loop.out"), "a") if os.path.isdir(
            os.path.join(self.work, ".loop")) else None
        if out is None:
            os.makedirs(os.path.join(self.work, ".loop"))
            out = open(os.path.join(self.work, ".loop", "loop.out"), "a")
        proc = subprocess.Popen([sys.executable, "-c", RUNNER], cwd=self.work, stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=True)
        self.supervisors.append(proc.pid)
        self.proc = proc
        return proc

    def wait_for(self, what, check, seconds=60):
        end = time.time() + seconds
        while time.time() < end:
            if check():
                return
            time.sleep(0.1)
        logs = os.path.join(self.work, ".loop", "logs")
        tail = "".join("\n--- %s\n%s" % (n, open(os.path.join(logs, n)).read()[-600:])
                       for n in sorted(os.listdir(logs))) if os.path.isdir(logs) else ""
        self.fail("timed out waiting for %s\n%s%s" % (what, "\n".join(self.out_lines()[-15:]), tail))

    def slow_running(self):
        return os.path.exists(os.path.join(self.work, ".loop", "slow-running"))

    def roles(self):
        return [c["role"] for c in self.claude_calls()]

    def board(self):
        path = os.path.join(self.gh_dir, "board.txt")
        return open(path).read() if os.path.exists(path) else ""

    def out_lines(self):
        with open(os.path.join(self.work, ".loop", "loop.out")) as f:
            return f.read().splitlines()

    def finish(self):
        """Let the build reach its review, ask the loop to stop and return what the run did."""
        self.wait_for("the reviewer", lambda: "reviewer" in self.roles(), 90)
        self.assertEqual(self.loop_cmd("stop").returncode, 0)
        self.assertEqual(self.proc.wait(timeout=120), 0)
        return {"roles": self.roles()}


class PauseTest(PauseBase):
    def check_pause_and_resume(self):
        self.start()
        self.wait_for("the slow Test command", self.slow_running)
        root = int(open(os.path.join(self.work, ".loop", "loop.pid")).read())
        self.assertEqual(root, self.proc.pid)

        before = states(tree(root))
        self.assertFalse(any(s.startswith("T") for s in before.values()))
        refused = self.loop_cmd("resume")  # not paused
        self.assertEqual((refused.returncode, refused.stdout.startswith("refused:"), len(refused.stdout.splitlines())),
                         (1, True, 1), refused.stdout + refused.stderr)
        self.assertEqual(states(before), before)

        paused = self.loop_cmd("pause")
        self.assertEqual(paused.returncode, 0, paused.stdout + paused.stderr)
        frozen = tree(root)
        self.assertTrue(frozen)
        kinds = {"supervisor": root}
        for name, needle in (("session", os.path.join(self.bin, "claude")), ("test command", SLOW)):
            kinds[name] = [p for p, (_, c) in frozen.items() if needle in c]
            self.assertTrue(kinds[name], "no %s in the tree: %s" % (name, frozen))
        if self.PARALLEL > 1:
            kinds["worker"] = [p for p, (_, c) in frozen.items() if "worker.py" in c]
            self.assertTrue(kinds["worker"], "no worker in the tree: %s" % frozen)
        for pid, (state, command) in frozen.items():
            self.assertTrue(state.startswith("T"), "%d is %s: %s" % (pid, state, command))
        numbers = re.findall(r"\d+", paused.stdout.splitlines()[0])
        self.assertEqual(int(numbers[0]), len(frozen), paused.stdout)

        # nothing moves while frozen, and the board and loop.out say so
        calls_then = self.roles()
        time.sleep(1)
        self.assertEqual(self.roles(), calls_then)
        line = re.compile(r"Paused since \d\d:\d\d\. Resume with loop resume\.")
        self.assertRegex(self.board().splitlines()[0], "^" + line.pattern + "$")
        self.assertRegex(self.out_lines()[-1], "^" + line.pattern + "$")

        again = self.loop_cmd("pause")
        self.assertEqual((again.returncode, again.stdout.startswith("refused:"), len(again.stdout.splitlines())),
                         (1, True, 1), again.stdout + again.stderr)
        self.assertEqual({p: s[0] for p, s in states(frozen).items()}, {p: "T" for p in frozen})

        resumed = self.loop_cmd("resume")
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertEqual([p for p, s in states(frozen).items() if s.startswith("T")], [])
        self.wait_for("the board to lose the pause line", lambda: "Paused since" not in self.board(), 30)

        # the result an unpaused build reaches: three sessions, no crash, the issue merged and closed
        done = self.finish()
        self.assertEqual(done["roles"], ["test-writer", "builder", "reviewer"])
        self.assertFalse(any(l.startswith("crash") for l in self.out_lines()), self.out_lines())
        self.assertTrue(json.load(open(os.path.join(self.gh_dir, "state.json")))["closed"])
        self.assertEqual(sum("Paused since" in l for l in self.out_lines()), 1)

    def test_parallel_1_pause_and_resume(self):
        self.check_pause_and_resume()


class PauseParallelTest(PauseTest):
    PARALLEL = 2

    def test_parallel_1_pause_and_resume(self):
        raise unittest.SkipTest("covered by PauseTest")

    def test_parallel_2_pause_and_resume(self):
        self.check_pause_and_resume()


class PauseRefusalTest(PauseBase):
    def refusal(self, word):
        p = self.loop_cmd(word)
        self.assertEqual((p.returncode, p.stdout.startswith("refused:"), len(p.stdout.splitlines())), (1, True, 1),
                         p.stdout + p.stderr)

    def test_pause_and_resume_with_no_live_loop_are_refused(self):
        self.refusal("pause")
        self.refusal("resume")
        os.makedirs(os.path.join(self.work, ".loop"))
        dead = subprocess.Popen(["true"])
        dead.wait()
        with open(os.path.join(self.work, ".loop", "loop.pid"), "w") as f:
            f.write(str(dead.pid))
        self.refusal("pause")
        self.refusal("resume")

    def test_stop_on_a_paused_loop_resumes_it_and_stops_it(self):
        self.start()
        self.wait_for("the slow Test command", self.slow_running)
        root = self.proc.pid
        self.assertEqual(self.loop_cmd("pause").returncode, 0)
        frozen = tree(root)
        stopped = self.loop_cmd("stop")
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertEqual([p for p, s in states(frozen).items() if s.startswith("T")], [])
        self.assertEqual(self.proc.wait(timeout=120), 0)
        self.assertIn("exiting: stop requested", self.out_lines())
        self.assertNotIn("Paused since", self.board())
        self.assertFalse(os.path.exists(os.path.join(self.work, ".loop", "loop.pid")))


class PauseSkillTest(unittest.TestCase):
    def test_the_loop_skill_names_pause_and_resume_and_their_limits(self):
        with open(os.path.join(ROOT, "kit", "skills", "loop", "SKILL.md"), encoding="utf-8") as f:
            text = " ".join(f.read().split()).lower()
        self.assertIn("loop pause", text)
        self.assertIn("loop resume", text)
        self.assertRegex(text, r"processor[^.]*stops? at once")
        self.assertRegex(text, r"memory[^.]*not (freed|released)[^.]*at once")
        self.assertRegex(text, r"session[^.]*may fail once[^.]*resum")
        self.assertRegex(text, r"build crash")


if __name__ == "__main__":
    unittest.main()
