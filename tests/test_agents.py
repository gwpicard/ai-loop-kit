"""Agent command selection and event handling."""
from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from helpers import git, pump_events
import agents


class AgentSessionTest(unittest.TestCase):
    def test_codex_disables_user_mcp_sources_in_every_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "--quiet")
            fake = root / "fake-codex"
            fake.write_text("#!/usr/bin/env python3\n"
                            "import json, sys\nprint(json.dumps(sys.argv[1:]))\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            for role in ("builder", "reviewer", "critic", "probe"):
                for walk_away in (False, True):
                    with self.subTest(role=role, walk_away=walk_away), \
                            mock.patch.dict(os.environ, {"LOOP_CODEX": str(fake)}):
                        proc = agents.start_session("codex", "brief", root, role=role,
                                                    walk_away=walk_away)
                        output, _ = proc.communicate(timeout=5)
                        self.assertEqual(proc.returncode, 0)
                        args = json.loads(output)
                        disabled = {args[index + 1] for index, arg in enumerate(args[:-1])
                                    if arg == "--disable"}
                        self.assertIn("--ignore-user-config", args)
                        self.assertTrue({"plugins", "apps"} <= disabled,
                                        "Codex can still start user plugin or app MCP servers")

    def test_codex_builder_grants_own_git_data_and_prepared_temp(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve() / "repo"
            repo.mkdir()
            git(repo, "init", "--quiet")
            git(repo, "commit", "--allow-empty", "-qm", "Initial")
            linked = repo.parent / "linked"
            git(repo, "worktree", "add", "-qb", "piece", str(linked))
            for root in (repo, linked):
                for walk_away in (False, True):
                    with self.subTest(linked=root == linked, walk_away=walk_away), \
                            mock.patch.object(agents, "subprocess") as process:
                        agents.start_session("codex", "brief", root, role="builder",
                                             walk_away=walk_away)
                        args = process.Popen.call_args.args[0]
                        env = process.Popen.call_args.kwargs["env"]
                        temp = root / ".loop" / "tmp"
                        self.assertEqual(env.get("TMPDIR"), str(temp))
                        self.assertTrue(temp.is_dir())
                        configs = [args[i + 1] for i, value in enumerate(args[:-1])
                                   if value == "--config"]
                        filesystem = next(value for value in configs
                                          if value.startswith("permissions.ai-loop.filesystem="))
                        git_dir = git(root, "rev-parse", "--absolute-git-dir")
                        self.assertIn(json.dumps(git_dir) + '="write"', filesystem)
                        self.assertIn(json.dumps(str(temp)) + '="write"', filesystem)
                        self.assertIn('":tmpdir"="write"', filesystem)
                        self.assertIn('":slash_tmp"="deny"', filesystem)
                        self.assertIn("permissions.ai-loop.network.enabled=false", configs)
                        self.assertIn('approval_policy="never"', configs)
                        if root == linked:
                            common = repo / ".git"
                            for path in (common / "objects", common / "refs/heads/piece",
                                         common / "refs/heads/piece.lock",
                                         common / "logs/refs/heads/piece"):
                                self.assertIn(json.dumps(str(path)) + '="write"', filesystem)
                            self.assertNotIn(json.dumps(str(common)) + '="write"', filesystem)
                            self.assertNotIn(json.dumps(str(repo)) + '="write"', filesystem)
                        prompt = args[-1]
                        self.assertIn("permissions.ai-loop.filesystem", prompt)
                        self.assertIn(git_dir, prompt)
                        self.assertIn(".loop/outcome", prompt)
                        self.assertIn("refused path", prompt)

    def test_codex_builder_refuses_temp_symlink_outside_worktree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            git(root, "init", "--quiet")
            outside = Path(temporary) / "outside"
            outside.mkdir()
            (root / ".loop").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "TMPDIR.*permissions.ai-loop.filesystem"), \
                    mock.patch.object(agents, "subprocess") as process:
                agents.start_session("codex", "brief", root, role="builder")
            process.Popen.assert_not_called()
            self.assertFalse((outside / "tmp").exists())

    def fake_codex(self, root: Path) -> Path:
        fake = root / "fake-codex-session"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib\n"
            "if os.getenv('FAKE_WRITE'):\n"
            " pathlib.Path(os.environ['FAKE_WRITE']).write_text('made')\n"
            "print(json.dumps({'type':'item.completed','item':"
            "{'type':'agent_message','text':os.environ['FAKE_MESSAGE']}}), flush=True)\n"
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        return fake

    def test_codex_uses_json_workspace_write_without_github_tokens(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "--quiet")
            fake = root / "fake-codex"
            result = root / "result.json"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "json.dump({'argv': sys.argv[1:], 'gh': os.getenv('GH_TOKEN'), "
                "'github': os.getenv('GITHUB_TOKEN')}, open(os.environ['FAKE_RESULT'], 'w'))\n"
                "print(json.dumps({'type':'item.completed','item':"
                "{'type':'agent_message','text':'<verdict>{}</verdict>'}}), flush=True)\n"
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = {**os.environ, "LOOP_CODEX": str(fake), "FAKE_RESULT": str(result),
                   "GH_TOKEN": "sentinel", "GITHUB_TOKEN": "sentinel"}
            with mock.patch.dict(os.environ, env, clear=True):
                proc = agents.start_session("codex", "brief", root, role="reviewer")
                output, _ = proc.communicate(timeout=5)
            called = json.loads(result.read_text())
            self.assertEqual(called["gh"], None)
            self.assertEqual(called["github"], None)
            self.assertEqual(called["argv"], [
                "exec", "--json", "--disable", "plugins", "--disable", "apps",
                "--sandbox", "workspace-write",
                "--config", 'approval_policy="never"', "--cd", str(root.resolve()),
                "--ignore-user-config", "--ephemeral", "--config",
                "sandbox_workspace_write.network_access=false", "--config",
                "sandbox_workspace_write.writable_roots=[]", "--config",
                "sandbox_workspace_write.exclude_slash_tmp=true", "--config",
                "sandbox_workspace_write.exclude_tmpdir_env_var=true", "brief",
            ])
            self.assertEqual(agents.event_text(output.decode()), "<verdict>{}</verdict>")

    def test_claude_keeps_stream_json_and_loop_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "--quiet")
            fake = root / "fake-claude"
            fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            with mock.patch.dict(os.environ, {"LOOP_CLAUDE": str(fake)}, clear=True):
                proc = agents.start_session("claude", "brief", root, role="builder")
                output, _ = proc.communicate(timeout=5)
            self.assertIn("--output-format stream-json", output.decode())

    def test_loop_choice_defaults_to_claude_and_accepts_a_per_run_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "AGENTS.md").write_text("## The loop\nAgent: codex\n")
            self.assertEqual(agents.selected(root), "codex")
            self.assertEqual(agents.selected(root, "claude"), "claude")
            (root / "AGENTS.md").write_text("## The loop\nTest command: true\n")
            self.assertEqual(agents.selected(root), "claude")

    def test_codex_event_text_uses_final_agent_message(self):
        events = "\n".join([
            json.dumps({"type": "item.completed", "item":
                        {"type": "agent_message", "text": "earlier"}}),
            json.dumps({"type": "item.completed", "item":
                        {"type": "agent_message", "text": "<verdict>{}</verdict>"}}),
        ])
        self.assertEqual(agents.event_text(events), "<verdict>{}</verdict>")

    def test_codex_json_events_reset_the_idle_clock(self):
        import session

        events = [json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": "working"}}) for _ in range(5)]
        status, output = pump_events(session, events, idle_seconds=2,
                                     backend="codex", clock_step=.75)
        self.assertEqual(status, "")
        self.assertEqual(output.count("working"), 5)

    def test_codex_builder_and_reviewer_log_final_message(self):
        import review
        import run

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "--quiet")
            fake = self.fake_codex(root)
            builder_output = root / "builder-output"
            builder_log = root / "builder.log"
            with mock.patch.dict(os.environ, {
                "LOOP_CODEX": str(fake), "FAKE_WRITE": str(builder_output),
                "FAKE_MESSAGE": "builder says done"}, clear=True):
                status = run.build_once(root, "same brief", [], builder_log,
                                         backend="codex")
            self.assertEqual(status, "")
            self.assertEqual(builder_output.read_text(), "made")
            self.assertIn("builder says done", builder_log.read_text())
            self.assertNotIn('"type":"item.completed"', builder_log.read_text())

            verdict = ('<verdict>{"findings":[],"follow_ups":[],"changes":"none"}</verdict>')
            review_log = root / "review.log"
            with mock.patch.dict(os.environ, {
                "LOOP_CODEX": str(fake), "FAKE_MESSAGE": verdict}, clear=True):
                status = review._review_session(root, "same brief", review_log, [], 5,
                                                backend="codex")
            self.assertEqual(status, "")
            self.assertEqual(review._logged_verdict(review_log, "standards")["changes"], "none")

    def test_codex_critic_parses_tagged_final_message(self):
        import critic

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "--quiet")
            (root / ".loop").mkdir()
            (root / "ours.txt").write_text("ours")
            (root / "reference.txt").write_text("reference")
            fake = self.fake_codex(root)
            verdict = ('<verdict>{"winner":"A","reasons":{"Readable labels":'
                       '{"winner":"A","reason":"clear"}}}</verdict>')
            with mock.patch.dict(os.environ, {"LOOP_CODEX": str(fake),
                                              "FAKE_MESSAGE": verdict}, clear=True):
                results = critic.judge(root, ["ours.txt"], "reference.txt",
                                       ["Readable labels"], agent="codex")
            self.assertEqual(len(results), 3)
            self.assertTrue(all(item["winner"] in {"ours", "reference"} for item in results))

    def run_codex_probe(self, messages):
        import sandbox

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / ".ssh").mkdir()
            sessions = [mock.Mock(returncode=0, communicate=mock.Mock(return_value=(
                json.dumps({"type": "item.completed", "item": {
                    "type": "agent_message", "text": message}}).encode(), None)))
                for message in messages]
            with mock.patch.object(Path, "home", return_value=home), \
                    mock.patch.object(sandbox, "PROBE_PATH", home / "sandbox-probe"), \
                    mock.patch.object(sandbox.shutil, "which", return_value="/usr/bin/curl"), \
                    mock.patch.object(agents, "start_session", side_effect=sessions) as start:
                result = sandbox.codex_probe(home)
            return result, start.call_count

    def test_codex_probe_retries_once_after_an_unreadable_answer(self):
        good = '<probe>{"write":1,"ssh_read":1,"network":7}</probe>'
        for unreadable in ("No final probe line", '<probe>{"write":</probe>',
                           '<probe>{"write":1}</probe>',
                           '<probe>{"write":"blocked","ssh_read":1,"network":7}</probe>'):
            with self.subTest(answer=unreadable):
                (active, detail), calls = self.run_codex_probe([unreadable, good])
                self.assertTrue(active, detail)
                self.assertEqual(calls, 2)
                self.assertIn("retried", detail.lower())

    def test_codex_probe_stops_after_two_unreadable_answers(self):
        for answer, reason in (("No probe line", "did not return"),
                               ('<probe>{"write":"bad"}</probe>', "invalid")):
            with self.subTest(answer=answer):
                (active, detail), calls = self.run_codex_probe([answer, answer])
                self.assertFalse(active)
                self.assertEqual(calls, 2)
                self.assertIn(reason, detail)
                self.assertIn("retried", detail.lower())

    def test_codex_probe_never_retries_a_readable_zero_code(self):
        for boundary in ("write", "ssh_read", "network"):
            with self.subTest(boundary=boundary):
                codes = dict.fromkeys(("write", "ssh_read", "network"), 1)
                codes[boundary] = 0
                (active, detail), calls = self.run_codex_probe([
                    "<probe>" + json.dumps(codes) + "</probe>"])
                self.assertFalse(active)
                self.assertEqual(calls, 1)
                self.assertIn("allowed", detail)
                self.assertNotIn("retried", detail.lower())

    def test_codex_probe_refuses_a_leak_after_an_unreadable_answer(self):
        (active, detail), calls = self.run_codex_probe([
            "No probe line", '<probe>{"write":1,"ssh_read":0,"network":7}</probe>'])
        self.assertFalse(active)
        self.assertEqual(calls, 2)
        self.assertIn("~/.ssh", detail)
        self.assertIn("retried", detail.lower())

    def test_codex_walkaway_probe_requires_every_boundary_to_block(self):
        import sandbox

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            root.mkdir()
            git(root, "init", "--quiet")
            fake = self.fake_codex(root)
            home = Path(temporary) / "home"
            (home / ".ssh").mkdir(parents=True)
            probe = home / "sandbox-probe"
            message = '<probe>{"write":1,"ssh_read":1,"network":7}</probe>'
            with mock.patch.object(Path, "home", return_value=home), \
                    mock.patch.object(sandbox, "PROBE_PATH", probe), \
                    mock.patch.object(sandbox.shutil, "which", return_value="/usr/bin/curl"), \
                    mock.patch.dict(os.environ, {"LOOP_CODEX": str(fake),
                                                 "FAKE_MESSAGE": message}, clear=True):
                self.assertEqual(sandbox.codex_probe(root),
                                 (True, "Codex sandbox blocked the home write, SSH read and outside network request"))
                self.assertFalse(probe.exists())
                with mock.patch.dict(os.environ, {"LOOP_CODEX": str(fake),
                                                   "FAKE_MESSAGE": '<probe>{"write":1,"ssh_read":0,"network":7}</probe>'},
                                     clear=True):
                    active, detail = sandbox.codex_probe(root)
                self.assertFalse(active)
                self.assertIn("~/.ssh", detail)


if __name__ == "__main__":
    unittest.main()
