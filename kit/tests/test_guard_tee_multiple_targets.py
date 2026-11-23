import os
import subprocess

from kit.tests.test_guard import GuardCase


class TestTeeMultipleTargets(GuardCase):
    def test_builder_cannot_overwrite_a_test_as_the_second_tee_target(self):
        command = "printf 'changed\\n' | tee src/guard-output.txt tests/test_app.py"
        result = self.bash(command, role="builder")
        # Demonstrate the real shell effect in the disposable repository.
        shell = subprocess.run(["/bin/sh", "-c", command], cwd=self.work,
                               capture_output=True, text=True)
        self.assertEqual(shell.returncode, 0, shell.stderr)
        with open(os.path.join(self.work, "tests/test_app.py")) as source:
            self.assertEqual(source.read(), "changed\n")
        self.refused(result, "existing test")
