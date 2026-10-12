"""Protected person-read generations: authority, completeness and identity."""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))

from loop import cli, github, moves, read_record, states  # noqa: E402
from loop.gates import CheckContext, ready  # noqa: E402


def fixtures() -> Any:
    description = importlib.util.spec_from_file_location(
        "read_record_fixtures", ROOT / "tests/unit/test_preapp_reads.py"
    )
    assert description is not None and description.loader is not None
    loaded = importlib.util.module_from_spec(description)
    sys.modules[description.name] = loaded
    description.loader.exec_module(loaded)
    return loaded


class ReadRecordCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = fixtures().PreAppReadsCase()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.paths = self.fixture.paths
        self.person = self.fixture.person

    def settings(self, change: Any, *, local: bool = False) -> None:
        path = self.paths.root / ".claude" / ("settings.local.json" if local else "settings.json")
        value = {} if local else json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value), "utf-8")

    def generation(self) -> dict[str, Any]:
        return read_record.collect(self.paths, self.person)

    def test_empty_complete_generation_preserves_unrelated_app_settings(self) -> None:
        read_record.invalidate(self.paths)
        initial = json.loads(self.paths.local_settings.read_text())
        initial["unrelated"] = {"name": "kept"}
        initial["github_app"] = {"app_id": 1, "installation_id": 2, "slug": "fixture"}
        self.paths.local_settings.write_text(json.dumps(initial), "utf-8")
        read_record.publish(self.paths, self.generation())
        found = read_record.load(self.paths)
        self.assertEqual(found.issues, {})
        self.assertEqual(json.loads(self.paths.local_settings.read_text())["unrelated"],
                         {"name": "kept"})
        self.assertEqual(json.loads(self.paths.local_settings.read_text())["github_app"],
                         {"app_id": 1, "installation_id": 2, "slug": "fixture"})

    def test_snapshot_catalogue_overrides_stale_local_duplicate_text(self) -> None:
        self.fixture.gate.capture(title="Export invoices as CSV", body="Export invoices as CSV")
        self.fixture.sync()
        self.person.writes.issues[1].update({"title": "Rotate deployment logs",
                                           "body": "Rotate deployment logs"})
        self.person.writes.issues[77] = {
            "number": 77, "title": "Export invoices as CSV", "body": "Export invoices as CSV",
            "labels": ["state:shaping"], "state": "open", "comments": [],
        }
        read_record.publish(self.paths, self.generation())
        self.fixture.gate.capture(title="Export invoices as CSV", body="Export invoices as CSV")
        local = moves.read_piece(self.paths, 2)
        assert local is not None
        self.assertIsNone(local.issue, "an uncaptured local piece must remain searchable")
        duplicates = fixtures().duplicates
        with (
            patch.object(duplicates, "_paths", return_value=self.paths),
            patch.object(duplicates.github, "GitHub", return_value=self.fixture.no_app),
        ):
            result = duplicates.search(argparse.Namespace(text="Export invoices as CSV",
                                                          threshold=0.6))
        matches = {(entry["number"], entry["source"]) for entry in result["matches"]}
        self.assertIn((77, "person-synced snapshot"), matches)
        self.assertIn((2, "record"), matches)
        self.assertEqual(self.fixture.spawned, [], "cached search must not contact GitHub")
        self.assertNotIn((1, "record"), matches,
                         "fresh catalogue text must supersede a captured piece's stale text")

    def test_missing_stale_future_and_changed_origin_refuse(self) -> None:
        with self.assertRaises(github.GitHubError):
            read_record.load(self.paths)
        generation = self.generation()
        read_record.publish(self.paths, generation)
        with self.assertRaises(github.GitHubError):
            read_record.load(self.paths, now=generation["collected_at"] + 901)
        with self.assertRaises(github.GitHubError):
            read_record.load(self.paths, now=generation["collected_at"] - 1)
        with (
            patch.object(github, "origin_identity", return_value=("example", "different")),
            self.assertRaises(github.GitHubError),
        ):
            read_record.load(self.paths)

    def test_effective_overlay_and_disabled_filesystem_refuse(self) -> None:
        self.settings(lambda value: value.update({"sandbox": {"filesystem": {"disabled": True}}}),
                      local=True)
        with self.assertRaises(github.GitHubError):
            read_record.protection(self.paths)
        self.settings(lambda value: value.update({"sandbox": {"excludedCommands": ["python3 *"]}}),
                      local=True)
        with self.assertRaises(github.GitHubError):
            read_record.protection(self.paths)
        self.settings(lambda value: value.update({"model": "person-value"}), local=True)
        read_record.protection(self.paths)
        for writes, denies in (([], []), (["/synthetic/additional-write-block"],
                                        ["Edit(//**/additional-protected.txt)"])):
            self.settings(lambda value, writes=writes, denies=denies: value.update({
                "sandbox": {"filesystem": {"denyWrite": writes}},
                "permissions": {"deny": denies},
            }), local=True)
            read_record.protection(self.paths)

        project = self.paths.root / ".claude/settings.json"
        before = json.loads(project.read_text())
        cases: list[Callable[[dict[str, Any]], None]] = [
            lambda value: value["sandbox"].update({"enabled": False}),
            lambda value: value["sandbox"].update({"failIfUnavailable": False}),
            lambda value: value["sandbox"].update({"allowUnsandboxedCommands": True}),
            lambda value: value["permissions"].update({"disableBypassPermissionsMode": "allow"}),
            lambda value: value["sandbox"]["excludedCommands"].append("sh *"),
            lambda value: value["sandbox"]["filesystem"].update({"denyWrite": []}),
        ]
        for change in cases:
            value = json.loads(json.dumps(before))
            change(value)
            project.write_text(json.dumps(value), "utf-8")
            preserved = project.read_bytes()
            with self.assertRaises(github.GitHubError):
                read_record.protection(self.paths)
            self.assertEqual(project.read_bytes(), preserved)
        project.write_text(json.dumps(before), "utf-8")
        read_record.protection(self.paths)

    def test_full_page_limit_requires_terminal_page_and_duplicates_refuse(self) -> None:
        original = self.person.api_json

        def pages(endpoint: str, **kwargs: Any) -> Any:
            if "/issues?" in endpoint:
                page = int(endpoint.rsplit("page=", 1)[1])
                if page <= 5:
                    return [{"number": (page - 1) * 100 + n, "id": 10000 + (page - 1) * 100 + n,
                             "title": "A", "body": "", "labels": [], "state": "open",
                             "updated_at": "2026-10-12T12:00:00Z", "pull_request": {}}
                            for n in range(1, 101)]
                return [{"number": 501, "id": 10501, "pull_request": {}}]
            return original(endpoint, **kwargs)

        with (
            patch.object(self.person, "api_json", side_effect=pages),
            self.assertRaises(github.GitHubError),
        ):
            self.generation()
        def terminal(endpoint: str, **kwargs: Any) -> Any:
            if "/issues?" in endpoint and endpoint.endswith("page=6"):
                return []
            return pages(endpoint, **kwargs)

        with patch.object(self.person, "api_json", side_effect=terminal):
            complete = self.generation()
        self.assertEqual(complete["catalogue"], [])
        self.assertEqual(complete["issues"], {})
        self.person.writes.issues[1] = {"number": 1, "title": "A", "body": "", "labels": [],
                                       "state": "open", "comments": []}

        def duplicate(endpoint: str, **kwargs: Any) -> Any:
            answer = original(endpoint, **kwargs)
            if "/issues?" in endpoint and answer:
                return answer + answer
            return answer

        with (
            patch.object(self.person, "api_json", side_effect=duplicate),
            self.assertRaises(github.GitHubError),
        ):
            self.generation()

        self.person.writes.issues[1]["labels"] = ["state:dropped"]

        def comments(endpoint: str, **kwargs: Any) -> Any:
            if "/comments?" in endpoint:
                page = int(endpoint.rsplit("page=", 1)[1])
                return [{"id": (page - 1) * 100 + n,
                         "body": "Moved to dropped\nReason: reason" + str((page - 1) * 100 + n)}
                        for n in range(1, 101)]
            return original(endpoint, **kwargs)

        with (
            patch.object(self.person, "api_json", side_effect=comments),
            self.assertRaises(github.GitHubError),
        ):
            self.generation()

        def final_comments(endpoint: str, **kwargs: Any) -> Any:
            if "/comments?" in endpoint and endpoint.endswith("page=6"):
                return []
            return comments(endpoint, **kwargs)

        with patch.object(self.person, "api_json", side_effect=final_comments):
            complete = self.generation()
        self.assertEqual(complete["issues"]["1"]["reason"], "reason500")

    def test_repository_id_change_refuses_complete_publication(self) -> None:
        original = self.person.api_json
        reads = 0

        def changed(endpoint: str, **kwargs: Any) -> Any:
            nonlocal reads
            answer = original(endpoint, **kwargs)
            if endpoint == "repos/example/project":
                reads += 1
                return {"id": 9000 + reads, "full_name": "example/project"}
            return answer

        with (
            patch.object(self.person, "api_json", side_effect=changed),
            self.assertRaises(github.GitHubError),
        ):
            self.generation()
        self.assertFalse(self.paths.local_settings.exists())

    def test_symlink_and_partial_generation_refuse(self) -> None:
        outside = self.paths.root.parent / "outside.json"
        outside.write_text("{}", "utf-8")
        self.paths.local_settings.parent.mkdir(parents=True)
        self.paths.local_settings.symlink_to(outside)
        with self.assertRaises(github.GitHubError):
            read_record.invalidate(self.paths)
        self.assertEqual(outside.read_text(), "{}")
        self.paths.local_settings.unlink()
        generation = self.generation()
        generation["complete"] = False
        with self.assertRaises(github.GitHubError):
            read_record.publish(self.paths, generation)

    def test_failed_refresh_invalidates_before_remote_write_and_app_stays_live(self) -> None:
        self.fixture.gate.capture(title="A", body="A")
        read_record.publish(self.paths, self.generation())
        digest = self.fixture.gate.sync(self.person, dry_run=True)["digest"]
        with (
            patch.object(self.person, "api_json", side_effect=github.GitHubError(
                "synthetic read failure", next_command="retry"
            )),
            self.assertRaises(moves.MoveError),
        ):
            self.fixture.gate.sync(self.person, confirm=digest)
        self.assertTrue(self.person.writes.calls, "approved remote writes were not rolled back")
        with self.assertRaises(github.GitHubError):
            read_record.load(self.paths)
        self.assertLess(abs(time.time() - self.generation()["collected_at"]), 5)


    def test_literal_origin_alias_and_foreign_bindings_refuse(self) -> None:
        generation = self.generation()
        read_record.publish(self.paths, generation)
        subprocess.run(["git", "-C", str(self.paths.root), "remote", "set-url", "origin",
                        "git@github.com:example/project.git"], check=True,
                       stdin=subprocess.DEVNULL, capture_output=True)
        with self.assertRaises(github.GitHubError):
            read_record.load(self.paths)
        for key in ("root", "common_git", "repository"):
            with self.subTest(key=key):
                bad = dict(self.generation())
                bad[key] = "foreign"
                with self.assertRaises(github.GitHubError):
                    read_record.publish(self.paths, bad)

    def test_git_routing_cannot_spoof_binding_or_person_host(self) -> None:
        expected = read_record.binding(self.paths)
        routing = {"GIT_DIR": "/nonexistent-fixture", "GIT_WORK_TREE": "/wrong-fixture",
                   "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "remote.origin.url",
                   "GIT_CONFIG_VALUE_0": "https://github.com/foreign/project.git",
                   "GH_HOST": "foreign.example", "GH_REPO": "foreign/project",
                   "GH_CONFIG_DIR": "/fixture/person-config", "GH_TOKEN": "fixture-value",
                   "GH_DEBUG": "api", "SSH_AUTH_SOCK": "/fixture/person-agent"}
        with patch.dict(os.environ, routing):
            self.assertEqual(read_record.binding(self.paths), expected)
            actual = github._gh_env(self.paths, None, routing, as_person=True)
            self.assertEqual(github._gh_env(self.paths, None, routing), routing)
        self.assertEqual(actual["GH_HOST"], "github.com")
        self.assertEqual(actual["GH_REPO"], "github.com/example/project")
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0",
                     "GIT_CONFIG_VALUE_0", "GH_DEBUG"):
            self.assertNotIn(name, actual)
        for name in ("GH_CONFIG_DIR", "GH_TOKEN", "SSH_AUTH_SOCK"):
            self.assertEqual(actual[name], routing[name])

    def test_byte_and_time_bounds_refuse_without_publication(self) -> None:
        with (
            patch.object(read_record, "RESPONSE_LIMIT", 64),
            self.assertRaises(github.GitHubError),
        ):
            self.generation()
        self.assertFalse(self.paths.local_settings.exists())
        self.person.read_calls.clear()
        with (
            patch("loop.read_record.time.monotonic", side_effect=[0, 181]),
            self.assertRaises(github.GitHubError),
        ):
            self.generation()
        self.assertEqual(self.person.read_calls, [])
        self.assertFalse(self.paths.local_settings.exists())

    def test_actual_bounded_process_reaps_timeout_and_oversized_child(self) -> None:
        original = subprocess.Popen
        children: list[Any] = []

        def launch(*args: Any, **kwargs: Any) -> Any:
            child = original(*args, **kwargs)
            children.append(child)
            return child

        for script, timeout in (("import time; time.sleep(1)", 0.02),
                                ("import sys; sys.stdout.write('x' * 8388609)", 5)):
            with self.subTest(script=script), patch("loop.github.subprocess.Popen",
                                                  side_effect=launch):
                with self.assertRaises(github.GitHubError):
                    github.bounded_person_process([sys.executable, "-c", script], timeout=timeout,
                                                  cwd=str(self.paths.root), env=dict(os.environ))
                self.assertIsNotNone(children[-1].poll())
                with self.assertRaises(ProcessLookupError):
                    os.killpg(children[-1].pid, 0)

    def test_transitive_cycle_tombstone_and_denied_endpoint_are_distinct(self) -> None:
        for number in (1, 2):
            self.person.writes.issues[number] = {
                "number": number, "title": "A piece", "body": "A", "labels": ["state:ready"],
                "state": "open", "comments": [],
            }
        original = self.person.api_json

        def linked(endpoint: str, **kwargs: Any) -> Any:
            if "/dependencies/blocked_by" in endpoint:
                number = int(endpoint.split("/issues/")[1].split("/")[0])
                return [self.person.issue_json(2 if number == 1 else 1)]
            return original(endpoint, **kwargs)

        with patch.object(self.person, "api_json", side_effect=linked):
            value = self.generation()
        read_record.publish(self.paths, value)
        context = CheckContext(number=1, move=states.by_number(2), origin="shaping", target="ready",
                               reason=None, title="A", body="A", spec=None,
                               record=[{"kind": "synced", "issue": 1}], paths=self.paths)
        problems = ready._github_blockers(context, self.fixture.no_app)
        self.assertTrue(any("cycle" in problem for problem in problems))
        assert isinstance(problems, ready.DependencyRead)
        self.assertIn("person-synced snapshot", problems.provenance)

        def missing(endpoint: str, **kwargs: Any) -> Any:
            if "/issues/2?" in endpoint or endpoint.endswith("/issues/2"):
                raise github.GitHubError("gone", next_command="retry", not_found=True)
            if "/issues?" in endpoint:
                return [self.person.issue_json(1)]
            if "/issues/1/dependencies/blocked_by" in endpoint:
                return [self.person.issue_json(2)]
            return original(endpoint, **kwargs)

        with patch.object(self.person, "api_json", side_effect=missing):
            value = self.generation()
        self.assertIsNone(value["issues"]["2"])
        read_record.publish(self.paths, value)
        self.assertTrue(any("does not exist" in problem
                            for problem in ready._github_blockers(context, self.fixture.no_app)))

        def denied(endpoint: str, **kwargs: Any) -> Any:
            if "/dependencies/blocked_by" in endpoint:
                raise github.GitHubError("denied", next_command="retry")
            return original(endpoint, **kwargs)

        with (
            patch.object(self.person, "api_json", side_effect=denied),
            self.assertRaises(github.GitHubError),
        ):
            self.generation()

    def test_malformed_schema_and_unclosed_graph_refuse(self) -> None:
        value = self.generation()
        for key, wrong in (("schema", True), ("repository_id", True), ("collected_at", True),
                           ("catalogue", [True]), ("complete", False)):
            with self.subTest(key=key):
                bad = {**value, key: wrong}
                with self.assertRaises(github.GitHubError):
                    read_record.publish(self.paths, bad)
        closed = {**value, "catalogue": [1], "issues": {"1": {
            "number": 1, "title": "A", "body": "A", "labels": [], "state": "open",
            "updated_at": "2026-10-12T12:00:00Z", "blocked_by": [], "reason": None}}}
        read_record.publish(self.paths, closed)
        self.assertIsNone(read_record.load(self.paths).issues["1"]["reason"])
        for field in ("reason", "body"):
            with self.subTest(missing=field):
                malformed = json.loads(json.dumps(closed))
                malformed["issues"]["1"].pop(field)
                with self.assertRaises(github.GitHubError):
                    read_record.publish(self.paths, malformed)
                stored = json.loads(self.paths.local_settings.read_text())
                stored["github_reads"] = malformed
                self.paths.local_settings.write_text(json.dumps(stored), "utf-8")
                with self.assertRaises(github.GitHubError):
                    read_record.load(self.paths)
                read_record.publish(self.paths, closed)
        malformed = json.loads(json.dumps(closed))
        malformed["issues"]["1"]["blocked_by"] = [2]
        with self.assertRaises(github.GitHubError):
            read_record.publish(self.paths, malformed)

        crowded = {**value, "catalogue": list(range(1, 501)), "issues": {}}
        for number in range(1, 501):
            crowded["issues"][str(number)] = {
                "number": number, "title": "A", "body": "A", "labels": [], "state": "open",
                "updated_at": "2026-10-12T12:00:00Z", "blocked_by": list(range(1, 13)),
                "reason": None,
            }
        with self.assertRaises(github.GitHubError):
            read_record.publish(self.paths, crowded)

    def test_valid_cache_does_not_rescue_failed_app_read(self) -> None:
        self.person.writes.issues[1] = {"number": 1, "title": "A", "body": "A",
                                       "labels": ["state:ready"], "state": "open", "comments": []}
        read_record.publish(self.paths, self.generation())
        self.assertIn("1", read_record.load(self.paths).issues)
        app = Mock()
        app.available = True
        app.read_issue.side_effect = github.GitHubError("App refused", next_command="retry App")
        context = CheckContext(number=1, move=states.by_number(2), origin="shaping", target="ready",
                               reason=None, title="A", body="A", spec=None,
                               record=[{"kind": "synced", "issue": 1}], paths=self.paths)
        with patch.object(read_record, "load", side_effect=AssertionError("App used cache")):
            with self.assertRaises(github.GitHubError):
                ready._github_blockers(context, app)
            app.read_issue.side_effect = None
            app.read_issue.return_value = {"labels": ["state:ready"]}
            app.api_json.return_value = []
            result = ready._github_blockers(context, app)
            self.assertEqual(result, [])
            assert isinstance(result, ready.DependencyRead)
            self.assertIn("live as the App", result.provenance)

    def test_protection_and_invalidation_failure_stop_before_queued_writes(self) -> None:
        self.fixture.gate.capture(title="A", body="A")
        digest = self.fixture.gate.sync(self.person, dry_run=True)["digest"]
        self.settings(lambda value: value["sandbox"].update({"enabled": False}))
        with self.assertRaises(moves.MoveError):
            self.fixture.gate.sync(self.person, confirm=digest)
        self.assertEqual(self.person.writes.calls, [])
        self.settings(lambda value: value["sandbox"].update({"enabled": True}))
        with (
            patch.object(read_record, "atomic", side_effect=github.GitHubError(
                "invalidation failed", next_command="retry"
            )),
            self.assertRaises(moves.MoveError),
        ):
            self.fixture.gate.sync(self.person, confirm=digest)
        self.assertEqual(self.person.writes.calls, [])
        read_record.publish(self.paths, self.generation())
        create = self.person.writes.create_issue

        def checked_create(*args: Any, **kwargs: Any) -> int:
            self.assertNotIn("github_reads", json.loads(self.paths.local_settings.read_text()))
            return int(create(*args, **kwargs))

        with patch.object(self.person.writes, "create_issue", side_effect=checked_create):
            self.fixture.gate.sync(self.person, confirm=digest)
        self.assertIn("github_reads", json.loads(self.paths.local_settings.read_text()))

    def test_json_renderer_refuses_invalid_roots_before_write(self) -> None:
        renderer = fixtures().merge_settings
        template = (ROOT / "kit/templates/claude-settings.json").read_text()
        for root in (None, "relative", str(self.paths.root) + "*", str(self.paths.root) + '"'):
            values = {"KIT_DIR": str(ROOT / "kit")}
            if root is not None:
                values["PROJECT_ROOT"] = root
            with self.subTest(root=root), self.assertRaises(cli.Failure):
                renderer.render_settings(template, values)
        rendered = renderer.render_settings(template, {"KIT_DIR": str(ROOT / "kit"),
                                                       "PROJECT_ROOT": str(self.paths.root)})
        self.assertNotIn("{{", rendered)
        self.assertEqual(json.loads(rendered)["sandbox"]["filesystem"]["denyWrite"][-1],
                         str(self.paths.root / ".agents/loop"))
        with self.assertRaises(cli.Failure):
            renderer.render_settings('{"value":"{{UNFILLED}}"}', {})
