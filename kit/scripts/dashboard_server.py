#!/usr/bin/env python3
"""Serve a live view of every piece and the run on localhost.

Usage: `kit-python dashboard_server.py` prints a URL with a token and serves
until closed. It reads `.loop/events.jsonl` and GitHub. Its one action is
`POST /api/run`, which starts a detached walk-away run, and
`POST /api/preferences`, which saves the notification setting, and
`POST /api/answer`, which records the answer to a builder's question.
"""
from __future__ import annotations
if __name__ == "__main__":
    import kit_python
    kit_python.require()

import hmac
import json
import os
import secrets
import signal
import socket
import threading
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import answers
import dashboard_run
import holds
import notifications
import procs
from loopkit import NEEDS_YOU, STATE_PREFIX, GitHub, branch_name, records

POLL_SECONDS = 1.0      # how often the events file is checked
GITHUB_SECONDS = 20.0   # the longest GitHub state goes without a refresh
PAGE = Path(__file__).resolve().parent / "dashboard_page"
FILES = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
         "/app.css": ("app.css", "text/css")}
COOKIE = "loop_dashboard"
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'"
LANE_ORDER = ("to-shape", "shaped", "in-run", "landed")
HANDED_BACK = ("give-back", "reject")
MAX_BODY = 4096
POSTS = ("/api/run", "/api/preferences", "/api/answer")


