import json
import os
import tempfile
import unittest

from kit.tests.helpers import FakeGh, copy_repo, make_repo, run_git
import common
import merge

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"
BRIEFS = os.path.join(os.path.dirname(__file__), "..", "briefs")


def ok(stdout=""):
    return {"code": 0, "stdout": stdout}


def rule(match, *responses):
    return {"match": match, "responses": list(responses)}


# Built at run time so that no tracked file holds a literal agent trailer.
CO = "Co-Author" + "ed-By: "
AGENT_TRAILERS = [
    CO + "Claude Sonnet 5.5 <noreply@" + "anthropic.com>",
    CO.replace("By", "by") + "Codex <codex@users.noreply.github.com>",
    CO.lower() + "ChatGPT <bot@example.com>",
    CO.replace("By", "by") + "OpenAI Helper <helper@example.com>",
    CO.replace("By", "by") + "Some Bot <bot@ANTHROPIC" + ".com>",
    CO.upper() + "Another <x@openai" + ".com>",
]
KEPT = [
    CO.replace("By", "by") + "Ada Lovelace <ada@example.com>",
    "Signed-off-by: Guillaume Picard <gwpicard@gmail.com>",
]


class SquashMessageTest(FakeGh):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        work, _ = make_repo(cls._dir.name, {"AGENTS.md": AGENTS, "app.py": "x = 1\n"})
        run_git(["push", "origin", "main:loop/main"], work)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        super().setUp()
        self.work, _ = copy_repo(self._dir.name, self.tmp)

    def build(self, messages):
        run_git(["checkout", "-b", "issue/1", "main"], self.work)
        for i, message in enumerate(messages):
            with open(os.path.join(self.work, "app.py"), "w") as f:
                f.write("x = %d\n" % (i + 2))
            run_git(["add", "-A"], self.work)
            run_git(["commit", "-m", message], self.work)
        run_git(["push", "origin", "issue/1"], self.work)
        sha = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["checkout", "main"], self.work)
        return sha

    def merge_body(self, messages):
        sha = self.build(messages)
        pr = [ok("[]")] + [ok(json.dumps([{
            "number": 7, "state": st, "headRefOid": sha,
            "mergeCommit": {"oid": "abc123"} if st == "MERGED" else None}]))
            for st in ("OPEN", "MERGED")]
        self.scenario([
            rule("issue view 1 --json body", ok(json.dumps({"body": "Add.", "comments": []}))),
            rule("issue view 1 --json state", ok('{"state": "CLOSED"}')),
            rule("pr list", *pr),
            rule("pr create", ok("https://example/pull/7")),
            rule("pr comment", ok()),
            rule("pr merge", ok()),
            rule("--json comments", ok('{"comments": []}')),
            rule("issue close", ok()),
            rule("issue edit", ok()),
        ])
        text = "VERDICT: APPROVE\nHEAD: %s\n\n1. nothing\n" % sha
        result = merge.merge(1, "issue/1", text, self.work)
        self.assertTrue(result.ok, result.reason)
        call = [c for c in self.calls() if c[:2] == ["pr", "merge"]][0]
        self.assertIn("--subject", call)
        self.assertIn("--body", call)
        return (call[call.index("--subject") + 1], call[call.index("--body") + 1])

    def test_subject_and_body_are_passed_and_the_subject_is_unchanged(self):
        subject, body = self.merge_body(["first change", "second change"])
        self.assertEqual(subject, "Issue 1 (#7)")
        self.assertLess(body.index("first change"), body.index("second change"))

    def test_agent_trailers_go_and_human_trailers_stay_across_commits(self):
        messages = ["first change\n\n" + AGENT_TRAILERS[0],
                    "second change\n\n" + KEPT[0] + "\n" + AGENT_TRAILERS[1] + "\n" + KEPT[1]]
        _, body = self.merge_body(messages)
        self.assertNotIn(AGENT_TRAILERS[0], body)
        self.assertNotIn(AGENT_TRAILERS[1], body)
        for line in KEPT:
            self.assertIn(line, body)
        self.assertLess(body.index("first change"), body.index("second change"))

    def test_a_human_coauthor_survives_beside_every_agent_trailer(self):
        _, body = self.merge_body(["work\n\n" + "\n".join(AGENT_TRAILERS + KEPT)])
        for agent in AGENT_TRAILERS:
            self.assertNotIn(agent, body)
        for line in KEPT:
            self.assertIn(line, body)

    def test_reviewer_brief_says_trailers_are_not_a_reason_for_changes(self):
        with open(os.path.join(BRIEFS, "reviewer.md")) as f:
            text = f.read().lower()
        self.assertIn("trailer", text)
        near = text[text.index("trailer") - 300:text.index("trailer") + 300]
        self.assertIn("changes", near)
        self.assertIn("merge", near)
