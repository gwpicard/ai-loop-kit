"""A fake `claude` on PATH, driven by a JSON scenario: {role: [step, ...]}.

A step is {"files": {path: text}, "remove": [paths], "reply": text (with
{HEAD} replaced by the git head), "session_id", "limit": message, "error":
text, "crash": true, "sleep": seconds, "spawn": true (leave a `sleep` running
holding the session's stdout, its pid in <scenario>.pid), "passed": true (record
the head as the Stop hook would, with the tail "all passed"), "hooked": true
(leave a `sleep` in a group of its own, listed in LOOP_GROUPS as a Stop hook's
command is), "stop_hook": path (run the real Stop hook)}. The nth call of a role uses step n;
the last step repeats. Files and removals are committed.
"""
import json
import os

from kit.tests.helpers import FakeGh, write_exe

FAKE_CLAUDE = '''#!PYTHON
import json, os, subprocess, sys, time
path = os.environ["FAKE_CLAUDE_SCENARIO"]
role = os.environ.get("LOOP_ROLE", "")
prompt = sys.stdin.read()
state = json.load(open(path + ".state")) if os.path.exists(path + ".state") else {}
n = state.get(role, 0)
state[role] = n + 1
json.dump(state, open(path + ".state", "w"))
env = {k: v for k, v in os.environ.items() if k.startswith("LOOP_")}
with open(path + ".calls", "a") as f:
    f.write(json.dumps({"role": role, "argv": sys.argv[1:], "env": env,
                        "prompt": prompt, "cwd": os.getcwd()}) + "\\n")
steps = json.load(open(path)).get(role, [])
step = steps[min(n, len(steps) - 1)] if steps else {}
time.sleep(step.get("sleep", 0))
if step.get("crash"):
    sys.stderr.write("claude exploded\\n")
    sys.exit(1)
if step.get("spawn"):  # a child that outlives the session, in its process group
    open(path + ".pid", "w").write(str(subprocess.Popen(["sleep", "300"]).pid))
if step.get("hooked"):
    child = subprocess.Popen(["sleep", "300"], start_new_session=True)
    open(path + ".pid", "w").write(str(child.pid))
    open(os.environ["LOOP_GROUPS"], "a").write(str(child.pid) + "\\n")
for name, text in step.get("files", {}).items():
    os.makedirs(os.path.dirname(os.path.abspath(name)), exist_ok=True)
    open(name, "w").write(text)
for name in step.get("remove", []):
    os.remove(name)
if step.get("files") or step.get("remove"):
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", role], capture_output=True)
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
sid = step.get("session_id", "sess-" + role)
if step.get("stop_hook"):
    stopped = subprocess.run([sys.executable, step["stop_hook"]], input=json.dumps({"session_id": sid}),
                             capture_output=True, text=True, check=True)
    assert not stopped.stdout.strip(), stopped.stdout
if step.get("passed"):
    folder = os.path.join(os.environ["LOOP_PROJECT"], ".loop")
    os.makedirs(folder, exist_ok=True)
    open(os.path.join(folder, "passed-" + sid), "w").write(head + "\\nall passed\\n")
reply = step.get("limit") or step.get("error") or step.get("reply", "ok")
print(json.dumps({"type": "result", "is_error": bool(step.get("limit") or step.get("error")),
                  "result": reply.replace("{HEAD}", head),
                  "session_id": sid}))
sys.exit(1 if step.get("limit") else 0)
'''


class FakeClaudeGh(FakeGh):
    def setUp(self):
        super().setUp()
        script = os.path.join(self.tmp, "bin", "claude")
        write_exe(script, FAKE_CLAUDE)
        self.claude_path = os.path.join(self.tmp, "claude.json")
        os.environ["FAKE_CLAUDE_SCENARIO"] = self.claude_path
        self.claude({})

    def claude(self, scenario):
        for ext in (".calls", ".state"):
            if os.path.exists(self.claude_path + ext):
                os.remove(self.claude_path + ext)
        with open(self.claude_path, "w") as f:
            json.dump(scenario, f)

    def claude_calls(self):
        path = self.claude_path + ".calls"
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]
