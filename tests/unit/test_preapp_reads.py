"""Founding regressions for protected reads before the App exists.

Synthetic settings show the intended authority boundary; these tests do not
claim that an operating-system sandbox has been exercised.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "kit"
sys.path.insert(0, str(KIT / "scripts"))

from loop import evidence, github, moves, states  # noqa: E402
from loop.gates import CheckContext, ready  # noqa: E402
from loop.paths import Paths  # noqa: E402


def module(name: str, relative: str) -> Any:
    description = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert description is not None and description.loader is not None
    loaded = importlib.util.module_from_spec(description)
    sys.modules[name] = loaded
    description.loader.exec_module(loaded)
    return loaded


# Load helper objects without importing or inheriting another discovered case.
move_fixtures = module("preapp_move_fixtures", "tests/unit/test_moves.py")
merge_settings = module("preapp_merge_settings", "kit/scripts/merge-settings.py")
setup = module("preapp_setup", "kit/scripts/setup.py")
duplicates = module("preapp_duplicates", "kit/skills/shape/scripts/find-duplicates.py")


class PersonHub:
    """Existing person write methods plus deterministic GitHub GET responses."""

    available = True
    as_person = True
    actor = "fixture-person"

    def __init__(self) -> None:
        self.writes: Any = move_fixtures.FakeHub()
        self.read_calls: list[str] = []
        self.env: dict[str, str] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.writes, name)

    def repo_view(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self.read_calls.append("repository")
        return {"id": 9001, "nameWithOwner": "example/project",
                "name": "project", "owner": {"login": "example"}}

    def issue_json(self, number: int) -> dict[str, Any]:
        value = self.writes.read_issue(number)
        return {**value, "id": 10000 + number,
                "updated_at": "2026-10-12T12:00:00Z",
                "repository_url": "https://api.github.com/repos/example/project",
                "url": f"https://api.github.com/repos/example/project/issues/{number}"}

    def api_json(self, endpoint: str, **_kwargs: Any) -> Any:
        self.read_calls.append(endpoint)
        endpoint = endpoint.replace("{owner}/{repo}", "example/project").lstrip("/")
        route, _, query = endpoint.partition("?")
        if route == "repos/example/project":
            return {"id": 9001, "full_name": "example/project"}
        if route == "repos/example/project/issues":
            page = int(dict(part.split("=", 1) for part in query.split("&") if part)["page"])
            values = [self.issue_json(n) for n in sorted(self.writes.issues)]
            return values[(page - 1) * 100:page * 100]
        prefix = "repos/example/project/issues/"
        if route.startswith(prefix):
            parts = route[len(prefix):].split("/")
            number = int(parts[0])
            if parts[1:] == ["dependencies", "blocked_by"]:
                return []
            if parts[1:] == ["comments"]:
                return [{"id": 20000 + i, "body": body,
                         "updated_at": "2026-10-12T12:00:00Z"}
                        for i, body in enumerate(self.writes.issues[number]["comments"])]
            if len(parts) == 1:
                return self.issue_json(number)
        raise AssertionError(f"unexpected synthetic GitHub endpoint: {endpoint}")


class PreAppReadsCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.root = base / "project"
        self.root.mkdir()
        for args in (("init", "-q"),
                     ("remote", "add", "origin", "https://github.com/example/project.git")):
            subprocess.run(["git", "-C", str(self.root), *args], check=True,
                           stdin=subprocess.DEVNULL, capture_output=True)
        self.paths = Paths.for_project(self.root, data_base=base / "data", kit_folder=KIT)
        self.spawned: list[list[str]] = []

        def no_network(command: list[str], **_kwargs: Any) -> Any:
            self.spawned.append(list(command))
            raise AssertionError("an agent started a program without the App")

        self.no_app = github.GitHub(self.paths, runner=no_network, env={})
        self.person = PersonHub()
        self.gate = moves.Gate(self.paths, self.no_app, env={}, terminal=lambda: True)
        # Deliberate authority fixture, independent of the missing shipping setting.
        settings = json.loads(merge_settings.render(
            (KIT / "templates/claude-settings.json").read_text("utf-8"),
            {"KIT_DIR": str(KIT), "PROJECT_ROOT": str(self.root)},
        ))
        denied = settings["sandbox"]["filesystem"]["denyWrite"]
        loop_folder = str(self.root / ".agents/loop")
        if loop_folder not in denied:
            denied.append(loop_folder)
        (self.root / ".claude").mkdir()
        (self.root / ".claude/settings.json").write_text(json.dumps(settings), "utf-8")

    def sync(self) -> dict[str, Any]:
        before = self.gate.sync(self.person, dry_run=True)
        self.assertEqual(self.person.read_calls, [], "dry-run must not collect reads")
        result = self.gate.sync(self.person, confirm=before["digest"])
        self.assertEqual(result["refused"], [])
        return result

    def test_confirmed_sync_supplies_actual_ready_dependency_reader_without_app(self) -> None:
        self.gate.capture(title="A shaped piece", body=move_fixtures.BODY)
        self.sync()
        piece = moves.read_piece(self.paths, 1)
        self.assertIsNotNone(piece)
        assert piece is not None
        self.assertEqual(piece.issue, 1, "the ordinary queued write must still be sent")
        self.assertEqual(piece.queue, [])
        context = CheckContext(number=1, move=states.by_number(2), origin="shaping",
                               target="ready", reason=None, title=piece.title,
                               body=piece.body, spec=None, record=evidence.read(self.paths, 1),
                               paths=self.paths)
        try:
            problems = ready._github_blockers(context, self.no_app)
        except github.GitHubError as error:
            self.fail("confirmed person sync did not supply the real ready dependency reader: "
                      + error.message)
        self.assertEqual(problems, [])
        self.assertEqual(self.spawned, [])

    def test_empty_queue_sync_supplies_uncaptured_remote_dropped_duplicate(self) -> None:
        self.person.writes.issues[77] = {
            "number": 77, "title": "Export invoices as CSV", "body": "Export invoices as CSV",
            "labels": ["state:dropped", "type:feature"], "state": "closed",
            "comments": ["Moved to dropped\nReason: CSV export is no longer wanted"],
        }
        self.person.writes.next = 78
        self.sync()
        self.assertEqual(self.gate.numbers(), [], "remote catalogue must not capture pieces")
        self.assertEqual(self.person.writes.calls, [], "an empty queue must send no writes")
        with patch.object(duplicates, "_paths", return_value=self.paths), \
                patch.object(duplicates.github, "GitHub", return_value=self.no_app):
            result = duplicates.search(argparse.Namespace(text="Export invoices as CSV",
                                                          threshold=0.6))
        matches = [entry for entry in result["matches"] if entry["number"] == 77]
        self.assertEqual(len(matches), 1, "person sync lost an uncaptured remote duplicate")
        self.assertTrue(matches[0]["dropped"])
        self.assertEqual(matches[0]["reason"], "CSV export is no longer wanted")
        self.assertTrue(any("77" in warning for warning in result["warnings"]))
        self.assertEqual(self.spawned, [])

    def test_actual_setup_renderer_protects_absolute_project_loop_folder(self) -> None:
        fresh = self.root.parent / "fresh project's folder"
        fresh.mkdir()
        prepared = setup.prepare_settings(fresh, KIT, merge_settings)
        settings = json.loads(prepared["text"])
        denied = settings["sandbox"]["filesystem"]["denyWrite"]
        self.assertIn(str(KIT), denied, "installed kit protection must remain")
        self.assertFalse((fresh / ".claude").exists(), "preparation must not write settings")
        self.assertIn(str(fresh.resolve() / ".agents/loop"), denied,
                      "the real settings renderer leaves the attended read record writable")


if __name__ == "__main__":
    unittest.main()
