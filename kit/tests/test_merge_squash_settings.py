"""Committed settings control the body passed to the squash merge command."""
import json

from kit.tests import test_merge_squash_message as squash
from kit.tests.helpers import FakeGh, make_repo, run_git


class SquashSettingsTest(FakeGh):
    build = squash.SquashMessageTest.build
    merge_body = squash.SquashMessageTest.merge_body

    def project(self, settings, name="Alex Morgan", email="alex@example.com"):
        values = {"Test command": "true", "Loop branch": "loop/main", **settings}
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps(values), "app.py": "x = 1\n"})
        run_git(["push", "origin", "main:loop/main"], self.work)
        run_git(["config", "user.name", name], self.work)
        run_git(["config", "user.email", email], self.work)
        return "Signed-off-by: %s <%s>" % (name, email)

    def test_sign_off_uses_the_project_git_identity_at_the_end(self):
        for name, email in (("Alex Morgan", "alex@example.com"),
                            ("Robin Patel", "robin@contributors.example.org")):
            with self.subTest(name=name):
                trailer = self.project({"Sign-off": True}, name, email)
                _, body = self.merge_body([
                    "first change\n\n" + squash.AGENT_TRAILERS[0],
                    "second change\n\nDetails.\n\n" + squash.KEPT[0]])
                self.assertEqual(body.rstrip().splitlines()[-1], trailer)
                self.assertEqual(body.splitlines().count(trailer), 1)
                self.assertIn(squash.KEPT[0], body)
                self.assertNotIn(squash.AGENT_TRAILERS[0], body)

    def test_sign_off_occurs_once_even_when_builder_commits_already_sign(self):
        for repeated in (False, True):
            with self.subTest(repeated=repeated):
                trailer = self.project({"Sign-off": True})
                other = "Signed-off-by: Builder <builder@example.com>"
                messages = ["first change\n\n" + trailer + "\n" + other,
                            "second change\n\n" + squash.KEPT[0]]
                if repeated:
                    messages.reverse()
                    messages[0] += "\n" + trailer
                _, body = self.merge_body(messages)
                self.assertEqual(body.splitlines().count(trailer), 1)
                self.assertEqual(body.rstrip().splitlines()[-1], trailer)
                self.assertIn(other, body)
                self.assertIn(squash.KEPT[0], body)

    def test_absent_or_false_sign_off_adds_no_trailer(self):
        for settings in ({}, {"Sign-off": False}):
            with self.subTest(settings=settings):
                self.project(settings)
                _, body = self.merge_body(["first change", "second change\n\nDetails."])
                self.assertEqual(body, "first change\n\nsecond change\n\nDetails.")

    def test_agent_attribution_true_keeps_agent_and_human_trailers(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.project({"Agent attribution": True})
                trailers = squash.AGENT_TRAILERS + squash.KEPT
                if reverse:
                    trailers = list(reversed(trailers))
                messages = ["first change\n\n" + "\n".join(trailers[:3]),
                            "second change\n\n" + "\n".join(trailers[3:])]
                _, body = self.merge_body(messages)
                self.assertEqual(body, "\n\n".join(messages))

    def test_absent_or_false_agent_attribution_removes_only_agent_trailers(self):
        for settings in ({}, {"Agent attribution": False}):
            with self.subTest(settings=settings):
                self.project(settings)
                _, body = self.merge_body([
                    "first change\n\n" + "\n".join(squash.AGENT_TRAILERS[:3]),
                    "second change\n\n" + "\n".join(
                        squash.KEPT + squash.AGENT_TRAILERS[3:])])
                for trailer in squash.AGENT_TRAILERS:
                    self.assertNotIn(trailer, body)
                for trailer in squash.KEPT:
                    self.assertIn(trailer, body)
