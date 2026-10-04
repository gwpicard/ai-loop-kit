#!/usr/bin/env sh
# fake-github.sh: check the replay harness's stand-in for the GitHub CLI.
#
# The stand-in answers the commands the kit reaches for and refuses the rest to
# a log. Both halves matter. An answer that drifts from the real CLI's shape
# makes a scenario fail for a reason the kit did not cause, and a refusal that
# quietly becomes an answer hides the fact that nobody modelled it.
#
# Everything here runs against a throwaway state file. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
GH="$ROOT/tests/replay/fake-github/gh"

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

FAKE_GH_STATE="$WORK/.gh-fixture.json"
FAKE_GH_LOG="$WORK/gh.log"
export FAKE_GH_STATE FAKE_GH_LOG

# A repository to stand on, so the branch a pull request is opened from is real.
git init -q "$WORK/project"
cd "$WORK/project"
git config user.email rehearsal@example.com
git config user.name Rehearsal
git commit -q --allow-empty -m "first"
git branch -M main
# A bare remote next door, as the replay harness gives every project, so a merge
# has somewhere to land.
git init -q --bare "$WORK/project.git"
git remote add origin "$WORK/project.git"
git push -q origin main
git checkout -q -b deposits
echo deposit > deposit.txt
git add deposit.txt
git commit -q -m "Take a deposit"
git push -q origin deposits

echo "== The commands the kit uses =="

"$GH" --version | grep -q "gh version" \
  && pass "--version answers plainly" \
  || fail "--version did not answer"

first=$("$GH" issue create --title "Take a deposit" --body "## Done when
- a deposit is recorded" --label behaviour)
case "$first" in
  https://github.com/*/issues/1) pass "issue create returns the new issue's address" ;;
  *) fail "issue create returned '$first'" ;;
esac

"$GH" issue create --title "Refund a deposit" --body "## Done when
- a refund is recorded" --label behaviour > /dev/null

# A dependency the agent worked out during a run, rather than one seeded by a
# fixture. This is the call that was refused throughout the first measured pass.
"$GH" api --method POST "repos/rehearsal/project/issues/2/dependencies/blocked_by" \
  -f issue_id=1 > /dev/null 2>&1 \
  && pass "a dependency can be recorded during a run" \
  || fail "recording a dependency was refused"

blocked=$("$GH" api "repos/rehearsal/project/issues/2/dependencies/blocked_by")
case "$blocked" in
  *'"number": 1'*) pass "the recorded dependency reads back" ;;
  *) fail "the dependency did not read back: $blocked" ;;
esac

summary=$("$GH" api "repos/rehearsal/project/issues?state=open")
case "$summary" in
  *'"blocked_by": 1'*) pass "the listing says which pieces are held up" ;;
  *) fail "the listing does not report the dependency" ;;
esac

echo "== A piece made of parts =="

"$GH" issue create --title "Booking flow" --body "## So that
- guests can book" --label "how it works" > /dev/null
"$GH" issue create --title "Pick a date range" --body "## Done when
- a range is chosen" --label "how it works" > /dev/null

# Issue 3 is the parent, issue 4 a part of it. The kit sends the issue number,
# mirroring the blocked-by call.
"$GH" api --method POST "repos/rehearsal/project/issues/3/sub_issues" \
  -f sub_issue_id=4 > /dev/null 2>&1 \
  && pass "a part can be recorded during a run" \
  || fail "recording a sub-issue was refused"

parts=$("$GH" api "repos/rehearsal/project/issues/3/sub_issues")
case "$parts" in
  *'"number": 4'*) pass "the recorded part reads back" ;;
  *) fail "the sub-issue did not read back: $parts" ;;
esac

made_of=$("$GH" api "repos/rehearsal/project/issues?state=open")
case "$made_of" in
  *'"total": 1, "completed": 0'*) pass "the listing counts a piece's open parts" ;;
  *) fail "the listing does not count the parts" ;;
esac

# Closing the part moves the parent's tally, which is what tells the printout a
# part is done.
"$GH" issue close 4 > /dev/null 2>&1 || fail "closing the part failed"
done_summary=$("$GH" api "repos/rehearsal/project/issues?state=open")
case "$done_summary" in
  *'"total": 1, "completed": 1'*) pass "closing a part moves the parent's tally" ;;
  *) fail "the parent tally did not move: $done_summary" ;;
