import unittest

import merge


class MoreLockfilesTest(unittest.TestCase):
    def test_other_ecosystem_lockfiles_are_stops(self):
        for path in ("bun.lock", "bun.lockb", "npm-shrinkwrap.json", "Podfile.lock", "mix.lock",
                     "pubspec.lock", "flake.lock", "Package.resolved"):
            self.assertIsNotNone(merge.stop_reason(path, []), path)


if __name__ == "__main__":
    unittest.main()
