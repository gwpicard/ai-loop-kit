"""The login rule: the kit starts only the unmodified claude and codex binaries.

Piece D-items: D1 the design says so, D2 and D3 the house rules refuse an
Agent SDK or API client, D4 the real repository still passes.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "tests/house-rules.sh"
SDK = "anth" + "ropic"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


def check(files):
    """Run the house rules over a throwaway repository holding `files`."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        git(repo, "init", "-q")
        for name, text in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        git(repo, "add", "-A")
        done = subprocess.run(["sh", str(RULES), "--root", str(repo)],
                              capture_output=True, text=True)
        return done.returncode, done.stdout + done.stderr


class LoginRuleTest(unittest.TestCase):
    def test_d1_design_states_the_login_rule(self):
        text = (ROOT / "docs/DESIGN.md").read_text()
        section = text.split("## 10. The boundary", 1)[1].split("## 11.", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("unmodified `claude` binary and `codex`", flat)
        self.assertIn("Agent SDK", flat)
        self.assertIn("API client", flat)

    def test_d2_python_import_of_an_api_client_is_refused_and_named(self):
        for module in (SDK, "claude_agent_sdk", "claude_code_sdk"):
            for line in (f"import {module}\n", f"from {module} import X\n"):
                with self.subTest(line=line):
                    code, out = check({"kit/scripts/x.py": line})
                    self.assertNotEqual(code, 0)
                    self.assertIn("kit/scripts/x.py", out)

    def test_d2_extras_and_script_imports_are_refused(self):
        code, out = check({"extras/a.js": f"import C from '@{SDK}-ai/sdk';\n"})
        self.assertNotEqual(code, 0)
        self.assertIn("extras/a.js", out)
        code, out = check({"kit/b.ts": f"const c = require(\"@{SDK}-ai/sdk\");\n"})
        self.assertNotEqual(code, 0)
        self.assertIn("kit/b.ts", out)

    def test_d3_package_json_dependency_is_refused(self):
        body = '{"dependencies": {"@%s-ai/sdk": "^1.0.0"}}\n' % SDK
        code, out = check({"kit/package.json": body})
        self.assertNotEqual(code, 0)
        self.assertIn("kit/package.json", out)

    def test_d3_pyproject_dependency_is_refused(self):
        body = '[project]\ndependencies = ["%s>=0.30"]\n' % SDK
        code, out = check({"kit/pyproject.toml": body})
        self.assertNotEqual(code, 0)
        self.assertIn("kit/pyproject.toml", out)

    def test_d3_requirements_dependency_is_refused(self):
        code, out = check({"kit/requirements.txt": f"{SDK}==0.30\n"})
        self.assertNotEqual(code, 0)
        self.assertIn("kit/requirements.txt", out)

    def test_d4_mentions_in_kit_text_are_allowed(self):
        text = ("Run `claude setup-token`, then set CLAUDE_CODE_OAUTH_TOKEN.\n"
                f"The {SDK} client is not used here.\n")
        code, out = check({"kit/skills/x.md": text,
                           "kit/scripts/y.py": f"# no {SDK} import here\n"})
        self.assertEqual(code, 0, out)

    def test_d4_this_repository_passes(self):
        done = subprocess.run(["sh", str(RULES)], capture_output=True,
                              text=True, cwd=ROOT)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("sdk-import", done.stdout)


if __name__ == "__main__":
    unittest.main()
