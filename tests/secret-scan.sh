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

# Install the hook where Git looks for it. The hook finds the scan only in the
# project's kit folder, in the installed kit under HOME, or beside itself.
# Here the kit folder is a copy of this repository's kit/scripts.
mkdir -p "$TP_ROOT/.githooks" "$TP_ROOT/kit"
cp "$HOOK" "$TP_ROOT/.githooks/pre-push"
chmod +x "$TP_ROOT/.githooks/pre-push"
cp -R "$ROOT/kit/scripts" "$TP_ROOT/kit/scripts"
git -C "$TP_ROOT" config core.hooksPath .githooks
# An old override must change nothing.
AI_LOOP_KIT_SECRET_SCAN=/bin/true
CLAUDE_PLUGIN_ROOT=/nonexistent
export AI_LOOP_KIT_SECRET_SCAN CLAUDE_PLUGIN_ROOT

# A fake key made at run time: a low-entropy filler, so no file here is a secret.
FILLER=$(printf 'AbCdEf%.0s' 1 2 3 4 5 6)
KEY="gh""p_$FILLER"

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

# --- a missing scan stops the push, and no override opens it ----------------
mv "$TP_ROOT/kit/scripts/secret-scan.py" "$TP_ROOT/kit/scripts/secret-scan.py.away"
git -C "$TP_ROOT" checkout -q clean
git -C "$TP_ROOT" checkout -q -b needs-scan
printf 'more\n' > "$TP_ROOT/more.txt"
git -C "$TP_ROOT" add more.txt
git -C "$TP_ROOT" commit -q -m "Add more"
if HOME="$TP_BASE/nohome" git -C "$TP_ROOT" push -q origin needs-scan 2>"$TP_BASE/missing.err"; then
  fail "the hook allowed a push with no scan to run"
fi
grep -q 'cannot find secret-scan.py' "$TP_BASE/missing.err" || { cat "$TP_BASE/missing.err"; fail "the refusal does not say the scan is missing"; }
grep -q '^next:' "$TP_BASE/missing.err" || fail "the refusal has no next: line"
if grep -q 'AI_LOOP_KIT_SECRET_SCAN' "$TP_BASE/missing.err"; then fail "the hook still names the override"; fi
mv "$TP_ROOT/kit/scripts/secret-scan.py.away" "$TP_ROOT/kit/scripts/secret-scan.py"
ok "a missing scan stops the push, even with an override set"

echo "Secret scan checks passed."
