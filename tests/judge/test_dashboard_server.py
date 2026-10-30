"""A live, read-only view of every piece and the run, served on localhost."""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import select
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import FakeGitHub

# isort: split
import dashboard
import dashboard_server
import gate
import network
import run
import run_cli
from loopkit import record_text

KIT = Path(__file__).resolve().parents[2] / "kit"
SCRIPT = KIT / "scripts" / "dashboard_server.py"
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'")


def issue(gh, state, title="A piece", depends=()):
    """A piece in the given state; a ready piece carries a ready record."""
    n = gh.create_issue(title, "", ["state:" + state])
    if state == "ready":
        gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": list(depends)}},
                                  "ready"))
    return n


def hand_back(gh, n, reason, author="OWNER", move="give-back"):
    gh.comment(n, record_text({"move": move, "reason": reason, "type": "stopped"}, move), author)


class Spy(FakeGitHub):
    """Remembers which methods were called."""

    def __init__(self):
        super().__init__()
        self.calls = set()

    def __getattribute__(self, name):
        if name in ("issue", "issues_with_label", "comments", "pr_for_branch", "comment",
                    "set_labels", "close", "edit_body", "create_issue", "create_pr",
                    "edit_pr", "merge_pr", "ensure_label"):
            object.__getattribute__(self, "calls").add(name)
        return object.__getattribute__(self, name)


class Base(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gh = FakeGitHub()
        self.events_path = self.root / ".loop" / "events.jsonl"

    def event(self, name, piece=None, state="", attempt=0, reason="", pieces=None):
        dashboard.run_event(self.root, name, piece, state, attempt, reason, pieces)

    def hold_lock(self):
        lock = self.root / ".loop" / "run.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": os.getpid(), "children": []}))

    def snapshot(self):
        return dashboard_server.snapshot(self.root, self.gh)

    def piece(self, n):
        return next(p for p in self.snapshot()["pieces"] if p["number"] == n)


class Served(Base):
    def serve(self, gh=None, **options):
        self.server = dashboard_server.Dashboard(self.root, gh or self.gh, **options)
        self.addCleanup(self.server.close)
        self.server.start()
        return self.server

    def request(self, path="/", method="GET", cookie=True, host=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=10)
        self.addCleanup(connection.close)
        send = dict(headers or {})
        if cookie is True:
            send["Cookie"] = "loop_dashboard=" + self.server.token
        elif cookie:
            send["Cookie"] = cookie
        connection.putrequest(method, path, skip_host=True)
        connection.putheader("Host", host or f"127.0.0.1:{self.server.port}")
        for key, value in send.items():
            connection.putheader(key, value)
        connection.endheaders()
        response = connection.getresponse()
        return response.status, response, response.read()

    def state(self):
        status, _, body = self.request("/api/state")
        self.assertEqual(status, 200)
        return json.loads(body)

    def stream(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=10)
        self.addCleanup(connection.close)
        connection.putrequest("GET", "/api/events", skip_host=True)
        connection.putheader("Host", f"127.0.0.1:{self.server.port}")
        connection.putheader("Cookie", "loop_dashboard=" + self.server.token)
        connection.endheaders()
        sock = connection.sock
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        response.socket = sock
        return response

    def next_snapshot(self, response, seconds):
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            response.socket.settimeout(left)
            try:
                line = response.fp.readline().decode()
            except TimeoutError:
                return None
            if line.startswith("data: "):
                return json.loads(line[6:])
        return None


