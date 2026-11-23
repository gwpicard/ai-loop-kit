import unittest

import flow
import merge
import pass_


class ReplyBlockFormattingTest(unittest.TestCase):
    def test_plain_head_with_full_stop_is_read(self):
        for head in ("abc1234", "abcdef1234567890abcdef1234567890abcdef12"):
            with self.subTest(head=head):
                self.assertEqual(merge.parse_verdict("VERDICT: APPROVE\nHEAD: " + head + "."),
                                 ("APPROVE", head))

    def test_bold_verdict_label_with_colon_outside_bold_is_read(self):
        for prefix in ("", "VERDICT: CHANGES\nHEAD: def5678\n\n"):
            with self.subTest(prefix=prefix):
                reply = prefix + "**VERDICT**: APPROVE\nHEAD: abc1234\n"
                self.assertEqual(merge.parse_verdict(reply), ("APPROVE", "abc1234"))

    def test_bold_tests_label_with_colon_outside_bold_is_read(self):
        for prefix in ("", "TESTS:\nold.py\n\n"):
            with self.subTest(prefix=prefix):
                reply = prefix + "**TESTS**:\n- a.py\n- b.py\n"
                self.assertEqual(flow.parse_block(reply), ["a.py", "b.py"])

    def test_bold_around_backticked_paths_is_removed(self):
        for paths in (("a.py", "tests/test_b.py"), ("tests/test_b.py", "a.py")):
            with self.subTest(paths=paths):
                reply = "TESTS:\n" + "\n".join("- **`%s`**" % path for path in paths)
                self.assertEqual(flow.parse_block(reply), list(paths))

    def test_number_after_bullet_is_removed(self):
        for paths in (("a.py", "b.py"), ("b.py", "a.py")):
            with self.subTest(paths=paths):
                reply = "TESTS:\n" + "\n".join(
                    "- %d. %s" % (i, path) for i, path in enumerate(paths, 1))
                self.assertEqual(flow.parse_block(reply), list(paths))

    def test_dash_only_items_are_preserved(self):
        for items in (("---", "----"), ("----", "---")):
            with self.subTest(items=items):
                self.assertEqual(flow.parse_block("TESTS:\n" + "\n".join(items)), list(items))

    def test_empty_final_verdict_has_no_verdict(self):
        for verdict in ("APPROVE", "CHANGES"):
            for ending in ("VERDICT:", "VERDICT:\n", "**VERDICT**:", "**VERDICT**:\n"):
                with self.subTest(verdict=verdict, ending=ending):
                    reply = "VERDICT: %s\nHEAD: abc1234\n\n%s" % (verdict, ending)
                    self.assertIsNone(merge.parse_verdict(reply)[0])

    def test_empty_final_bold_tests_label_does_not_restore_old_paths(self):
        for ending in ("**TESTS**:", "**TESTS**:\n"):
            with self.subTest(ending=ending):
                self.assertEqual(flow.parse_block("TESTS:\na.py\n\n" + ending), [])

    def test_colon_title_keeps_findings_in_either_order(self):
        rows = [
            ("CLI: empty input", "crashes", ".loop/pass/kit/tests/test_empty.py"),
            ("Repeated run fails", "loses state", ".loop/pass/kit/tests/test_repeat.py"),
        ]
        for ordered in (rows, rows[::-1]):
            with self.subTest(rows=ordered):
                reply = "FINDINGS:\n" + "\n".join(" | ".join(row) for row in ordered)
                self.assertEqual(pass_.findings(reply), ordered)

    def test_rubric_rejected_findings_stay_separate_in_either_order(self):
        confirmed = "RUBRIC CONFIRMED:\nReal defect | reproduced\n"
        rejected = "RUBRIC REJECTED:\nWrong claim | expected behaviour\n"
        for blocks in ((confirmed, rejected), (rejected, confirmed)):
            with self.subTest(blocks=blocks):
                reply = "".join(blocks) + "HELD:\nnone\n"
                self.assertEqual(pass_.findings(reply, "RUBRIC CONFIRMED"),
                                 [("Real defect", "reproduced", "")])
                self.assertEqual(pass_.findings(reply, "RUBRIC REJECTED"),
                                 [("Wrong claim", "expected behaviour", "")])


if __name__ == "__main__":
    unittest.main()
