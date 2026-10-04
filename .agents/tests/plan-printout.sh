#!/usr/bin/env sh
# plan-printout.sh: check what plan-refresh.sh writes into plan.local.md.
#
# The printout is the only view of the plan a person gets when GitHub cannot be
# reached, so what it groups and what it says about each piece has to be right.
# Greps over the script cannot judge that. This runs it against a fixed set of
# issues and reads the file it produces.
#
# A stand-in for the GitHub CLI supplies the issues. plan-refresh.sh asks gh for
# JSON and does its own filtering, which is what makes that substitution honest.
#
# Everything here runs in a throwaway directory. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
REFRESH="$ROOT/skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh"
GATE="$ROOT/skills/setup-ai-build-kit/templates/foundation/gate.py"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

# One issue per case the printout has to tell apart. The columns come first,
# then the mistakes it has to name, then what it must leave out.
#
# Every piece the gate script's report would name prints under Needs attention:
# Card checkout and dark mode maybe carry no state, Weekly payouts, Share a
# booking link and Coupon codes carry labels from AI Build Kit's model, Gift
# cards carries two states, Stock alerts a state with no sub-label, Room photos
# a sub-label beside the wrong state, Price list two review labels, and Guest
# accounts is a parent carrying a state. Email reminders and Old export are
# closed, and the endpoint asks only for open issues, so a stand-in that returns
# them anyway proves the printout checks for itself.
cat >"$WORK/issues.json" <<'JSON'
[
  {"number": 1, "title": "Card checkout", "html_url": "http://x/1",
   "body": "## Done when\nA card is charged.", "assignees": [],
   "labels": [{"name": "finance"}, {"name": "external service"}]},
  {"number": 2, "title": "Rename the header", "html_url": "http://x/2",
   "body": "## Done when\nIt reads Bookings.\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready",
   "assignees": [{"login": "ana"}],
   "labels": [{"name": "visual"}, {"name": "state:building"}, {"name": "type:feature"}]},
  {"number": 3, "title": "Weekly payouts", "html_url": "http://x/3",
   "body": "## Done when\nSellers are paid.", "assignees": [],
   "labels": [{"name": "finance"}, {"name": "blocked"}]},
  {"number": 4, "title": "make the calendar nicer", "html_url": "http://x/4",
   "body": "half a sentence\n\n## Open question\nWhich days matter most?", "assignees": [],
   "labels": [{"name": "state:shaping"}, {"name": "shaping:clarify"}]},
  {"number": 5, "title": "how should the dashboard look", "html_url": "http://x/5",
   "body": "no idea yet", "assignees": [],
   "labels": [{"name": "state:shaping"}, {"name": "shaping:prototype"}]},
  {"number": 6, "title": "what does the VAT API return", "html_url": "http://x/6",
   "body": "need to check", "assignees": [],
   "labels": [{"name": "state:shaping"}, {"name": "shaping:research"}]},
  {"number": 7, "title": "Duplicate bookings", "html_url": "http://x/7",
   "body": "## Done when\nOne booking per click.\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready",
   "assignees": [{"login": "sam"}],
   "labels": [{"name": "how it works"}, {"name": "type:bug"}, {"name": "state:building"}]},
  {"number": 8, "title": "A pull request, not a piece", "html_url": "http://x/8",
   "body": "## Done when\nnever", "assignees": [], "labels": [],
   "pull_request": {"url": "http://x/8"}},
  {"number": 9, "title": "Booking flow", "html_url": "http://x/9",
   "body": "## So that\nGuests can book.", "assignees": [],
   "labels": [{"name": "how it works"}],
   "sub_issues_summary": {"total": 2, "completed": 1, "percent_completed": 50}},
  {"number": 10, "title": "Guest list export", "html_url": "http://x/10",
   "body": "## Done when\nThe list downloads.", "assignees": [],
   "labels": [{"name": "how it works"}, {"name": "state:ready"}]},
  {"number": 11, "title": "Deposits", "html_url": "http://x/11",
   "body": "## Done when\nA deposit is held.", "assignees": [],
   "labels": [{"name": "finance"}, {"name": "state:ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 12, "title": "Refund button", "html_url": "http://x/12",
   "body": "## Done when\nA refund is sent.", "assignees": [],
   "labels": [{"name": "finance"}, {"name": "state:ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 13, "title": "Invoice download", "html_url": "http://x/13",
   "body": "## Done when\nAn invoice downloads.\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready",
   "assignees": [],
   "labels": [{"name": "finance"}, {"name": "state:in-review"}, {"name": "review:person"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 14, "title": "Loyalty points", "html_url": "http://x/14",
   "body": "## Done when\nPoints add up.\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready",
   "assignees": [],
   "labels": [{"name": "finance"}, {"name": "state:in-review"}, {"name": "review:auto"}]},
  {"number": 15, "title": "Gift cards", "html_url": "http://x/15",
   "body": "## Done when\nA card is redeemed.", "assignees": [],
   "labels": [{"name": "finance"}, {"name": "state:ready"}, {"name": "state:building"}]},
  {"number": 16, "title": "Stock alerts", "html_url": "http://x/16",
   "body": "check the supplier feed", "assignees": [],
   "labels": [{"name": "state:shaping"}]},
  {"number": 17, "title": "tidy the footer", "html_url": "http://x/17",
   "body": "it looks off", "assignees": [],
   "labels": [{"name": "visual"}, {"name": "state:ready"}]},
  {"number": 18, "title": "Email reminders", "html_url": "http://x/18",
   "body": "Left out: nobody reads email here.", "assignees": [], "state": "closed",
   "labels": [{"name": "state:shaping"}, {"name": "shaping:raw"}]},
  {"number": 19, "title": "Old export", "html_url": "http://x/19",
   "body": "## Done when\nIt exported.", "assignees": [], "state": "closed",
   "labels": [{"name": "ready"}]},
  {"number": 20, "title": "dark mode maybe", "html_url": "http://x/20",
   "body": "jotted on a phone", "assignees": [], "labels": []},
  {"number": 21, "title": "Share a booking link", "html_url": "http://x/21",
   "body": "a link a guest can send on", "assignees": [], "state": "open",
   "labels": [{"name": "idea"}]},
  {"number": 22, "title": "Late fees", "html_url": "http://x/22",
   "body": "charge a fee when a booking is paid late", "assignees": [],
   "labels": [{"name": "finance"}, {"name": "state:building"}]},
  {"number": 23, "title": "Waiting list", "html_url": "http://x/23",
   "body": "let guests queue for a full night", "assignees": [],
   "labels": [{"name": "state:in-review"}, {"name": "review:person"}]},
  {"number": 24, "title": "Table plan", "html_url": "http://x/24",
   "body": "## Done when\nTables can be dragged.", "assignees": [],
   "labels": [{"name": "state:building"}]},
  {"number": 25, "title": "Opening hours", "html_url": "http://x/25",
   "body": "## Done when\nHours show.\n\n## Readiness check\nlooked fine", "assignees": [],
   "labels": [{"name": "state:in-review"}, {"name": "review:person"}]},
  {"number": 26, "title": "Allergy notes", "html_url": "http://x/26",
   "body": "## Done when\nA note is kept.\n\n## readiness\n2026-09-30, checked by a session that did not shape it: Ready",
   "assignees": [], "labels": [{"name": "state:building"}]},
  {"number": 27, "title": "Guest accounts", "html_url": "http://x/27",
   "body": "## So that\nGuests can sign in.", "assignees": [],
   "labels": [{"name": "state:building"}],
   "sub_issues_summary": {"total": 3, "completed": 0, "percent_completed": 0}},
  {"number": 28, "title": "Lost receipts", "html_url": "http://x/28",
   "body": "receipts stopped sending", "assignees": [],
   "labels": [{"name": "type:bug"}, {"name": "state:shaping"}, {"name": "shaping:raw"}]},
  {"number": 29, "title": "Room photos", "html_url": "http://x/29",
   "body": "add photos of each room", "assignees": [],
   "labels": [{"name": "state:building"}, {"name": "shaping:research"}]},
  {"number": 30, "title": "Seat colours", "html_url": "http://x/30",
   "body": "## Done when\nSeats are coloured.", "assignees": [],
   "labels": [{"name": "state:shaping"}, {"name": "shaping:spec"}]},
  {"number": 31, "title": "Menu wording", "html_url": "http://x/31",
   "body": "## Done when\nThe menu reads well.", "assignees": [],
   "labels": [{"name": "state:shaping"}, {"name": "shaping:check"}]},
  {"number": 32, "title": "Price list", "html_url": "http://x/32",
   "body": "## Done when\nPrices show.\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready",
   "assignees": [],
   "labels": [{"name": "state:in-review"}, {"name": "review:auto"}, {"name": "review:person"}]},
  {"number": 33, "title": "Coupon codes", "html_url": "http://x/33",
   "body": "## Done when\nA code takes money off.", "assignees": [],
   "labels": [{"name": "state:ready"}, {"name": "needs-research"}]}
]
JSON

# Every call is written to a log, so the check can prove the printout reads and
# never writes: no label, no issue edit, nothing moved off an old label.
mkdir -p "$WORK/bin"
cat >"$WORK/bin/gh" <<'SH'
#!/usr/bin/env sh
printf '%s\n' "$*" >> "${GH_CALLS:-/dev/null}"
# GH_DOWN stands in for a machine that cannot reach GitHub: every call fails.
[ -z "${GH_DOWN:-}" ] || exit 1
case "$1 $2" in
  "repo view") echo '{"nameWithOwner":"someone/project"}' ;;
  *) case "$2" in
       *"/issues?"*) cat "$FIXTURE" ;;
       # Deposits is held up by an open piece, which is the case the printout
       # has to name. Refund button counts a blocker too, but that blocker has
       # closed, so it is free to build. Both go through the same call, and only
       # the state in the answer tells them apart.
       *"/issues/11/dependencies/blocked_by")
         echo '[{"number":1,"title":"Card checkout","state":"open"}]' ;;
       *"/issues/13/dependencies/blocked_by")
         echo '[{"number":1,"title":"Card checkout","state":"open"}]' ;;
       *"/issues/12/dependencies/blocked_by")
         echo '[{"number":2,"title":"Rename the header","state":"closed"}]' ;;
       *dependencies/blocked_by*) echo '[]' ;;
       *) echo '[]' ;;
     esac ;;
