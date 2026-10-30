"""The dashboard starts a detached walk-away run for the ticked ready pieces."""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import sys
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import SPEC, Project
from judge.test_dashboard_server import Served, issue

# isort: split
import gate
import run
import run_cli
from loopkit import record_text

PASS = [(True, "the sandbox works", "")]
FAIL = [(True, "the first check", ""), (False, "Prepare is red on main", "fix the Prepare command"),
        (False, "no network rule", "install the tool")]


class RunStartCase(Served):
    def setUp(self):
        super().setUp()
        self.started = []
        self.checks = PASS
        patcher = patch.object(run_cli, "start_detached", side_effect=self.fake_start)
        patcher.start()
        self.addCleanup(patcher.stop)
        doctor = patch.object(gate, "doctor", side_effect=lambda *a, **k: self.checks)
        self.doctor = doctor.start()
        self.addCleanup(doctor.stop)

    def fake_start(self, root, argv, command=None):
        self.started.append(argv)
        return 4242, root / ".loop" / "logs" / "run-20261030T000000Z.log"

    def post(self, body, token=True, cookie=True, kind="application/json", origin=None,
             raw=None):
        headers = {"Content-Type": kind}
        if token is True:
            headers["X-Loop-Token"] = self.server.token
        elif token:
            headers["X-Loop-Token"] = token
        if origin:
            headers["Origin"] = origin
        if cookie:
            headers["Cookie"] = "loop_dashboard=" + self.server.token
        data = raw if raw is not None else json.dumps(body).encode()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=20)
        self.addCleanup(connection.close)
        connection.request("POST", "/api/run", data, {
            "Host": f"127.0.0.1:{self.server.port}", "Content-Length": str(len(data)), **headers})
        response = connection.getresponse()
        text = response.read()
        return response.status, json.loads(text) if text.startswith(b"{") else text


