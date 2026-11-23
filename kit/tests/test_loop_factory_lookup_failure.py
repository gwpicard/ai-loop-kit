"""A failed Factory lookup leaves the board unwritten and can be retried."""
import json

from kit.tests.helpers import FakeGh
import loop


class FactoryLookupFailureTest(FakeGh):
    def check_failed_lookup(self, response):
        self.scenario([{"match": "issue list", "responses": [response]}])
        st = loop.new_state()

        try:
            loop.write_board(self.tmp, st)
        except Exception as error:
            self.fail("write_board raised after a failed Factory lookup: %s: %s"
                      % (type(error).__name__, error))

        self.assertIsNone(st["factory"])
        calls = self.calls()
        self.assertTrue(calls, "the fake gh must receive the Factory lookup")
        self.assertTrue(all(call[:2] == ["issue", "list"] for call in calls), calls)
        self.assertIn("Factory in:title", calls[0])

        factory = {"number": 42, "title": "Factory", "body": "Old board"}
        self.scenario([
            {"match": "issue list", "responses": [{"stdout": json.dumps([factory])}]},
            {"match": "issue edit", "responses": [{}]},
        ])
        loop.write_board(self.tmp, st)
        self.assertEqual(st["factory"]["number"], factory["number"])
        self.assertEqual([call[:3] for call in self.calls()],
                         [["issue", "list", "--state"], ["issue", "edit", "42"]])

    def test_non_json_factory_lookup_skips_board_write(self):
        self.check_failed_lookup({"stdout": "not json"})

    def test_github_error_in_factory_lookup_skips_board_write(self):
        self.check_failed_lookup({"code": 1, "stderr": "Factory lookup refused"})