def read_events(root: Path) -> tuple[list[dict], list[str]]:
    """Events since the last run-start, by the same rules as the static page."""
    events, notices = [], []
    try:
        lines = (root / ".loop" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return events, notices
    for line in lines:
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("not an event")
        except ValueError:
            if "Part of the event file could not be read." not in notices:
                notices.append("Part of the event file could not be read.")
            continue
        if event.get("event") == "run-start":
            events = []
        events.append(event)
    return events, notices


def _states(issue: dict) -> list[str]:
    return [label[len(STATE_PREFIX):] for label in issue["labels"]
            if label.startswith(STATE_PREFIX)]


def _reason(comments: list[str]) -> str | None:
    found = [r for r in records(comments) if r.get("move") in HANDED_BACK]
    return str(found[-1].get("reason", ""))[:500] if found else None


def _link(gh, n: int) -> str | None:
    url = (gh.pr_for_branch(branch_name(n)) or {}).get("url", "")
    return url if urlsplit(url).scheme in ("http", "https") else None


def snapshot(root: Path, gh, starting: bool = False) -> dict:
    """The run, and every piece in its lane. GitHub labels are the source of truth."""
    events, notices = read_events(root)
    boundary = next((e for e in reversed(events) if e.get("event") in ("run-start", "run-stop")),
                    {})
    live = boundary.get("event") == "run-start" and procs.lock_holder(root) is not None
    status = ("running" if live else "interrupted" if boundary.get("event") == "run-start"
              else "finished" if boundary else "none")
    selected = {p for e in events if e.get("event") == "run-pieces"
                for p in e.get("pieces") or [] if isinstance(p, int)}
    latest = {e["piece"]: e for e in events if isinstance(e.get("piece"), int)}
    handed = {e["piece"] for e in events if e.get("event") in HANDED_BACK
              and isinstance(e.get("piece"), int)}
    in_run = selected | set(latest)
    issues, reachable = {}, True
    try:
        issues = {i["number"]: i for i in gh.issues_with_label()}
    except Exception:  # GitHub could not answer, or ran past its time limit
        reachable = False
        notices.append("Could not reach GitHub. Showing local events.")
    numbers = sorted({n for n, i in issues.items()
                      if len(_states(i)) == 1} | in_run)
    pieces, questions, asked = [], set(), None
    for n in numbers:
        event, issue, lost, risks, lane = latest.get(n, {}), issues.get(n), False, {}, None
        try:
            if issue is None and reachable:
                issue = gh.issue(n)
            labels = _states(issue) if issue else []
            if issue and event.get("state") and labels != [event["state"]]:
                notices.append(f"Piece {n}: local events and GitHub labels disagree "
                               f"(page: {event['state']}; GitHub: {', '.join(labels) or 'no state'}). "
                               "GitHub labels are the source of truth.")
            state = labels[0] if len(labels) == 1 else (
                "" if issue else event.get("state") or "ready")
            lane, stage, waiting, reason, url = None, state, [], None, None
            if state == "shaping":
                lane, stage = ("in-run", "handed-back") if n in handed else ("to-shape", "shaping")
                if (n in handed or NEEDS_YOU in issue["labels"]) and reachable:
                    notes = gh.comments(n)
                    reason = _reason(notes) if n in handed else None
                    asked = answers.latest_question(notes)
            elif state == "ready":
                if reachable:
                    risks = dashboard_run.ready_risks(gh, n)
                    waiting = holds.unfinished(gh, tuple(risks.get("depends_on") or []))
                lane = "in-run" if live and n in selected else "shaped"
                stage = "waiting" if lane == "in-run" else "ready"
            elif state == "building":
                lane = "in-run"
            elif state == "approval":
                lane, stage = "in-run", "ready-for-review"
                url = _link(gh, n) if reachable else None
            elif state == "done" and n in in_run:
                lane, stage = "landed", "landed"
                url = _link(gh, n) if reachable else None
        except Exception:
            lost = True
            notices.append(f"Piece {n}: could not check GitHub. Showing local events.")
        if lane is None and not lost:
            continue  # dropped, or done in an earlier run
        if lost:
            state = event.get("state") or "ready"
            lane = {"shaping": "in-run" if n in handed else "to-shape", "ready": "shaped",
                    "done": "landed"}.get(state, "in-run")
            if lane == "shaped" and live and n in selected:
                lane = "in-run"
            stage, waiting, reason, url = state, [], None, None
            issue = None
        found = {"number": n, "title": issue["title"] if issue else f"Piece {n}",
                 "lane": lane, "stage": stage, "attempt": event.get("attempt") or 0,
                 "since": event.get("time"), "last_event": event.get("event"),
                 "pr_url": url, "waiting_on": waiting, "handback_reason": reason}
        if asked:
            found["question"] = asked
            questions.add(n)
            asked = None
        if lane == "shaped":
            found.update(depends_on=risks.get("depends_on") or [],
                         needs_services=risks.get("needs_services") or [])
        pieces.append(found)
    open_questions = {p["number"] for p in pieces if p.get("question", {}).get("answered") is False}
    for p in pieces:
        if blocking := [d for d in p["waiting_on"] if d in open_questions]:
            p["question_blockers"] = blocking
    pieces.sort(key=lambda p: (LANE_ORDER.index(p["lane"]), p["number"]))
    return {"run": {"status": status, "started": next(
                (e.get("time") for e in events if e.get("event") == "run-start"), None),
                    "starting": starting},
            "pieces": pieces, "notices": notices,
            "notifications": notifications.current(root),
            "preferences": notifications.read_preferences(root)}


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


class Handler(BaseHTTPRequestHandler):
    server_version = "LoopDashboard"
    protocol_version = "HTTP/1.0"

    def log_message(self, *args) -> None:
        pass

    def _send(self, status: int, body: bytes = b"", kind: str = "text/plain",
              extra: tuple = ()) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for key, value in extra:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _handle(self) -> None:
        dash: Dashboard = self.server.dash  # type: ignore[attr-defined]
        if self.headers.get("Host") not in dash.hosts:
            return self._send(403, b"forbidden")
        parts = urlsplit(self.path)
        if self.command not in ("GET", "HEAD") and not (
                self.command == "POST" and parts.path in POSTS):
            return self._send(405, b"read only", extra=(("Allow", "GET, HEAD, POST"),))
        token = (parse_qs(parts.query).get("t") or [""])[0]
        if parts.path == "/" and token:
            if not dash.is_token(token):
                return self._send(403, b"forbidden")
            return self._send(302, b"", extra=(
                ("Location", "/"),
                ("Set-Cookie", f"{COOKIE}={dash.token}; HttpOnly; SameSite=Strict; Path=/")))
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            pass
        if COOKIE not in jar or not dash.is_token(jar[COOKIE].value):
            return self._send(403, b"forbidden")
        if self.command == "POST":
            return self._post(dash, parts.path)
        if parts.path in FILES:
            name, kind = FILES[parts.path]
            page = (PAGE / name).read_bytes().replace(b"{{token}}", dash.token.encode())
            return self._send(200, page, kind)
        if parts.path == "/api/state":
            return self._send(200, json.dumps(dash.wait_first()).encode(), "application/json")
        if parts.path == "/api/events":
            return self._stream(dash)
        self._send(404, b"not found")

    def _post(self, dash: Dashboard, path: str) -> None:
        """Start a run, save a setting or record an answer. Needs the token header, JSON and the server's own origin."""
        origin = self.headers.get("Origin")
        if not dash.is_token(self.headers.get("X-Loop-Token", "")) or (
                origin is not None and origin not in {f"http://{h}" for h in dash.hosts}):
            return self._send(403, b"forbidden")
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self._send(415, b"send application/json")
        try:
            size = int(self.headers.get("Content-Length", ""))
            body = json.loads(self.rfile.read(size)) if 0 < size <= MAX_BODY else None
        except ValueError:
            body = None
        if path == "/api/preferences":
            status, answer = notifications.save_preferences(dash.root, body)
            dash.publish()
        elif path == "/api/answer":
            status, answer = dashboard_run.answer(dash, body)
            dash.publish()
        else:
            status, answer = dashboard_run.start(dash, body)
        self._send(status, json.dumps(answer).encode(), "application/json")

    def _stream(self, dash: Dashboard) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.close_connection = True
        if self.command == "HEAD":
            return
        seen = 0
        try:
            while not dash.stopped.is_set():
                seen, text = dash.wait_change(seen)
                chunk = f"data: {text}\n\n" if text else ": keep-alive\n\n"
                self.wfile.write(chunk.encode())
                self.wfile.flush()
        except OSError:
            pass

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _handle


class Dashboard:
    """The server, its token, and the thread that keeps the snapshot current."""

    def __init__(self, root: Path, gh, poll: float = POLL_SECONDS,
                 refresh: float = GITHUB_SECONDS) -> None:
        self.root, self.gh, self.poll, self.refresh = root, gh, poll, refresh
        self.token = secrets.token_urlsafe(32)
        self.httpd = _Server(("127.0.0.1", 0), Handler)
        self.httpd.dash = self  # type: ignore[attr-defined]
        self.port = self.httpd.server_address[1]
        self.hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        self.url = f"http://127.0.0.1:{self.port}/?t={self.token}"
        self.stopped = threading.Event()
        self._changed = threading.Condition()
        self._version, self._text = 0, ""
        self.starting, self.start_lock = False, threading.Lock()
        self.stuck_sent: set = set()
        self._threads: list[threading.Thread] = []

    def is_token(self, value: str) -> bool:
        return hmac.compare_digest(value.encode(), self.token.encode())

    def start(self) -> None:
        info = self.root / ".loop" / "dashboard.json"
        info.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(info, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as out:
            out.write(json.dumps({"pid": os.getpid(), "port": self.port, "token": self.token}))
        os.chmod(info, 0o600)
        for target in (self.httpd.serve_forever, self._watch):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)

    def close(self) -> None:
        self.stopped.set()
        with self._changed:
            self._changed.notify_all()
        self.httpd.shutdown()
        self.httpd.server_close()
        for thread in self._threads:
            thread.join(timeout=5)
        info = self.root / ".loop" / "dashboard.json"
        try:
            if json.loads(info.read_text()).get("token") == self.token:
                info.unlink()
        except (OSError, ValueError):
            pass

    def publish(self) -> None:
        try:
            found = snapshot(self.root, self.gh, self.starting)
            notifications.deliver_stuck(self.root, found["notifications"], self.stuck_sent)
            text = json.dumps(found)
        except Exception as error:  # keep serving; say what failed
            text = json.dumps({"run": {"status": "none", "started": None, "starting": self.starting}, "pieces": [],
                               "notices": [f"Could not build the view: {error}"]})
        with self._changed:
            if text != self._text:
                self._text, self._version = text, self._version + 1
                self._changed.notify_all()
            elif self._version == 0:
                self._version = 1

    def _key(self) -> tuple:
        try:
            size = (self.root / ".loop" / "events.jsonl").stat().st_size
        except OSError:
            size = -1
        return size, procs.lock_holder(self.root)

    def _watch(self) -> None:
        key, last = self._key(), 0.0
        while True:
            self.publish()
            last = time.monotonic()
            while not self.stopped.wait(self.poll):
                now = self._key()
                if now != key or time.monotonic() - last >= self.refresh:
                    key = now
                    break
            if self.stopped.is_set():
                return

    def wait_first(self) -> dict:
        with self._changed:
            self._changed.wait_for(lambda: self._version > 0 or self.stopped.is_set(), 150)
            return json.loads(self._text or "{}")

    def wait_change(self, seen: int) -> tuple[int, str]:
        """The next snapshot after `seen`, or an empty text after a quiet spell."""
        with self._changed:
            self._changed.wait_for(lambda: self._version > seen or self.stopped.is_set(), 15)
            return (self._version, self._text) if self._version > seen else (seen, "")


def live_server(root: Path) -> dict | None:
    """The recorded server for this project when its process is alive and listening."""
    try:
        info = json.loads((root / ".loop" / "dashboard.json").read_text())
        if not procs.process_alive(int(info["pid"])):
            return None
        with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=2):
            return info
    except (OSError, ValueError, KeyError, TypeError):
        return None


def main() -> int:
    from loopkit import repo_root
    root = repo_root(Path.cwd())
    found = live_server(root)
    if found:
        print(f"http://127.0.0.1:{found['port']}/?t={found['token']}", flush=True)
        return 0
    dash = Dashboard(root, GitHub(root))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    dash.start()
    print(dash.url, flush=True)
    try:
        dash.stopped.wait()
    except KeyboardInterrupt:
        pass
    finally:
        dash.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
