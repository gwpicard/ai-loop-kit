"""The orphan fixture must wait until the leader PID has been written."""
from pathlib import Path
from unittest import mock

from kit.tests import test_pass_orphan_cleanup as orphan_tests


class PassPidPublicationTest(orphan_tests.fixes.BackgroundPassFixture):
    orphan = orphan_tests.PassOrphanCleanupTest.orphan
    end_agents = orphan_tests.PassOrphanCleanupTest.end_agents
    assert_ended = orphan_tests.PassOrphanCleanupTest.assert_ended

    def agent(self, body):
        # Hold a direct write open until the fixture observes its empty file.
        # Publishing through a temporary file and rename needs no such pause.
        prelude = (
            "import pathlib, time\n"
            "original_write_text = pathlib.Path.write_text\n"
            "def write_text(path, data, *args, **kwargs):\n"
            "    if path.name == 'leader-pid':\n"
            "        with path.open('w') as stream:\n"
            "            release = path.with_name('release-pid-write')\n"
            "            until = time.monotonic() + 15\n"
            "            while not release.exists():\n"
            "                if time.monotonic() >= until:\n"
            "                    raise AssertionError('the fixture never read leader-pid')\n"
            "                time.sleep(0.01)\n"
            "            return stream.write(data)\n"
            "    return original_write_text(path, data, *args, **kwargs)\n"
            "pathlib.Path.write_text = write_text\n")
        marker = "command = [sys.executable, '-c', "
        self.assertEqual(body.count(marker), 1, "the fixture's child command changed")
        body = body.replace(marker, marker + repr(prelude) + " + ", 1)
        orphan_tests.PassOrphanCleanupTest.agent(self, body)

    def test_hook_cleanup_waits_for_the_leader_pid_contents(self):
        leader = self.runtime / "leader-pid"
        release = self.runtime / "release-pid-write"
        self.addCleanup(release.touch)
        read_text = Path.read_text

        def read(path, *args, **kwargs):
            contents = read_text(path, *args, **kwargs)
            if path == leader and not contents:
                release.touch()
            return contents

        with mock.patch.object(Path, "read_text", new=read):
            try:
                check = orphan_tests.PassOrphanCleanupTest.test_crashed_worker_collection_ends_a_hook_group_without_its_leader
                check(self)
            except ValueError as error:
                self.fail("the fixture read leader-pid before its contents were ready: %s" % error)
