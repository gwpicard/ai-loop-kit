#!/usr/bin/env sh
# secret-scan.sh: the secret scan in both of its places.
#
#   1. The pre-push hook, installed in a throwaway project, refuses a push
#      that carries a secret, and allows a clean push.
#   2. The scan, called as the gate's push step will call it (on a commit
#      range), gives the same refusal.
#
# No file here holds a real secret. The fake key is joined from pieces at run
# time. A refusal must name the file and line, and must never print the value.
#
# Run alone: tests/secret-scan.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

SCAN="$ROOT/kit/scripts/secret-scan.py"
HOOK="$ROOT/kit/templates/githooks/pre-push"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

[ -f "$SCAN" ] || fail "missing $SCAN"
[ -f "$HOOK" ] || fail "missing $HOOK"

# shellcheck disable=SC1091
. "$ROOT/tests/lib/throwaway-project.sh"
tp_new secretly
echo "Secret scan checks (project in $TP_ROOT):"

# Install the hook where Git looks for it. The hook finds the scan through
# this variable in a test, and through the kit folder in a real project.
mkdir -p "$TP_ROOT/.githooks"
cp "$HOOK" "$TP_ROOT/.githooks/pre-push"
chmod +x "$TP_ROOT/.githooks/pre-push"
git -C "$TP_ROOT" config core.hooksPath .githooks
AI_LOOP_KIT_SECRET_SCAN="$SCAN"
export AI_LOOP_KIT_SECRET_SCAN

# A fake key built from pieces.
KEY="gh""p_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"

# --- a clean push is allowed -------------------------------------------------
git -C "$TP_ROOT" checkout -q -b clean
printf 'nothing to hide\n' > "$TP_ROOT/clean.txt"
git -C "$TP_ROOT" add clean.txt
git -C "$TP_ROOT" commit -q -m "Add a clean file"
git -C "$TP_ROOT" push -q origin clean 2>"$TP_BASE/clean.err" || {
  cat "$TP_BASE/clean.err"
  fail "the hook refused a clean push"
}
ok "a clean push is allowed"

# --- a push with a secret is refused ----------------------------------------
git -C "$TP_ROOT" checkout -q -b leaky
printf 'one\ntwo\ntoken = %s\n' "$KEY" > "$TP_ROOT/settings.cfg"
git -C "$TP_ROOT" add settings.cfg
git -C "$TP_ROOT" commit -q -m "Add settings"
if git -C "$TP_ROOT" push -q origin leaky 2>"$TP_BASE/push.err"; then
  fail "the hook allowed a push that carries a secret"
fi
grep -q 'settings.cfg' "$TP_BASE/push.err" || { cat "$TP_BASE/push.err"; fail "the refusal does not name the file"; }
grep -q ':3' "$TP_BASE/push.err" || { cat "$TP_BASE/push.err"; fail "the refusal does not name the line"; }
grep -q 'github-token' "$TP_BASE/push.err" || { cat "$TP_BASE/push.err"; fail "the refusal does not name the kind"; }
if grep -q "$KEY" "$TP_BASE/push.err"; then fail "the refusal printed the secret"; fi
if git -C "$TP_BASE/origin.git" rev-parse -q --verify refs/heads/leaky >/dev/null; then
  fail "the leaky branch reached the remote"
fi
ok "the hook refuses the push, naming file, line and kind, and not the value"

# --- the same refusal from a commit range, as the gate's push step calls it --
if (cd "$TP_ROOT" && python3 "$SCAN" --json --range="main..leaky" >"$TP_BASE/range.out" 2>"$TP_BASE/range.err"); then
  fail "the range scan passed a range that carries a secret"
else
  code=$?
fi
[ "$code" -eq 3 ] || fail "the range scan exited $code, not 3"
grep -q '"file": "settings.cfg"' "$TP_BASE/range.out" || { cat "$TP_BASE/range.out"; fail "the range scan does not name the file"; }
grep -q '"line": 3' "$TP_BASE/range.out" || fail "the range scan does not name the line"
grep -q '"kind": "github-token"' "$TP_BASE/range.out" || fail "the range scan does not name the kind"
if grep -q "$KEY" "$TP_BASE/range.out" "$TP_BASE/range.err"; then fail "the range scan printed the secret"; fi
ok "the range scan gives the same refusal"

# --- a clean range passes -----------------------------------------------------
(cd "$TP_ROOT" && python3 "$SCAN" --json --range="main..clean" >/dev/null) || fail "the range scan refused a clean range"
ok "a clean range passes"

echo "Secret scan checks passed."
