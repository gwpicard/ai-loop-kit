"""The start check accepts the help text codex-cli 0.166.0 prints: short flags followed by a comma."""
import os
import subprocess
import unittest
from pathlib import Path

from kit.tests import test_setup
from kit.tests.fake_codex_check import FAKE, FLAGS, FakeCodexCheck
from kit.tests.helpers import make_repo, write_exe

KIT = Path(__file__).resolve().parents[1]
LOOP = "## Loop\nTest command: true\nLoop branch: loop/main\n"

# one help line per flag, as the real codex prints them; words that only contain a flag stay in
LINES = {
    "-c": "  -c, --config <key=value>",
    "-m": "  -m, --model <MODEL>",
    "-s": "  -s, --sandbox <SANDBOX_MODE>",
    "-o": "  -o, --output-last-message <FILE>",
    "--json": "      --json",
    "--dangerously-bypass-hook-trust": "      --dangerously-bypass-hook-trust",
}
LEFTOVERS = ("      --oss", "      --no-color", "      --jsonl", "          Pick -x or the like, not a-m or a-s.")
COMMA_FAKE = FAKE.replace('print("  " + flag)', 'print(%r[flag])' % (LINES,), 1).replace(
    '    sys.exit(0)\n', '    for extra in %r:\n        print(extra)\n    sys.exit(0)\n' % (LEFTOVERS,), 1)


class CommaCodex(FakeCodexCheck):
    def setUp(self):
        super().setUp()
        write_exe(os.path.join(self.tmp, "bin", "codex"), COMMA_FAKE)


class StartTest(CommaCodex):
    def start(self, env=None):
        self.work, _ = make_repo(self.tmp, {"AGENTS.md": LOOP + "Builder: codex gpt-6\nTest writer: codex gpt-6\n"})
        return subprocess.run([str(KIT / "bin" / "loop"), "run"], cwd=self.work, capture_output=True, text=True,
                              timeout=120, env=dict(os.environ, **(env or {})))

    def test_the_comma_form_is_not_refused_for_a_missing_flag(self):
        r = self.start()
        self.assertNotIn("has no", r.stdout + r.stderr)
        self.assertNotIn("codex", r.stdout + r.stderr)  # the run may still refuse for the missing loop branch

    def test_each_flag_left_out_is_refused_by_name(self):
        for flag in FLAGS:
            with self.subTest(flag=flag):
                r = self.start({"FAKE_CODEX_NO_FLAG": flag})
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("refused", r.stdout)
                self.assertIn("has no %s flag" % flag, r.stdout)


class SetupTest(test_setup.SetupTest, CommaCodex):
    def test_setup_accepts_the_comma_form(self):
        self.repo(LOOP + "Builder: codex gpt-6\n")
        self.fresh()
        code, text = test_setup.run(self.work)
        self.assertEqual(code, 0, text)


for _name in dir(SetupTest):
    if _name.startswith("test_") and _name not in vars(SetupTest):
        setattr(SetupTest, _name, None)  # keep the base fixtures, drop the tests they bring

if __name__ == "__main__":
    unittest.main()