class StartTest(RunStartCase):
    def test_D1_ready_pieces_start_a_detached_walk_away_run_and_answer_202_with_the_pid(self):
        first, second = issue(self.gh, "ready"), issue(self.gh, "ready")
        self.serve()
        status, answer = self.post({"pieces": [first, second], "keep_going": False})
        self.assertEqual(status, 202)
        self.assertEqual(answer["pid"], 4242)
        self.assertIn("run-", answer["log"])
        self.assertEqual(self.started, [["--walk-away", str(first), str(second)]])
        self.doctor.assert_called_once()
        self.assertEqual(self.doctor.call_args.kwargs["pieces"], [first, second])
        self.assertTrue(self.doctor.call_args.kwargs["walk_away"])

    def test_D1_the_real_launcher_logs_to_the_run_log_in_its_own_session(self):
        number = issue(self.gh, "ready")
        self.serve()
        real = run_cli.start_detached
        with patch.object(run_cli, "start_detached", side_effect=lambda root, argv: real(
                root, argv, ["true"])), redirect_stdout(io.StringIO()):
            status, answer = self.post({"pieces": [number]})
        self.assertEqual(status, 202)
        self.assertEqual(Path(answer["log"]).parent, self.root / ".loop" / "logs")

    def test_D2_keep_going_true_adds_the_flag_and_false_or_missing_does_not(self):
        number = issue(self.gh, "ready")
        self.serve()
        for body, flag in (({"pieces": [number], "keep_going": True}, True),
                           ({"pieces": [number], "keep_going": False}, False),
                           ({"pieces": [number]}, False)):
            self.started.clear()
            self.assertEqual(self.post(body)[0], 202)
            self.assertEqual("--keep-going" in self.started[0], flag, body)

    def test_D3_bad_lists_and_pieces_that_are_not_ready_start_nothing(self):
        ready = issue(self.gh, "ready")
        shaping = issue(self.gh, "shaping")
        self.serve()
        cases = [({"pieces": []}, 400), ({"pieces": [ready, ready]}, 400),
                 ({"pieces": ["1"]}, 400), ({"pieces": [True]}, 400), ({"pieces": ready}, 400),
                 ({"keep_going": True}, 400), ({"pieces": [ready], "keep_going": "yes"}, 400),
                 ([ready], 400), ({"pieces": [shaping]}, 409), ({"pieces": [ready, 999]}, 409)]
        for body, expected in cases:
            status, answer = self.post(body)
            self.assertEqual(status, expected, body)
            self.assertIn("error", answer)
        self.assertEqual(self.post(None, raw=b"not json")[0], 400)
        self.assertIn(str(shaping), self.post({"pieces": [shaping]})[1]["error"])
        self.assertEqual(self.started, [])

    def test_D3_a_piece_that_left_ready_after_the_page_loaded_is_refused(self):
        number = issue(self.gh, "ready")
        self.serve()
        self.gh.set_labels(number, ["state:building"], ["state:ready"])
        self.assertEqual(self.post({"pieces": [number]})[0], 409)
        self.assertEqual(self.started, [])

    def test_D4_a_live_run_lock_refuses_with_its_pid(self):
        number = issue(self.gh, "ready")
        self.hold_lock()
        self.serve()
        status, answer = self.post({"pieces": [number]})
        self.assertEqual(status, 409)
        self.assertIn(f"another run is live (pid {os.getpid()})", answer["error"])
        self.assertEqual((self.started, self.doctor.call_count), ([], 0))

    def test_D4_the_launcher_refusing_in_a_race_is_a_409(self):
        from loopkit import Refused
        number = issue(self.gh, "ready")
        self.serve()
        with patch.object(run_cli, "start_detached", side_effect=Refused("another run is live",
                                                                        "wait")):
            self.assertEqual(self.post({"pieces": [number]})[0], 409)

    def test_D5_failed_checks_refuse_with_every_check_and_offer_no_fallback(self):
        number = issue(self.gh, "ready")
        self.checks = FAIL
        self.serve()
        status, answer = self.post({"pieces": [number]})
        self.assertEqual(status, 409)
        self.assertEqual(answer["checks"], [
            {"ok": True, "what": "the first check", "next": ""},
            {"ok": False, "what": "Prepare is red on main", "next": "fix the Prepare command"},
            {"ok": False, "what": "no network rule", "next": "install the tool"}])
        self.assertNotIn("attended", json.dumps(answer).lower())
        self.assertEqual(self.started, [])

    def test_D6_a_second_request_is_refused_while_doctor_runs_and_state_says_starting(self):
        number = issue(self.gh, "ready")
        self.serve()
        entered, release = threading.Event(), threading.Event()

        def slow(*args, **kwargs):
            entered.set()
            release.wait(20)
            return PASS
        self.doctor.side_effect = slow
        results = []
        worker = threading.Thread(target=lambda: results.append(self.post({"pieces": [number]})))
        worker.start()
        self.assertTrue(entered.wait(10))
        try:
            self.assertIs(self.state()["run"]["starting"], True)
            status, answer = self.post({"pieces": [number]})
            self.assertEqual(status, 409)
            self.assertIn("being started", answer["error"])
        finally:
            release.set()
            worker.join(20)
        self.assertEqual(results[0][0], 202)
        self.assertEqual(len(self.started), 1)
        self.assertIs(self.state()["run"]["starting"], False)

    def test_D6_starting_is_cleared_when_doctor_raises(self):
        number = issue(self.gh, "ready")
        self.serve()
        self.doctor.side_effect = RuntimeError("probe failed")
        self.assertEqual(self.post({"pieces": [number]})[0], 500)
        self.assertIs(self.state()["run"]["starting"], False)


class GuardTest(RunStartCase):
    def test_D7_a_missing_or_wrong_token_header_starts_nothing(self):
        number = issue(self.gh, "ready")
        self.serve()
        for token in (False, "wrong"):
            self.assertEqual(self.post({"pieces": [number]}, token=token)[0], 403)
        self.assertEqual(self.post({"pieces": [number]}, cookie=False)[0], 403)
        self.assertEqual(self.post({"pieces": [number]}, token=False, cookie=False)[0], 403)
        self.assertEqual(self.started, [])

    def test_D7_a_content_type_that_is_not_json_is_415(self):
        number = issue(self.gh, "ready")
        self.serve()
        for kind in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
            self.assertEqual(self.post({"pieces": [number]}, kind=kind)[0], 415, kind)
        self.assertEqual(self.post({"pieces": [number]}, kind="application/json; charset=utf-8")[0],
                         202)
        self.assertEqual(len(self.started), 1)

    def test_D7_a_foreign_origin_is_refused_and_the_servers_own_is_allowed(self):
        number = issue(self.gh, "ready")
        self.serve()
        own = f"http://127.0.0.1:{self.server.port}"
        for origin in ("http://evil.example", "null", f"http://127.0.0.1:{self.server.port + 1}",
                       f"https://127.0.0.1:{self.server.port}"):
            self.assertEqual(self.post({"pieces": [number]}, origin=origin)[0], 403, origin)
        self.assertEqual(self.started, [])
        self.assertEqual(self.post({"pieces": [number]}, origin=own)[0], 202)

    def test_D7_the_page_carries_the_token_for_the_script_and_the_cookie_stays_http_only(self):
        self.serve()
        status, response, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(f'<meta name="loop-token" content="{self.server.token}">', body.decode())
        self.assertNotIn(self.server.token, self.request("/app.js")[2].decode())
        self.assertIn("X-Loop-Token", self.request("/app.js")[2].decode())
        _, redirect, _ = self.request("/?t=" + self.server.token, cookie=False)
        self.assertIn("HttpOnly", redirect.getheader("Set-Cookie"))


