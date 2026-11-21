"""The two disk checks used by the runner's inherited-environment regression."""
import unittest

from kit.tests import test_common


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(test_common.DiskTest(name) for name in (
        "test_a_command_waits_for_space_on_each_volume",
        "test_a_disk_full_command_waits_and_retries"))
