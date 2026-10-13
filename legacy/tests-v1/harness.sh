#!/usr/bin/env sh
# harness.sh: prove the offline test harness works end to end.
#
# It builds a throwaway project, opens an issue through the GitHub stand-in,
# runs a scripted Claude stand-in session that commits one file, and checks the
# commit and the stand-ins' logs. No network, no account, no model.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$ROOT/tests/lib/throwaway-project.sh"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

echo "Harness checks:"

tp_new demo

# --- the project and the stand-in App credential ---------------------------
[ -d "$TP_ROOT/.git" ] || fail "the throwaway project is not a Git repository"
[ "$(git -C "$TP_ROOT" rev-list --count HEAD)" = 1 ] || fail "the project should start with one commit"
ok "the throwaway project is a Git repository with one commit"

[ -f "$TP_APP_KEY" ] || fail "no stand-in App key at $TP_APP_KEY"
openssl rsa -in "$TP_APP_KEY" -check -noout >/dev/null 2>&1 || fail "the stand-in App key is not a valid RSA key"
case "$TP_APP_KEY" in "$TP_ROOT"/*) fail "the App key sits inside the project" ;; esac
[ "$(wc -c <"$TP_APP_KEY" | tr -d ' ')" -gt 500 ] || fail "the App key looks too short"
ok "the stand-in App key was made at test time, outside the project"

if git -C "$ROOT" grep -l 'BEGIN [A-Z ]*PRIVATE KEY' -- . ':(exclude)tests/harness.sh' | grep -q .; then
  fail "a private key is committed in the repository"
fi
ok "no private key is committed in the repository"

# --- an issue through the GitHub stand-in ---------------------------------
url=$(tp_issue "Add a hello file" "Write hello.txt with one line.")
case "$url" in */issues/1) ok "the stand-in opened issue one" ;; *) fail "unexpected issue address: $url" ;; esac
listed=$(cd "$TP_ROOT" && gh issue list --json number,title)
printf '%s' "$listed" | python3 -c '
import json, sys
items = json.load(sys.stdin)
assert [(i["number"], i["title"]) for i in items] == [(1, "Add a hello file")], items
' || fail "the stand-in does not list the issue it opened"
ok "the stand-in lists the issue it opened"

# --- a scripted Claude session ---------------------------------------------
tp_claude_script '{
  "files": {"hello.txt": "hello\n"},
  "commits": [{"message": "Add a hello file", "paths": ["hello.txt"]}],
  "handoff": {"path": ".agents/pieces/1/handoff.md", "content": "Done. One file added.\n"}
}'
result=$(cd "$TP_ROOT" && claude -p "Do the work in issue one" --output-format json)
printf '%s' "$result" | python3 -c '
import json, sys
data = json.load(sys.stdin)
assert data["is_error"] is False, data
assert data["type"] == "result", data
' || fail "the Claude stand-in did not report success"
ok "the Claude stand-in reported success"

[ "$(git -C "$TP_ROOT" rev-list --count HEAD)" = 2 ] || fail "the session should add exactly one commit"
[ "$(git -C "$TP_ROOT" log -1 --format=%s)" = "Add a hello file" ] || fail "wrong commit message"
[ "$(git -C "$TP_ROOT" show --name-only --format= HEAD)" = "hello.txt" ] || fail "the commit holds more than hello.txt"
[ "$(cat "$TP_ROOT/hello.txt")" = hello ] || fail "hello.txt has the wrong content"
ok "the session committed exactly one file, with the scripted message"

[ -f "$TP_ROOT/.agents/pieces/1/handoff.md" ] || fail "the hand-off was not left"
git -C "$TP_ROOT" status --porcelain | grep -q '^?? .agents/' || fail "the hand-off should be left unsaved"
ok "the session left a hand-off that it did not commit"

# --- the stand-ins' logs ----------------------------------------------------
[ "$(wc -l <"$FAKE_CLAUDE_LOG" | tr -d ' ')" = 1 ] || fail "the Claude stand-in log should hold one call"
python3 -c '
import json, sys
line = json.loads(open(sys.argv[1]).readline())
assert line["argv"][:1] == ["-p"], line
assert line["cwd"].endswith("/demo"), line
' "$FAKE_CLAUDE_LOG" || fail "the Claude stand-in log is wrong"
ok "the Claude stand-in logged its call"

grep -q "^CALL	issue create" "$FAKE_GH_LOG" || fail "the GitHub stand-in log has no issue create call"
if grep -q '^UNSUPPORTED' "$FAKE_GH_LOG"; then fail "the GitHub stand-in refused a call"; fi
ok "the GitHub stand-in logged its calls and refused none"

# --- the Claude stand-in refuses what it was not told to do ----------------
unset FAKE_CLAUDE_SCRIPT
if (cd "$TP_ROOT" && claude -p "x" >/dev/null 2>&1); then fail "a session with no script should fail"; fi
ok "a session with no script is refused"

tp_claude_script '{"files": {"../escape.txt": "x"}}'
set +e
(cd "$TP_ROOT" && claude -p "x" >/dev/null 2>&1)
code=$?
set -e
[ "$code" = 3 ] || fail "a script that writes outside the project should exit 3, got $code"
[ ! -e "$TP_BASE/escape.txt" ] || fail "the stand-in wrote outside the project"
ok "a script that writes outside the project is refused"

echo "Harness checks passed."