esac
SH
chmod +x "$WORK/bin/gh"

FIXTURE="$WORK/issues.json"
GH_CALLS="$WORK/calls.log"
export FIXTURE GH_CALLS
PATH="$WORK/bin:$PATH"
export PATH

cd "$WORK"
"$REFRESH" >/dev/null 2>&1 || fail "the printout could not be written"
OUT="$WORK/plan.local.md"
[ -f "$OUT" ] || { echo "FAIL: no printout was written" >&2; exit 1; }

# Everything under one heading, rather than the first entry a -A1 would reach.
# Several groups carry more than one piece, and a check that only ever reads the
# first would pass while the second sat in the wrong place.
section() {
  awk -v want="$1" '$0 == want { f = 1; next } /^[^ ]/ { f = 0 } f' "${2:-$OUT}"
}

# Pieces are named rather than numbered here, the same rule the printout's own
# readers follow. It also keeps this file clear of the issue-number check, which
# cannot tell a fixture apart from a real citation and should not have to.
under() {
  section "$1" | grep -q "$2"
}
# A piece's own line, not a mention of it as another piece's blocker.
once() {
  [ "$(grep -cE "^ +#[0-9]+ +$1" "$OUT")" -eq 1 ]
}

echo "== The printout reads as a board =="

# The headings in the order they print. Needs attention comes first, because
# somebody opening the file wants to know what is wrong before what is next.
# Then a column for each shaping sub-state, in the order a piece moves through
# them, then ready, split into the pieces free to start and the ones held up by
# another, with the groups of free pieces after the pieces they group. Then
# building, and review split by who it waits for. Parents last, because a parent
# has no state of its own. There is no column for a repair: a bug is marked
# wherever it sits.
headings=$(awk 'NR > 3 && /^[^ ]/ && !/^Plan / && !/^Last refreshed/ && !/entr(y|ies) (is|are) still/' "$OUT" | tr '\n' '|')
expected="Needs attention|Shaping: raw|Shaping: research|Shaping: clarify|Shaping: prototype|Shaping: spec|Shaping: check|To build|Go together|Held up|Building|In review, waiting for you|In review, automatic|Made of parts|"
[ "$headings" = "$expected" ] \
  && pass "the groups print in board order" \
  || fail "the groups print as '$headings', expected '$expected'"

under "Shaping: raw" "Lost receipts" && under "Shaping: research" "what does the VAT API return" \
  && under "Shaping: clarify" "make the calendar nicer" \
  && under "Shaping: prototype" "how should the dashboard look" \
  && under "Shaping: spec" "Seat colours" && under "Shaping: check" "Menu wording" \
  && pass "a piece being shaped is under the column of its sub-state" \
  || fail "a shaping piece is not under its sub-state's column"

under "Building" "Rename the header" \
  && section "Building" | grep "Rename the header" | grep -q "(ana)" \
  && pass "a piece under way is under Building, with who has it" \
  || fail "Rename the header is not under Building with its assignee"

under "In review, waiting for you" "Invoice download" \
  && pass "a piece whose review waits for the person is under In review, waiting for you" \
  || fail "Invoice download is not under In review, waiting for you"
under "In review, automatic" "Loyalty points" \
  && pass "a piece waiting on the automatic review is under In review, automatic" \
  || fail "Loyalty points is not under In review, automatic"

section "In review, waiting for you" | grep "Invoice download" | grep -q "needs Card checkout" \
  && pass "a piece in review that another piece holds up names it" \
  || fail "Invoice download does not name Card checkout as its blocker"

grep -q "A pull request, not a piece" "$OUT" \
  && fail "a pull request was printed as a piece" \
  || pass "pull requests stay out of the list"

echo "== A bug is marked wherever it sits =="

section "Building" | grep "Duplicate bookings" | grep -q "(bug)" \
  && section "Shaping: raw" | grep "Lost receipts" | grep -q "(bug)" \
  && pass "a type:bug piece carries a bug mark in whichever column it sits" \
  || fail "a type:bug piece is not marked as a bug in its column"
once "Duplicate bookings" && once "Lost receipts" \
  && pass "a bug prints once, in its own column" \
  || fail "a bug prints more than once"
grep -v "Duplicate bookings" "$OUT" | grep -v "Lost receipts" | grep -q "(bug)" \
  && fail "a piece that is not a bug carries the bug mark" \
  || pass "only a bug carries the bug mark"

echo "== What the printout leaves out =="

grep -q "Email reminders" "$OUT" \
  && fail "a closed issue still carrying a state was printed" \
  || pass "a closed issue still carrying a state is never printed"
grep -q "Old export" "$OUT" \
  && fail "a closed issue carrying an old label was printed" \
  || pass "a closed issue carrying an old label is ignored"

echo "== What needs attention is what the gate's report would print =="

# Each piece the report names prints once, under Needs attention, and in no
# column, because a piece whose labels are out of order has no column to trust.
for piece in "Card checkout" "dark mode maybe" "Gift cards" "Stock alerts" \
    "Room photos" "Price list" "Guest accounts" "Weekly payouts" \
    "Share a booking link" "Coupon codes"; do
  under "Needs attention" "$piece" && once "$piece" \
    || fail "$piece is not named once, under Needs attention"
done
pass "a piece the report names prints once, under Needs attention"

note_for() {
  section "Needs attention" | grep "$1" | grep -qF "$2"
}
# An issue opened by hand with no labels is named as having no state, which is
# what tells /shape to take it in.
note_for "dark mode maybe" "no state" && note_for "Card checkout" "no state" \
  && pass "an issue opened by hand with no labels is named as having no state" \
  || fail "an issue with no labels is not named as having no state"
note_for "Gift cards" "state:ready" && note_for "Gift cards" "state:building" \
  && pass "a piece with two states is named with both" \
  || fail "Gift cards does not name its two states"
note_for "Stock alerts" "no shaping sub-label" \
  && pass "a shaping piece with no sub-label is named" \
  || fail "Stock alerts is not named for its missing sub-label"
note_for "Room photos" "shaping:research beside state:building" \
  && pass "a sub-label beside the wrong state is named" \
  || fail "Room photos is not named for its sub-label beside building"
note_for "Price list" "two review labels" \
  && pass "two review labels on one piece are named" \
  || fail "Price list is not named for its two review labels"
note_for "Guest accounts" "parent" \
  && ! under "Made of parts" "Guest accounts" \
  && pass "a parent carrying a state is named, and not printed as a container too" \
  || fail "Guest accounts is not named as a parent carrying a state"

# A label from AI Build Kit's model is named as one the kit does not use, and
# nothing moves it.
note_for "Weekly payouts" "blocked, a label from AI Build Kit's model" \
  && note_for "Share a booking link" "idea, a label from AI Build Kit's model" \
  && note_for "Coupon codes" "needs-research, a label from AI Build Kit's model" \
  && pass "a label from AI Build Kit's model is named as one the kit does not use" \
  || fail "an old label is not named as one the kit does not use"
under "To build" "Coupon codes" \
  && fail "a ready piece carrying an old label was offered as buildable" \
  || pass "a ready piece carrying an old label is not offered as buildable"

# The gate's own report, run on the same issues, names the same pieces with the
# same words, because the printout takes the findings from it rather than
# working them out again.
# GitHub always says whether an issue is open, and the gate reads that field,
# so the report gets the same issues with it filled in.
python3 -c 'import json,sys; items=json.load(open(sys.argv[1]))
for i in items: i.setdefault("state", "open")
json.dump(items, open(sys.argv[2], "w"))' "$FIXTURE" "$WORK/issues-with-state.json"
FIXTURE="$WORK/issues-with-state.json" python3 "$GATE" report > "$WORK/report.txt" 2>&1 || true
matched=yes
while IFS= read -r line; do
  case "$line" in
    "#"*)
      title=$(printf '%s' "$line" | sed -E 's/^#[0-9]+ //; s/: .*//')
      found=$(printf '%s' "$line" | sed -E 's/^#[0-9]+ [^:]*: //')
      note_for "$title" "$found" || { matched=no; fail "the printout does not carry the report's line for $title: $found"; }
      ;;
  esac
