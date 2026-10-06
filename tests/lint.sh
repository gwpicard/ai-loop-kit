#!/usr/bin/env sh
# lint.sh: ruff and mypy over every Python file under kit/ and tests/.
#
# Two rule sets, as the build plan settles them:
#
#   Borrowed files that no v1 piece has adapted yet keep ruff E4,E7,E9,F and
#   default mypy. They are the rows of BORROWED.md, under "Copied files", whose
#   "Verbatim or edit" cell starts with "verbatim" or "edited". That table is
#   the one home of the list. A piece that adapts a file changes its row to
#   "adapted", and the file moves to the full set in the same pull request.
#
#   Every other Python file gets the full set in ruff.toml and mypy --strict.
#
# A Python file with no .py name, such as the GitHub stand-in, is found by its
# shebang. Ruff reads it from standard input under its real name. Mypy reads a
# copy under a temporary .py name.
#
# A check that did not run is never green: if ruff or mypy is missing, this
# fails and prints the install line.
#
# Usage:
#   tests/lint.sh                 lint this repository, then run the self-test
#   tests/lint.sh --root <folder> lint another tree (it needs BORROWED.md and ruff.toml)
#   tests/lint.sh --selftest      plant one fault at a time in a copy and
#                                 require a failure each time
#
# RUFF and MYPY name the tools to use. They default to "ruff" and "mypy".

set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
SELF="$HERE/$(basename -- "$0")"
RUFF=${RUFF:-ruff}
MYPY=${MYPY:-mypy}
MODE=default
INSTALL="python3 -m pip install ruff mypy"
LENIENT="E4,E7,E9,F"

while [ $# -gt 0 ]; do
  case "$1" in
    --root)
      [ $# -ge 2 ] || { echo "lint: --root needs a folder. next: tests/lint.sh --help" >&2; exit 2; }
      ROOT=$(CDPATH= cd -- "$2" && pwd) || exit 2
      MODE=check
      shift 2
      ;;
    --selftest) MODE=selftest; shift ;;
    -h | --help)
      sed -n '2,/^set -u/p' "$SELF" | sed '$d' | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "lint: unknown option $1. next: tests/lint.sh --help" >&2; exit 2 ;;
  esac
done

PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

need_tools() {
  for tool in "$RUFF" "$MYPY"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "FAIL: $tool is not installed, so the lint did not run. Install it: $INSTALL" >&2
      return 1
    fi
  done
}

# is_python <path>: a .py name, or a first line that is a Python shebang.
is_python() {
  case "$1" in
    *.py) return 0 ;;
    *.sh | *.md | *.json | *.yml | *.yaml | *.txt) return 1 ;;
  esac
  [ "$(head -c 2 "$1" 2>/dev/null)" = '#!' ] || return 1
  head -n 1 "$1" | grep -q python
}

