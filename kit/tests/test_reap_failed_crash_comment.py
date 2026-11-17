"""A failed crash comment when a build process dies must not make reap raise: the loop's final wait has no guard."""
import unittest
from unittest import mock

from kit.tests.test_loop import Base, issue, setUpModule, tearDownModule  # noqa: F401
import common
import loop


class DeadProcess:
    returncode = 3

    def poll(self):
        return 3


class ReapFailedCrashComment(Base):
    def test_reap_survives_a_failed_crash_comment(self):
        self.world([issue(2, labels=("building",))])
        st = loop.new_state()
        st["building"][2] = ("10:00", DeadProcess())
        real = loop.gh

        def fail_comment(args, **kw):
            if args[:2] == ["issue", "comment"]:
                raise common.GitHubError("HTTP 502")
            return real(args, **kw)
        with mock.patch.object(loop, "gh", side_effect=fail_comment):
            try:
                loop.reap(self.work, st)
            except common.GitHubError as e:
                self.fail("reap raised on a failed crash comment: %s" % e)


if __name__ == "__main__":
    unittest.main()