esac

"$GH" issue comment 1 --body "Built in pull request #1." > /dev/null \
  && pass "issue comment is accepted" \
  || fail "issue comment was refused"

echo "== The repository, as founding reads and sets it =="

# The tooling check reads these three fields together. Refusing one made the
# whole call fail, and founding then reported that no repository existed.
repo=$("$GH" repo view --json nameWithOwner,hasIssuesEnabled,viewerPermission)
case "$repo" in
  *'"viewerPermission": "ADMIN"'*) pass "repo view answers the fields the tooling check reads" ;;
  *) fail "repo view returned '$repo'" ;;
esac

# Founding switches on deleting a merged branch, and the setup skill names the
# API form. Both forms land on the same setting.
"$GH" api -X PATCH repos/rehearsal/project -F delete_branch_on_merge=true > /dev/null \
  && pass "the API form of the merged-branch setting is accepted" \
  || fail "the API form of the merged-branch setting was refused"
case "$("$GH" repo view --json deleteBranchOnMerge)" in
  *'"deleteBranchOnMerge": true'*) pass "and the setting reads back as on" ;;
  *) fail "the merged-branch setting did not read back as on" ;;
esac
"$GH" repo edit --delete-branch-on-merge > /dev/null \
  && pass "repo edit --delete-branch-on-merge is accepted" \
  || fail "repo edit --delete-branch-on-merge was refused"

# Any other setting is one nobody modelled, so it must stay refused.
if "$GH" repo edit --visibility public > /dev/null 2>&1; then
  fail "an unmodelled repository setting was accepted"
else
  pass "an unmodelled repository setting is still refused"
fi
if "$GH" api -X PATCH repos/rehearsal/project -F private=false > /dev/null 2>&1; then
  fail "an unmodelled setting through the API was accepted"
else
  pass "an unmodelled setting through the API is still refused"
fi

echo "== Pull requests =="

url=$("$GH" pr create --title "Take a deposit" --body "Closes #1")
case "$url" in
  https://github.com/*/pull/1) pass "pr create returns the new address" ;;
  *) fail "pr create returned '$url'" ;;
esac

# Straight after opening one, which is how the kit reports the link.
looked_up=$("$GH" pr view --json url)
case "$looked_up" in
  *'/pull/1'*) pass "pr view finds the pull request for the current branch" ;;
  *) fail "pr view --json url returned '$looked_up'" ;;
esac

by_number=$("$GH" pr view 1 --json number,title,state,statusCheckRollup)
case "$by_number" in
  *'"conclusion": "SUCCESS"'*) pass "pr view reports the check by number" ;;
  *) fail "pr view by number returned '$by_number'" ;;
esac

by_branch=$("$GH" pr view deposits --json url)
case "$by_branch" in
  *'/pull/1'*) pass "pr view accepts a branch name" ;;
  *) fail "pr view by branch returned '$by_branch'" ;;
esac

checks=$("$GH" pr checks 1)
case "$checks" in
  *pass*) pass "pr checks reports the check green" ;;
  *) fail "pr checks returned '$checks'" ;;
esac

# Opening a pull request closes nothing. GitHub closes the issue named by
# "Closes #1" when the pull request merges, and a stand-in that closed it on
# opening told the kit a piece was done while its fix sat unmerged.
case "$("$GH" issue view 1)" in
  *'"state": "open"'*) pass "opening a pull request leaves its piece open" ;;
  *) fail "the piece closed when its pull request was only opened" ;;
esac

"$GH" pr merge 1 > /dev/null \
  && pass "pr merge is accepted" \
  || fail "pr merge was refused"
case "$("$GH" issue view 1)" in
  *'"state": "closed"'*) pass "the piece closes when its pull request merges" ;;
  *) fail "the piece stayed open after its pull request merged" ;;
esac
case "$("$GH" pr view 1 --json state)" in
  *MERGED*) pass "the pull request reads as merged" ;;
  *) fail "the pull request does not read as merged" ;;