done < "$WORK/report.txt"
[ "$(grep -c '^#' "$WORK/report.txt")" -ge 10 ] || { matched=no; fail "the gate's report named too few pieces: $(cat "$WORK/report.txt")"; }
[ "$matched" = no ] || pass "every finding of the gate's report is under Needs attention, word for word"

# The printout reads. It never writes a label or edits an issue.
grep -qE '^(issue edit|issue create|label )' "$GH_CALLS" \
  && fail "the printout wrote to GitHub: $(grep -E '^(issue|label)' "$GH_CALLS" | head -3)" \
  || pass "the printout moved nothing on GitHub"

for piece in "Rename the header" "Loyalty points" "Invoice download" "Seat colours"; do
  if under "Needs attention" "$piece"; then
    fail "$piece has one state and its sub-label but was named under Needs attention"
  fi
done
pass "a piece in order is not named under Needs attention"

echo "== A piece built or checked without its earlier steps =="

# A person can put a later state on a piece by hand, so a piece can carry it
# without ever being shaped, or without the readiness check. It looks exactly
# like one that went the proper way, so the printout names what is missing under
# Needs attention. A piece being built or reviewed still stays in its own
# column, because it really is being built or reviewed.
note_for "Late fees" "(building with no Done when, so never shaped)" \
  && under "Building" "Late fees" \
  && pass "a building piece with no Done when is named and stays under Building" \
  || fail "Late fees is not named as never shaped, or left Building"
