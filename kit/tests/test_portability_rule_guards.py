"""Check the platform and fake exceptions through the portability rule's CLI."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PortabilityRuleGuardsTest(unittest.TestCase):
    def test_only_the_guarded_branch_or_mocked_command_is_exempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "-q", folder], check=True, capture_output=True)
            source = root / "kit/tests/test_example.py"
            source.parent.mkdir(parents=True)
            source.touch()
            subprocess.run(["git", "-C", folder, "add", "."], check=True, capture_output=True)
            cases = [
                ("subprocess.%s(args=['caffeinate', 'true'])\n" % name, False)
                for name in ("Popen", "call", "check_call", "check_output")
            ] + [
                ("subprocess.run(args=['caffeinate', 'true'], check=True)\n", False),
                ("os.popen(cmd='sysctl -n hw.ncpu')\n", False),
                ("common.run_shell(command='memory_pressure', cwd='.', timeout=1)\n", False),
                ("run_shell(command='getconf DARWIN_USER_TEMP_DIR', cwd='.', timeout=1)\n", False),
                ("if sys.platform == 'darwin':\n"
                 "    subprocess.run(args=['caffeinate', 'true'], check=True)\n", True),
                ("with mock.patch('subprocess.run'):\n"
                 "    subprocess.run(args=['caffeinate', 'true'], check=True)\n", True),
                ("if sys.platform != 'darwin':\n"
                 "    subprocess.run(['sysctl'])\n", False),
                ("if sys.platform != 'darwin':\n    pass\nelse:\n"
                 "    subprocess.run(['/usr/sbin/sysctl'])\n", True),
                ("@unittest.skipUnless(sys.platform == 'darwin', 'macOS')\n"
                 "def test_mac():\n    subprocess.run(['caffeinate'])\n", True),
                ("with mock.patch.object(subprocess, 'run'):\n"
                 "    subprocess.run(['memory_pressure'])\n", True),
                ("with mock.patch('os.getcwd'):\n"
                 "    subprocess.run(['memory_pressure'])\n", False),
                ("with mock.patch('subprocess.run'):\n    pass\n"
                 "subprocess.run(['taskpolicy'])\n", False),
                ("if sys.platform == 'darwin':\n"
                 "    value = os.environ['TMPDIR']\n", False),
                ("os.environ['TMPDIR'] = 'fixture-folder'\n"
                 "del os.environ['TMPDIR']\n", True),
            ]
            for body, passes in cases:
                with self.subTest(body=body):
                    source.write_text(body)
                    result = subprocess.run([
                        sys.executable, str(ROOT / "tests/test-portability.py"), folder,
                    ], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0 if passes else 1,
                                     result.stdout + result.stderr)
                    if not passes:
                        self.assertIn("test_example.py:", result.stdout)