class AccessTest(Served):
    def test_D1_the_socket_is_loopback_and_the_url_holds_port_and_token(self):
        server = self.serve()
        self.assertEqual(server.httpd.server_address[0], "127.0.0.1")
        self.assertEqual(server.url, f"http://127.0.0.1:{server.port}/?t={server.token}")
        self.assertGreater(server.port, 0)

    def test_D2_no_cookie_gets_403_without_piece_data(self):
        issue(self.gh, "shaping", "Secret title")
        self.serve()
        for path in ("/", "/api/state", "/api/events", "/app.js"):
            status, _, body = self.request(path, cookie=False)
            self.assertEqual(status, 403, path)
            self.assertNotIn(b"Secret title", body)

    def test_D2_a_wrong_token_gets_403_and_the_right_one_sets_a_cookie(self):
        self.serve()
        status, _, _ = self.request("/?t=wrong", cookie=False)
        self.assertEqual(status, 403)
        status, response, _ = self.request("/?t=" + self.server.token, cookie=False)
        self.assertEqual((status, response.getheader("Location")), (302, "/"))
        cookie = response.getheader("Set-Cookie")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        value = cookie.split(";", 1)[0]
        self.assertEqual(self.request("/", cookie=value)[0], 200)
        self.assertEqual(self.request("/", cookie="loop_dashboard=wrong")[0], 403)

    def test_D3_a_foreign_host_header_gets_403_even_with_the_cookie(self):
        self.serve()
        for host in ("evil.example", f"evil.example:{self.server.port}", "127.0.0.1",
                     f"127.0.0.1:{self.server.port + 1}"):
            self.assertEqual(self.request("/api/state", host=host)[0], 403, host)
        self.assertEqual(self.request("/api/state", host=f"localhost:{self.server.port}")[0], 200)


