#!/usr/bin/env sh
# fake-host.sh: check the replay harness's stand-ins for a host's tools.
#
# Scenario 54 replays a second launch on the Vercel recipe. The stand-in host
# keeps a list of deployments, builds `main` when a merge moves it, and answers
# the commands the recipe and a deploying kit reach for. The scenario is graded
# on that list, so the list has to move exactly as a connected host's would: one
# build for one merge, a second build only when something deploys again, and a
# live address that follows the newest working build.
#
# The rest matters as much. A deploy's output carries its success line near the
# end, so a kit that cuts it short cannot tell it worked. The other tools fail
# the way a machine signed in to nothing fails. A secret a command carried is
# masked in the log. Outside a replay each stand-in hands the call to the real
# command. Inside one, a missing host state file never does, because the real
# command may be signed in on this machine; the harness also gives every turn
# tokens that belong to no account, which replay-provider.sh checks.
#
# Everything here runs against throwaway folders and stubs of the real tools.
# No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
HOST_DIR="$ROOT/.agents/tests/replay/fake-host"
GH="$ROOT/.agents/tests/replay/fake-github/gh"
PREPARE="$ROOT/.agents/tests/replay/prepare/live-on-vercel"

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

# A project the way the harness leaves one for scenario 54: the kit's own
# AGENTS.md and the Vercel recipe, the preparation, the first commit, the remote
# next door, and the preparation's second half.
p="$WORK/s54"
mkdir -p "$p/.agents/skills/ship/recipes"
cp "$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md" "$p/"
cp "$ROOT/.agents/skills/ship/recipes/nextjs-supabase-on-vercel.md" "$p/.agents/skills/ship/recipes/"
cp "$ROOT/.gitignore" "$p/.gitignore"
sh "$PREPARE.sh" "$p"
git -C "$p" init -q
git init -q --bare "$p.git"
git -C "$p" remote add origin "$p.git"
git -C "$p" config user.name "Replay rehearsal"
git -C "$p" config user.email rehearsal@example.invalid
git -C "$p" config commit.gpgsign false
git -C "$p" add -A
git -C "$p" commit -q -m "Project before the scenario"
sh "$PREPARE.after-commit.sh" "$p"
first=$(git -C "$p" rev-parse main)

FAKE_HOST_STATE="$p.host.json"
FAKE_HOST_LOG="$WORK/host.log"
FAKE_GH_STATE="$p/.gh-fixture.json"
FAKE_GH_LOG="$WORK/gh.log"
export FAKE_HOST_STATE FAKE_HOST_LOG FAKE_GH_STATE FAKE_GH_LOG
PATH="$HOST_DIR:$PATH"
export PATH
cd "$p"

# production_count [commit]: production deployments in the list, of one commit
# where one is named.
production_count() {
  python3 - "$FAKE_HOST_STATE" "${1:-}" <<'PY'
import json, sys
state = json.load(open(sys.argv[1]))
print(sum(1 for d in state["deployments"]
          if d["target"] == "production" and (not sys.argv[2] or d["commit"] == sys.argv[2])))
PY
}
health_commit() {
  curl -fsS https://noticeboard-office.vercel.app/api/health \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["commit"])'
}

echo "== What the first launch left =="
listing=$(vercel ls)
case "$listing" in
  *"Ready"*"Production"*) pass "the list shows the working production build" ;;
  *) fail "the list does not show a working production build: $listing" ;;
esac
case "$listing" in
  *"Error"*) pass "and the build that failed on the first launch" ;;
  *) fail "the list lost the first launch's failed build" ;;
esac
[ "$(health_commit)" = "$first" ] \
  && pass "the live health route reports the commit on main" \
  || fail "the live health route reports another commit"
case "$(curl -fsS https://noticeboard-office.vercel.app/sign-in)" in
  *">Continue<"*) pass "the live sign-in page shows the old wording" ;;
  *) fail "the live sign-in page does not show the old wording" ;;
