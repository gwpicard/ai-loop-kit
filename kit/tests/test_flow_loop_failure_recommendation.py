"""Check the recommendation posted after a real loop-branch test failure."""
from pathlib import Path
import unittest
from unittest import mock

import common
from kit.tests import test_flow
from kit.tests.helpers import run_git


class LoopFailureRecommendationTest(unittest.TestCase):
    def test_park_recommends_fixing_the_loop_branch_and_explains_the_retry(self):
        test_flow.FlowTest.setUpClass()
        self.addCleanup(test_flow.FlowTest.tearDownClass)
        f = test_flow.FlowTest()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.tearDown)
        Path(f.work, "FAIL").write_text("earlier regression\n")
        run_git(["add", "FAIL"], f.work)
        run_git(["commit", "-m", "break fixture loop head"], f.work)
        run_git(["push", "origin", "HEAD:loop/main"], f.work)
        f.merge.side_effect = test_flow.REAL_MERGE
        f.build_scenario(builder=[{"files": {"app.py": "1\n"}, "passed": True}])
        with mock.patch.object(common, "gh", wraps=common.gh) as sent:
            result = f.build()
        self.assertEqual(result.status, "parked", result.reason)
        self.assertIn("already on the loop branch", result.reason.lower())
        comments = [call.kwargs.get("input", "") for call in sent.call_args_list
                    if call.args[0][:2] == ["issue", "comment"]]
        park = next(body for body in comments if body.startswith("## Needs you"))
        recommendation = park.split("Recommended: ", 1)[1].split("\n\n", 1)[0].lower()
        with self.subTest(behaviour="fix"):
            self.assertRegex(recommendation, r"fix.*loop branch|loop branch.*fix")
        with self.subTest(behaviour="retry"):
            self.assertRegex(recommendation, r"retr(?:y|ied|ies)")
            self.assertRegex(recommendation, r"pass(?:es|ing)?")
        with self.subTest(behaviour="no path permission request"):
            self.assertNotIn("name the path", recommendation)
