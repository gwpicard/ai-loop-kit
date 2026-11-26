"""A fake `codex` on PATH, driven by a JSON scenario: {"steps": [step, ...]}.

A step is {"reply": text, "thread": session id, "error": text, "files": {path:
text} (committed)}. The nth call uses step n; the last step repeats. A new
session reports `thread`, default "thread-<n>"; `exec resume <id>` reports <id>.
It writes JSON events on stdout as `codex exec --json` does, and the reply to
the file after -o when given. Each call is recorded with its argv, standard
input, working directory and every LOOP_ variable.
"""
import json
import os

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import write_exe

FAKE_CODEX = '''#!PYTHON
import json, os, subprocess, sys
path = os.environ["FAKE_CODEX_SCENARIO"]
argv = sys.argv[1:]
prompt = sys.stdin.read()
state = json.load(open(path + ".state")) if os.path.exists(path + ".state") else {"n": 0}
n = state["n"]
state["n"] = n + 1
json.dump(state, open(path + ".state", "w"))
env = {k: v for k, v in os.environ.items() if k.startswith("LOOP_") or k in ("TMPDIR", "TMP", "TEMP")}
with open(path + ".calls", "a") as f:
    f.write(json.dumps({"argv": argv, "env": env, "prompt": prompt, "cwd": os.getcwd()}) + "\\n")
steps = json.load(open(path)).get("steps", [])
step = steps[min(n, len(steps) - 1)] if steps else {}
for name, text in step.get("files", {}).items():
    os.makedirs(os.path.dirname(os.path.abspath(name)), exist_ok=True)
    open(name, "w").write(text)
if step.get("files"):
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", "codex"], capture_output=True)
if step.get("error"):
    print(json.dumps({"type": "error", "message": step["error"]}))
    sys.exit(1)
i = argv.index("resume") if "resume" in argv else -1
thread = argv[i + 1] if i >= 0 else step.get("thread", "thread-%d" % n)
reply = step.get("reply", "ok")
events = [{"type": "thread.started", "thread_id": thread}, {"type": "turn.started"},
          {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": reply}}]
events += step.get("events", [{"type": "turn.completed", "usage": {}}])
for event in events:
    print(json.dumps(event))
if "-o" in argv:
    open(argv[argv.index("-o") + 1], "w").write(reply)
'''


class FakeCodexGh(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        os.environ.pop("LOOP_CACHE_DIR", None)
        write_exe(os.path.join(self.tmp, "bin", "codex"), FAKE_CODEX)
        self.codex_path = os.path.join(self.tmp, "codex.json")
        os.environ["FAKE_CODEX_SCENARIO"] = self.codex_path
        self.codex([])

    def codex(self, steps):
        for ext in (".calls", ".state"):
            if os.path.exists(self.codex_path + ext):
                os.remove(self.codex_path + ext)
        with open(self.codex_path, "w") as f:
            json.dump({"steps": steps}, f)

    def codex_calls(self):
        path = self.codex_path + ".calls"
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]