note_for "Waiting list" "(in review with no Done when, so never shaped)" \
  && under "In review, waiting for you" "Waiting list" \
  && pass "a piece in review with no Done when is named and stays in its column" \
  || fail "Waiting list is not named as never shaped, or left In review"
note_for "Table plan" "(building with no Readiness check)" \
  && under "Building" "Table plan" \
  && pass "a building piece with a Done when and no Readiness is named for it" \
  || fail "Table plan is not named as having no Readiness check"

# A heading with extra words is not the Readiness section.
note_for "Opening hours" "(in review with no Readiness check)" \
  && under "In review, waiting for you" "Opening hours" \
  && pass "a Readiness heading with extra words does not count as the section" \
  || fail "Opening hours has only a Readiness check heading but is not named"

# Where both are missing, the first one is the whole story.
section "Needs attention" | grep "Late fees" | grep -q "Readiness" \
  && fail "Late fees has no Done when and also got the Readiness note" \
  || pass "a piece missing both shows only the Done when note"

twice=yes
for piece in "Late fees" "Waiting list" "Table plan" "Opening hours"; do
  [ "$(grep -c "$piece" "$OUT")" -eq 2 ] || { twice=no; fail "$piece does not print exactly twice"; }
done
[ "$twice" = no ] || pass "each prints under Needs attention and in its own column, once each"

# A ready piece nobody sized is named, and never offered to build.
note_for "tidy the footer" "(ready with no Done when, so never shaped)" \
  && once "tidy the footer" \
  && pass "a ready piece with no Done when is named, and prints only there" \
  || fail "tidy the footer is not named as never shaped, or prints elsewhere"
under "To build" "tidy the footer" \
  && fail "a ready piece with no Done when was offered as buildable" \
  || pass "a ready piece with no Done when is not offered as buildable"

under "Needs attention" "Allergy notes" \
  && fail "Allergy notes has a lower-case Readiness section but was named" \
  || pass "a Readiness heading in another case counts"

echo "== What the printout says about a piece ready to build =="

section "To build" | grep "Guest list export" | grep -q "(ready)" \
  && pass "a shaped piece waiting to be built says it is ready" \
  || fail "Guest list export does not say it is ready"

echo "== What the printout says about a held-up piece =="

# The commands that read this file say what is holding a piece up in a sentence
# a person can follow. A number is not that, and it is one they would have to go
# and look up.
section "Held up" | grep "Deposits" | grep -q "needs Card checkout" \
  && pass "a held-up piece names the piece holding it" \
  || fail "Deposits does not name Card checkout as its blocker"

section "Held up" | grep "Deposits" | grep -q "needs #" \
  && fail "Deposits names its blocker by number instead of by name" \
  || pass "a blocker is named rather than numbered"

# The invariant the whole plan rests on: a piece with an open blocker is never
# offered as buildable, so nothing in To build can be waiting on anything else
# in To build. Refund button counts a blocker, but it has closed, so it is free.
under "Held up" "Refund button" \
  && fail "Refund button's blocker has closed but it is still held" \
  || pass "a closed blocker does not hold a piece back"

section "To build" | grep "Refund button" | grep -q "(ready)" \
  && pass "a piece whose blocker has closed is ready to build" \
  || fail "Refund button is not offered as ready"

under "To build" "Deposits" \
  && fail "a piece with an open blocker was offered as buildable" \
  || pass "a piece with an open blocker stays out of To build"

echo "== A piece made of parts =="

# A parent piece is a container. It gets its own group, shows how many of its
# parts are done, and is never offered as a slice to build directly.
section "Made of parts" | grep "Booking flow" | grep -q "1 of 2 parts done" \
  && pass "the parent is under Made of parts and shows how many parts are done" \
  || fail "Booking flow is not under Made of parts with its part count"