esac

# The merge has to reach the remote. A kit that checks the base branch there
# would otherwise find the fix missing and rightly say it never went live.
git fetch -q origin
if git merge-base --is-ancestor origin/deposits origin/main; then
  pass "the merge lands the branch on the remote's main"
else
  fail "main on the remote does not carry the merged branch"
fi

if "$GH" pr merge 1 > /dev/null 2>&1; then
  fail "a pull request merged twice"
else
  pass "a merged pull request cannot merge again"
fi

if "$GH" pr view no-such-branch --json url > /dev/null 2>&1; then
  fail "pr view invented a pull request for a branch that has none"
else
  pass "a branch with no pull request says so, as the real CLI does"
fi

echo "== A pull request stacked on another =="

# A run builds a piece that waits on another piece of the same run on top of
# that piece's branch, and its pull request aims at that branch rather than at
# main. GitHub refuses a base that is not a branch on the repository, so the
# stand-in does too, and a kit that opens the stacked pull request before the
# branch under it is uploaded finds out here rather than on the day.
git fetch -q origin
git checkout -q main
git merge -q --ff-only origin/main
git checkout -q -b invoices
echo invoice > invoice.txt
git add invoice.txt
git commit -q -m "Keep an invoice"
git checkout -q -b invoice-totals
echo total > total.txt
git add total.txt
git commit -q -m "Total the invoices"

before=$("$GH" pr list --state all --json number)
if "$GH" pr create --title "Total the invoices" --body "Merge the invoice piece first." \
    --head invoice-totals --base invoices > /dev/null 2>&1; then
  fail "a pull request was opened on a base that is not on the remote"
else
  pass "a base that is not on the remote is refused, as on GitHub"
fi
[ "$("$GH" pr list --state all --json number)" = "$before" ] \
  && pass "and the refused pull request was not recorded" \
  || fail "a refused pull request was recorded anyway"

git push -q origin invoices invoice-totals
printf 'Closes #1\n\nThe invoice piece.\n' > "$WORK/invoices-body.md"
base_url=$("$GH" pr create --title "Keep an invoice" --body-file "$WORK/invoices-body.md" \
  --head invoices --base main)
base_pr=${base_url##*/}
case "$("$GH" pr view "$base_pr" --json body)" in
  *'The invoice piece.'*) pass "pr create reads the body from --body-file" ;;
  *) fail "pr create lost the body given with --body-file" ;;
esac

stacked_url=$(printf 'Merge #%s first, then this one.\n' "$base_pr" \
  | "$GH" pr create --title "Total the invoices" --body-file - --head invoice-totals --base invoices)
stacked_pr=${stacked_url##*/}
stacked_view=$("$GH" pr view "$stacked_pr" --json baseRefName,headRefName)
case "$stacked_view" in
  *'"baseRefName": "invoices"'*) pass "a stacked pull request reads back with the branch it stacks on as its base" ;;
  *) fail "the stacked pull request did not keep its base: $stacked_view" ;;
esac
case "$("$GH" pr view "$stacked_pr" --json body)" in
  *"Merge #$base_pr first"*) pass "pr create reads the body from standard input with --body-file -" ;;
  *) fail "pr create lost the body given on standard input" ;;
esac

listed=$("$GH" pr list --base invoices --json number,baseRefName)
case "$listed" in
  *"\"number\": $stacked_pr"*) pass "pr list --base finds the stacked pull request" ;;
  *) fail "pr list --base invoices returned '$listed'" ;;
esac
case "$listed" in
  *'"baseRefName": "main"'*) fail "pr list --base also listed a pull request aimed at main" ;;
  *) pass "and leaves out the one aimed at main" ;;
esac
# A resumed run looks for a pull request already open from the piece's branch
# before it opens one, so it never opens a second.
by_head=$("$GH" pr list --head invoice-totals --json number,headRefName)
case "$by_head" in
  *"\"number\": $stacked_pr"*) pass "pr list --head finds the pull request open from a branch" ;;
  *) fail "pr list --head invoice-totals returned '$by_head'" ;;
