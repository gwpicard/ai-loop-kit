"""A fake `codex` that also answers the inspection commands the start check may run.

It extends fake_codex. `codex --version` prints a version. `codex features list`
prints one `name  stage  enabled` line per feature, leaving out `hooks` when
the environment variable FAKE_CODEX_NO_HOOKS is set. `codex exec --help` and
`codex exec resume --help` list the flags the kit passes, leaving out the one
named in FAKE_CODEX_NO_FLAG. None of these counts as a session call.
"""
import os
import shutil
import sys

from kit.tests.fake_codex import FAKE_CODEX, FakeCodexGh
from kit.tests.helpers import write_exe

FLAGS = ("-s", "-m", "-c", "--json", "-o", "--dangerously-bypass-hook-trust")

PROLOGUE = '''if argv[:1] == ["--version"]:
    print("codex-cli 9.9.9")
    sys.exit(0)
if argv[:2] == ["features", "list"]:
    print("shell_tool  stable  true")
    if not os.environ.get("FAKE_CODEX_NO_HOOKS"):
        print("hooks  stable  true")
    sys.exit(0)
if "--help" in argv:
    gone = os.environ.get("FAKE_CODEX_NO_FLAG", "")
    print("Usage: codex exec [OPTIONS]")
    for flag in %r:
        if flag != gone:
            print("  " + flag)
    sys.exit(0)
'''

FAKE = FAKE_CODEX.replace("argv = sys.argv[1:]\n", "argv = sys.argv[1:]\n" + PROLOGUE % (FLAGS,), 1)
# a real session names its thread before it fails, so a resume after a usage limit has one to resume
FAKE = FAKE.replace('if step.get("error"):\n', 'if step.get("error"):\n'
                    '    print(json.dumps({"type": "thread.started", "thread_id": step.get("thread", "thread-%d" % n)}))\n', 1)
TOOLS = ("git", "sh", "dirname", "rmdir", "rm", "mkdir", "ls", "env", "ps", "sleep", "uname", "cat", "head",
         "tail", "tr", "awk", "sed", "date", "kill", "mktemp", "pwd", "basename", "true", "false", "test", "seq",
         "grep", "sort", "wc", "cp", "mv", "touch", "vm_stat", "sysctl", "nproc", "uptime", "pgrep", "tee")


class FakeCodexCheck(FakeCodexGh):
    def setUp(self):
        super().setUp()
        write_exe(os.path.join(self.tmp, "bin", "codex"), FAKE)
        for name in ("FAKE_CODEX_NO_HOOKS", "FAKE_CODEX_NO_FLAG"):
            os.environ.pop(name, None)

    def without_codex(self):
        """Hide every `codex` on the machine: PATH holds only the fakes and the tools the kit needs."""
        tools = os.path.join(self.tmp, "tools")
        os.makedirs(tools, exist_ok=True)
        found = [("python3", sys.executable)] + [(n, shutil.which(n, path=os.defpath + ":/usr/sbin:/sbin")) for n in TOOLS]
        for name, path in found:
            if path and not os.path.exists(os.path.join(tools, name)):
                os.symlink(path, os.path.join(tools, name))
        os.remove(os.path.join(self.tmp, "bin", "codex"))
        os.environ["PATH"] = os.pathsep.join((os.path.join(self.tmp, "bin"), tools))
