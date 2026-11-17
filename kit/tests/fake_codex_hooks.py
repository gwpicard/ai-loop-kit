"""A fake `codex` that honours the hook configuration it is given.

It extends fake_codex: it reads every `-c hooks...` argument (TOML or JSON
text), runs the PreToolUse commands whose matcher fits each sample payload in
the step's "tool_calls" (recording matched and exit code in <scenario>.hooks),
and, after the step, runs the Stop commands as Codex does: a reply
{"decision": "block", "reason": text} starts a further turn whose prompt is
the reason and which uses the next step. It gives up after six turns.
"""
import json
import os

from kit.tests.fake_codex import FAKE_CODEX, FakeCodexGh
from kit.tests.helpers import write_exe

HOOKS = r'''
import re
def segments(event):
    found = []
    for i, a in enumerate(argv):
        if a != "-c" or i + 1 >= len(argv) or not argv[i + 1].startswith("hooks"):
            continue
        s = argv[i + 1]
        marks = sorted((s.find(e), e) for e in ("PreToolUse", "Stop") if e in s)
        for j, (pos, e) in enumerate(marks):
            if e == event:
                found.append(s[pos:marks[j + 1][0] if j + 1 < len(marks) else len(s)])
    return found
def entries(event):
    out = []
    for seg in segments(event):
        matcher = ".*"
        for m in re.finditer(r"(matcher|command)\"?\s*[=:]\s*(\"(?:[^\"\\]|\\.)*\"|'[^']*')", seg):
            text = json.loads(m.group(2)) if m.group(2)[0] == '"' else m.group(2)[1:-1]
            if m.group(1) == "matcher":
                matcher = ".*" if text == "*" else text
            else:
                out.append((matcher, text))
    return out
def fire(event, payload, tool=None):
    results = []
    for matcher, command in entries(event):
        if tool is not None and not re.fullmatch(matcher, tool):
            continue
        p = subprocess.run(command, shell=True, input=json.dumps(payload), capture_output=True, text=True)
        results.append((p.returncode, p.stdout))
    return results
for call in step.get("tool_calls", []):
    results = fire("PreToolUse", dict(call, cwd=os.getcwd(), session_id="pre", hook_event_name="PreToolUse"),
                   call["tool_name"])
    with open(path + ".hooks", "a") as f:
        f.write(json.dumps({"tool_name": call["tool_name"], "matched": bool(results),
                            "code": 2 if any(r[0] == 2 for r in results) else 0}) + "\n")
turns = 0
while turns < 6:
    block = None
    for code, stdout in fire("Stop", {"session_id": thread, "cwd": os.getcwd(), "hook_event_name": "Stop",
                                      "stop_hook_active": turns > 0}):
        try:
            data = json.loads(stdout)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("decision") == "block":
            block = str(data.get("reason") or "")
    if block is None:
        break
    turns += 1
    state = json.load(open(path + ".state"))
    n = state["n"]
    state["n"] = n + 1
    json.dump(state, open(path + ".state", "w"))
    with open(path + ".calls", "a") as f:
        f.write(json.dumps({"argv": argv, "env": env, "prompt": block, "cwd": os.getcwd(), "via": "hook"}) + "\n")
    step = steps[min(n, len(steps) - 1)] if steps else {}
    for name, text in step.get("files", {}).items():
        os.makedirs(os.path.dirname(os.path.abspath(name)), exist_ok=True)
        open(name, "w").write(text)
    if step.get("files"):
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "codex"], capture_output=True)
    reply = step.get("reply", "ok")
    print(json.dumps({"type": "item.completed", "item": {"id": "item_%d" % turns, "type": "agent_message", "text": reply}}))
    if "-o" in argv:
        open(argv[argv.index("-o") + 1], "w").write(reply)
'''


class FakeCodexHooks(FakeCodexGh):
    def setUp(self):
        super().setUp()
        write_exe(os.path.join(self.tmp, "bin", "codex"), FAKE_CODEX + HOOKS)

    def hook_results(self):
        path = self.codex_path + ".hooks"
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]
