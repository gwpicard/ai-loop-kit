"""Unit tests for loop/cli.py: the shared script contract."""

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop import cli  # noqa: E402


def handler_ok(args: Any) -> dict[str, Any]:
    return {"seen": args.name, "dry_run": args.dry_run}


def handler_refuse(args: Any) -> dict[str, Any]:
    raise cli.Failure("nothing is ready", next_command="demo --help", code=cli.ExitCode.REFUSED)


def handler_crash(args: Any) -> dict[str, Any]:
    raise RuntimeError("boom")


def setup(parser: Any) -> None:
    parser.add_argument("name", nargs="?", default="x")


def call(handler: Any, argv: list[str], tty: bool = False) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.run(
            "demo", "A demo.", setup, handler, argv, changes_state=True, stdout_is_tty=tty
        )
    return code, out.getvalue(), err.getvalue()


class ExitCodes(unittest.TestCase):
    def test_codes_are_distinct_and_stable(self) -> None:
        values = [c.value for c in cli.ExitCode]
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual(cli.ExitCode.OK, 0)
        self.assertEqual(cli.ExitCode.USAGE, 2)
        self.assertEqual(cli.ExitCode.REFUSED, 3)


class Run(unittest.TestCase):
    def test_success_prints_json_and_exits_zero(self) -> None:
        code, out, err = call(handler_ok, ["bob"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["ok"])
        self.assertEqual(data["seen"], "bob")
        self.assertEqual(err, "")

    def test_json_when_not_a_terminal_and_with_the_flag(self) -> None:
        for argv in ([], ["--json"]):
            _, out, _ = call(handler_ok, argv, tty=False)
            json.loads(out)

    def test_dry_run_is_passed_on_and_reported(self) -> None:
        _, out, _ = call(handler_ok, ["--dry-run"])
        data = json.loads(out)
        self.assertTrue(data["dry_run"])

    def test_help_exits_zero_and_names_the_flags_and_exit_codes(self) -> None:
        code, out, _ = call(handler_ok, ["--help"])
        self.assertEqual(code, 0)
        for word in ("--json", "--dry-run", "exit codes"):
            self.assertIn(word, out)

    def test_bad_option_exits_two_and_names_the_next_command(self) -> None:
        code, out, err = call(handler_ok, ["--nope"])
        self.assertEqual(code, cli.ExitCode.USAGE)
        self.assertIn("next: demo --help", err)
        self.assertFalse(json.loads(out)["ok"])

    def test_refusal_has_its_own_code_and_a_next_line(self) -> None:
        code, out, err = call(handler_refuse, [])
        self.assertEqual(code, cli.ExitCode.REFUSED)
        self.assertIn("next: demo --help", err)
        data = json.loads(out)
        self.assertFalse(data["ok"])
        self.assertEqual(data["next"], "demo --help")

    def test_a_crash_is_a_failure_not_a_traceback(self) -> None:
        code, out, err = call(handler_crash, [])
        self.assertEqual(code, cli.ExitCode.FAILURE)
        self.assertNotIn("Traceback", err)
        self.assertIn("next:", err)
        self.assertFalse(json.loads(out)["ok"])

    def test_terminal_output_is_plain_text(self) -> None:
        _, out, _ = call(handler_ok, [], tty=True)
        with self.assertRaises(ValueError):
            json.loads(out)

    def test_same_input_gives_same_output(self) -> None:
        self.assertEqual(call(handler_ok, ["a"]), call(handler_ok, ["a"]))

    def test_no_dry_run_flag_when_the_script_changes_nothing(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.run(
                "demo", "A demo.", lambda p: None, lambda a: {}, ["--dry-run"],
                changes_state=False, stdout_is_tty=False,
            )
        self.assertEqual(code, cli.ExitCode.USAGE)


if __name__ == "__main__":
    unittest.main()
