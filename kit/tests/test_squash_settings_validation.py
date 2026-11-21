"""Boolean validation and combined squash trailer settings."""
import json
from pathlib import Path

import common
from kit.tests import test_merge_squash_message as squash
from kit.tests import test_merge_squash_settings as settings
from kit.tests.helpers import FakeGh


class SquashOptionsTest(FakeGh):
    project = settings.SquashSettingsTest.project
    build = settings.SquashSettingsTest.build
    merge_body = settings.SquashSettingsTest.merge_body

    def test_committed_options_require_booleans(self):
        for key in ("Sign-off", "Agent attribution"):
            for value in ("true", 0, 1, None, [], {}):
                with self.subTest(key=key, value=value):
                    Path(self.tmp, "loop.json").write_text(json.dumps({
                        "Test command": "true", key: value}), encoding="utf-8")
                    with self.assertRaises(common.SettingsError) as caught:
                        common.read_settings(self.tmp)
                    self.assertIn("wrong type", str(caught.exception))
                    self.assertIn(key, str(caught.exception))

    def test_sign_off_and_agent_attribution_work_together(self):
        trailer = self.project({"Sign-off": True, "Agent attribution": True})
        _, body = self.merge_body([
            "first change\n\n" + trailer.lower(),
            "second change\n\n" + squash.AGENT_TRAILERS[0]])
        self.assertIn(squash.AGENT_TRAILERS[0], body)
        self.assertEqual(body.casefold().count(trailer.casefold()), 1)
        self.assertEqual(body.splitlines()[-1], trailer)
