"""Codex network access is a deliberate project setting for every build role."""
import json
import os
from pathlib import Path
import unittest

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import make_repo
import common
import session

KIT = Path(__file__).resolve().parents[1]


class CodexNetworkTest(FakeCodexGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {"loop.json": json.dumps({"Test command": "true"})})

    def test_network_setting_defaults_to_false_and_accepts_only_booleans(self):
        self.assertIs(common.read_settings(self.work).get("Codex network"), False)
        for value in (True, False, "true", 1, [], None):
            with self.subTest(value=value):
                Path(self.work, "loop.json").write_text(json.dumps({
                    "Test command": "true", "Codex network": value,
                }))
                if type(value) is bool:
                    try:
                        found = common.read_settings(self.work)
                    except common.SettingsError as error:
                        self.fail("Codex network must accept a JSON boolean: %s" % error)
                    self.assertIs(found["Codex network"], value)
                else:
                    with self.assertRaises(common.SettingsError):
                        common.read_settings(self.work)

    def test_each_role_passes_network_permission_to_fresh_and_resumed_sessions(self):
        settings = common.read_settings(self.work)
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                # Exercise launch independently of the setting validation above.
                with common.settings_environment(dict(settings, **{"Codex network": enabled})):
                    for role in ("test-writer", "builder", "reviewer"):
                        self.codex([{"reply": "done"}, {"reply": "done"}])
                        _, thread = session.run(role, "work", self.work, "gpt-6", self.work, 7,
                                                agent="codex")
                        session.run(role, "continue", self.work, "gpt-6", self.work, 7,
                                    agent="codex", resume=thread)
                        for call in self.codex_calls():
                            config = [call["argv"][i + 1] for i, arg in enumerate(call["argv"])
                                      if arg == "-c"]
                            network = [value.split("=", 1)[1].strip() for value in config
                                       if value.startswith("sandbox_workspace_write.network_access=")]
                            self.assertEqual(network if enabled else (network or ["false"]),
                                             [str(enabled).lower()], (role, call["argv"]))
                            self.assertIn('sandbox_mode="workspace-write"', config)

    def test_setup_guidance_links_package_fetching_to_the_network_setting(self):
        text = (KIT / "skills/setup/SKILL.md").read_text()
        paragraphs = text.split("\n\n")
        self.assertTrue(any("Codex network" in paragraph and "Prepare command" in paragraph
                            and "package" in paragraph.lower() for paragraph in paragraphs),
                        "Setup must explain Codex network for Prepare commands that fetch packages")


if __name__ == "__main__":
    unittest.main()
