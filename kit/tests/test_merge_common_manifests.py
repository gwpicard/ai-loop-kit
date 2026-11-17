import unittest

import merge


class CommonManifestsTest(unittest.TestCase):
    def test_common_lockfiles_and_manifests_are_stops(self):
        for path in ("Pipfile.lock", "composer.lock", "Gemfile", "Pipfile", "composer.json"):
            self.assertIsNotNone(merge.stop_reason(path, []), path)


if __name__ == "__main__":
    unittest.main()