class ProcessTest(Base):
    def environment(self):
        bin_folder = self.root / "bin"
        bin_folder.mkdir(exist_ok=True)
        fake = bin_folder / "gh"
        fake.write_text("#!/bin/sh\nexit 1\n")
        fake.chmod(0o755)
        return {**os.environ, "PATH": f"{bin_folder}:{os.environ['PATH']}",
                "PYTHONDONTWRITEBYTECODE": "1"}

    def project(self, name):
        folder = self.root / name
        folder.mkdir()
        subprocess.run(["git", "init", "--quiet", str(folder)], check=True)
        return folder

    def launch(self, folder):
        process = subprocess.Popen([sys.executable, str(SCRIPT)], cwd=folder, text=True,
                                   env=self.environment(), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        def stop():
            process.terminate()
            process.wait(timeout=20)
            process.stdout.close()
            process.stderr.close()
        self.addCleanup(stop)
        ready, _, _ = select.select([process.stdout], [], [], 30)
        self.assertTrue(ready, "the server printed nothing")
        return process, process.stdout.readline().strip()

    def test_D1_the_command_prints_the_url_and_keeps_the_token_in_a_private_file(self):
        folder = self.project("one")
        _, line = self.launch(folder)
        info = json.loads((folder / ".loop" / "dashboard.json").read_text())
        self.assertEqual(line, f"http://127.0.0.1:{info['port']}/?t={info['token']}")
        self.assertEqual(set(info), {"pid", "port", "token"})
        mode = stat.S_IMODE((folder / ".loop" / "dashboard.json").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_D2_two_servers_have_different_tokens_and_a_second_start_reuses_the_first(self):
        first_folder, second_folder = self.project("one"), self.project("two")
        _, first = self.launch(first_folder)
        _, second = self.launch(second_folder)
        self.assertNotEqual(first.split("?t=")[1], second.split("?t=")[1])
        again = subprocess.run([sys.executable, str(SCRIPT)], cwd=first_folder, text=True,
                               env=self.environment(), capture_output=True, timeout=30)
        self.assertEqual((again.returncode, again.stdout.strip()), (0, first))

    def test_the_script_is_started_like_the_other_kit_scripts(self):
        text = SCRIPT.read_text()
        self.assertTrue(text.startswith("#!/usr/bin/env python3"))
        self.assertIn("kit_python.require()", text)
        self.assertTrue(os.access(SCRIPT, os.X_OK))


class StateTest(Served):
    def test_D4_each_piece_has_the_listed_fields(self):
        number = issue(self.gh, "shaping", "Shape me")
        self.serve()
        pieces = self.state()["pieces"]
        self.assertEqual([p["number"] for p in pieces], [number])
        self.assertEqual(set(pieces[0]),
                         {"number", "title", "lane", "stage", "attempt", "since", "last_event",
                          "pr_url", "waiting_on", "handback_reason"})
        self.assertEqual((pieces[0]["lane"], pieces[0]["title"]), ("to-shape", "Shape me"))
        self.assertEqual(set(self.state()), {"run", "pieces", "notices"})
        self.assertEqual(set(self.state()["run"]), {"status", "started", "starting"})

    def test_D4_each_state_maps_to_its_lane(self):
        shaping = issue(self.gh, "shaping")
        ready = issue(self.gh, "ready")
        building = issue(self.gh, "building")
        approval = issue(self.gh, "approval")
        self.gh.prs[f"piece/{approval}"] = {"url": "https://example.invalid/pull/1",
                                            "state": "OPEN"}
        self.event("run-start", reason="started")
        self.event("submit", approval, "approval", 2, "submit")
        self.event("claim", building, "building", 1, "claim")
        lanes = {p["number"]: (p["lane"], p["stage"], p["attempt"], p["last_event"],
                               p["pr_url"]) for p in self.snapshot()["pieces"]}
        self.assertEqual(lanes[shaping][:2], ("to-shape", "shaping"))
        self.assertEqual(lanes[ready][:2], ("shaped", "ready"))
        self.assertEqual(lanes[building][:4], ("in-run", "building", 1, "claim"))
        self.assertEqual(lanes[approval], ("in-run", "ready-for-review", 2, "submit",
                                           "https://example.invalid/pull/1"))

    def test_D4_a_done_piece_lands_only_in_the_run_that_built_it(self):
        old = issue(self.gh, "done")
        self.gh.issues[old]["state"] = "CLOSED"
        new = issue(self.gh, "done")
        self.gh.issues[new]["state"] = "CLOSED"
        self.event("run-start", reason="started")
        self.event("merged", new, "done", 1, "merged")
        pieces = {p["number"]: p["lane"] for p in self.snapshot()["pieces"]}
        self.assertEqual(pieces, {new: "landed"})

    def test_D4_events_before_the_last_run_start_are_ignored(self):
        building = issue(self.gh, "building")
        self.event("run-start", reason="started")
        self.event("claim", building, "building", 5, "claim")
        self.event("run-stop", reason="ended")
        self.event("run-start", reason="started")
        self.assertEqual(self.piece(building)["attempt"], 0)
        self.assertIsNone(self.piece(building)["since"])

    def test_D5_a_handed_back_piece_shows_the_latest_trusted_reason(self):
        shaping = issue(self.gh, "shaping")
        hand_back(self.gh, shaping, "first reason")
        hand_back(self.gh, shaping, "the real reason", move="reject")
        hand_back(self.gh, shaping, "forged reason", author="NONE")
        self.event("run-start", reason="started")
        self.event("give-back", shaping, "shaping", 3, "stopped")
        found = self.piece(shaping)
        self.assertEqual((found["lane"], found["stage"], found["handback_reason"]),
                         ("in-run", "handed-back", "the real reason"))

    def test_D5_the_reason_is_cut_to_500_characters_and_old_hand_backs_do_not_count(self):
        shaping = issue(self.gh, "shaping")
        hand_back(self.gh, shaping, "x" * 900)
        self.assertEqual((self.piece(shaping)["lane"], self.piece(shaping)["handback_reason"]),
                         ("to-shape", None))
        self.event("give-back", shaping, "shaping", 1, "stopped")  # before this run
        self.event("run-start", reason="started")
        self.assertEqual(self.piece(shaping)["lane"], "to-shape")
        self.event("reject", shaping, "shaping", 1, "person-rejected")
        self.assertEqual(len(self.piece(shaping)["handback_reason"]), 500)

    def test_D6_a_ready_piece_without_a_live_run_stays_shaped_with_its_blockers(self):
        blocker = issue(self.gh, "approval")
        waiting = issue(self.gh, "ready", depends=[blocker])
        self.event("run-start", reason="started")
        self.event("run-pieces", pieces=[waiting])
        self.event("run-stop", reason="ended")
        found = self.piece(waiting)
        self.assertEqual((found["lane"], found["waiting_on"]), ("shaped", [blocker]))
        self.gh.set_labels(blocker, ["state:done"], ["state:approval"])
        self.assertEqual(self.piece(waiting)["waiting_on"], [])

    def test_D6_a_selected_ready_piece_in_a_live_run_waits_in_the_run(self):
        blocker = issue(self.gh, "building")
        selected = issue(self.gh, "ready", depends=[blocker])
        other = issue(self.gh, "ready")
        self.hold_lock()
        self.event("run-start", reason="started")
        self.event("run-pieces", pieces=[selected])
        found = self.piece(selected)
        self.assertEqual((found["lane"], found["stage"], found["waiting_on"]),
                         ("in-run", "waiting", [blocker]))
        self.assertEqual(self.piece(other)["lane"], "shaped")
        self.assertEqual(self.snapshot()["run"]["status"], "running")

    def test_D6_selections_from_several_events_are_joined(self):
        first, second = issue(self.gh, "ready"), issue(self.gh, "ready")
        self.hold_lock()
        self.event("run-start", reason="started")
        self.event("run-pieces", pieces=[first])
        self.event("run-pieces", pieces=[first, second])
        self.assertEqual([self.piece(n)["lane"] for n in (first, second)], ["in-run"] * 2)

    def test_D6_a_run_that_died_leaves_the_selected_piece_in_shaped(self):
        number = issue(self.gh, "ready")
        self.event("run-start", reason="started")
        self.event("run-pieces", pieces=[number])
        self.assertEqual(self.piece(number)["lane"], "shaped")
        self.assertNotEqual(self.snapshot()["run"]["status"], "running")

    def test_D8_a_label_that_disagrees_with_the_events_is_reported(self):
        number = issue(self.gh, "ready")
        self.event("run-start", reason="started")
        self.event("claim", number, "building", 1, "claim")
        notices = self.snapshot()["notices"]
        self.assertTrue(any("disagree" in note and "GitHub labels are the source of truth" in note
                            for note in notices), notices)
        self.assertEqual(self.piece(number)["lane"], "shaped")

    def test_D8_an_unreadable_event_line_becomes_a_notice(self):
        number = issue(self.gh, "shaping")
        self.event("run-start", reason="started")
        with self.events_path.open("a") as out:
            out.write("not json\n")
        self.assertIn("Part of the event file could not be read.", self.snapshot()["notices"])
        self.assertEqual(self.piece(number)["lane"], "to-shape")

    def test_D8_unreachable_github_serves_local_state_with_a_notice(self):
        for error in (RuntimeError("down"), network.StepTimeout("gh issue list ran long")):
            with self.subTest(error=type(error).__name__):
                gh = FakeGitHub()
                number = issue(gh, "ready")
                gh.issues_with_label = lambda *a, **k: (_ for _ in ()).throw(error)
                gh.issue = lambda n: (_ for _ in ()).throw(error)
                self.event("run-start", reason="started")
                self.event("run-pieces", pieces=[number])
                self.event("claim", number, "building", 1, "claim")
                found = dashboard_server.snapshot(self.root, gh)
                self.assertTrue(any("GitHub" in note for note in found["notices"]))
                self.assertEqual([(p["number"], p["lane"], p["title"]) for p in found["pieces"]],
                                 [(number, "in-run", f"Piece {number}")])

    def test_D8_the_server_keeps_running_when_github_fails(self):
        gh = FakeGitHub()
        gh.issues_with_label = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
        self.serve(gh)
        first = self.state()
        self.assertTrue(first["notices"])
        self.assertEqual(self.request("/api/state")[0], 200)


class StreamTest(Served):
    def test_D7_an_appended_event_reaches_a_connected_client_within_3_seconds(self):
        number = issue(self.gh, "building")
        self.serve(poll=0.2)
        stream = self.stream()
        first = self.next_snapshot(stream, 5)
        self.assertEqual(first["pieces"][0]["last_event"], None)
        self.event("claim", number, "building", 4, "claim")
        update = self.next_snapshot(stream, 3)
        self.assertIsNotNone(update, "no snapshot within 3 seconds")
        self.assertEqual((update["pieces"][0]["attempt"], update["pieces"][0]["last_event"]),
                         (4, "claim"))

    def test_D7_a_github_only_change_appears_without_a_local_event(self):
        number = issue(self.gh, "shaping")
        self.serve(poll=0.1, refresh=0.5)
        stream = self.stream()
        self.assertEqual(self.next_snapshot(stream, 5)["pieces"][0]["lane"], "to-shape")
        self.gh.set_labels(number, ["state:ready"], ["state:shaping"])
        update = self.next_snapshot(stream, 5)
        self.assertEqual(update["pieces"][0]["lane"], "shaped")

    def test_D7_the_default_timings_meet_the_spec(self):
        self.assertLessEqual(dashboard_server.POLL_SECONDS, 1)
        self.assertEqual(dashboard_server.GITHUB_SECONDS, 20)

    def test_D7_a_late_client_starts_with_the_whole_snapshot(self):
        issue(self.gh, "shaping", "Already there")
        self.serve(poll=0.2)
        stream = self.stream()
        self.assertEqual(self.next_snapshot(stream, 5)["pieces"][0]["title"], "Already there")


class ReadOnlyTest(Served):
    def tree(self):
        out = {}
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return out

    def test_D13_other_methods_return_405_except_an_authenticated_post_to_the_run_path(self):
        self.serve()
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
            status, _, _ = self.request("/api/state", method=method)
            self.assertEqual(status, 405, method)
        for method in ("PUT", "DELETE", "PATCH", "OPTIONS"):
            status, _, _ = self.request("/api/run", method=method)
            self.assertEqual(status, 405, method)
        self.assertEqual(self.request("/api/run", method="POST", cookie=False)[0], 403)

    def test_D9_get_and_head_write_nothing_and_change_nothing_on_github(self):
        gh = Spy()
        issue(gh, "ready")
        issue(gh, "approval")
        self.event("run-start", reason="started")
        gh.calls.clear()
        self.serve(gh)
        self.state()
        before = self.tree()
        for path in ("/", "/app.js", "/app.css", "/api/state", "/missing"):
            self.request(path)
            self.request(path, method="HEAD")
        self.request("/?t=" + self.server.token, cookie=False)
        self.assertEqual(self.tree(), before)
        self.assertTrue(gh.calls)
        self.assertLessEqual(gh.calls, {"issue", "issues_with_label", "comments",
                                        "pr_for_branch"})

    def test_D9_head_returns_headers_and_no_body(self):
        self.serve()
        status, response, body = self.request("/", method="HEAD")
        self.assertEqual((status, body), (200, b""))
        self.assertIn("text/html", response.getheader("Content-Type"))

    def test_the_server_writes_only_its_own_file_in_the_loop_folder(self):
        self.serve()
        self.assertEqual(sorted(p.name for p in (self.root / ".loop").iterdir()),
                         ["dashboard.json"])


class ContentTest(Served):
    def test_D10_every_response_carries_the_content_security_policy(self):
        self.serve()
        cases = [("/", True, "GET"), ("/app.js", True, "GET"), ("/app.css", True, "GET"),
                 ("/api/state", True, "GET"), ("/missing", True, "GET"),
                 ("/", False, "GET"), ("/?t=" + self.server.token, False, "GET"),
                 ("/", True, "POST")]
        for path, cookie, method in cases:
            _, response, _ = self.request(path, method=method, cookie=cookie)
            self.assertEqual(response.getheader("Content-Security-Policy"), CSP,
                             (path, method))
        stream = self.stream()
        self.assertEqual(stream.getheader("Content-Security-Policy"), CSP)

    def test_D10_a_script_in_a_title_is_data_and_the_page_script_has_no_inner_html(self):
        title = "<script>alert(1)</script>"
        issue(self.gh, "shaping", title)
        self.serve()
        status, response, body = self.request("/api/state")
        self.assertEqual(response.getheader("Content-Type").split(";")[0], "application/json")
        self.assertEqual(json.loads(body)["pieces"][0]["title"], title)
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        script = self.request("/app.js")[2].decode()
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            self.assertNotIn(banned, script)
        self.assertIn("textContent", script)
        self.assertIn("EventSource", script)
        page = self.request("/")[2].decode()
        self.assertIn('src="/app.js"', page)
        self.assertNotIn("<script>", page)
        for lane in ("To shape", "Shaped", "In the run", "Landed"):
            self.assertIn(lane, script + page)


class RunPiecesTest(Base):
    def cli(self, ready, build=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for target, name, value in ((run_cli, "repo_root", self.root),
                                    (run_cli, "GitHub", self.gh)):
            stack.enter_context(patch.object(target, name, return_value=value))
        stack.enter_context(patch.object(run_cli.signal, "signal"))
        stack.enter_context(patch.object(run_cli.base_check, "confirm"))
        stack.enter_context(patch.object(gate, "ignore_loop_folder"))
        stack.enter_context(patch.object(gate, "sync"))
        stack.enter_context(patch.object(run, "recover_building", return_value=[]))
        stack.enter_context(patch.object(run, "cleanup_interrupted_reviews", return_value=[]))
        stack.enter_context(patch.object(run, "ready_pieces", return_value=ready))
        stack.enter_context(patch.object(run, "build_piece", side_effect=build or (
            lambda gh, root, n, *a: f"piece {n}: built")))
        stack.enter_context(patch.object(run, "acquire_lock",
                                         return_value=self.root / "lock-file"))
        stack.enter_context(patch.object(run, "release_lock"))
        out = io.StringIO()
        stack.enter_context(redirect_stdout(out))
        run.main(["--attended"])
        return out.getvalue()

    def events(self):
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text().splitlines()]

    def test_D12_a_run_with_pieces_records_them_after_the_start(self):
        first, second = issue(self.gh, "ready"), issue(self.gh, "ready")
        self.cli([first, second])
        names = [(e["event"], e.get("pieces")) for e in self.events()]
        self.assertEqual(names[0], ("run-start", None))
        self.assertEqual(names[1], ("run-pieces", [first, second]))
        self.assertIsNone(self.events()[1]["piece"])

    def test_D12_an_empty_run_writes_no_run_pieces_event(self):
        self.cli([])
        self.assertEqual([e["event"] for e in self.events()], ["run-start", "run-stop"])

    def test_D12_the_event_is_written_again_only_when_pieces_join(self):
        run_cli.record_pieces(self.root, [4, 5], [])
        known = run_cli.record_pieces(self.root, [4, 5], [4, 5])
        known = run_cli.record_pieces(self.root, [4, 5, 6], known)
        self.assertEqual(known, [4, 5, 6])
        self.assertEqual([e["pieces"] for e in self.events()], [[4, 5], [4, 5, 6]])

    def test_D12_other_events_keep_their_fields(self):
        dashboard.run_event(self.root, "claim", 3, "building", 1, "claim")
        self.assertEqual(set(self.events()[0]),
                         {"time", "piece", "event", "state", "attempt", "reason"})

    def test_D12_a_piece_in_approval_is_ready_for_review_in_the_run(self):
        number = issue(self.gh, "approval")
        dashboard.run_event(self.root, "run-start", reason="started")
        dashboard.run_event(self.root, "run-pieces", pieces=[number])
        found = dashboard_server.snapshot(self.root, self.gh)["pieces"][0]
        self.assertEqual((found["lane"], found["stage"]), ("in-run", "ready-for-review"))


class StaysTest(Base):
    def test_D11_the_static_page_and_its_path_remain(self):
        number = issue(self.gh, "ready")
        dashboard.run_event(self.root, "run-start", reason="started")
        path = dashboard.render(self.root, self.gh, [number])
        self.assertEqual(path, self.root / ".loop" / "dashboard.html")
        self.assertTrue(path.is_file())
        self.assertIn("Run progress", path.read_text())
        self.assertIn("Run page: {root / '.loop' / 'dashboard.html'}",
                      (KIT / "scripts" / "run_cli.py").read_text())


if __name__ == "__main__":
    unittest.main()
