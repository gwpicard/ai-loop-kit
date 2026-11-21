"""Settings validation, migration and live changes through the loop commands."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import FakeGh, make_repo, run_git
import common
import loop
import merge
import setup


class JsonSettingsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        # A readable legacy file must not hide JSON validation failures.
        self.write("AGENTS.md", "## Loop\nTest command: legacy\nParallel: 1\n")

    def write(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def refused(self, filename, key):
        with self.assertRaises(common.SettingsError) as caught:
            common.read_settings(str(self.root))
        self.assertIn(filename, str(caught.exception))
        self.assertIn(key, str(caught.exception))

    def test_json_values_are_read_without_markdown_parsing(self):
        values = {
            "Test command": "echo `literal`", "Test files command": "pytest {files}",
            "Prepare command": "make deps", "Check command": "make lint",
            "Smoke command": "make smoke", "Loop branch": "loop/custom",
            "Protected paths": ["folder, with comma/", "private/"],
            "Codex writable roots": ["~/cache, one", "/tmp/cache two"],
            "Red-team surfaces": ["imports, including CSV", "exports"],
            "Parallel": 3, "Idle hours": 1.5, "Max rounds": 4,
            "Session minutes": 12.5, "Builder": "codex gpt-6",
            "Test writer": "claude opus", "Reviewer": "codex gpt-6",
            "Pass": "claude sonnet"}
        for ordered in (values, dict(reversed(list(values.items())))):
            with self.subTest(order=list(ordered)):
                self.write("loop.json", json.dumps(ordered))
                result = common.read_settings(str(self.root))
                for key, value in values.items():
                    self.assertEqual(result[key], tuple(value.split()) if key in common.ROLES else value)

    def test_missing_file_and_required_command_name_the_file_and_key(self):
        self.refused("loop.json", "Test command")
        self.write("loop.json", "{}")
        self.refused("loop.json", "Test command")

    def test_unknown_keys_and_legacy_aliases_are_refused(self):
        for key in ("Future key", "Builder model", "Reviewer model"):
            with self.subTest(key=key):
                self.write("loop.json", json.dumps({"Test command": "true", key: "sonnet"}))
                self.refused("loop.json", key)

    def test_wrong_types_are_refused_for_every_setting(self):
        strings = ("Test command", "Test files command", "Prepare command", "Check command",
                   "Smoke command", "Loop branch", "Builder", "Test writer", "Reviewer", "Pass")
        invalid = [(key, value) for key in strings for value in (7, None, [], True)]
        invalid += [(key, value) for key in ("Parallel", "Idle hours", "Max rounds", "Session minutes")
                    for value in ("2", None, [], True)]
        invalid += [(key, value) for key in ("Protected paths", "Codex writable roots", "Red-team surfaces")
                    for value in ("one/, two/", ["one/", 2], None, {})]
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                self.write("loop.json", json.dumps({"Test command": "true", key: value}))
                self.refused("loop.json", key)

    def test_invalid_json_and_non_object_documents_are_refused(self):
        for document in ("{", "[]", '"text"', "null"):
            with self.subTest(document=document):
                self.write("loop.json", document)
                self.refused("loop.json", "")

    def test_local_values_override_committed_values_in_either_order(self):
        self.write("loop.json", json.dumps({"Test command": "true", "Parallel": 2, "Idle hours": 12}))
        for local in ({"Idle hours": 0.5, "Parallel": 4}, {"Parallel": 3, "Idle hours": 2}):
            with self.subTest(local=local):
                self.write("loop.local.json", json.dumps(local))
                result = common.read_settings(str(self.root))
                self.assertEqual((result["Parallel"], result["Idle hours"]),
                                 (local["Parallel"], local["Idle hours"]))

    def test_local_file_refuses_every_other_setting(self):
        self.write("loop.json", '{"Test command": "true"}')
        for key in ({"Test command", "Future key", "Builder model", "Reviewer model"}
                    | (set(common.DEFAULTS) - {"Parallel", "Idle hours"})):
            with self.subTest(key=key):
                self.write("loop.local.json", json.dumps({key: "anything"}))
                self.refused("loop.local.json", key)

    def test_local_values_are_validated_too(self):
        self.write("loop.json", '{"Test command": "true"}')
        for key in ("Parallel", "Idle hours"):
            for value in ("2", True, None, []):
                with self.subTest(key=key, value=value):
                    self.write("loop.local.json", json.dumps({key: value}))
                    self.refused("loop.local.json", key)
        self.write("loop.local.json", "{")
        self.refused("loop.local.json", "")

    def test_defaults_include_settings_files_and_exclude_model_aliases(self):
        self.write("loop.json", '{"Test command": "true"}')
        result = common.read_settings(str(self.root))
        for path in ("loop.json", "loop.local.json"):
            self.assertIn(path, result["Protected paths"])
        for key in ("Builder model", "Reviewer model"):
            self.assertNotIn(key, result)
            self.assertNotIn(key, common.DEFAULTS)

    def test_json_does_not_require_an_agents_file(self):
        self.write("loop.json", '{"Test command": "true"}')
        (self.root / "AGENTS.md").unlink()
        try:
            result = common.read_settings(str(self.root))
        except common.SettingsError as error:
            self.fail("loop.json must work without AGENTS.md: " + str(error))
        self.assertEqual(result["Test command"], "true")


def rule(match, value=""):
    return {"match": match, "responses": [{"code": 0, "stdout": value}]}


def snapshot(folder):
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in Path(folder).rglob("*") if p.is_file()}


class JsonMigrationTest(FakeGh):
    def test_setup_command_migrates_previews_and_is_repeatable(self):
        for newline, explicit in (("\n", False), ("\r\n", True)):
            with self.subTest(newline=repr(newline), explicit=explicit):
                parent = Path(self.tmp, "crlf" if explicit else "lf")
                parent.mkdir()
                before_section = "# Project\nKeep this guidance.\n\n"
                after_section = "## Other\nTest command: keep this prose\n"
                section = ("## Loop\nTest command: `true`\nTest files command: `pytest {files}`\n"
                           "Prepare command: true\nCheck command: true\nSmoke command: echo ok\n"
                           "Loop branch: loop/main\nProtected paths: `private/`, `secret/`\n"
                           "Codex writable roots: `~/cache`, `/tmp/cache`\nParallel: 2\n"
                           "Idle hours: 1.5\nMax rounds: 4\nSession minutes: 12.5\n"
                           "Builder model: opus\nReviewer model: sonnet\n")
                if explicit:
                    section += "Reviewer: claude opus\nBuilder: claude sonnet\n"
                agents = (before_section + section + after_section).replace("\n", newline)
                work, origin = make_repo(str(parent), {"AGENTS.md": agents, ".gitignore": "cache/"})
                self.scenario([rule("label list", "[]"), rule("label create"), rule("issue list", "[]"),
                               rule("issue create", "https://example/issues/7"), rule("issue pin")])

                def command(*args):
                    return subprocess.run([sys.executable, setup.__file__, *args, work],
                                          capture_output=True, text=True, timeout=30)

                before, remote = snapshot(work), snapshot(origin)
                preview = command("--dry-run")
                self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
                self.assertEqual(snapshot(work), before)
                self.assertEqual(snapshot(origin), remote)
                self.assertFalse(any(c[:2] in (["label", "create"], ["issue", "create"],
                                             ["issue", "pin"]) for c in self.calls()))
                applied = command()
                self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
                config = Path(work, "loop.json")
                self.assertTrue(config.exists(), "setup must create loop.json")
                values = json.loads(config.read_text())
                expected = {
                    "Test command": "true", "Test files command": "pytest {files}",
                    "Prepare command": "true", "Check command": "true", "Smoke command": "echo ok",
                    "Loop branch": "loop/main", "Protected paths": ["private/", "secret/"],
                    "Codex writable roots": ["~/cache", "/tmp/cache"], "Parallel": 2,
                    "Idle hours": 1.5, "Max rounds": 4, "Session minutes": 12.5,
                    "Builder": "claude sonnet" if explicit else "claude opus",
                    "Test writer": "claude opus", "Reviewer": "claude opus" if explicit else "claude sonnet",
                    "Pass": "claude sonnet"}
                for key, value in expected.items():
                    self.assertEqual(values[key], value, key)
                self.assertNotIn("Builder model", values)
                self.assertNotIn("Reviewer model", values)
                self.assertEqual(Path(work, "AGENTS.md").read_bytes(),
                                 (before_section + after_section).replace("\n", newline).encode())
                self.assertIn("loop.local.json", Path(work, ".gitignore").read_text().splitlines())
                previewed = [line.removeprefix("would change: ") for line in preview.stdout.splitlines()
                             if line.startswith("would change: ")]
                changes = [line.removeprefix("change: ") for line in applied.stdout.splitlines()
                           if line.startswith("change: ")]
                self.assertEqual(previewed, changes)
                records = [json.loads(line) for line in Path(work, ".loop/migrations.log").read_text().splitlines()]
                self.assertEqual([r["change"] for r in records], changes)
                for filename in ("loop.json", "AGENTS.md", "loop.local.json"):
                    matching = [r for r in records if filename in r["change"]]
                    self.assertTrue(matching, filename + " must have a migration record")
                    self.assertTrue(all(r["undo"] for r in matching))
                self.assertTrue(any("AGENTS.md" in r["change"] and "Test command:" in r["undo"]
                                    and "Builder model:" in r["undo"] for r in records),
                                "the undo must retain the removed settings")
                saved = {name: Path(work, name).read_bytes() for name in
                         ("AGENTS.md", "loop.json", ".gitignore", ".loop/migrations.log")}
                self.scenario([rule("label list", json.dumps([{"name": n} for n in setup.LABELS])),
                               rule("issue list", '[{"number":7,"title":"Factory"}]')])
                again = command()
                self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
                self.assertIn("summary: 0 change(s)", again.stdout)
                for name, content in saved.items():
                    self.assertEqual(Path(work, name).read_bytes(), content, name)


class JsonLoopTest(unittest.TestCase):
    def test_run_command_refuses_legacy_settings_before_starting_the_loop(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "AGENTS.md").write_text("## Loop\nTest command: true\n")
            result = subprocess.run([sys.executable, loop.__file__, "run"], cwd=folder,
                                    capture_output=True, text=True, timeout=15)
            text = result.stdout + result.stderr
            self.assertEqual(result.returncode, 1, text)
            self.assertIn("loop.json", text)
            self.assertIn("setup", text)
            self.assertIn("refused", text)
            self.assertFalse(Path(folder, ".loop/loop.pid").exists())

    def test_run_reloads_both_files_retains_last_good_settings_and_warns_once(self):
        for damaged in ("loop.json", "loop.local.json"):
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "AGENTS.md").write_text(
                    "## Loop\nTest command: true\nParallel: 2\nIdle hours: 12\n")
                base = {"Test command": "true", "Parallel": 2, "Idle hours": 12}
                (root / "loop.json").write_text(json.dumps(base))
                (root / "loop.local.json").write_text("{}")
                (root / ".loop").mkdir()
                counts, processes, sleeps = [], [], []

                def wait(stop, seconds):
                    sleeps.append(seconds)
                    if len(sleeps) > 100:
                        (root / ".loop/stop").touch()

                def spawn(*args, **kwargs):
                    proc = mock.Mock(pid=900000 + len(processes))
                    proc.poll.return_value = None
                    processes.append(proc)
                    return proc

                def world(st):
                    st["issues"] = [dict(number=n, title="Piece", body="", labels={"ready"})
                                    for n in range(1, 7)]

                def finish_workers(project, st, cap):
                    st["building"].clear()

                def cycle_end(project, st):
                    if not st["building"]:
                        return
                    counts.append(len(st["building"]))
                    if len(counts) == 1:
                        (root / "loop.local.json").write_text('{"Parallel": 3}')
                    elif len(counts) == 2:
                        (root / damaged).write_text("{")
                    elif len(counts) == 4:
                        base["Parallel"] = 4
                        (root / "loop.json").write_text(json.dumps(base))
                        (root / "loop.local.json").write_text("{}")
                    elif len(counts) >= 5:
                        (root / ".loop/stop").touch()

                with contextlib.ExitStack() as stack:
                    old = os.getcwd()
                    stack.callback(os.chdir, old)
                    os.chdir(folder)
                    for target, options in (
                        ("loop.sys.platform", {"new": "linux"}),
                        ("loop.setup.missing", {"return_value": None}),
                        ("loop.snapshot", {"side_effect": world}),
                        ("loop.reap", {"side_effect": finish_workers}),
                        ("loop.write_board", {"side_effect": cycle_end}),
                        ("loop.headroom", {"return_value": None}),
                        ("loop.stray_workers", {"return_value": []}),
                        ("loop.clean_up", {"return_value": None}),
                        ("loop.sync_default", {"return_value": False}),
                        ("loop.drain", {"return_value": None}),
                        ("common.ready_is_trusted", {"return_value": True}),
                        ("common.add_label", {"return_value": None}),
                        ("common.remove_label", {"return_value": None}),
                        ("loop.wait_stop", {"side_effect": wait}),
                        ("loop.subprocess.Popen", {"side_effect": spawn})):
                        stack.enter_context(mock.patch(target, **options))
                    with (root / ".loop/loop.out").open("w") as log, contextlib.redirect_stdout(log):
                        code = loop.main(["run"])
                text = (root / ".loop/loop.out").read_text()
                self.assertEqual(code, 0, text)
                self.assertEqual(counts, [2, 3, 3, 3, 4], text)
                notices = [line for line in text.splitlines() if damaged in line]
                self.assertEqual(len(notices), 1, text)
                self.assertRegex(notices[0].lower(), r"keep|keeping|kept|previous|last good")
                self.assertFalse((root / ".loop/loop.pid").exists())


class JsonMergeTest(FakeGh):
    def test_merge_protects_each_settings_file_unless_the_issue_names_it(self):
        for filename in ("loop.json", "loop.local.json"):
            for allowed in (False, True):
                with self.subTest(filename=filename, allowed=allowed):
                    work, _ = make_repo(self.tmp, {
                        "AGENTS.md": "## Loop\nTest command: true\n",
                        "loop.json": '{"Test command": "true"}', "loop.local.json": "{}"})
                    run_git(["push", "origin", "main:loop/main"], work)
                    run_git(["checkout", "-b", "piece"], work)
                    Path(work, filename).write_text(json.dumps(
                        {"Test command": "true", "Parallel": 2} if filename == "loop.json" else {"Parallel": 2}))
                    run_git(["add", filename], work)
                    run_git(["commit", "-m", "Change build concurrency"], work)
                    run_git(["push", "origin", "piece"], work)
                    sha = common.git(["rev-parse", "HEAD"], cwd=work)
                    body = "Change concurrency.\n"
                    if allowed:
                        body += "\n## Protected paths this issue may change\n\n" + filename + "\n"
                    self.scenario([
                        rule("issue view 1 --json body", json.dumps({"body": body, "comments": []})),
                        rule("pr list", json.dumps([{"number": 7, "state": "MERGED", "headRefOid": sha,
                                                     "mergeCommit": {"oid": sha}}])),
                        rule("issue close"), rule("issue edit")])
                    result = merge.merge(1, "piece", "VERDICT: APPROVE\nHEAD: " + sha, work)
                    if allowed:
                        self.assertTrue(result.ok, result.reason)
                    else:
                        self.assertFalse(result.ok, "settings changes require an explicit path grant")
                        self.assertTrue(result.park, result.reason)
                        self.assertIn(filename, result.reason)
                        self.assertFalse(any(c[:2] == ["pr", "merge"] for c in self.calls()))


if __name__ == "__main__":
    unittest.main()
