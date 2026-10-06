#!/usr/bin/env sh
# script-contracts.sh: hold every agent script to design principle 8.
#
# A script marked with the line "# contract: agent" in its first ten lines is
# built for an agent reader: no prompts, `--help`, JSON out, distinct exit
# codes, idempotent, errors that name the next command. A second marker line,
# "# contract: changes-state", adds `--dry-run`.
#
# The check itself must be able to fail. So the first half runs it on small
# sample scripts: good ones must pass, and each one with a single planted fault
# must fail. The second half runs it on every marked script under kit/.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHECK="$ROOT/tests/lib/contract_check.py"
PYTHONDONTWRITEBYTECODE=1
# A script that hangs is refused after this many seconds.
CONTRACT_TIMEOUT=${CONTRACT_TIMEOUT:-4}
export PYTHONDONTWRITEBYTECODE CONTRACT_TIMEOUT

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

[ -f "$CHECK" ] || fail "missing $CHECK"

WORK=$(mktemp -d)
echo "Script contract checks (samples in $WORK):"

# --- samples ----------------------------------------------------------------
# A good script written with the shared helper.
cat > "$WORK/good.py" <<PY
#!/usr/bin/env python3
# contract: agent
# contract: changes-state
import sys
from pathlib import Path
sys.path.insert(0, "$ROOT/kit/scripts")
from loop import cli


def setup(parser):
    parser.add_argument("--target", default="made.txt")


def handle(args):
    target = Path(args.target)
    if not args.dry_run:
        target.write_text("x\n")
    return {"target": args.target, "changed": not args.dry_run and not target.exists()}


sys.exit(cli.run("good", "Make a file.", setup, handle, sys.argv[1:], changes_state=True))
PY

# A good script in shell.
cat > "$WORK/good.sh" <<'SH'
#!/usr/bin/env sh
# contract: agent
case "${1:-}" in
  --help)
    echo "usage: good.sh [--json]"
    echo "exit codes: 0 ok, 2 usage"
    exit 0
    ;;
esac
echo '{"ok": true}'
SH

# One planted fault each.
sed 's/^sys.exit.*/sys.exit(0 if "--help" in sys.argv else cli.run("good", "x", setup, handle, [], changes_state=True))/' \
  "$WORK/good.py" > "$WORK/no-help.py"

cat > "$WORK/prompts.py" <<'PY'
#!/usr/bin/env python3
# contract: agent
import sys
if "--help" in sys.argv:
    print("usage: prompts [--json]\nexit codes: 0 ok")
    sys.exit(0)
name = input("Your name? ")
print('{"ok": true}')
PY

cat > "$WORK/not-idempotent.sh" <<'SH'
#!/usr/bin/env sh
# contract: agent
case "${1:-}" in
  --help) echo "usage: x [--json]"; echo "exit codes: 0 ok"; exit 0 ;;
esac
n=$(cat counter 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > counter
printf '{"ok": true, "count": %s}\n' "$n"
SH

cat > "$WORK/bare-error.sh" <<'SH'
#!/usr/bin/env sh
# contract: agent
case "${1:-}" in
  --help) echo "usage: x [--json]"; echo "exit codes: 0 ok, 1 failed"; exit 0 ;;
esac
echo "something went wrong" >&2
exit 1
SH

cat > "$WORK/text-out.sh" <<'SH'
#!/usr/bin/env sh
# contract: agent
case "${1:-}" in
  --help) echo "usage: x [--json]"; echo "exit codes: 0 ok"; exit 0 ;;
esac
echo "all done, nothing to see"
SH

cat > "$WORK/no-codes.sh" <<'SH'
#!/usr/bin/env sh
# contract: agent
case "${1:-}" in
  --help) echo "usage: x [--json]"; exit 0 ;;
esac
echo '{"ok": true}'
SH

cat > "$WORK/dry-run-writes.sh" <<'SH'
#!/usr/bin/env sh
# contract: agent
# contract: changes-state
case "${1:-}" in
  --help) echo "usage: x [--json] [--dry-run]"; echo "exit codes: 0 ok"; exit 0 ;;
esac
echo 'x' > "made-$$.txt"
echo '{"ok": true}'
SH

cat > "$WORK/hangs.sh" <<'SH'
#!/usr/bin/env sh
# contract: agent
case "${1:-}" in
  --help) echo "usage: x [--json]"; echo "exit codes: 0 ok"; exit 0 ;;
esac
sleep 60
SH

chmod +x "$WORK"/*.py "$WORK"/*.sh

# --- the check passes good scripts -----------------------------------------
python3 "$CHECK" "$WORK/good.py" >"$WORK/good-py.out" 2>&1 || {
  cat "$WORK/good-py.out"
  fail "the check refused a good Python script"
}
ok "a good Python script passes"
python3 "$CHECK" "$WORK/good.sh" >"$WORK/good-sh.out" 2>&1 || {
  cat "$WORK/good-sh.out"
  fail "the check refused a good shell script"
}
ok "a good shell script passes"

# --- and refuses each planted fault, for the right reason --------------------
refused() {
  # refused <file> <text the refusal must contain>
  if python3 "$CHECK" "$WORK/$1" >"$WORK/$1.out" 2>&1; then
    cat "$WORK/$1.out"
    fail "the check passed $1, which has a planted fault"
  fi
  grep -qi -- "$2" "$WORK/$1.out" || {
    cat "$WORK/$1.out"
    fail "the check refused $1, but not for '$2'"
  }
  ok "$1 is refused ($2)"
}

refused no-help.py "--help"
refused prompts.py "no arguments"
refused not-idempotent.sh "twice"
refused bare-error.sh "next:"
refused text-out.sh "json"
refused no-codes.sh "exit codes"
refused dry-run-writes.sh "dry-run"
refused hangs.sh "timed out"

# An unmarked script is not a contract script: the check says so and fails.
printf '#!/usr/bin/env sh\necho hi\n' > "$WORK/unmarked.sh"
chmod +x "$WORK/unmarked.sh"
refused unmarked.sh "not marked"

# --- every marked script under kit/ ----------------------------------------
marked=""
for f in $(find "$ROOT/kit" -type f ! -name '*.md' ! -name '*.json' ! -name '*.yml' | sort); do
  if head -n 10 "$f" | grep -q '^# contract: agent$'; then
    marked="$marked $f"
  fi
done

if [ -z "$marked" ]; then
  echo "  skipped: no script under kit/ is marked '# contract: agent' yet"
else
  for f in $marked; do
    python3 "$CHECK" "$f" || fail "$f breaks the script contract"
    ok "${f#"$ROOT"/} meets the script contract"
  done
fi

echo "Script contract checks passed."
