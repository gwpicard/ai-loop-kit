"""Settings merged into the loop branch govern the rest of the running batch."""
import contextlib
import json
import os
from pathlib import Path
import shlex
import shutil
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import finish_pass, make_repo, run_git
import common
import loop
import merge


class LoopBranchSettingsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="loop-branch-settings-")
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def project(self):
        parent = self.folder / str(len(list(self.folder.iterdir())))
        parent.mkdir()
        self.checkout = {"Test command": "true", "Loop branch": "loop/main",
                         "Parallel": 3, "Idle hours": 12, "Max rounds": 5}
        work, _ = make_repo(str(parent), {
            "loop.json": json.dumps(self.checkout), "piece.txt": "checkout\n",
            ".gitignore": ".loop/\nloop.local.json\n"})
        self.work = Path(work)
        run_git(["push", "origin", "main:loop/main"], work)
        self.local = {"Parallel": 1, "Idle hours": 0}
        (self.work / "loop.local.json").write_text(json.dumps(self.local), encoding="utf-8")
        self.prs, self.closed, self.received, self.merges = {}, set(), [], []

    def marker_command(self, name):
        return "printf '%s\\n' \"$(cat piece.txt)\" >> " + shlex.quote(str(self.work.parent / name))

    def marker(self, name):
        path = self.work.parent / name
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def github(self, args, input=None, **kwargs):
        """Stand in for GitHub, fast-forwarding only the disposable local remote."""
        value = ""
        if args[:2] == ["issue", "view"]:
            value = {"title": "Piece " + args[2], "comments": [],
                     "body": "## Protected paths this issue may change\n\nloop.json\n"}
        elif args[:2] == ["issue", "close"]:
            self.closed.add(int(args[2]))
        elif args[:2] in (["issue", "edit"], ["pr", "comment"]):
            pass
        elif args[:2] == ["issue", "list"]:
            value = []
        elif args[:2] == ["pr", "list"]:
            value = list(self.prs.values())
            for flag, key in (("--head", "headRefName"), ("--base", "baseRefName"),
                              ("--state", "state")):
                if flag in args and args[args.index(flag) + 1] != "all":
                    expected = args[args.index(flag) + 1]
                    value = [p for p in value if p[key].lower() == expected.lower()]
        elif args[:2] == ["pr", "create"]:
            head, base = (args[args.index(flag) + 1] for flag in ("--head", "--base"))
            number = len(self.prs) + 100
            self.prs[number] = dict(number=number, state="OPEN", headRefName=head,
                                    baseRefName=base, comments=[], body=input or "",
                                    headRefOid=common.git(["rev-parse", "origin/" + head], cwd=self.work),
                                    url="https://example.test/pull/%d" % number)
            value = self.prs[number]["url"]
        elif args[:2] == ["pr", "merge"]:
            pr = self.prs[int(args[2])]
            sha = pr["headRefOid"]
            self.assertEqual(args[args.index("--match-head-commit") + 1], sha)
            run_git(["push", "origin", sha + ":" + pr["baseRefName"]], self.work)
            pr.update(state="MERGED", mergeCommit={"oid": sha})
        elif args[:2] == ["pr", "view"]:
            value = self.prs[int(args[2])]
        elif args[:2] == ["pr", "edit"]:
            self.prs[int(args[2])]["body"] = input
        elif args[0] == "api":
            value = False  # delete_branch_on_merge advice
        else:
            raise AssertionError("unexpected GitHub call: %r" % args)
        return 0, json.dumps(value) if not isinstance(value, str) else value, ""

    def run_batch(self, pieces):
        """Run the command with scripted builders and foreground pass sessions.

        Each builder commits a piece and calls the real merge gate. The supervisor,
        settings reads, Git refs, command execution, drain and pass are real.
        """
        pending = list(enumerate(pieces, 7))
        cycles = []

        def snapshot(st):
            cycles.append(True)
            st["building"].clear()  # the scripted builder finished in the previous cycle
            st["closed"] = set(self.closed)
            st["issues"] = [dict(number=n, title="Piece %d" % n, body="", labels={"ready"})
                            for n, _ in pending[:1]]

        def build(project, settings, st):
            if not pending:
                return
            number, files = pending.pop(0)
            self.received.append(dict(settings))
            branch = "issue/%d" % number
            with common.settings_environment(settings):
                with common.scratch_tree(project, "origin/loop/main") as tree:
                    for name, content in dict({"piece.txt": "piece-%d\n" % number}, **files).items():
                        path = Path(tree, name)
                        if content is None:
                            path.unlink()
                        else:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(content, encoding="utf-8")
                    run_git(["add", "-A"], tree)
                    run_git(["commit", "-qm", "Issue %d" % number], tree)
                    sha = common.git(["rev-parse", "HEAD"], cwd=tree)
                    run_git(["push", "origin", "HEAD:refs/heads/" + branch], tree)
                result = merge.merge(number, branch, "VERDICT: APPROVE\nHEAD: " + sha, project)
            self.merges.append(result)
            if not result.ok:
                (self.work / ".loop/stop").touch()
            # Keep the supervisor busy until its next settings reload, as a worker does.
            st["building"][number] = ("00:00", None)

        def wait(*args):
            if len(cycles) > len(pieces) + 5:
                (self.work / ".loop/stop").touch()

        original_which = shutil.which
        output = self.work / ".loop/loop.out"
        output.parent.mkdir(exist_ok=True)
        before = (self.work / "loop.json").read_bytes()
        with contextlib.ExitStack() as stack:
            stack.callback(os.chdir, os.getcwd())
            os.chdir(self.work)
            for target, options in (
                    ("common._run_gh", {"side_effect": self.github}),
                    ("loop.setup.missing", {"return_value": None}),
                    ("loop.snapshot", {"side_effect": snapshot}),
                    ("loop.start_builds", {"side_effect": build}),
                    ("loop.start_pass", {"side_effect": finish_pass}),
                    ("loop.write_board", {"return_value": None}),
                    ("loop.wait_stop", {"side_effect": wait}),
                    ("loop.shutil.which", {"side_effect": lambda name: None if name == "caffeinate"
                                          else original_which(name)}),
                    ("loop.session.run", {"return_value": ("FINDINGS:\nnone\n", "fake-pass")})):
                stack.enter_context(mock.patch(target, **options))
            stream = stack.enter_context(output.open("a", encoding="utf-8"))
            stack.enter_context(contextlib.redirect_stdout(stream))
            result = loop.main(["run"])
        text = output.read_text(encoding="utf-8")
        self.assertEqual(result, 0, text)
        self.assertFalse(pending, text)
        self.assertEqual(len(self.merges), len(pieces), text)
        self.assertTrue(all(r.ok for r in self.merges), [r.reason for r in self.merges])
        self.assertEqual(self.closed, set(range(7, 7 + len(pieces))), text)
        self.assertLessEqual(len(cycles), len(pieces) + 2, text)
        self.assertEqual((self.work / "loop.json").read_bytes(), before)
        return text

    def test_second_merge_and_drain_use_branch_commands_with_checkout_overrides(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.project()
                branch = dict(self.checkout, **{
                    "Loop branch": "loop/elsewhere", "Parallel": 9, "Idle hours": 20,
                    "Max rounds": 2, "Test command": self.marker_command("tests-ran"),
                    "Check command": self.marker_command("checks-ran")})
                if reverse:
                    branch = dict(reversed(list(branch.items())))
                self.run_batch([{"loop.json": json.dumps(branch)}, {}])
                self.assertEqual(self.marker("checks-ran"), ["piece-8", "piece-8"],
                                 "the second merge and the drain must execute the merged Check command")
                self.assertEqual(self.marker("tests-ran"), ["piece-8", "piece-8"])
                self.assertEqual(self.received[1]["Max rounds"], 2)
                for settings in self.received:
                    self.assertEqual(settings["Loop branch"], "loop/main")
                    self.assertEqual(settings["Parallel"], self.local["Parallel"])
                    self.assertEqual(settings["Idle hours"], self.local["Idle hours"])
                self.assertEqual(common.git(["ls-remote", "--heads", "origin", "loop/elsewhere"],
                                            cwd=self.work), "")

    def test_pass_runs_smoke_defined_only_on_loop_branch(self):
        self.project()
        branch = dict(self.checkout, **{"Smoke command": self.marker_command("smoke-ran")})
        self.run_batch([{"loop.json": json.dumps(branch)}])
        self.assertEqual(self.marker("smoke-ran"), ["piece-7"],
                         "the pass must execute the loop branch's Smoke command")
        report = json.loads((self.work / ".loop/pass.json").read_text(encoding="utf-8"))["text"]
        smoke = report.split("### Smoke\n\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(smoke, "passed", report)
        self.assertNotIn("not set", smoke)
        self.assertIn("### Problems\n\nnone", report)

    def test_settings_source_is_logged_once_until_source_changes(self):
        self.project()
        first = json.dumps(dict(self.checkout, **{"Max rounds": 2}))
        another = json.dumps(dict(self.checkout, **{"Max rounds": 4}))
        text = self.run_batch([{"loop.json": first}, {}, {"loop.json": another},
                               {"loop.json": json.dumps(self.checkout)}, {}])
        lines = [line for line in text.splitlines() if "settings:" in line.lower()]
        remote = [line for line in lines if "origin/loop/main" in line and "loop.json" in line]
        self.assertEqual(len(remote), 1, text)
        self.assertIn("checkout", remote[0].lower())
        after = lines[lines.index(remote[0]) + 1:]
        self.assertEqual(len(after), 1, text)
        self.assertIn("loop.json", after[0])
        self.assertIn("checkout", after[0].lower())
        self.assertNotIn("origin/loop/main", after[0])

    def test_invalid_branch_settings_log_once_and_missing_file_keeps_checkout_settings(self):
        for content, error in ((None, None),
                               ('{"Test command": "true", "Unknown setting": 1}', "Unknown setting"),
                               ('{"Test command": "true", "Parallel": "many"}', "Parallel")):
            with self.subTest(content=content):
                self.project()
                self.checkout["Check command"] = self.marker_command("checkout-checks")
                (self.work / "loop.json").write_text(json.dumps(self.checkout), encoding="utf-8")
                # A valid branch setting first distinguishes checkout fallback from retaining it.
                valid = json.dumps(dict(self.checkout, **{"Max rounds": 2}))
                text = self.run_batch([{"loop.json": valid}, {"loop.json": content}, {}, {}])
                for settings in self.received[2:]:
                    self.assertEqual(settings["Max rounds"], self.checkout["Max rounds"])
                    self.assertEqual(settings["Loop branch"], self.checkout["Loop branch"])
                    self.assertEqual(settings["Parallel"], self.local["Parallel"])
                self.assertEqual(self.marker("checkout-checks"),
                                 ["piece-7", "piece-8", "piece-9", "piece-10", "piece-10"])
                errors = [line for line in text.splitlines()
                          if "loop.json" in line and error and error.lower() in line.lower()]
                if error:
                    self.assertEqual(len(errors), 1, text)
                else:
                    self.assertNotIn("keeping previous settings", text)
                    self.assertNotIn("missing file", text)
