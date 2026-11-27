"""Process helpers retain rows when command lines contain invalid UTF-8."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import write_exe
from kit.tests.test_loop_pause import table


class ProcessHelperTextTest(unittest.TestCase):
    def test_table_replaces_invalid_command_bytes_and_keeps_every_row(self):
        examples = (
            (b"  21 1 S /usr/bin/worker --name=bad-\xff value\n"
             b"  22 21 R /usr/bin/child --normal\n",
             {21: (1, "S", "/usr/bin/worker --name=bad-\ufffd value"),
              22: (21, "R", "/usr/bin/child --normal")}),
            (b"\t22\t21\tR\t/usr/bin/child --normal\n"
             b"21   1   S   /usr/bin/worker --name=bad-\xe2\x82\n",
             {22: (21, "R", "/usr/bin/child --normal"),
              21: (1, "S", "/usr/bin/worker --name=bad-\ufffd")}),
        )
        with tempfile.TemporaryDirectory(prefix="loop-process-text-") as folder:
            for output, expected in examples:
                with self.subTest(output=output):
                    write_exe(str(Path(folder, "ps")),
                              "#!PYTHON\nimport sys\nsys.stdout.buffer.write(%r)\n" % output,
                              shared=False)
                    with mock.patch.dict(os.environ, PATH=folder + os.pathsep + os.environ.get("PATH", "")):
                        try:
                            rows = table()
                        except UnicodeDecodeError as error:
                            self.fail("table() must replace invalid command bytes: %s" % error)
                    self.assertEqual(rows, expected)
