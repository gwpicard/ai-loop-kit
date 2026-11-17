from kit.tests.test_guard import GuardCase


class TestSlackTokenKinds(GuardCase):
    def test_other_slack_token_prefixes_are_refused(self):
        for prefix in ["xo" + "xa-", "xo" + "xs-", "xo" + "xr-"]:
            with self.subTest(prefix=prefix):
                self.refused(self.call("Write", {"file_path": "a.txt", "content": prefix + "1234567890-abcdefghij"}))
