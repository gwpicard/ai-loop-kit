"""A Codex builder's zsh writes here-document files under TMPDIR, not /tmp."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

try:
    import agents
except ImportError as error:
    if error.name != "agents" and not str(error.name).startswith("agents."):
        raise
    agents = None

try:
    import walkaway
except ImportError as error:
    if error.name != "walkaway" and not str(error.name).startswith("walkaway."):
        raise
    walkaway = None

REAL_RUN = subprocess.run


def git(folder, *args):
    REAL_RUN(["git", *args], cwd=folder, check=True, capture_output=True)


def make_repo(folder):
    (folder / "AGENTS.md").write_text("## The loop\n\nTest command: true\n")
    git(folder, "init", "--quiet")
    git(folder, "add", "AGENTS.md")
    git(folder, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "x")


def session_env(test, backend, role="builder"):
    """Start a session against a fake process launcher; return the environment it got."""
    test.assertIsNotNone(agents, "agents must exist")
    test.assertTrue(hasattr(agents, "start_session"), "agents.start_session must exist")
    seen = {}

    def fake_popen(args, **kwargs):
        seen["env"] = kwargs["env"]
        return object()

    fake = SimpleNamespace(Popen=fake_popen, PIPE=-1, STDOUT=-2)
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp).resolve()
        make_repo(folder)
        environ = {key: value for key, value in os.environ.items() if key != "TMPPREFIX"}
        if backend == "codex":
            environ["TMPPREFIX"] = "/tmp/zsh"  # a leftover from the person's shell
        with patch.dict(os.environ, environ, clear=True), patch.object(agents, "subprocess", fake):
            agents.start_session(backend, "do it", folder, role=role)
    return seen["env"]


class CodexTmpprefixTest(unittest.TestCase):
    def test_D1_a_codex_builder_gets_tmpprefix_inside_its_tmpdir(self):
        env = session_env(self, "codex")
        tmpdir = Path(env["TMPDIR"])
        self.assertEqual(tmpdir.parts[-2:], (".loop", "tmp"))
        self.assertEqual(env.get("TMPPREFIX"), str(tmpdir / "zsh"))

    def test_D2_the_sandbox_test_command_gets_tmpprefix_inside_its_tmpdir(self):
        self.assertIsNotNone(walkaway, "walkaway must exist")
        self.assertTrue(hasattr(walkaway, "codex_sandbox_test"),
                        "walkaway.codex_sandbox_test must exist")
        seen = {}

        def fake_run(args, **kwargs):
            seen["env"] = kwargs["env"]
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        fake = SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve() / "repo"
            root.mkdir()
            make_repo(root)
            environ = {**os.environ, "TMPPREFIX": "/tmp/zsh"}
            with patch.dict(os.environ, environ, clear=True), \
                 patch.object(walkaway, "main_ref", return_value="HEAD"), \
                 patch.object(walkaway, "subprocess", fake):
                ok, detail = walkaway.codex_sandbox_test(root)
        self.assertTrue(ok, detail)
        env = seen["env"]
        tmpdir = Path(env["TMPDIR"])
        self.assertEqual(tmpdir.parts[-2:], (".loop", "tmp"))
        self.assertEqual(env.get("TMPPREFIX"), str(tmpdir / "zsh"))

    def test_D3_a_claude_session_has_no_tmpprefix(self):
        env = session_env(self, "claude")
        self.assertNotIn("TMPPREFIX", env)

    def test_D3_a_codex_session_without_a_write_boundary_keeps_no_kit_tmpprefix(self):
        env = session_env(self, "codex", role="judge-writer")
        self.assertNotEqual(Path(env.get("TMPPREFIX", "")).parts[-3:-1], (".loop", "tmp"))


if __name__ == "__main__":
    unittest.main()