esac
# The worktree script asks for the head commit, so a merged piece whose branch
# has gone from the remote still counts its merged work as saved.
case "$("$GH" pr list --head invoice-totals --state all --json state,headRefOid)" in
  *"\"headRefOid\": \"$(git rev-parse invoice-totals)\""*) pass "pr list --json headRefOid gives the head branch's commit" ;;
  *) fail "pr list --json headRefOid did not give the head branch's commit" ;;
esac
[ "$("$GH" pr list --head no-such-branch --json number)" = "[]" ] \
  && pass "and answers an empty list for a branch with none" \
  || fail "pr list --head invented a pull request for a branch with none"
# /maintain's stale-branch listing compares a branch with the tip GitHub
# recorded for its merged pull request.
oid=$("$GH" pr list --state merged --head deposits --base main --json number,headRefOid)
case "$oid" in
  *"\"headRefOid\": \"$(git rev-parse deposits)\""*) pass "pr list gives a merged pull request's head commit" ;;
  *) fail "pr list --json headRefOid returned '$oid'" ;;
esac
case "$("$GH" pr list --state all --json number,state)" in
  *'"MERGED"'*) pass "pr list --state all includes a merged pull request" ;;
  *) fail "pr list --state all left out the merged pull request" ;;
esac
if "$GH" pr list --json number,nosuchfield > /dev/null 2>&1; then
  fail "pr list answered a field nobody modelled"
else
  pass "pr list refuses a field nobody modelled, as pr view does"
fi

# A remote that is a network address is never contacted. Its branches cannot
# be read, so a base other than main counts as missing, and stderr says so.
git remote set-url origin https://example.invalid/rehearsal/project.git
if "$GH" pr create --title "Anything" --body "x" --head invoice-totals --base invoices > /dev/null 2> "$WORK/far.err"; then
  fail "a base was taken as present on a remote that was never asked"
else
  grep -q 'not a folder on this computer' "$WORK/far.err" \
    && pass "a network remote is never asked, and the base counts as missing" \
    || fail "the refusal did not say the remote was not asked"
fi
git remote set-url origin "$WORK/project.git"

# The base merges first. The stacked pull request is then aimed at main, as
# the merge rule says, and merges there.
"$GH" pr merge "$base_pr" > /dev/null || fail "the base pull request did not merge"
if "$GH" pr edit "$stacked_pr" --base no-such-branch > /dev/null 2>&1; then
  fail "a pull request was moved onto a base that is not on the remote"
else
  pass "moving a pull request onto a base that is not on the remote is refused"
fi
"$GH" pr edit "$stacked_pr" --base main > /dev/null \
  && pass "pr edit --base moves a stacked pull request onto main" \
  || fail "pr edit --base main was refused"
case "$("$GH" pr view "$stacked_pr" --json baseRefName)" in
  *'"baseRefName": "main"'*) pass "and it reads back as aimed at main" ;;
  *) fail "the stacked pull request still does not aim at main" ;;
esac
"$GH" pr merge "$stacked_pr" > /dev/null || fail "the stacked pull request did not merge"
git fetch -q origin
git merge-base --is-ancestor origin/invoice-totals origin/main \
  && pass "the stacked pull request lands on the remote's main after the move" \
  || fail "the remote's main does not carry the stacked branch"

echo "== A claim on a piece =="

# A run claims a piece and reads the claim back, and backs off by taking its
# own name off a piece somebody else claimed first.
"$GH" issue edit 2 --add-assignee @me --add-label building > /dev/null
printf 'Claimed by run 2026-09-30-2215\n' > "$WORK/claim.md"
"$GH" issue comment 2 --body-file "$WORK/claim.md" > /dev/null \
  && pass "issue comment accepts --body-file" \
  || fail "issue comment --body-file was refused"
case "$("$GH" issue view 2 --json labels,assignees,comments)" in
  *'Claimed by run 2026-09-30-2215'*) pass "issue view shows the comments, so a claim can be read back" ;;
  *) fail "issue view does not show the claim comment" ;;
