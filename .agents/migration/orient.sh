#!/usr/bin/env bash
# orient.sh [source-repo]
#
# Establishes where things stand before a migration, for a session that was not
# there when the plan was written.
#
# Everything in docs/MIGRATION.md was true on 10 September 2026. A plan is a
# claim about the world, and the world moves: an issue gets opened, a branch
# gets merged, somebody half runs the migration and stops. This reads the world
# back and says which of the plan's assumptions still hold.
#
# It reads and reports. It changes nothing, locally or on GitHub. Nothing here
# needs approval and nothing here can break anything.
#
# Read the output before doing anything. A line marked ATTENTION is not
# necessarily a problem, but it is something the plan did not expect, and the
# plan should be re-read where it touches that thing.
set -u

SRC=${1:-gwpicard/ai-build-kit}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
attention=0

say()  { printf '  %-58s %s\n' "$1" "$2"; }
ok()   { say "$1" "ok: $2"; }
att()  { say "$1" "ATTENTION: $2"; attention=$((attention + 1)); }

echo "Orientation for a migration of $SRC"
echo "Recorded state is from 10 September 2026."
echo

# --------------------------------------------------------------------------
echo "== tools =="
command -v gh      >/dev/null && ok "gh"      "present" || att "gh"      "missing, nothing here works without it"
command -v python3 >/dev/null && ok "python3" "present" || att "python3" "missing, the port script needs it"
command -v curl    >/dev/null && ok "curl"    "present" || att "curl"    "missing, used to check the web address"
who=$(gh api user -q .login 2>/dev/null)
[ -n "$who" ] && ok "signed in as" "$who" || att "gh sign-in" "not signed in, run gh auth status"

# --------------------------------------------------------------------------
echo
echo "== the local clone =="
branch=$(git -C "$ROOT" branch --show-current 2>/dev/null)
ok "clone" "$ROOT"
ok "branch" "${branch:-detached}"
if [ -z "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]; then
  ok "working tree" "clean"
else
  att "working tree" "has uncommitted changes, settle them before migrating"
fi

# The plan and its scripts may live only on a branch. A session that opened main
# will not find them, which is confusing in exactly the wrong way.
if [ -f "$ROOT/docs/MIGRATION.md" ]; then
  ok "the plan" "present in this checkout"
else
  att "the plan" "not in this checkout; it is on the migration-plan branch, or in ~/ai-build-kit-backups"
fi

unmerged=$(git -C "$ROOT" branch --no-merged main --format='%(refname:short)' 2>/dev/null \
           | grep -v '^main$' | tr '\n' ' ')
if [ -z "$unmerged" ]; then
  ok "branches not on main" "none, main carries everything"
else
  att "branches not on main" "$unmerged"
  echo "        The new repository is built by pushing main. A branch that is not"
  echo "        merged does not exist there. The rules that stop the trailers"
  echo "        coming back are on one of these."
fi

localmain=$(git -C "$ROOT" rev-parse main 2>/dev/null)
remotemain=$(git -C "$ROOT" ls-remote origin refs/heads/main 2>/dev/null | cut -f1)
if [ "$localmain" = "$remotemain" ]; then
  ok "main matches the remote" "${localmain:0:8}"
else
  att "main against the remote" "local ${localmain:0:8}, remote ${remotemain:0:8}"
fi

# --------------------------------------------------------------------------
echo
echo "== the repository on GitHub =="
info=$(gh api "repos/$SRC" 2>/dev/null)
if [ -z "$info" ]; then
  att "$SRC" "cannot be read; wrong name, or it has already been renamed"
else
  # The JSON travels through the environment rather than a pipe: a heredoc
  # takes over standard input, so anything piped in never reaches the script.
  REPO_INFO="$info" python3 - <<'PY'
import json, os
d = json.loads(os.environ["REPO_INFO"])
for name, value in (
    ("visibility", d["visibility"]),
    ("default branch", d["default_branch"]),
    ("stars, forks", f"{d['stargazers_count']}, {d['forks_count']}"),
    ("created", d["created_at"][:10]),
):
    print(f"  {name:<58} ok: {value}")
PY
fi

rules=$(gh api "repos/$SRC/rulesets" -q '.[] | "\(.name)=\(.enforcement)"' 2>/dev/null | tr '\n' ' ')
case "$rules" in
  *active*)   ok  "branch ruleset" "$rules" ;;
  *disabled*) att "branch ruleset" "$rules, so main is unprotected right now" ;;
  "")         att "branch ruleset" "none found" ;;
  *)          ok  "branch ruleset" "$rules" ;;
esac

# --------------------------------------------------------------------------
echo
echo "== has a migration already been started? =="
for name in "${SRC}-next" "${SRC}-archive"; do
  if gh api "repos/$name" -q .full_name >/dev/null 2>&1; then
    att "$name" "already exists; a previous attempt stopped part way"
  else
    ok "$name" "does not exist, as expected"
  fi