once "Booking flow" \
  && pass "the parent appears once, only as a container" \
  || fail "Booking flow appears somewhere other than its own group"

under "Needs attention" "Booking flow" \
  && fail "a parent with no state was named for having none" \
  || pass "a parent with no state is never named for having none"

echo "== A project still on AI Build Kit's labels =="

# Only the labels an older project had. Nothing moves its issues onto the new
# labels, so each one is named under Needs attention, none is offered to build,
# and nothing is written to GitHub.
cat >"$WORK/older.json" <<'JSON'
[
  {"number": 1, "title": "Card checkout", "html_url": "http://x/1",
   "body": "## Done when\nA card is charged.", "assignees": [],
   "labels": [{"name": "ready"}]},
  {"number": 2, "title": "Rename the header", "html_url": "http://x/2",
   "body": "## Done when\nIt reads Bookings.", "assignees": [],
   "labels": [{"name": "building"}]},
  {"number": 3, "title": "Weekly payouts", "html_url": "http://x/3",
   "body": "## Done when\nSellers are paid.", "assignees": [],
   "labels": [{"name": "blocked"}]},
  {"number": 4, "title": "make the calendar nicer", "html_url": "http://x/4",
   "body": "half a sentence", "assignees": [],
   "labels": [{"name": "shaping"}, {"name": "needs-clarification"}]}
]
JSON
mkdir -p "$WORK/older"
: > "$WORK/older-calls.log"
(cd "$WORK/older" && FIXTURE="$WORK/older.json" GH_CALLS="$WORK/older-calls.log" \
  "$REFRESH" >/dev/null 2>&1) \
  || fail "the printout could not be written for an older project"
OLDER="$WORK/older/plan.local.md"
if [ -f "$OLDER" ]; then
  named=yes
  for piece in "Card checkout" "Rename the header" "Weekly payouts" "make the calendar nicer"; do
    section "Needs attention" "$OLDER" | grep "$piece" | grep -q "a label from AI Build Kit's model" \
      || { named=no; fail "$piece carries an old label but is not named under Needs attention"; }
  done
  [ "$named" = no ] || pass "every piece on an old label is named as carrying one the kit does not use"
  section "To build" "$OLDER" | grep -q . \
    && fail "a piece on an old label was offered as buildable" \
    || pass "a piece on an old label is not offered as buildable"
  grep -qE '^(issue edit|issue create|label )' "$WORK/older-calls.log" \
    && fail "the printout moved an older project's issues" \
    || pass "an older project's issues are left exactly as they are"
else
  fail "no printout was written for an older project"
fi

echo "== When the gate script is not beside the printout =="

# The printout takes Needs attention from the gate script beside it. A copy with
# no gate beside it still writes the board, and says the labels were not checked
# and how to get the gate back, rather than leaving Needs attention silently
# empty.
mkdir -p "$WORK/lone/tools" "$WORK/lone/project"
cp "$REFRESH" "$WORK/lone/tools/plan-refresh.sh"
(cd "$WORK/lone/project" && sh "$WORK/lone/tools/plan-refresh.sh" >/dev/null 2>&1) \
  || fail "the printout could not be written with no gate script beside it"
if [ -f "$WORK/lone/project/plan.local.md" ]; then
  section "Needs attention" "$WORK/lone/project/plan.local.md" | grep -q "gate.py" \
    && section "Needs attention" "$WORK/lone/project/plan.local.md" | grep -q "/maintain" \
    && pass "with no gate script beside it, the printout says so and names /maintain" \
    || fail "with no gate script beside it, the printout does not say the labels were not checked"
else
  fail "no printout was written with no gate script beside it"
fi

echo "== Which ready pieces go together =="