esac
# The later claimant deletes its own claim comment. As on GitHub, the view
# gives each comment its node id, the REST listing gives the numeric id, and a
# deletion through the API takes the numeric one. The CLI form deletes the last.
"$GH" issue comment 2 --body "Claimed by run 2026-09-30-221501" > /dev/null
case "$("$GH" issue view 2 --json comments)" in
  *'"id": "IC_'*) pass "issue view gives each comment its node id, as GitHub does" ;;
  *) fail "issue view does not give node ids for the comments" ;;
esac
node=$("$GH" issue view 2 --json comments | python3 -c 'import json, sys; print(json.load(sys.stdin)["comments"][-1]["id"])')
if "$GH" api -X DELETE "repos/rehearsal/project/issues/comments/$node" > /dev/null 2>&1; then
  fail "a comment was deleted by its node id, which the REST endpoint does not take"
else
  pass "a deletion by node id is refused, as the REST endpoint refuses it"
fi
later=$("$GH" api repos/rehearsal/project/issues/2/comments | python3 -c 'import json, sys; print([c["id"] for c in json.load(sys.stdin) if c["body"].startswith("Claimed by run 2026-09-30-221501")][0])')
case "$later" in
  [0-9]*) pass "the REST listing gives each comment its numeric id" ;;
  *) fail "the REST listing gave '$later' as the id" ;;
esac
"$GH" api -X DELETE "repos/rehearsal/project/issues/comments/$later" > /dev/null \
  && pass "a comment can be deleted through the API by its numeric id" \
  || fail "deleting a comment through the API was refused"
case "$("$GH" issue view 2 --json comments)" in
  *'221501'*) fail "the deleted comment is still on the piece" ;;
  *'Claimed by run 2026-09-30-2215'*) pass "and only that comment is gone" ;;
  *) fail "deleting one comment took the others with it" ;;
esac
if "$GH" api -X DELETE "repos/rehearsal/project/issues/comments/$later" > /dev/null 2>&1; then
  fail "a comment was deleted twice"
else
  pass "a comment that is gone cannot be deleted again"
fi
"$GH" issue comment 2 --body "Claimed by run 2026-09-30-221502" > /dev/null
"$GH" issue comment 2 --delete-last --yes > /dev/null \
  && pass "issue comment --delete-last is accepted" \
  || fail "issue comment --delete-last was refused"
case "$("$GH" issue view 2 --json comments)" in
  *'221502'*) fail "the last comment is still on the piece" ;;
  *'Claimed by run 2026-09-30-2215'*) pass "and removes the last comment only" ;;
  *) fail "--delete-last took more than the last comment" ;;
esac
# A state file written before comments had ids keeps each as a bare string.
# Those get ids from a range of their own, so they never collide with new ones.
python3 - "$FAKE_GH_STATE" <<'PY2'
import json, sys
state = json.load(open(sys.argv[1]))
for issue in state["issues"]:
    if issue["number"] == 1:
        issue["comments"] = ["An older comment."]
json.dump(state, open(sys.argv[1], "w"))
PY2
ids=$( { "$GH" api repos/rehearsal/project/issues/1/comments; "$GH" api repos/rehearsal/project/issues/2/comments; } \
  | python3 -c 'import json, sys; ids = [c["id"] for line in sys.stdin for c in json.loads(line)]; print(len(ids), len(set(ids)))')
[ "$(echo "$ids" | cut -d' ' -f1)" = "$(echo "$ids" | cut -d' ' -f2)" ] \
  && pass "an older bare comment and the new ones never share an id" \
  || fail "two comments share an id: $ids"
"$GH" api --method POST repos/rehearsal/project/issues/1/comments -f body="Added through the API." > /dev/null \
  && pass "a comment can be added through the API" \
  || fail "adding a comment through the API was refused"
"$GH" issue edit 2 --remove-assignee @me > /dev/null \
  && pass "issue edit --remove-assignee is accepted" \
  || fail "issue edit --remove-assignee was refused"
case "$("$GH" issue view 2)" in
  *'"assignees": []'*) pass "and the assignee is gone" ;;
  *) fail "the assignee is still on the piece" ;;