run_lint() {
  root="$1"
  work=$(mktemp -d)
  failures=0
  fail() { printf 'FAIL: %s\n' "$1"; failures=$((failures + 1)); }
  pass() { printf 'ok: %s\n' "$1"; }

  need_tools || return 1
  [ -f "$root/ruff.toml" ] || { echo "FAIL: $root/ruff.toml is missing. Add the v1 rule set."; return 1; }
  [ -f "$root/BORROWED.md" ] || { echo "FAIL: $root/BORROWED.md is missing."; return 1; }

  # The lenient list, read from BORROWED.md.
  awk -F'|' '
    /^## / { in_copied = ($0 == "## Copied files") }
    in_copied && /^\| `/ {
      dest = $2; gsub(/[ `]/, "", dest)
      kind = $5; sub(/^ +/, "", kind)
      if (kind ~ /^(verbatim|edited)/) print dest
    }
  ' "$root/BORROWED.md" | sort > "$work/lenient-rows"

  : > "$work/lenient"
  : > "$work/full"
  for top in kit tests; do
    [ -d "$root/$top" ] || continue
    find "$root/$top" -type f ! -path '*/__pycache__/*' ! -path '*/node_modules/*' \
      ! -path '*/.mypy_cache/*' | sort > "$work/found"
    while IFS= read -r path; do
      is_python "$path" || continue
      rel=${path#"$root"/}
      if grep -qxF "$rel" "$work/lenient-rows"; then
        echo "$rel" >> "$work/lenient"
      else
        echo "$rel" >> "$work/full"
      fi
    done < "$work/found"
  done
  nl=$(wc -l < "$work/lenient" | tr -d ' ')
  nf=$(wc -l < "$work/full" | tr -d ' ')
  echo "lint: $nl borrowed Python files (E4,E7,E9,F and default mypy), $nf others (full set and mypy --strict)"

  # --- ruff -----------------------------------------------------------------
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    if ! "$RUFF" check --quiet --isolated --select "$LENIENT" --stdin-filename "$rel" - \
      < "$root/$rel" > "$work/out" 2>&1; then
      cat "$work/out"
      fail "ruff ($LENIENT) refuses $rel"
    fi
  done < "$work/lenient"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    if ! "$RUFF" check --quiet --config "$root/ruff.toml" --stdin-filename "$rel" - \
      < "$root/$rel" > "$work/out" 2>&1; then
      cat "$work/out"
      fail "ruff (full set) refuses $rel"
    fi
  done < "$work/full"
  [ "$failures" -eq 0 ] && pass "ruff accepts every Python file"

  # --- mypy, default settings, on the borrowed files ----------------------------
  mkdir -p "$work/lenient-copy"
  i=0
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    i=$((i + 1))
    base=$(basename -- "$rel" | sed 's/\.py$//; s/[^A-Za-z0-9]/_/g')
    copy="$work/lenient-copy/b${i}_${base}.py"
    cp "$root/$rel" "$copy"
    if ! (cd "$work/lenient-copy" && "$MYPY" --cache-dir "$work/mypy-cache-b" \
      --no-error-summary "$copy") > "$work/out" 2>&1; then
      sed "s|$copy|$rel|g" "$work/out"
      fail "mypy refuses $rel"
    fi
  done < "$work/lenient"

  # --- mypy --strict on everything else --------------------------------------
  mkdir -p "$work/strict-copy"
  : > "$work/strict-list"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    case "$rel" in
      *.py) echo "$rel" >> "$work/strict-list" ;;
      *)
        base=$(basename -- "$rel" | sed 's/[^A-Za-z0-9]/_/g')
        cp "$root/$rel" "$work/strict-copy/${base}.py"
        echo "$work/strict-copy/${base}.py" >> "$work/strict-list"
        ;;
    esac
  done < "$work/full"
  if [ -s "$work/strict-list" ]; then
    # Run from kit/scripts so that "loop" is one package, not also kit.scripts.loop.
    set --
    while IFS= read -r f; do
      case "$f" in
        /*) set -- "$@" "$f" ;;
        *) set -- "$@" "$root/$f" ;;
      esac
    done < "$work/strict-list"
    if ! (cd "$root" && MYPYPATH="$root/kit/scripts" "$MYPY" --strict --cache-dir "$work/mypy-cache-s" \
      --no-error-summary --explicit-package-bases "$@") > "$work/out" 2>&1; then
      sed "s|$root/||g; s|$work/strict-copy/||g" "$work/out"
      fail "mypy --strict refuses the files above"
    fi
  fi
  [ "$failures" -eq 0 ] && pass "mypy accepts every Python file"

  [ "$failures" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Self-test. A check that cannot fail proves nothing, so build a small tree,
# plant one fault at a time and require the lint to refuse each.
# ---------------------------------------------------------------------------

new_tree() {
  t=$(mktemp -d)
  mkdir -p "$t/kit/scripts/loop" "$t/tests"
  cp "$ROOT/ruff.toml" "$t/ruff.toml"
  : > "$t/kit/scripts/loop/__init__.py"
  printf 'def double(x: int) -> int:\n    return x * 2\n' > "$t/kit/scripts/loop/ok.py"
  printf 'import sys\n\nprint(sys.argv)\n' > "$t/kit/scripts/old.py"
  cat > "$t/BORROWED.md" <<'MD'
# Borrowed code

## Copied files

| Destination | Source | Commit | Verbatim or edit | What it must shed later |
|---|---|---|---|---|
| `kit/scripts/old.py` | `abc:old.py` | `abc` | verbatim | Nothing known. |

## New files, not borrowed

| Destination | What it is |
|---|---|
| `kit/scripts/loop/ok.py` | New. |
MD
  printf '%s' "$t"
}

st_pass() {
  # st_pass <description> <tree> [env assignments...]
  desc="$1"; tree="$2"; shift 2
  if env "$@" sh "$SELF" --root "$tree" >"$tree/out.txt" 2>&1; then
    echo "  ok: $desc"
  else
    cat "$tree/out.txt"
    echo "FAIL: self-test: $desc (expected a pass)"
    st_failures=$((st_failures + 1))
  fi
}

st_refuse() {
  # st_refuse <description> <tree> <text the output must hold> [env assignments...]
  desc="$1"; tree="$2"; want="$3"; shift 3
  if env "$@" sh "$SELF" --root "$tree" >"$tree/out.txt" 2>&1; then
    cat "$tree/out.txt"
    echo "FAIL: self-test: $desc (expected a failure)"
    st_failures=$((st_failures + 1))
  elif ! grep -q -- "$want" "$tree/out.txt"; then
    cat "$tree/out.txt"
    echo "FAIL: self-test: $desc (failed, but the output lacks '$want')"
    st_failures=$((st_failures + 1))
  else
    echo "  ok: $desc"
  fi
}

selftest() {
  st_failures=0
  need_tools || return 1
  echo "lint self-test:"

  t=$(new_tree)
  st_pass "a clean tree passes" "$t" X=1

  t=$(new_tree)
  printf 'import os, sys\n' > "$t/kit/scripts/loop/bad.py"
  st_refuse "an unused import in a new file is refused" "$t" "ruff (full set) refuses kit/scripts/loop/bad.py" X=1

  t=$(new_tree)
  printf 'def f(x):\n    return x\n' > "$t/kit/scripts/loop/untyped.py"
  st_refuse "a missing type in a new file is refused by mypy --strict" "$t" "mypy --strict" X=1

  t=$(new_tree)
  printf 'import sys\nimport os\n\nprint(os, sys)\n' > "$t/kit/scripts/old.py"
  st_pass "a borrowed file with unsorted imports keeps passing" "$t" X=1

  t=$(new_tree)
  printf 'import os\n' > "$t/kit/scripts/old.py"
  st_refuse "an unused import in a borrowed file is refused" "$t" "ruff (E4,E7,E9,F) refuses kit/scripts/old.py" X=1

  t=$(new_tree)
  printf 'def f() -> int:\n    return "x"\n' > "$t/kit/scripts/old.py"
  st_refuse "a type error in a borrowed file is refused by default mypy" "$t" "mypy refuses kit/scripts/old.py" X=1

  t=$(new_tree)
  printf 'import sys\nimport os\n\nprint(os, sys)\n' > "$t/kit/scripts/old.py"
  sed 's/| verbatim |/| adapted: shed the old layout |/' "$t/BORROWED.md" > "$t/b.md"
  cp "$t/b.md" "$t/BORROWED.md"
  st_refuse "a row changed to adapted moves the file to the full set" "$t" "ruff (full set) refuses kit/scripts/old.py" X=1

  t=$(new_tree)
  printf '#!/usr/bin/env python3\nimport os\n' > "$t/kit/scripts/tool"
  st_refuse "a Python file with no .py name is found by its shebang" "$t" "ruff (full set) refuses kit/scripts/tool" X=1

  t=$(new_tree)
  st_refuse "a missing ruff fails and prints the install line" "$t" "pip install" RUFF=/nonexistent/ruff
  st_refuse "a missing mypy fails and prints the install line" "$t" "pip install" MYPY=/nonexistent/mypy

  [ "$st_failures" -eq 0 ] && echo "lint self-test passed"
  [ "$st_failures" -eq 0 ]
}

case "$MODE" in
  check) run_lint "$ROOT" ;;
  selftest) selftest ;;
  default) run_lint "$ROOT" && selftest ;;
esac