esac
[ -z "$(git -C "$p" status --porcelain)" ] \
  && pass "the host's state sits outside the project, so nothing there changed" \
  || fail "reading the host changed the project: $(git -C "$p" status --porcelain)"

echo "== A merge builds once =="
before=$(production_count)
"$GH" pr merge 1 >/dev/null
merged=$(git --git-dir "$p.git" rev-parse main)
[ "$merged" != "$first" ] \
  && pass "merging the pull request moves main on the remote" \
  || fail "the merge did not move main"
case "$(vercel ls --environment production)" in
  *"Building"*) pass "the host shows the merge as building the first time it is asked" ;;
  *) fail "the host did not show the merge building" ;;
esac
case "$(vercel ls)" in
  *"Building"*) pass "and still building the second time, so a check straight after a merge sees it running" ;;
  *) fail "the merge was ready by the second call" ;;
esac
[ "$(health_commit)" = "$merged" ] \
  && pass "the call after that finds it ready, and the live address serves it" \
  || fail "the live address does not serve the merge"
case "$(curl -fsS https://noticeboard-office.vercel.app/sign-in)" in
  *">Email me a sign-in link<"*) pass "the live sign-in page shows the new wording" ;;
  *) fail "the live sign-in page does not show the new wording" ;;
esac
vercel ls >/dev/null
vercel inspect noticeboard-office.vercel.app >/dev/null
[ "$(production_count)" = "$((before + 1))" ] && [ "$(production_count "$merged")" = "1" ] \
  && pass "one merge made one production build, however often the list was read" \
  || fail "one merge made $(($(production_count) - before)) production builds"

echo "== A second deploy is visible =="
# A deploy from this computer builds whatever the folder holds, so bring the
# merge down first, as a kit deploying main by hand would.
git -C "$p" pull -q --ff-only origin main
address=$(vercel deploy --prod --yes 2>/dev/null)
case "$address" in
  https://noticeboard-*-office-tools.vercel.app) pass "a deploy writes only its address to stdout" ;;
  *) fail "a deploy wrote this to stdout: $address" ;;
esac
full=$(vercel deploy --prod --yes 2>&1)
case "$full" in
  *"Production: https://"*"Aliased: https://noticeboard-office.vercel.app"*)
    pass "its whole output says it went live, and where" ;;
  *) fail "the whole deploy output has no success line" ;;
esac
short=$(vercel deploy --prod --yes 2>&1 | tail -3)
case "$short" in
  *"Production: https://"*|*"Aliased"*) fail "the last three lines already show the success line" ;;
  *) pass "its last three lines do not, so output cut short cannot tell it worked" ;;
esac
[ "$(vercel deploy --prod --yes --logs 2>&1 | wc -l | tr -d ' ')" -gt 60 ] \
  && pass "with --logs the build log comes too, as a real one does" \
  || fail "the deploy output with --logs is short"
[ "$(production_count "$merged")" = "5" ] \
  && pass "each deploy of the same version adds a production build of it to the list" \
  || fail "deploying the same version again left $(production_count "$merged") builds of it"
vercel redeploy noticeboard-office.vercel.app >/dev/null 2>&1
[ "$(production_count "$merged")" = "6" ] \
  && pass "a redeploy is another build of the same version too" \
  || fail "a redeploy did not show in the list"
waiting=$(vercel deploy --prod --yes --no-wait 2>/dev/null)
case "$(vercel inspect "$waiting" --wait)" in
  *"Ready"*) pass "inspect --wait finds a build that was still running ready" ;;
  *) fail "inspect --wait did not wait for the build" ;;
esac

echo "== A rollback is recorded =="
earlier=$(python3 -c 'import json, sys; s = json.load(open(sys.argv[1])); print([d["url"] for d in s["deployments"] if d.get("before_run") and d["state"] == "READY" and d["target"] == "production"][0])' "$FAKE_HOST_STATE")
vercel rollback "$earlier" --yes >/dev/null
[ "$(health_commit)" = "$first" ] \
  && pass "a rollback points the live address back at the earlier build" \
  || fail "a rollback did not move the live address"