done

# --------------------------------------------------------------------------
echo
echo "== is the migration still needed? =="
# The commits GitHub keeps alive behind pull request references. This asks
# GitHub what it actually serves today, rather than reading a local clone.
#
# It counts the commits listed on each pull request's Commits tab. The plan's
# figure of 35 is a wider count: every attributed commit reachable by walking
# back from a pull request reference, which includes the old history the
# branches were cut from. Both are true at once, so the two are reported side
# by side rather than one being compared against the other.
needle_link=$(printf 'claude.ai/code/%s' 'session_')
needle_author=$(printf 'co-%sed-by: claude' 'author')
prs=$(gh api "repos/$SRC/pulls?state=all&per_page=100" --paginate -q '.[].number' 2>/dev/null)
seen=$(mktemp)
for n in $prs; do
  # One line per commit, so a message carrying two attribution lines is still
  # one commit, and a commit reachable from two pull requests is still one
  # commit once the list is made unique.
  gh api "repos/$SRC/pulls/$n/commits" \
     -q '.[] | "\(.sha) \(.commit.message | gsub("\n"; " "))"' 2>/dev/null \
    | grep -iE "$needle_link|$needle_author|claude-session:" \
    | cut -d' ' -f1 >> "$seen"
done
dirty=$(sort -u "$seen" | grep -c . || true)
rm -f "$seen"
if [ "$dirty" -gt 0 ]; then
  att "attributed commits still served" "$dirty listed on pull request Commits tabs (plan counted 35 reachable by address)"
  echo "        This is what the migration exists to remove. Nothing else reaches them."
else
  ok "attributed commits still served" "none, the migration may no longer be needed"
fi

mainbad=$(git -C "$ROOT" log --format=%B main 2>/dev/null \
          | grep -icE "$needle_link|$needle_author|claude-session:")
[ "$mainbad" = "0" ] && ok "main's own history" "clean" \
                     || att "main's own history" "$mainbad lines, the rewrite did not hold"

# --------------------------------------------------------------------------
echo
echo "== does the content still match the plan? =="
python3 - "$SRC" <<'PY'
import json, subprocess, sys

def gh(path):
    out = subprocess.run(["gh", "api", path, "--paginate"],
                         capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else []

src = sys.argv[1]
items = gh(f"repos/{src}/issues?state=all&per_page=100")
labels = gh(f"repos/{src}/labels?per_page=100")
rels = gh(f"repos/{src}/releases?per_page=100")

nums = sorted(i["number"] for i in items)
gaps = [n for n in range(1, nums[-1] + 1) if n not in nums] if nums else []
comments = sum(len(gh(f"repos/{src}/issues/{n}/comments?per_page=100")) for n in nums)

recorded = {
    "numbered items": (len(items), 37),
    "pull requests": (sum(1 for i in items if "pull_request" in i), 17),
    "issues": (sum(1 for i in items if "pull_request" not in i), 20),
    "open issues": (sum(1 for i in items
                        if "pull_request" not in i and i["state"] == "open"), 14),
    "comments": (comments, 41),
    "labels": (len(labels), 25),
    "releases": (len(rels), 17),
    "release assets": (sum(len(r["assets"]) for r in rels), 4),
}
bad = 0
for name, (now, then) in recorded.items():
    if now == then:
        print(f"  {name:<58} ok: {now}")
    else:
        print(f"  {name:<58} ATTENTION: {now}, plan recorded {then}")
        bad += 1
if gaps:
    print(f"  {'numbering':<58} ATTENTION: gaps at {gaps}, numbering cannot be kept")
    bad += 1
else:
    print(f"  {'numbering':<58} ok: 1 to {nums[-1] if nums else 0}, no gaps")
sys.exit(1 if bad else 0)
PY
[ $? -eq 0 ] || attention=$((attention + 1))

# --------------------------------------------------------------------------
echo
echo "== the things kept outside the repository =="
B=$HOME/ai-build-kit-backups
for f in social-preview.png MIGRATION.md port.py export.sh port-settings.sh verify-port.sh; do
  [ -f "$B/$f" ] && ok "$f" "present" || att "$f" "missing from $B"
done
ls "$B"/*.bundle >/dev/null 2>&1 && ok "history bundle" "present" \
                                 || att "history bundle" "missing from $B"

# --------------------------------------------------------------------------
echo
if [ "$attention" -eq 0 ]; then
  echo "Everything matches what the plan expects. Read docs/MIGRATION.md and begin."
else
  echo "$attention thing(s) marked ATTENTION above."
  echo "None of them necessarily blocks the migration, but re-read the plan where"
  echo "it touches each one before starting. Do not begin on the assumption that"
  echo "the plan is still describing this repository."
fi
