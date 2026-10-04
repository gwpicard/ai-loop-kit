#!/usr/bin/env sh
# run.sh: replay scenarios from the contract and record what the kit actually did.
#
# Usage:
#   ./run.sh                     every case, the default number of repeats
#   ./run.sh 5 15                only these scenarios
#   REPEATS=1 ./run.sh 5         one pass, for a quick look
#
# Each run produces a transcript and a graded verdict. Those land outside this
# repository; the run prints where at the end, and REPLAY_RESULTS overrides it.
# Nothing is written inside this repository, and no agent configuration is
# changed.

set -eu

REPLAY_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$REPLAY_DIR/lib.sh"
. "$REPLAY_DIR/turn-gate.sh"

REPEATS=${REPEATS:-5}
REPLAY_PROVIDER=${REPLAY_PROVIDER:-claude}
case "$REPLAY_PROVIDER" in
  claude)
    MODEL=${MODEL:-opus}
    GRADER_MODEL=${GRADER_MODEL:-opus}
    ;;
  codex)
    MODEL=${MODEL:-}
    GRADER_MODEL=${GRADER_MODEL:-$MODEL}
    ;;
esac
VERSION=${VERSION:-v0.0.0-replay}

WORK=${REPLAY_WORK:-${TMPDIR:-/tmp}/abk-replay-$$}
# Graded output is written outside this repository. A pass rewrites a couple of
# hundred files, which made this the highest-churn directory in the project, and
# the project sits in a folder a sync daemon watches. One such daemon removed
# the results directory mid-pass and the next run, clearing what it thought were
# its own stale results, destroyed the raw output of four scenarios from the run
# before it. Nothing here is worth keeping inside a synced tree: the record that
# travels is baseline.md, and everything else is re-derivable by re-running.
# REPLAY_RESULTS moves it somewhere else.
RESULTS=${REPLAY_RESULTS:-${XDG_STATE_HOME:-$HOME/.local/state}/abk-replay/results}
GH_DIR="$REPLAY_DIR/fake-github"
# Stand-ins for a host's command-line tools, for a scenario that launches on a
# recipe. The harness names a host state file for every run, so in a scenario
# that never wrote one each answers as a tool signed in to nothing, and never
# hands the call to the real command, which may be signed in on this machine.
HOST_DIR="$REPLAY_DIR/fake-host"

command -v python3 >/dev/null 2>&1 || fail "python3 is needed to read run output"
[ -x "$ROOT/.agents/tools/build-release.sh" ] || fail "release builder is missing"

# A time cap stops a wedged turn running forever. timeout is GNU coreutils and
# is not on macOS by default, where Homebrew installs it as gtimeout. Use
# whichever is here. If neither is, run without a cap rather than stopping: a
# headless turn ends on its own when the conversation does, and a missing
# timeout used to kill every turn silently and blame the kit for it.
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_CMD=timeout
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_CMD=gtimeout
else
  TIMEOUT_CMD=
  note "no timeout or gtimeout found, so turns run without a time cap"
fi

. "$REPLAY_DIR/provider.sh"
provider_check

mkdir -p "$WORK" "$RESULTS"
provider_prepare
echo "Replay provider: $REPLAY_PROVIDER"

# --- the kit under test, assembled once -----------------------------------
# The builder refuses an existing folder, so this is built once per run and
# every case copies from it. release-builder.sh proves two builds are identical,
# which is what makes one build safe to share across cases.
KIT="$WORK/kit"
echo "Assembling $VERSION into $KIT"
"$ROOT/.agents/tools/build-release.sh" "$VERSION" "$KIT" >/dev/null

# --- which cases to run ----------------------------------------------------
if [ "$#" -gt 0 ]; then
  cases=$*
else
  cases=$(find "$REPLAY_DIR/cases" -name '*.txt' -exec basename {} .txt \; | sed 's/^0*//' | sort -n)
fi