esac
printf '## Done when\n- a refund is recorded\n\nWhere is the refund kept?\n' > "$WORK/question.md"
"$GH" issue edit 2 --body-file "$WORK/question.md" > /dev/null
case "$("$GH" issue view 2)" in
  *'Where is the refund kept?'*) pass "issue edit reads the body from --body-file" ;;
  *) fail "issue edit lost the body given with --body-file" ;;
esac

echo "== The first upload into an empty repository =="

# A founded project's repository exists on GitHub but holds nothing. The first
# upload reads that, names the repository and whether it is public or private,
# and on a yes pushes the piece's branch, creates main through the API at the
# commit the branch was cut from, and makes main the default branch. Branches
# are named in every init, since Git's default branch is master on some hosts.
up="$WORK/upload"
git init -q -b main "$up"
git -C "$up" config user.email rehearsal@example.com
git -C "$up" config user.name Rehearsal
git -C "$up" config commit.gpgsign false
git -C "$up" commit -q --allow-empty -m "Founded"
git init -q --bare -b main "$up.git"
git -C "$up" remote add origin "$up.git"
FAKE_GH_STATE="$WORK/upload.json"
printf '{"repo": "rehearsal/upload", "next": 1, "issues": []}\n' > "$FAKE_GH_STATE"
cd "$up"

set +e
git ls-remote --exit-code --heads origin > /dev/null 2>&1
empty=$?
set -e
[ "$empty" -eq 2 ] \
  && pass "an empty repository answers the branch listing with exit 2" \
  || fail "the branch listing of an empty repository exited $empty, not 2"

case "$("$GH" repo view --json nameWithOwner,visibility,isEmpty,defaultBranchRef)" in
  *'"visibility": "PRIVATE"'*'"isEmpty": true'*'"defaultBranchRef": null'*)
    pass "repo view says the repository is private, empty, and has no default branch yet" ;;
  *) fail "repo view of an empty repository returned the wrong shape" ;;
esac
[ "$("$GH" repo view --json visibility -q .visibility)" = "PRIVATE" ] \
  && pass "repo view answers --jq .visibility with the bare word" \
  || fail "repo view --jq .visibility did not print PRIVATE"
printf '{"repo": "rehearsal/upload", "next": 1, "issues": [], "visibility": "PUBLIC"}\n' > "$WORK/public.json"
[ "$(FAKE_GH_STATE="$WORK/public.json" "$GH" repo view --json visibility -q .visibility)" = "PUBLIC" ] \
  && pass "a scenario can make the repository public" \
  || fail "the visibility a scenario set was not read back"

if "$GH" repo edit --default-branch main > /dev/null 2>&1; then
  fail "main became the default branch before it existed"
else
  pass "main cannot be the default branch before it exists, as on GitHub"
fi

git checkout -q -b first-piece
echo piece > piece.txt
git add piece.txt
git commit -q -m "The first piece"
git push -q origin first-piece
base=$(git merge-base main first-piece)

if "$GH" api repos/rehearsal/upload/git/refs -f ref=refs/heads/main -f sha=0123456789abcdef0123456789abcdef01234567 > /dev/null 2>&1; then
  fail "main was created at a commit the repository does not hold"
else
  pass "a commit the repository does not hold is refused, as on GitHub"
fi
made=$("$GH" api repos/rehearsal/upload/git/refs -f ref=refs/heads/main -f sha="$base")
case "$made" in
  *'"ref": "refs/heads/main"'*"$base"*) pass "the API creates main at the commit the piece was cut from" ;;
  *) fail "creating main through the API returned '$made'" ;;
esac
[ "$(git -C "$up.git" rev-parse refs/heads/main)" = "$base" ] \
  && pass "and main is on the remote at that commit, with no push" \
  || fail "the remote's main is not at the merge base"
git ls-remote --exit-code --heads origin > /dev/null 2>&1 \
  && pass "the branch listing then exits 0" \
  || fail "the branch listing still says the repository is empty"
case "$("$GH" api repos/rehearsal/upload/git/ref/heads/main --jq .object.sha)" in
  "$base") pass "the new branch reads back through the API" ;;
  *) fail "reading main back through the API gave the wrong commit" ;;
esac
if "$GH" api repos/rehearsal/upload/git/refs -f ref=refs/heads/main -f sha="$base" > /dev/null 2>&1; then
  fail "main was created twice"