class AdviceTest(RunStartCase):
    def ready_with(self, **risks):
        n = self.gh.create_issue("Piece", "", ["state:ready"])
        self.gh.comment(n, record_text({"move": "ready", "risks": risks}, "ready"))
        return n

    def test_D8_a_blocker_that_is_not_done_or_ticked_gives_a_warning_naming_both(self):
        blocker = issue(self.gh, "approval")
        done = issue(self.gh, "done")
        dependent = self.ready_with(depends_on=[blocker, done])
        self.serve()
        status, answer = self.post({"pieces": [dependent]})
        self.assertEqual(status, 202)
        self.assertEqual(len(answer["warnings"]), 1)
        self.assertIn(f"piece {dependent}", answer["warnings"][0])
        self.assertIn(f"piece {blocker}", answer["warnings"][0])

    def test_D8_a_ticked_blocker_gives_no_warning(self):
        blocker = issue(self.gh, "ready")
        dependent = self.ready_with(depends_on=[blocker])
        self.serve()
        self.assertEqual(self.post({"pieces": [blocker, dependent]})[1]["warnings"], [])

    def test_D8_a_piece_that_needs_services_is_refused_with_the_reason(self):
        needing = self.ready_with(needs_services=["postgres"])
        self.serve()
        status, answer = self.post({"pieces": [needing]})
        self.assertEqual(status, 409)
        self.assertIn("postgres", answer["error"])
        self.assertEqual((self.started, self.doctor.call_count), ([], 0))

    def test_D8_the_snapshot_carries_depends_on_and_needs_services_for_shaped_pieces(self):
        blocker = issue(self.gh, "approval")
        piece = self.ready_with(depends_on=[blocker], needs_services=["redis"])
        found = self.snapshot()["pieces"]
        shaped = next(p for p in found if p["number"] == piece)
        self.assertEqual((shaped["depends_on"], shaped["needs_services"]), ([blocker], ["redis"]))
        self.assertEqual(self.snapshot()["run"]["starting"], False)


class RunScriptTest(unittest.TestCase):
    def test_D9_stays_pieces_without_keep_going_build_only_those_and_a_second_run_is_refused(self):
        p = Project()
        self.addCleanup(p.close)
        p.loop_section("true")
        gh, built = p.gh, []
        ready = []
        for _ in range(2):
            n = gh.create_issue("A piece", SPEC, ["state:ready"])
            gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []},
                                       "waiting_limit": "9"}, "ready"))
            ready.append(n)

        def build(gh_, root, n, *args):
            built.append(n)
            gh.set_labels(n, ["state:approval"], ["state:ready"])
            return f"piece {n}: built"

        def main(*argv):
            with patch.object(run_cli, "repo_root", return_value=p.root), \
                    patch.object(run_cli, "GitHub", return_value=gh), \
                    patch.object(run_cli.signal, "signal"), \
                    patch.object(run, "ready_pieces", side_effect=lambda *a: sorted(
                        n for n, i in gh.issues.items() if "state:ready" in i["labels"])), \
                    patch.object(run, "build_piece", side_effect=build), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return run.main(["--attended", *argv])
        lock = p.root / ".loop" / "run.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": os.getpid(), "children": []}))
        self.assertEqual(main(str(ready[0])), 2)
        self.assertEqual(built, [])
        lock.unlink()
        self.assertEqual(main(str(ready[0])), 0)
        self.assertEqual(built, [ready[0]])


class ReadOnlyKept(RunStartCase):
    def test_D13_the_run_start_writes_no_file_of_its_own_and_other_paths_stay_refused(self):
        number = issue(self.gh, "ready")
        self.serve()
        before = {str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                  for f in sorted(self.root.rglob("*")) if f.is_file()}
        self.assertEqual(self.post({"pieces": [number]})[0], 202)
        after = {str(f) for f in self.root.rglob("*") if f.is_file()}
        self.assertEqual(after, set(before))  # the fake launcher writes the log; the server none
        for method in ("PUT", "DELETE", "PATCH", "OPTIONS"):
            self.assertEqual(self.request("/api/run", method=method)[0], 405, method)
        self.assertEqual(self.request("/api/state", method="POST")[0], 405)
        self.assertEqual(self.request("/api/run", method="POST", cookie=False)[0], 403)


if __name__ == "__main__":
    unittest.main()
