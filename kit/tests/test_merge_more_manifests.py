import unittest

import merge


class MoreManifestsTest(unittest.TestCase):
    def test_other_lockfiles_and_manifests_are_stops(self):
        for path in ("pdm.lock", "deno.lock", "pom.xml", "build.gradle", "setup.py", "requirements.in"):
            self.assertIsNotNone(merge.stop_reason(path, []), path)


if __name__ == "__main__":
    unittest.main()
