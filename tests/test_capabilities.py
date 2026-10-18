"""Shaping roles share a launcher and refuse unavailable tools."""
from __future__ import annotations

import helpers

# isort: split

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agents


class CapabilityTest(unittest.TestCase):
    def test_researcher_starts_on_both_backends_with_web_only_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for backend in ("claude", "codex"):
                with self.subTest(backend=backend), patch.object(subprocess, "Popen") as start, \
                        patch.object(agents, "command_env", return_value={}):
                    agents.start_session(backend, "Check the timeout API", folder,
                                         role="researcher")
                    args = start.call_args.args[0]
                    if backend == "claude":
                        self.assertIn("--tools", args)
                        self.assertEqual(args[args.index("--tools") + 1], "WebSearch,WebFetch")
                        self.assertIn("--strict-mcp-config", args)
                    else:
                        self.assertIn('web_search="live"', args)
                        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
                        self.assertIn("shell_tool", args)
                        self.assertIn("--ignore-user-config", args)

    def test_network_policy_refuses_research_before_starting_either_backend(self):
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend), patch.object(subprocess, "Popen") as start:
                with self.assertRaisesRegex(ValueError, "researcher.*requires.*web-"):
                    agents.start_session(backend, "question", Path.cwd(),
                                         role="researcher", walk_away=True)
                start.assert_not_called()

    def fake_cli(self, folder):
        path = folder / "fake-agent"
        path.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "pathlib.Path(os.environ['ARGS']).write_text(json.dumps(sys.argv[1:]))\n"
            "text = os.environ['ANSWER']\n"
            "event = ({'type':'assistant','message':{'content':[{'type':'text','text':text}]}}\n"
            " if '-p' in sys.argv else {'type':'item.completed','item':"
            "{'type':'agent_message','text':text}})\n"
            "intro = json.loads(json.dumps(event))\n"
            "if '-p' in sys.argv: intro['message']['content'][0]['text'] = 'Checking sources'\n"
            "else: intro['item']['text'] = 'Checking sources'\n"
            "print(json.dumps(intro))\n"
            "print(json.dumps(event))\n"
            "sys.stdout.write(os.environ.get('TAIL_EVENT', ''))\n"
            "sys.exit(int(os.environ.get('EXIT_CODE', '0')))\n"
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def invoke(self, folder, backend, role, data, answer, exit_code=0, tail=""):
        helpers.git(folder, "init", "--quiet")
        source = folder / "input.json"
        source.write_text(json.dumps(data))
        output = folder / "answer.txt"
        fake = self.fake_cli(folder)
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "ARGS": str(folder / "args.json"), "ANSWER": answer,
               "EXIT_CODE": str(exit_code), "TAIL_EVENT": tail}
        result = subprocess.run(
            [sys.executable, str(helpers.KIT / "scripts/session.py"),
             "--role", role, "--agent", backend, "--input", str(source),
             "--output", str(output), "--folder", str(folder)],
            env=env, capture_output=True, text=True, timeout=10, check=False)
        return result, output

    def test_research_cli_returns_dated_findings_on_both_backends(self):
        finding = "- R1: Timeout is supported (source: https://example.test/api, read: 2026-10-15)"
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for backend in ("claude", "codex"):
                with self.subTest(backend=backend):
                    result, output = self.invoke(folder, backend, "researcher",
                                                 {"question": "Does it accept a timeout?"}, finding)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(output.read_text().strip(), finding)
                    args = json.loads((folder / "args.json").read_text())
                    self.assertIn("Does it accept a timeout?", " ".join(args))
                    self.assertIn("Open every page", " ".join(args))

    def test_judge_cli_uses_approved_fields_and_validates_verdict(self):
        data = {"Intent": "Keep a habit", "Approach": "",
                "Contract": "D1: keep the habit"}
        verdict = '<verdict>{"judge_files":["judge.py"],"tests_per_id":true,"notes":"ok"}</verdict>'
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for backend in ("claude", "codex"):
                with self.subTest(backend=backend):
                    result, output = self.invoke(folder, backend, "judge-writer", data, verdict)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(output.read_text().strip(), verdict)
                    prompt = " ".join(json.loads((folder / "args.json").read_text()))
                    self.assertIn("Keep a habit", prompt)
                    self.assertIn("D1: keep the habit", prompt)
                    result, _ = self.invoke(folder, backend, "judge-writer",
                                            {**data, "chat": "unapproved conversation"}, verdict)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("input", result.stderr)

    def test_failed_final_event_without_newline_cannot_reuse_a_valid_verdict(self):
        data = {"Intent": "Keep a habit", "Approach": "", "Contract": "D1: keep it"}
        verdict = '<verdict>{"judge_files":["judge.py"],"tests_per_id":true,"notes":"ok"}</verdict>'
        for backend in ("claude", "codex"):
            tail = ({"type": "result", "is_error": True, "result": "tool unavailable"}
                    if backend == "claude" else
                    {"type": "turn.failed", "error": "tool unavailable"})
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as temporary:
                result, output = self.invoke(Path(temporary), backend, "judge-writer", data,
                                             verdict, tail=json.dumps(tail))
                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())
                self.assertIn("tool unavailable", result.stderr)

    def test_invalid_judge_verdict_stops_both_backends(self):
        data = {"Intent": "Keep a habit", "Approach": "", "Contract": "D1: keep it"}
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as temporary:
                result, output = self.invoke(Path(temporary), backend, "judge-writer", data,
                                             '<verdict>{"tests_per_id":false}</verdict>')
                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())
                self.assertIn("judge-writer verdict", result.stderr)

    def test_failed_or_unchecked_research_cannot_produce_output(self):
        finding = "- R1: Supported (source: https://example.test/api, read: 2026-10-15)"
        for backend in ("claude", "codex"):
            for answer, code in (("Web search is unavailable", 0), (finding, 1),
                                 ("- R1: An unchecked claim", 0)):
                with self.subTest(backend=backend, answer=answer, code=code), \
                        tempfile.TemporaryDirectory() as temporary:
                    folder = Path(temporary)
                    result, output = self.invoke(folder, backend, "researcher",
                                                 {"question": "Check it"}, answer, code)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertIn("next:", result.stderr)
                    self.assertIn("web-search", result.stderr)
                    self.assertIn("web-open", result.stderr)


if __name__ == "__main__":
    unittest.main()