# /queue prints the groups and never works them out, so the printout is where a
# clash has to be caught. Each ready piece names the areas it may change on the
# Boundary line of its Reach section. Two pieces that name the same area, in
# any mix of capitals, never share a group, since building them in one run
# could change the same thing twice. A piece whose Boundary line is missing
# goes alone, because nothing says what it changes. A piece opened with the
# GitHub form carries the line under a Reach heading of its own, and it counts
# the same. The one-line Touches an older piece carries is no longer read, so
# such a piece goes alone like one with no line at all.
#
# Guest list export and Export to spreadsheet both name exports. Booking
# reminders names the guest list under a form heading. Seat map has no Boundary
# line and Gift wrap left the form's field empty. Old refunds carries only a
# Touches line, which names an area another piece's Boundary names, and it
# must still go alone. Refund receipts clashes with
# every group before Seat map's, so it is the piece that would join Seat map if
# a piece going alone could be joined. Deposits is ready but held up
# by an open piece, so it is in no group to build now. Guest list export and
# Refund button share nothing, so they must end up together, or a printout that
# put every piece alone would pass the rest of this.
cat >"$WORK/groups.json" <<'JSON'
[
  {"number": 1, "title": "Guest list export", "html_url": "http://x/1",
   "body": "## Done when\nThe list downloads.\n\nBoundary: guest list, exports\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 2, "title": "Refund button", "html_url": "http://x/2",
   "body": "## Done when\nA refund is sent.\n\nBoundary: Refunds\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 3, "title": "Export to spreadsheet", "html_url": "http://x/3",
   "body": "## Done when\nA sheet downloads.\n\nBoundary: Exports, settings\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 4, "title": "Seat map", "html_url": "http://x/4",
   "body": "## Done when\nSeats show.", "assignees": [],
   "labels": [{"name": "state:ready"}]},
  {"number": 5, "title": "Booking reminders", "html_url": "http://x/5",
   "body": "### Done when\n\nA reminder goes out.\n\n### Reach\n\nBoundary: Guest List\nReaches: invitations, no test covers it\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 6, "title": "Deposits", "html_url": "http://x/6",
   "body": "## Done when\nA deposit is held.\n\nBoundary: payments\n",
   "assignees": [], "labels": [{"name": "state:ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 7, "title": "Card checkout", "html_url": "http://x/7",
   "body": "## Done when\nA card is charged.\n\nBoundary: payments\n",
   "assignees": [], "labels": [{"name": "state:shaping"}, {"name": "shaping:raw"}]},
  {"number": 8, "title": "Gift wrap", "html_url": "http://x/8",
   "body": "## Done when\nA gift is wrapped.\n\n### Reach\n\n_No response_\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 9, "title": "Refund receipts", "html_url": "http://x/9",
   "body": "## Done when\nA receipt is sent.\n\nBoundary: refunds, settings\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 10, "title": "Deposit refunds", "html_url": "http://x/10",
   "body": "## Done when\nA deposit comes back.\n\nBoundary: deposits\n",
   "assignees": [], "labels": [{"name": "state:ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 11, "title": "Calendar invites", "html_url": "http://x/11",
   "body": "## Done when\nAn invite goes out.\n\nBoundary: invites\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready\n",
   "assignees": [], "labels": [{"name": "state:ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 12, "title": "Calendar sync", "html_url": "http://x/12",
   "body": "## Done when\nThe calendar syncs.\n\nBoundary: `calendar`.\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Not ready\n- BLOCKING Data: nobody said which calendar wins.\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 13, "title": "Calendar colours", "html_url": "http://x/13",
   "body": "## Done when\nDays are coloured.\n\n~~~\nBoundary: menu\n~~~\n\n## Reach\nBoundary: Calendar\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 14, "title": "Invite reminders", "html_url": "http://x/14",
   "body": "## Done when\nA reminder follows the invite.\n\nBoundary: reminders\n",
   "assignees": [], "labels": [{"name": "state:ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 15, "title": "Stock sync", "html_url": "http://x/15",
   "body": "## Done when\nStock matches.\n\nBoundary: stock\n",
   "assignees": [], "labels": [{"name": "state:ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 16, "title": "Supplier account", "html_url": "http://x/16",
   "body": "## Done when\nOrders reach the supplier.\n\n## Waiting on you\nOpen the supplier account and put its key in .env.\n\nBoundary: suppliers\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 17, "title": "Menu photos", "html_url": "http://x/17",
   "body": "## Done when\nEach dish has a photo.\n\nWaiting on you: try it\n\nBoundary: menu\n\n## Readiness\n2026-09-30, checked by a session that did not shape it: Ready\n",
   "assignees": [], "labels": [{"name": "state:ready"}]},
  {"number": 18, "title": "Old refunds", "html_url": "http://x/18",
   "body": "## Done when\nAn old refund is listed.\n\nTouches: refunds\n",
   "assignees": [], "labels": [{"name": "state:ready"}]}
]
JSON
cat >"$WORK/bin-groups-gh" <<'SH'
#!/usr/bin/env sh
case "$1 $2" in
  "repo view") echo '{"nameWithOwner":"someone/project"}' ;;
  *) case "$2" in
       *"/issues?"*) cat "$FIXTURE" ;;
       *"/issues/6/dependencies/blocked_by")
         echo '[{"number":7,"title":"Card checkout","state":"open"}]' ;;
       *"/issues/10/dependencies/blocked_by")
         echo '[{"number":6,"title":"Deposits","state":"open"}]' ;;
       *"/issues/11/dependencies/blocked_by")
         echo '[{"number":12,"title":"Calendar sync","state":"open"}]' ;;
       *"/issues/14/dependencies/blocked_by")
         echo '[{"number":11,"title":"Calendar invites","state":"open"}]' ;;
       *"/issues/15/dependencies/blocked_by")
         echo '[{"number":1,"title":"Guest list export","state":"open"}]' ;;
       *) echo '[]' ;;
     esac ;;
esac
SH
mkdir -p "$WORK/groups/bin"
mv "$WORK/bin-groups-gh" "$WORK/groups/bin/gh"
chmod +x "$WORK/groups/bin/gh"
(cd "$WORK/groups" && PATH="$WORK/groups/bin:$PATH" FIXTURE="$WORK/groups.json" \
  "$REFRESH" >/dev/null 2>&1) \
  || fail "the printout could not be written for the groups fixture"
TOGETHER="$WORK/groups/plan.local.md"

# Each piece line under Go together, prefixed with the group it sits in.
grouped() {
  section "Go together" "$TOGETHER" \
    | awk '/^  Group [0-9]/ { g = $2; next } /^    / { print g "\t" $0 }'
}
group_of() {
  grouped | grep "$1" | cut -f1
}

if [ -f "$TOGETHER" ]; then
  [ -n "$(section "Go together" "$TOGETHER")" ] \
    && pass "the printout prints the groups of ready pieces" \
    || fail "the printout has no Go together groups"

  missing=""
  for piece in "Guest list export" "Refund button" "Export to spreadsheet" \
      "Seat map" "Booking reminders" "Gift wrap" "Refund receipts" "Old refunds"; do
    [ "$(grouped | grep -c "$piece")" -eq 1 ] || missing="$missing, $piece"
  done
  [ -z "$missing" ] \
    && pass "every piece free to build sits in exactly one group" \
    || fail "not in exactly one group: ${missing#, }"

  a=$(group_of "Guest list export"); b=$(group_of "Export to spreadsheet")
  [ -n "$a" ] && [ -n "$b" ] && [ "$a" != "$b" ] \
    && pass "two pieces naming the same area, in different capitals, never share a group" \
    || fail "Guest list export and Export to spreadsheet both touch exports but are not in separate groups"

  a=$(group_of "Guest list export"); b=$(group_of "Booking reminders")
  [ -n "$a" ] && [ -n "$b" ] && [ "$a" != "$b" ] \
    && grouped | grep "Booking reminders" | grep -q "boundary: guest list" \
    && pass "a Boundary line under a form heading is read and compared the same way" \
    || fail "Booking reminders' Boundary under the form heading was not read, or it shares a group with Guest list export"

  a=$(group_of "Guest list export"); b=$(group_of "Refund button")
  [ -n "$a" ] && [ "$a" = "$b" ] \
    && pass "two pieces that share no area go together" \
    || fail "Guest list export and Refund button share nothing but are not grouped together"

  alone=yes
  for piece in "Seat map" "Gift wrap" "Old refunds"; do
    g=$(group_of "$piece")
    [ -n "$g" ] && [ "$(grouped | awk -F '\t' -v g="$g" '$1 == g' | wc -l | tr -d ' ')" -eq 1 ] \
      || { alone=no; fail "$piece has no Boundary line but does not go alone"; }
    grouped | grep "$piece" | grep -q "Boundary unknown" \
      || { alone=no; fail "$piece does not say its Boundary is unknown"; }
  done
  [ "$alone" = no ] \
    || pass "a piece with no Boundary line, or only a Touches line, goes alone and says its Boundary is unknown"

  # The blocker invariant reaches the groups: a piece with an open blocker is
  # never in a group to build now.
  section "Go together" "$TOGETHER" | grep -q "Deposits" \
    && fail "a piece with an open blocker was put in a group to build now" \
    || pass "a piece with an open blocker is in no group"
  section "Held up" "$TOGETHER" | grep "Deposits" | grep -q "needs Card checkout" \
    && pass "and it still names the piece holding it up" \
    || fail "Deposits does not name Card checkout under Held up"

  # Backticks and a closing full stop come off in either order, a Boundary line
  # under a `## Reach` heading counts like the form's, and a line inside a ~~~ block is an
  # example rather than the piece's own.
  a=$(group_of "Calendar sync"); b=$(group_of "Calendar colours")
  [ -n "$a" ] && [ -n "$b" ] && [ "$a" != "$b" ] \
    && grouped | grep "Calendar sync" | grep -q "(boundary: calendar)" \
    && grouped | grep "Calendar colours" | grep -q "(boundary: calendar)" \
    && pass "an area written in backticks with a full stop clashes with the bare name" \
    || fail "Calendar sync and Calendar colours both touch the calendar but are not in separate groups"

  echo "== What a run can do with each ready piece =="

  # The marks the printout can read on the piece itself. /queue reads them here
  # and never opens the pieces, so the printout stays its only source.
  mark_on() {
    section "$1" "$TOGETHER" | grep "$2" | grep -q "$3"
  }
  mark_on "To build" "Guest list export" "(not yet checked)" \
    && pass "a piece with no Readiness section is marked not yet checked" \
    || fail "Guest list export has no Readiness section but is not marked not yet checked"
  mark_on "To build" "Calendar sync" "(not ready)" \
    && pass "a piece whose Readiness says Not ready is marked not ready" \
    || fail "Calendar sync is not marked not ready"
  mark_on "To build" "Supplier account" "(needs you)" \
    && pass "a piece with a step of the person's is marked needs you" \
    || fail "Supplier account is not marked needs you"
  mark_on "To build" "Menu photos" "(try it)" \
    && ! mark_on "To build" "Menu photos" "(needs you)" \
    && pass "a try it line is marked try it, never needs you" \
    || fail "Menu photos is not marked try it alone"
  section "To build" "$TOGETHER" | grep "Calendar colours" | grep -qE "\\((not |needs you|try it)" \
    && fail "Calendar colours is checked Ready but carries a mark" \
    || pass "a piece checked Ready with nothing of the person's carries no mark"

  echo "== Which held-up pieces are in the plan =="

  # A held-up piece joins the plan only when every open blocker in its chain
  # is in the plan. Deposits waits on a raw piece, so it waits its turn, and so does
  # Deposit refunds, which waits on Deposits.
  mark_on "Held up" "Deposits" "(in the plan)" \
    && fail "Deposits waits on a raw piece but was put in the plan" \
    || pass "a piece whose blocker is outside the plan waits its turn"
  mark_on "Held up" "Deposit refunds" "(in the plan)" \
    && fail "Deposit refunds waits on Deposits, which is outside the plan, but was put in it" \
    || pass "a piece further down a chain that leaves the plan waits its turn too"
  mark_on "Held up" "Stock sync" "(in the plan)" \
    && ! mark_on "Held up" "Stock sync" "(waits for" \
    && pass "a piece whose blocker is ready joins the plan and stacks on it" \
    || fail "Stock sync is not in the plan, or says it waits"

  # A piece stacked on one a run cannot take waits for it, with the reason,
  # and so does the piece stacked on that one.
  mark_on "Held up" "Calendar invites" "(in the plan)" \
    && mark_on "Held up" "Calendar invites" "(waits for Calendar sync, which is not ready)" \
    && pass "a piece stacked on one that is not ready waits for it and says why" \
    || fail "Calendar invites does not say it waits for Calendar sync, which is not ready"
  mark_on "Held up" "Invite reminders" "(in the plan)" \
    && mark_on "Held up" "Invite reminders" "(waits for Calendar invites, which waits for Calendar sync, which is not ready)" \
    && pass "the wait passes down the chain with each reason" \
    || fail "Invite reminders does not say it waits for Calendar invites and why"
else
  fail "no printout was written for the groups fixture"
fi

echo "== When GitHub cannot be reached =="

# The printout is the only view of the plan left when GitHub is out of reach, so
# a refresh that fails keeps the last one and says when it was written.
stamp=$(sed -n 's/^Last refreshed: //p' "$OUT")
before=$(cksum < "$OUT")
said=$(GH_DOWN=1 "$REFRESH" 2>&1) && fail "a refresh with GitHub out of reach reported success"
[ "$(cksum < "$OUT")" = "$before" ] \
  && pass "the last printout is left as it was" \
  || fail "a failed refresh changed the printout"
case "$said" in
  *"could not reach GitHub"*"$stamp"*) pass "it says GitHub was out of reach and when the printout was written" ;;
  *) fail "a failed refresh does not say when the printout was written: $said" ;;