else
  pass "a branch that already exists cannot be created again"
fi
# The fields may come before the path, and a field's slash is not the path.
"$GH" api --method POST -f ref=refs/heads/spare -f sha="$base" repos/rehearsal/upload/git/refs > /dev/null \
  && pass "the fields may come before the path" \
  || fail "fields before the path were misread"

"$GH" repo edit --default-branch main > /dev/null \
  && pass "repo edit --default-branch main is accepted once main exists" \
  || fail "repo edit --default-branch main was refused"
case "$("$GH" repo view --json defaultBranchRef,isEmpty)" in
  *'"defaultBranchRef": {"name": "main"}'*'"isEmpty": false'*) pass "and main reads back as the default branch" ;;
  *) fail "the default branch did not read back as main" ;;
esac
"$GH" api -X PATCH repos/rehearsal/upload -f default_branch=main > /dev/null \
  && pass "the API form of the default branch is accepted" \
  || fail "the API form of the default branch was refused"

# Moving or deleting a branch through the API, and another repository's
# branches, are nothing the kit should reach for.
for refused in "api -X PATCH repos/rehearsal/upload/git/refs/heads/main -f sha=$base -F force=true" \
               "api -X DELETE repos/rehearsal/upload/git/refs/heads/spare" \
               "api repos/rehearsal/upload/git/ref -f ref=refs/heads/other -f sha=$base" \
               "api repos/someone/else/git/refs -f ref=refs/heads/main -f sha=$base" \
               "repo edit --default-branch main --visibility public"; do
  if "$GH" $refused > /dev/null 2>&1; then
    fail "'$refused' was answered; it should be refused"
  else
    pass "'$refused' is refused"
  fi
done
cd "$WORK/project"
FAKE_GH_STATE="$WORK/.gh-fixture.json"

echo "== What it still refuses =="

# A project's own agent has no business searching GitHub, so a refusal here is
# information rather than a gap.
for refused in "search repos bramble" "repo list bramble-team"; do
  if "$GH" $refused > /dev/null 2>&1; then
    fail "'$refused' was answered; it should be refused"
  else
    pass "'$refused' is still refused"
  fi
done

if grep -q "UNSUPPORTED.*search repos" "$FAKE_GH_LOG"; then
  pass "a refusal is written to the log"
else
  fail "the refusal log did not record the refused command"
fi

echo "== Labels, closing reasons and the faults the gate script is tried against =="

# The repository's labels are modelled, because the gate script creates the
# kit's set and must be seen creating each one once. A new repository starts
# with GitHub's nine, which founding deletes.
names=$("$GH" label list --json name)
case "$names" in
  *'"bug"'*'"wontfix"'*) pass "a new repository lists GitHub's nine labels" ;;
  *) fail "the label list did not start with GitHub's nine: $names" ;;
esac
"$GH" label create "state:ready" --color 0E8A16 --description "Ready to build" \
  && pass "a label with a colon in its name can be created" \
  || fail "creating state:ready was refused"
case "$("$GH" label list --json name,color)" in
  *'"name": "state:ready", "color": "0E8A16"'*) pass "a created label lists with its colour" ;;
  *) fail "the created label did not list with its colour" ;;
esac
if "$GH" label create "state:ready" --color 0E8A16 > /dev/null 2>&1; then
  fail "creating a label that exists was answered; GitHub refuses it without --force"
else
  pass "creating a label that already exists is refused, as on GitHub"
fi
"$GH" label delete wontfix --yes \
  && ! "$GH" label list --json name | grep -q '"wontfix"' \
  && pass "a label can be deleted" || fail "deleting a label did not take it off the list"

# Labels on an issue still need no label to exist first, as before.
"$GH" issue edit 1 --add-label "loop:build" > /dev/null \
  && "$GH" issue view 1 --json labels | grep -q '"loop:build"' \
  && pass "an issue still takes a label the repository does not list" \
  || fail "an issue refused a label the repository does not list"

# One issue read on its own, as the gate script reads a piece.
case "$("$GH" api "repos/rehearsal/project/issues/1")" in
  *'"number": 1'*'"sub_issues_summary"'*) pass "one issue reads on its own, with its parts summary" ;;
  *) fail "one issue did not read on its own" ;;