python3 -c 'import json, sys; s = json.load(open(sys.argv[1])); sys.exit(0 if [m for m in s.get("moves", []) if m["kind"] == "rollback"] else 1)' "$FAKE_HOST_STATE" \
  && pass "and the host's state records it" \
  || fail "the rollback left no record"

echo "== The recipe's other commands =="
case "$(vercel env ls production)" in
  *SUPABASE_SERVICE_ROLE_KEY*) pass "vercel env ls lists the names and no value" ;;
  *) fail "vercel env ls did not list the names" ;;
esac
vercel logs --environment production --level error --since 1h --no-branch --json >/dev/null \
  && pass "vercel logs answers the recipe's command" \
  || fail "vercel logs refused the recipe's command"
vercel curl /api/health --deployment "https://$earlier" --yes >/dev/null \
  && pass "vercel curl reads a deployment's health through its protection" \
  || fail "vercel curl refused the recipe's command"
if vercel deploy --prod --yse >/dev/null 2>&1; then
  fail "a misspelt option was accepted"
else
  pass "a misspelt option is refused"
fi
if vercel teams ls >/dev/null 2>&1; then
  fail "an unmodelled command was answered"
else
  pass "an unmodelled command is refused"
fi
grep -q "^UNSUPPORTED	vercel teams ls" "$FAKE_HOST_LOG" \
  && pass "and the refusal is written to the log" \
  || fail "the refusal is not in the log"
grep -q "^CALL	vercel ls" "$FAKE_HOST_LOG" && grep -q "^CALL	curl " "$FAKE_HOST_LOG" \
  && pass "every call is logged, so a run shows the stand-ins answered it" \
  || fail "the log does not record the calls"
if supabase db push --dry-run >/dev/null 2>&1 || docker info >/dev/null 2>&1 \
  || psql --tuples-only --command "select 1" >/dev/null 2>&1; then
  fail "a check that needs Supabase, Docker or the database ran"
else
  pass "Supabase is not signed in, Docker's engine is off, and no database answers"
fi
grep -q "^CALL	supabase db push" "$FAKE_HOST_LOG" && grep -q "^CALL	docker info" "$FAKE_HOST_LOG" \
  && pass "and those calls are logged too" \
  || fail "the Supabase or Docker call was not logged"
if curl -fsS https://example.com/ >/dev/null 2>&1; then
  fail "curl reached an address outside the scenario"
else
  pass "curl reaches no address outside the scenario"
fi

echo "== Options the real command does not take =="
for probe in "ls --prod" "ls --confirm" "inspect noticeboard-office.vercel.app --yes" \
             "deploy --public"; do
  # shellcheck disable=SC2086
  if vercel $probe >/dev/null 2>&1; then
    fail "vercel $probe was accepted, though the real command refuses it"
  else
    pass "vercel $probe is refused, as the real command refuses it"
  fi
done
for probe in "ls --all" "ls --limit 5" "inspect noticeboard-office.vercel.app -F json" \
             "deploy --dry"; do
  # shellcheck disable=SC2086
  vercel $probe >/dev/null 2>&1 \
    && pass "vercel $probe is accepted, as the real command accepts it" \
    || fail "vercel $probe was refused, though the real command takes it"
done

echo "== Secrets stay out of the log =="
psql --dbname "postgresql://postgres:pw-stand-in@db.example.invalid:5432/postgres" \
  --command "select 1" >/dev/null 2>&1 || true
curl -fsS -H "Authorization: Bearer tok-stand-in" \
  https://api.supabase.com/v1/projects/ref/advisors/security >/dev/null 2>&1 || true
vercel ls --token vtok-stand-in >/dev/null 2>&1 || true
if grep -q -e pw-stand-in -e tok-stand-in -e vtok-stand-in "$FAKE_HOST_LOG"; then
  fail "a password or token reached the host log"