esac

mkdir -p "$WORK/fresh"
said=$(cd "$WORK/fresh" && GH_DOWN=1 "$REFRESH" 2>&1) && fail "a refresh with no GitHub and no printout reported success"
case "$said" in
  *"no earlier printout"*) pass "with no earlier printout, it says there is none" ;;
  *) fail "a failed first refresh does not say there is no printout: $said" ;;
esac

echo "== GitHub failures explain how to recover =="

mkdir -p "$WORK/access/bin" "$WORK/access/project"
cat >"$WORK/access/bin/gh" <<'SH'
#!/usr/bin/env sh
case "$1 $2" in
  "repo view") stage=repo ;;
  *) case "$2" in
    *"/dependencies/blocked_by") stage=blockers ;;
    *) stage=listing ;;
  esac ;;
esac
if [ "$stage" = "$FAIL_STAGE" ]; then
  cat "$ERROR_FILE" >&2
  exit 1
fi
case "$stage" in
  repo) echo '{"nameWithOwner":"someone/project"}' ;;
  listing) cat "$FIXTURE" ;;
  blockers) echo "${BLOCKER_RESPONSE:-[]}" ;;
esac
SH
chmod +x "$WORK/access/bin/gh"

# Each of the three GitHub calls can fail. None may replace the last list,
# particularly when the missing answer names a blocker.
for stage in repo listing blockers; do
  cp "$OUT" "$WORK/access/project/plan.local.md"
  before=$(cksum < "$WORK/access/project/plan.local.md")
  printf '%s\n' 'error connecting to api.github.com' > "$WORK/access/error"
  said=$(cd "$WORK/access/project" && PATH="$WORK/access/bin:$PATH" \
    FAIL_STAGE="$stage" ERROR_FILE="$WORK/access/error" FIXTURE="$WORK/issues.json" \
    "$REFRESH" 2>&1) && fail "$stage failure reported success"
  case "$said" in
    *"error connecting to api.github.com"*"network"*) pass "$stage failure keeps the GitHub error and names network access" ;;
    *) fail "$stage failure hides the cause or the recovery: $said" ;;
  esac
  [ "$(cksum < "$WORK/access/project/plan.local.md")" = "$before" ] \
    && pass "$stage failure preserves the earlier printout" \
    || fail "$stage failure replaced the earlier printout"