# case_setup <file>   blank or fixture
case_setup() {
  awk -F': *' '/^# setup:/ { print $2; exit }' "$1"
}

new_uuid() {
  if [ -r /proc/sys/kernel/random/uuid ]; then
    cat /proc/sys/kernel/random/uuid
  else
    python3 -c 'import uuid; print(uuid.uuid4())'
  fi
}

# --- one run ---------------------------------------------------------------
# Drives the whole conversation rather than one turn. The contract for a
# scenario describes where a conversation ends up, so a single turn grades the
# first interview question against the whole contract and manufactures misses
# for everything the session never reached.
run_once() {
  number=$1
  repeat=$2
  casefile=$3
  project="$WORK/s${number}-r${repeat}"

  mkdir -p "$project"
  cp -R "$KIT/." "$project/"
  setup=$(case_setup "$casefile")
  if [ "$setup" = "fixture" ]; then
    cp "$REPLAY_DIR/fixture/masterplan.md" "$project/masterplan.md"
    cp "$REPLAY_DIR/fixture/CHANGELOG.md" "$project/CHANGELOG.md"
    # The fixture project's pieces are issues, seeded into the stand-in's state
    # file, so the run measures the path a real project of this shape takes.
    cp "$REPLAY_DIR/fixture/issues.json" "$project/.gh-fixture.json"
    # The application matters. Without code to run, a scenario about fixing a
    # bug stops because there is nothing to reproduce against, and the run
    # proves nothing about the scenario under test.
    cp -R "$REPLAY_DIR/fixture/app" "$project/app"
    cat "$REPLAY_DIR/fixture/AGENTS-additions.md" >> "$project/AGENTS.md"
  fi
  # A starting state no conversation should build, such as instructions past
  # their ceiling, is written by the harness before the first commit.
  prepare=$(case_prepare "$casefile")
  if [ -n "$prepare" ]; then
    sh "$REPLAY_DIR/prepare/$prepare.sh" "$project" || {
      echo "  preparation '$prepare' failed for scenario $number" >&2
      return 1
    }
  fi

  git -C "$project" init -q
  # A real remote, so the pull-request save route is reachable. It is a bare
  # repository next door rather than anything on GitHub: push works, nothing
  # leaves this machine, and no account is involved.
  git init -q --bare -b main "$project.git"
  git -C "$project" remote add origin "$project.git"
  git -C "$project" config user.name "Replay rehearsal"
  git -C "$project" config user.email "rehearsal@example.invalid"
  git -C "$project" config commit.gpgsign false
  git -C "$project" add -A
  git -C "$project" commit -q -m "Project before the scenario"

  # Some starting states grow from that first commit, such as a pull request,
  # which is a branch cut from it and pushed to the remote next door. A
  # preparation with a second half in `<name>.after-commit.sh` has it run here.
  if [ -n "$prepare" ] && [ -f "$REPLAY_DIR/prepare/$prepare.after-commit.sh" ]; then
    sh "$REPLAY_DIR/prepare/$prepare.after-commit.sh" "$project" || {
      echo "  preparation '$prepare' failed after the first commit for scenario $number" >&2
      return 1
    }
  fi

  # The GitHub stand-in keeps its state beside the project from here on, not
  # in it. The copy in the first commit still says what the project started
  # with. A state file inside the project is a tracked file the kit's own Git
  # work moves: one run committed it on a records branch, switched back to
  # main, and so put both merged pull requests back to open, for the stand-in
  # and for the state check alike.
  ghstate="$project.gh.json"
  rm -f "$ghstate"
  if [ -f "$project/.gh-fixture.json" ]; then
    cp "$project/.gh-fixture.json" "$ghstate"
  fi

  # Every push that reaches the remote next door is written to the GitHub
  # log, between the markers for the turns it happened in. That is what shows
  # whether a push came before or after the person's yes. The hook is in the
  # bare remote, outside the project, so the kit never sees it.
  ghlog="$WORK/s${number}-r${repeat}-gh.log"
  : > "$ghlog"
  log_pushes "$project.git" "$ghlog"

  provider_new_session
  transcript="$WORK/s${number}-r${repeat}.transcript"
  turns="$WORK/s${number}-r${repeat}-turns"
  : > "$transcript"
  mkdir -p "$turns"
  split_turns "$casefile" "$turns"

  # A turn is due when its precondition is met, not when its position comes up.
  # turn-gate.sh holds the rule; this loop carries out what it decides.
  total=$(find "$turns" -name 'turn-*.txt' | wc -l | tr -d ' ')
  filler=$(case_filler "$casefile")
  lastreply="$WORK/s${number}-r${repeat}-lastreply.txt"
  : > "$lastreply"
  index=0
  turn=0
  fillers=0
  while [ "$index" -lt "$total" ]; do
    next=$((index + 1))
    turnfile=$(printf '%s/turn-%02d.txt' "$turns" "$next")
    [ -f "$turnfile" ] || break
    whenfile="${turnfile%.txt}.when"
    pattern=""
    [ -f "$whenfile" ] && pattern=$(cat "$whenfile")

    case $(gate_decision "$pattern" "$lastreply" "$fillers" "$FILLER_CAP") in
      wait)
        message=$filler
        fillers=$((fillers + 1))
        label=" (filler: turn $next waits for the kit to say something matching /$pattern/)"
        ;;
      force)
        message=$(cat "$turnfile")
        index=$next
        fillers=0
        label=" (sent unheld: nothing the kit said matched /$pattern/ within $FILLER_CAP fillers)"
        ;;
      *)
        message=$(cat "$turnfile")
        index=$next
        fillers=0
        label=""
        ;;
    esac

    turn=$((turn + 1))
    printf '\n### user turn %s%s\n%s\n' "$turn" "$label" "$message" >> "$transcript"

    raw="$WORK/s${number}-r${repeat}-t${turn}.json"
    # The stand-in for the GitHub CLI goes first on PATH, so the kit's issue
    # work is answered without an account or a network. It refuses anything it
    # does not model, and logs it, so a command nobody predicted shows up in
    # the transcript rather than passing quietly.
    FAKE_GH_STATE="$ghstate"
    FAKE_GH_LOG="$ghlog"
    export FAKE_GH_STATE FAKE_GH_LOG
    # Mark the turn in the log, so a push or a call can be placed against what
    # the person had said by then. A turn marked `# grants:` in the case is the
    # one that gives the permission the scenario measures; a filler never is.
    kind=scripted
    if [ "$message" = "$filler" ]; then
      kind=filler
    elif [ -f "${turnfile%.txt}.grants" ]; then
      kind=grants
    fi
    printf 'TURN\t%s\t%s\n' "$turn" "$kind" >> "$FAKE_GH_LOG"
    # The stand-in host keeps its list of deployments beside the project rather
    # than in it, so the kit never commits it. Only a preparation that launches
    # on a recipe writes that file.
    FAKE_HOST_STATE="$project.host.json"
    FAKE_HOST_LOG="$WORK/s${number}-r${repeat}-host.log"
    export FAKE_HOST_STATE FAKE_HOST_LOG
    # PATH is a suggestion rather than a boundary. A session that doubts an
    # answer could look for the real tool, find it at its usual place, and use
    # the maintainer's own signed-in account. The credentials are taken away
    # instead. gh reads them from these, so the real binary agrees with the
    # stand-in, and a run cannot act on anybody's account.
    GH_CONFIG_DIR="$project/.gh-empty-config"
    mkdir -p "$GH_CONFIG_DIR"
    GH_TOKEN=
    GITHUB_TOKEN=
    GH_ENTERPRISE_TOKEN=
    GITHUB_ENTERPRISE_TOKEN=
    # A push to a real remote would ask the maintainer's credential helper. The
    # only remote here is the bare repository next door, so nothing needs one,
    # and a prompt nobody can answer should fail rather than wait.
    GIT_TERMINAL_PROMPT=0
    export GH_CONFIG_DIR GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN \
      GITHUB_ENTERPRISE_TOKEN GIT_TERMINAL_PROMPT
    # The host's tools may be signed in on this machine too. provider.sh says
    # how each is kept from reaching an account.
    provider_isolate_host "$project"

    # A turn that says "I merged your fix" has to be true, or the kit rightly
    # answers that the fix never went live and the case measures nothing. So the
    # person merges every open pull request first, on the remote next door, and
    # the transcript says so. A filler merges nothing: it is not the scripted
    # turn, and the merge belongs to the line that reports it.
    if [ "$message" != "$filler" ] && [ -f "${turnfile%.txt}.merge" ]; then
      merged=$(merge_open_pulls "$project")
      printf '(before this turn the person merged: %s)\n' "${merged:-nothing was open}" \
        >> "$transcript"
    fi
    # Both providers run without approval prompts. Nobody is here to answer,
    # and refusing commands would turn every evidence field into a harness
    # failure. The project and remote are disposable, while GitHub credentials
    # are empty and the stand-in is first on the command path.
    if ! provider_turn "$project" "$message" "$raw" "$lastreply"; then
      printf '\n### run ended at turn %s\n' "$turn" >> "$transcript"
      break
    fi

    # The reply is kept on its own as well as in the transcript, because the
    # next turn's precondition is read against the last thing the kit said.
    printf '\n### kit reply %s\n' "$turn" >> "$transcript"
    cat "$lastreply" >> "$transcript"
    printf '\n' >> "$transcript"
  done

  printf '%s\n' "${PROVIDER_SESSION:-}" > "$WORK/s${number}-r${repeat}.session"
  printf '%s' "$transcript"
}

