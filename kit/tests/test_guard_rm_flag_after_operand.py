from kit.tests.test_guard import GuardCase


class TestRmFlagAfterOperand(GuardCase):
    def test_recursive_flag_after_operand_refused(self):
        for cmd in ["rm dir -r", "rm dir -rf", "rm -f dir --recursive"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd), "recursive delete")