done

cp "$OUT" "$WORK/access/project/plan.local.md"
before=$(cksum < "$WORK/access/project/plan.local.md")
said=$(cd "$WORK/access/project" && PATH="$WORK/access/bin:$PATH" \
  FAIL_STAGE=none BLOCKER_RESPONSE='{}' ERROR_FILE="$WORK/access/error" \
  FIXTURE="$WORK/issues.json" "$REFRESH" 2>&1) \
  && fail "a malformed blocker answer reported success"
[ "$(cksum < "$WORK/access/project/plan.local.md")" = "$before" ] \
  && pass "a malformed blocker answer preserves the earlier printout" \
  || fail "a malformed blocker answer replaced the earlier printout"

access_error() {
  printf '%s\n' "$1" > "$WORK/access/error"
  (cd "$WORK/access/project" && PATH="$WORK/access/bin:$PATH" \
    FAIL_STAGE=repo ERROR_FILE="$WORK/access/error" FIXTURE="$WORK/issues.json" \
    GH_TOKEN=synthetic-private-value "$REFRESH" 2>&1)
}
said=$(access_error 'HTTP 401: Requires authentication') && fail "unauthenticated gh reported success"
case "$said" in
  *"GH_TOKEN"*"terminal"*) pass "authentication refusal asks about credential sources before re-login" ;;
  *) fail "authentication refusal skipped credential diagnosis: $said" ;;
esac

said=$(access_error 'To get started with GitHub CLI, please run: gh auth login') \
  && fail "signed-out gh reported success"
case "$said" in
  *"not signed in"*"gh auth login"*) pass "signed-out gh names sign-in and the login command" ;;
  *) fail "signed-out gh has no sign-in recovery: $said" ;;
esac
said=$(access_error 'none of the git remotes configured for this repository point to a known GitHub host') \
  && fail "a project with no GitHub remote reported success"
case "$said" in
  *"no GitHub remote"*) pass "a missing GitHub remote is named" ;;
  *) fail "a missing GitHub remote is called an access failure: $said" ;;
esac
said=$(access_error 'HTTP 403: Resource not accessible by integration') \
  && fail "refused access reported success"
case "$said" in
  *"HTTP 403"*"permission"*) pass "refused access names permission rather than network" ;;
  *) fail "refused access has no permission recovery: $said" ;;
esac

said=$(access_error "GraphQL: Could not resolve to a Repository with the name 'someone/private-project'. (repository)") \
  && fail "an inaccessible repository reported success"
case "$said" in
  *"permission"*) pass "a GitHub repository lookup refusal is not called a network failure" ;;
  *) fail "a repository lookup refusal has the wrong recovery: $said" ;;
esac

# Fake credentials cover environment values, GitHub tokens, request headers,
# URL credentials and query parameters. None is a real account's credential.
said=$(access_error 'error connecting to api.github.com
synthetic-private-value ghp_FakeTokenForPrintoutOnly github_pat_FakeTokenForPrintoutOnly
Authorization: Bearer synthetic-header-value
https://user:synthetic-url-password@example.test/?access_token=synthetic-query-value
password=synthetic-password-value') && fail "a failure containing credentials reported success"
printf '%s\n' "$said" | grep -q 'error connecting to api.github.com' \
  && pass "redaction keeps the useful error" || fail "redaction lost the useful error"
for secret in synthetic-private-value ghp_FakeTokenForPrintoutOnly github_pat_FakeTokenForPrintoutOnly \
    synthetic-header-value synthetic-url-password synthetic-query-value synthetic-password-value; do
  case "$said" in
    *"$secret"*) fail "a diagnostic disclosed a fake credential" ;;
    *) pass "a fake credential is masked" ;;
  esac
done

if [ "$FAIL" -eq 0 ]; then
  echo
  echo "plan-printout.sh: all checks passed"
else
  echo
  echo "plan-printout.sh: FAILED" >&2
fi
exit "$FAIL"