esac
if "$GH" api "repos/rehearsal/project/issues/999" > /dev/null 2>"$WORK/missing"; then
  fail "an issue that does not exist was answered"
else
  grep -q "404" "$WORK/missing" && pass "an issue that does not exist answers 404" \
    || fail "a missing issue did not answer 404"
fi

# Closing as not planned keeps the reason and the comment.
"$GH" issue create --title "An idea nobody wants" --body "x" > /dev/null
"$GH" issue close 3 --reason "not planned" --comment "Nobody needs it." > /dev/null
python3 - "$FAKE_GH_STATE" <<'CHECK' && pass "a close keeps its reason and its comment" || fail "a close lost its reason or comment"
import json, sys
issue = [i for i in json.load(open(sys.argv[1]))["issues"] if i["number"] == 3][0]
bodies = [c["body"] if isinstance(c, dict) else c for c in issue.get("comments", [])]
assert issue["state"] == "closed" and issue["state_reason"] == "not_planned"
assert bodies == ["Nobody needs it."]
CHECK
case "$("$GH" issue list --state closed --label "state:ready")" in
  '[]') pass "closed issues list by label" ;;
  *) fail "a closed issue with no such label was listed" ;;
esac

set_fault() {
  python3 - "$FAKE_GH_STATE" "$1" <<'FAULT'
import json, sys
path, given = sys.argv[1], sys.argv[2]
state = json.load(open(path))
state["faults"] = json.loads(given)
json.dump(state, open(path, "w"))
FAULT
}

set_fault '{"offline": true}'
if "$GH" issue view 1 > /dev/null 2>"$WORK/offline"; then
  fail "a call answered while GitHub was taken away"
else
  grep -q "error connecting" "$WORK/offline" && pass "with GitHub taken away every call fails as with no network" \
    || fail "the offline failure did not say it could not connect"
fi

set_fault '{"refuse_label_write": true}'
if "$GH" issue edit 1 --add-label "state:building" > /dev/null 2>&1; then
  fail "a label write was answered while label writes were refused"
else
  pass "a label write can be refused, as for an account without write access"
fi
"$GH" issue edit 1 --title "Take a deposit" > /dev/null \
  && pass "an edit with no label change still goes through" \
  || fail "an edit with no label change was refused"

set_fault '{"refuse_label_create": ["loop:goal"]}'
if "$GH" label create "loop:goal" > /dev/null 2>&1; then
  fail "a label creation was answered while it was refused"
else
  "$GH" label create "loop:fix" > /dev/null \
    && pass "a creation can be refused by name while others go through" \
    || fail "an unrefused label creation failed"
fi

set_fault '{"refuse_comment": true}'
if "$GH" issue comment 1 --body "x" > /dev/null 2>&1; then
  fail "a comment was answered while comments were refused"
else
  pass "a comment can be refused"
fi

# A second session moving the same piece: the change lands on the second read.
set_fault '{"race": {"number": 1, "on_read": 2, "add": ["state:in-review"], "remove": []}}'
"$GH" api "repos/rehearsal/project/issues/1" | grep -q '"state:in-review"' \
  && fail "the race landed on the first read" || pass "the first read is answered as it stood"
"$GH" api "repos/rehearsal/project/issues/1" | grep -q '"state:in-review"' \
  && pass "the race lands on the second read" || fail "the race never landed"
set_fault '{}'

# Nothing the kit reached for during this rehearsal should have been refused.
if grep -q "UNSUPPORTED" "$FAKE_GH_LOG"; then
  unexpected=$(grep "UNSUPPORTED" "$FAKE_GH_LOG" | grep -vc "search repos\|repo list\|nosuchfield\|visibility public\|private=false\|force=true\|-X DELETE\|someone/else\|git/ref -f" || true)
  if [ "$unexpected" -gt 0 ]; then
    fail "$unexpected modelled command was refused; see $FAKE_GH_LOG"
  fi
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "fake-github.sh: all checks passed"
else
  echo "fake-github.sh: FAILED" >&2
fi
exit "$FAIL"