# --- grading ---------------------------------------------------------------
# The grader is given the contract and transcript, not the skills that produced
# the behaviour. Claude Code has its tools switched off. Codex runs read-only
# from an empty folder, as described in the replay guide.
grade_once() {
  number=$1
  transcript=$2
  out=$3

  input="$WORK/grade-input-$number-$$.txt"
  {
    cat "$REPLAY_DIR/grader-prompt.md"
    printf '\n## The contract\n\n'
    expectations_json "$number"
    printf '\n## The transcript\n\n'
    cat "$transcript"
  } > "$input"

  provider_grade "$input" "$out.raw"

  python3 "$REPLAY_DIR/grade-parse.py" "$out.raw" "$out" "$number"
}

# turn_count <casefile>
# How many turns this case should produce, counted the same way split_turns
# splits them, so the two can never disagree about what a whole conversation is.
turn_count() {
  awk '
    /^#/ { next }
    /^---$/ { if (started) { count++; started = 0 } next }
    { started = 1 }
    END { if (started) count++; print count + 0 }
  ' "$1"
}

# --- the pass --------------------------------------------------------------
# one_pass <number> <repeat> <casefile> <padded>
one_pass() {
  transcript=$(run_once "$1" "$2" "$3")
  out="$RESULTS/s${4}-r${2}.json"
  cp "$transcript" "$RESULTS/s${4}-r${2}.transcript"

  # A conversation that stopped early must never be graded. The grader cannot
  # tell a fragment from a whole session, so it judges what it was given and a
  # run killed before the pushback arrives comes back as a confident hold: it
  # held because it was never given the chance to fail. That is a false pass,
  # and false passes only ever push a score up.
  #
  # Counting replies rather than looking for the ended-early marker catches the
  # case where the harness itself was killed and never got to write one.
  want=$(turn_count "$3")
  got=$(grep -c '^### kit reply' "$transcript" || true)
  if [ "$got" -lt "$want" ]; then
    python3 - "$out" "$1" "$got" "$want" <<'PY'
import json, sys
out, scenario, got, want = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
json.dump({"scenario": int(scenario),
           "error": "conversation ended after %s of %s turns; not graded, because a "
                    "fragment scores as a hold it did not earn" % (got, want)},
          open(out, "w"))
PY
    echo "  scenario $1 run $2 ended early at $got of $want turns, not graded"
    return
  fi

  # A run whose GitHub commands reached the real CLI measured the harness, not
  # the kit. The real one finds no account during a run, so the kit carries on
  # without pull requests or issues, and what it does next is partly the
  # harness's doing. The transcript still reads normally, so this is looked for
  # here: the grader would score the run as if nothing had gone wrong.
  if sign=$({ printf '%s\n' "$transcript"
              provider_session_records "$WORK/s${1}-r${2}"; } | real_gh_answered); then
    python3 - "$out" "$1" "$sign" <<'PY'
import json, sys
out, scenario, sign = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({"scenario": int(scenario),
           "error": "the real GitHub CLI answered a command (%s); not graded, "
                    "because the kit worked without the stand-in" % sign},
          open(out, "w"))
PY
    echo "  scenario $1 run $2 reached the real GitHub CLI, not graded"
    return
  fi

  grade_once "$1" "$transcript" "$out"

  # Grade the world the run left behind, next to the transcript. The state
  # assertions are deterministic and cost no model, and they catch a kit that
  # said the right words and wrote nothing, which the transcript grader cannot
  # see. This is additive: a failure to read the state never un-grades a run.
  project="$WORK/s${1}-r${2}"
  state=$("$REPLAY_DIR/state-check.sh" "$1" "$project" 2>/dev/null || true)
  if [ -n "$state" ]; then
    python3 - "$out" "$state" <<'PY' 2>/dev/null || true
import json, sys
out, state = sys.argv[1], sys.argv[2]
try:
    result = json.load(open(out))
    extra = json.loads(state)
except Exception:
    sys.exit(0)
result["state_verdicts"] = extra.get("state_verdicts", {})
result["state_held"] = extra.get("state_held")
json.dump(result, open(out, "w"))
PY
  fi

  echo "  finished scenario $1 run $2"
}