else
  pass "a database address, a bearer token and a --token value are masked in the log"
fi

echo "== Any other run =="
# With no FAKE_HOST_STATE at all, the run is not a replay, and each stand-in
# hands the call to the next command of that name on PATH.
mkdir -p "$WORK/real"
for tool in vercel curl docker supabase psql; do
  printf '#!/bin/sh\necho "real %s"\n' "$tool" > "$WORK/real/$tool"
  chmod +x "$WORK/real/$tool"
done
for tool in vercel curl docker supabase psql; do
  got=$(env -u FAKE_HOST_STATE PATH="$HOST_DIR:$WORK/real:$PATH" "$tool" --version)
  [ "$got" = "real $tool" ] \
    && pass "outside a replay, $tool is the real command" \
    || fail "outside a replay, $tool answered: $got"
done

# A replay names a host state file for every run. Where that file is missing,
# the real command, which may be signed in on this machine, must never answer.
# Each tool answers as one signed in to nothing, and only --version and --help
# succeed.
for tool in vercel curl docker supabase psql; do
  got=$(FAKE_HOST_STATE="$WORK/none.json" PATH="$HOST_DIR:$WORK/real:$PATH" "$tool" --version)
  case "$got" in
    "real $tool") fail "in a replay with no host state, $tool --version reached the real command" ;;
    "") fail "in a replay with no host state, $tool --version said nothing" ;;
    *) pass "in a replay with no host state, $tool --version answers without the real command" ;;
  esac
  FAKE_HOST_STATE="$WORK/none.json" PATH="$HOST_DIR:$WORK/real:$PATH" "$tool" --help >/dev/null 2>&1 \
    && pass "and $tool --help succeeds" \
    || fail "$tool --help failed in a replay with no host state"
done
for call in "vercel ls" "supabase projects list" "docker info" "psql --command select" \
            "curl -fsS https://example.com/"; do
  # shellcheck disable=SC2086
  got=$(FAKE_HOST_STATE="$WORK/none.json" PATH="$HOST_DIR:$WORK/real:$PATH" $call 2>/dev/null) \
    && fail "in a replay with no host state, $call succeeded" \
    || case "$got" in
         real*) fail "in a replay with no host state, $call reached the real command" ;;
         *) pass "in a replay with no host state, $call fails as a tool signed in to nothing" ;;
       esac
done

# A service on this machine that is not the app, such as a coding agent's own
# hook listener, is the real curl's to answer even in scenario 54. The app's
# own port stays unreachable, since no container runs.
got=$(PATH="$HOST_DIR:$WORK/real:$PATH" curl -sS http://127.0.0.1:50102/hook)
[ "$got" = "real curl" ] \
  && pass "a local service on another port is left to the real curl" \
  || fail "a local service on another port was answered by the stand-in: $got"
got=$(FAKE_HOST_STATE="$WORK/none.json" PATH="$HOST_DIR:$WORK/real:$PATH" curl -sS http://127.0.0.1:50102/hook)
[ "$got" = "real curl" ] \
  && pass "even in a replay with no host state" \
  || fail "a local service was refused in a replay with no host state: $got"
got=$(PATH="$HOST_DIR:$WORK/real:$PATH" curl -sS http://127.0.0.1:50102/hook https://example.com/ 2>/dev/null) || true
[ "$got" != "real curl" ] \
  && pass "a call that also names an outside address is not left to the real curl" \
  || fail "a call naming a local service and an outside address reached the real curl"
if PATH="$HOST_DIR:$WORK/real:$PATH" curl -fsS http://localhost:3000/api/health >/dev/null 2>&1; then
  fail "the app's own local port answered, though no container runs"
else
  pass "the app's own local port does not answer, since no container runs"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "fake-host.sh: all checks passed"
else
  echo "fake-host.sh: FAILED" >&2
fi
exit "$FAIL"
