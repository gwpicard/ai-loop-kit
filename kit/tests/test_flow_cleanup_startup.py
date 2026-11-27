"""The cleanup probe must reach its command before its timeout starts."""
import unittest
from unittest import mock

from kit.tests import test_flow_temp_paths as paths


class FlowCleanupStartupTest(unittest.TestCase):
    def test_cleanup_checks_survive_a_slow_command_start(self):
        dedent = paths.textwrap.dedent
        delayed = []

        def delay_start(text):
            code = dedent(text)
            call = '        common.run_shell(command,'
            if call in code:
                delayed.append(True)
                code = code.replace(call, "        __import__('time').sleep(2.2)\n" + call, 1)
            return code

        probe = paths.FlowTempPathsCleanupTest(
            'test_timeouts_stop_commands_before_removing_temporary_folders')
        result = unittest.TestResult()
        with mock.patch.object(paths.textwrap, 'dedent', side_effect=delay_start):
            probe.run(result)
        self.assertEqual(delayed, [True], 'The real cleanup probe must receive the startup delay')
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