# Runs are independent conversations in separate throwaway projects, so they can
# overlap. A whole conversation takes roughly twenty minutes, and running thirty
# of them one after another is most of a working day.
JOBS=${JOBS:-4}
running=0

for number in $cases; do
  padded=$(printf '%02d' "$number")
  casefile="$REPLAY_DIR/cases/$padded.txt"
  [ -f "$casefile" ] || { note "no case file for scenario $number, skipping"; continue; }

  # Clear earlier results for this scenario before running it again. A shorter
  # run otherwise leaves the tail of a longer one in place: three repeats over a
  # scenario last run five times leaves runs four and five behind, and rollup.sh
  # counts all five as one measurement. That misreports the rate, which is the
  # single number this harness exists to produce, and it misreports it in
  # whichever direction the stale runs happen to point.
  rm -f "$RESULTS/s${padded}-r"*".json" \
        "$RESULTS/s${padded}-r"*".json.raw" \
        "$RESULTS/s${padded}-r"*".transcript"

  repeat=1
  while [ "$repeat" -le "$REPEATS" ]; do
    echo "Starting scenario $number, run $repeat of $REPEATS"
    one_pass "$number" "$repeat" "$casefile" "$padded" &
    running=$((running + 1))
    if [ "$running" -ge "$JOBS" ]; then
      wait
      running=0
    fi
    repeat=$((repeat + 1))
  done
done
wait

echo
echo "Transcripts and verdicts are in $RESULTS"
echo "Working copies are in $WORK"
# Invoked through the shell so a checkout without the execute bit still gets the
# summary table, which is the whole point of the run. It is handed the directory
# this run actually wrote to: rollup.sh falls back to a path inside this
# repository, and the output has not lived there since it moved out of the
# synced tree, so leaving the argument off ends every pass by reporting that
# there are no results.
sh "$REPLAY_DIR/rollup.sh" "$RESULTS" || true
