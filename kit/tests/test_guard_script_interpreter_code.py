import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from kit.tests.test_guard import GUARD, GuardCase


TEST = "uv run python -m pytest"
FILES = TEST + " {files}"
FORMS = ("claude", "codex", "codex-shell")


def inline_commands(words):
    code = "import subprocess; subprocess.run(%r)" % list(words)
    yield "python3 -c " + shlex.quote(code)
    yield "python3 - <<'PY'\n" + code + "\nPY"
    yield "python3 - <<<" + shlex.quote(code)
    node = "require('child_process').spawnSync(%s, %s)" % (
        json.dumps(words[0]), json.dumps(list(words[1:])))
    yield "node -e " + shlex.quote(node)


class TestScriptInterpreterCode(GuardCase):
    def hook(self, command, form, role="builder"):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        env.update(LOOP_AGENT="claude" if form == "claude" else "codex",
                   LOOP_TEST_COMMAND=TEST, LOOP_TEST_FILES_COMMAND=FILES)
        if role:
            env["LOOP_ROLE"] = role
        payload = ["/bin/bash", "-lc", command] if form == "codex-shell" else command
        data = {"tool_name": "Bash", "tool_input": {"command": payload},
                "cwd": self.work}
        result = subprocess.run([sys.executable, GUARD], input=json.dumps(data),
                                capture_output=True, text=True, env=env, timeout=30)
        self.assertNotIn("guard: internal error", result.stderr)
        return result

    def test_inline_interpreter_rules_also_apply_inside_session_scripts(self):
        cases = (("recursive-delete", ("rm", "-rf", "scratch")),
                 ("role-git", ("git", "push", "origin", "feature")),
                 ("role-git", ("git", "merge", "feature")))
        path = Path(self.work, "src/session-script.sh")
        for rule, words in cases:
            for inline in inline_commands(words):
                path.write_text("#!/bin/sh\n" + inline + "\n")
                for form in FORMS:
                    with self.subTest(rule=rule, inline=inline, form=form):
                        direct = self.hook(inline, form)
                        self.refused(direct, "rule: " + rule)
                        scripted = self.hook("bash src/session-script.sh", form)
                        self.refused(scripted, "rule: " + rule)
                        self.assertIn(path.name, scripted.stderr)

    def test_safe_and_targeted_inline_code_in_scripts_remains_allowed(self):
        path = Path(self.work, "src/safe-script.sh")
        for words in (("git", "status"), (*shlex.split(TEST), "tests/test_app.py")):
            for inline in inline_commands(words):
                path.write_text("#!/bin/sh\n" + inline + "\n")
                for form in FORMS:
                    with self.subTest(inline=inline, form=form):
                        self.allowed(self.hook("bash src/safe-script.sh", form))

    def test_inline_code_in_a_script_is_not_read_without_a_role(self):
        path = Path(self.work, "src/no-role-script.sh")
        path.write_text("#!/bin/sh\n" + next(inline_commands(("rm", "-rf", "scratch"))) + "\n")
        for form in FORMS:
            with self.subTest(form=form):
                self.allowed(self.hook("bash src/no-role-script.sh", form, role=None))
