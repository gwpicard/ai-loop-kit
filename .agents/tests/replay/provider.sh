#!/usr/bin/env sh
# provider.sh: run replay turns and graders through Claude Code or Codex.

# The caller sets REPLAY_PROVIDER, MODEL, GRADER_MODEL, WORK, REPLAY_DIR,
# TIMEOUT_CMD and GH_DIR before loading this file, and HOST_DIR where it has
# stand-ins for a host's tools.

provider_check() {
  case "$REPLAY_PROVIDER" in
    claude)
      command -v claude >/dev/null 2>&1 \
        || fail "Claude Code is not installed"
      ;;
    codex)
      command -v codex >/dev/null 2>&1 \
        || fail "Codex CLI is not installed"
      ;;
    *)
      fail "REPLAY_PROVIDER must be 'claude' or 'codex', not '$REPLAY_PROVIDER'"
      ;;
  esac
}

provider_prepare() {
  # Both providers run commands through a login shell, and on macOS a login
  # shell rebuilds PATH from the person's own profile. A profile that puts
  # Homebrew first puts the real gh ahead of the rehearsal stand-in. Codex
  # starts each command that way. Claude Code's Bash tool reads a snapshot of a
  # login shell, and when that snapshot is taken the real gh answers. It did in
  # one run, saying "gh auth login", while other commands in the same run
  # reached the stand-in. These throwaway profiles put the stand-in back after
  # login. Bash reads BASH_ENV for its non-interactive shell; zsh reads the
  # .zprofile in ZDOTDIR instead of the person's own.
  # The host's stand-ins go second, for the same reason: a login shell would
  # otherwise find the person's own deploy command, which may be signed in.
  REPLAY_TOOLS="$GH_DIR${HOST_DIR:+:$HOST_DIR}"
  REPLAY_SHELL_HOME="$WORK/replay-shell"
  mkdir -p "$REPLAY_SHELL_HOME"
  printf 'export PATH="%s:$PATH"\n' "$REPLAY_TOOLS" \
    > "$REPLAY_SHELL_HOME/.zprofile"
  cp "$REPLAY_SHELL_HOME/.zprofile" "$REPLAY_SHELL_HOME/bash-env"
  ZDOTDIR=$REPLAY_SHELL_HOME
  BASH_ENV="$REPLAY_SHELL_HOME/bash-env"
  export ZDOTDIR BASH_ENV

  [ "$REPLAY_PROVIDER" = "codex" ] || return 0
  CODEX_GRADER_DIR="$WORK/codex-grader"
  mkdir -p "$CODEX_GRADER_DIR"
}

# provider_isolate_host <project>
# The host's real tools may be signed in on this machine, and a turn that
# reaches one past the stand-ins must find no account. An empty token does
# nothing to them, so each gets one that is set and belongs to no account: the
# Vercel CLI uses a set VERCEL_TOKEN in place of its stored sign-in, and the
# Supabase CLI puts SUPABASE_ACCESS_TOKEN ahead of its stored login. Docker is
# pointed at an engine that does not exist and a configuration folder with
# nothing in it, and the database tools at no stored password and no stored
# service. HOME is left alone, since the coding agent itself lives there.
provider_isolate_host() {
  VERCEL_TOKEN=replay-no-account
  SUPABASE_ACCESS_TOKEN=replay-no-account
  DOCKER_HOST=unix:///nonexistent/replay.sock
  DOCKER_CONFIG="$1/.docker-empty"
  PGPASSFILE=/dev/null
  PGSERVICEFILE=/dev/null
  export VERCEL_TOKEN SUPABASE_ACCESS_TOKEN DOCKER_HOST DOCKER_CONFIG \
    PGPASSFILE PGSERVICEFILE
}

provider_new_session() {
  if [ "$REPLAY_PROVIDER" = "claude" ]; then
    PROVIDER_SESSION=$(new_uuid)
  else
    PROVIDER_SESSION=
  fi
}

# provider_session_records <run-prefix>
# Print, one to a line, the files where the provider kept what each command in
# a run printed. The transcript holds only what the person and the kit said, so
# a command answered by the wrong tool shows up here and nowhere else. Codex
# writes every event into the turn's raw output. Claude Code keeps its own
# record of the session under its configuration folder, named by the session id
# the harness chose. run_once writes that id beside the run, because it runs in
# a subshell and the caller never sees the variable.
provider_session_records() {
  prefix=$1
  session=
  [ -f "$prefix.session" ] && session=$(cat "$prefix.session")
  case "$REPLAY_PROVIDER" in
    claude)
      [ -n "$session" ] || return 0
      find "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects" -maxdepth 2 \
        -name "$session.jsonl" 2>/dev/null || true
      ;;
    codex)
      for raw in "$prefix"-t*.json; do
        [ -f "$raw" ] && printf '%s\n' "$raw"
      done
      ;;
  esac
  return 0
}

# real_gh_answered
# Read file names from stdin, one to a line, and print the first sign that the
# real GitHub CLI answered a command. During a run the real one finds no
# account, so it says one of two things the stand-in never says. A kit that
# tells somebody to run "gh auth login" is not a sign; the real tool's own
# sentences are. Exits 0 when it finds one and 1 when it finds none.
REAL_GH_SIGNED_OUT="To get started with GitHub CLI, please run"
REAL_GH_NO_HOSTS="You are not logged into any GitHub hosts"
real_gh_answered() {
  while IFS= read -r record; do
    [ -f "$record" ] || continue
    sign=$(grep -o -F -e "$REAL_GH_SIGNED_OUT" -e "$REAL_GH_NO_HOSTS" \
      "$record" 2>/dev/null | head -n 1)
    if [ -n "$sign" ]; then
      printf '"%s" in %s\n' "$sign" "$(basename "$record")"
      return 0
    fi
  done
  return 1
}

codex_thread_id() {
  python3 - "$1" <<'PY'
import json
import sys

for line in open(sys.argv[1]):
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    if event.get("type") == "thread.started" and event.get("thread_id"):
        print(event["thread_id"])
        break
PY
}

wrap_codex_result() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

message, output = sys.argv[1:]
try:
    text = open(message).read()
except OSError:
    text = ""
with open(output, "w") as handle:
    json.dump({"result": text}, handle)
PY
}

run_codex_start() {
  message=$1
  raw=$2
  reply=$3
  if [ -n "$MODEL" ]; then
    ${TIMEOUT_CMD:+$TIMEOUT_CMD 1800} \
      codex exec --json --ignore-user-config --ignore-rules \
      -c shell_environment_policy.inherit=all \
      --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
      -m "$MODEL" -o "$reply" "$message" > "$raw" 2>/dev/null
  else
    ${TIMEOUT_CMD:+$TIMEOUT_CMD 1800} \
      codex exec --json --ignore-user-config --ignore-rules \
      -c shell_environment_policy.inherit=all \
      --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
      -o "$reply" "$message" > "$raw" 2>/dev/null
  fi
}

run_codex_resume() {
  message=$1
  raw=$2
  reply=$3
  if [ -n "$MODEL" ]; then
    ${TIMEOUT_CMD:+$TIMEOUT_CMD 1800} \
      codex exec resume --json --ignore-user-config --ignore-rules \
      -c shell_environment_policy.inherit=all \
      --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
      -m "$MODEL" -o "$reply" "$PROVIDER_SESSION" "$message" \
      > "$raw" 2>/dev/null
  else
    ${TIMEOUT_CMD:+$TIMEOUT_CMD 1800} \
      codex exec resume --json --ignore-user-config --ignore-rules \
      -c shell_environment_policy.inherit=all \
      --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
      -o "$reply" "$PROVIDER_SESSION" "$message" > "$raw" 2>/dev/null
  fi
}

# provider_turn <project> <message> <raw-output> <last-reply>
provider_turn() {
  project=$1
  message=$2
  raw=$3
  reply=$4
  : > "$reply"

  case "$REPLAY_PROVIDER" in
    claude)
      if [ -e "$reply.session-started" ]; then
        resume_args="--resume $PROVIDER_SESSION"
      else
        resume_args="--session-id $PROVIDER_SESSION"
      fi
      # shellcheck disable=SC2086
      (cd "$project" && PATH="${REPLAY_TOOLS:-$GH_DIR}:$PATH" \
        ${TIMEOUT_CMD:+$TIMEOUT_CMD 1800} claude -p "$message" \
        $resume_args \
        --strict-mcp-config \
        --permission-mode bypassPermissions \
        --output-format json \
        --model "$MODEL" > "$raw" 2>/dev/null) || return 1
      python3 - "$raw" "$reply" <<'PY'
import json
import sys

raw, reply = sys.argv[1:]
try:
    data = json.load(open(raw))
except Exception:
    raise SystemExit(1)
with open(reply, "w") as handle:
    handle.write(data.get("result") or "")
PY
      : > "$reply.session-started"
      ;;
    codex)
      if [ -n "$PROVIDER_SESSION" ]; then
        (cd "$project" && PATH="${REPLAY_TOOLS:-$GH_DIR}:$PATH" \
          run_codex_resume "$message" "$raw" "$reply") || return 1
      else
        (cd "$project" && PATH="${REPLAY_TOOLS:-$GH_DIR}:$PATH" \
          run_codex_start "$message" "$raw" "$reply") || return 1
        PROVIDER_SESSION=$(codex_thread_id "$raw")
        [ -n "$PROVIDER_SESSION" ] || return 1
      fi
      ;;
  esac

  [ -f "$reply" ]
}

run_codex_grader() {
  prompt=$1
  events=$2
  message=$3
  if [ -n "$GRADER_MODEL" ]; then
    ${TIMEOUT_CMD:+$TIMEOUT_CMD 600} \
      codex exec --json --ephemeral --ignore-user-config --ignore-rules \
      -c shell_environment_policy.inherit=all \
      --skip-git-repo-check --sandbox read-only \
      -m "$GRADER_MODEL" -o "$message" "$prompt" > "$events" 2>/dev/null
  else
    ${TIMEOUT_CMD:+$TIMEOUT_CMD 600} \
      codex exec --json --ephemeral --ignore-user-config --ignore-rules \
      -c shell_environment_policy.inherit=all \
      --skip-git-repo-check --sandbox read-only \
      -o "$message" "$prompt" > "$events" 2>/dev/null
  fi
}

# provider_grade <input> <outer-json-output>
provider_grade() {
  input=$1
  outer=$2

  case "$REPLAY_PROVIDER" in
    claude)
      # shellcheck disable=SC2086
      (cd "$WORK" && ${TIMEOUT_CMD:+$TIMEOUT_CMD 600} \
        claude -p "$(cat "$input")" \
        --allowedTools "" \
        --strict-mcp-config \
        --output-format json \
        --model "$GRADER_MODEL" 2>/dev/null) > "$outer" || true
      ;;
    codex)
      events="$outer.events"
      message=$(mktemp "$CODEX_GRADER_DIR/message.XXXXXX")
      # Codex has no command-line switch that removes every tool. The grader
      # runs read-only from an empty folder and receives only the contract and
      # transcript. Its final message is wrapped in the shape grade-parse.py
      # already reads for Claude.
      (cd "$CODEX_GRADER_DIR" && \
        run_codex_grader "$(cat "$input")" "$events" "$message") || true
      wrap_codex_result "$message" "$outer"
      rm -f "$message"
      ;;
  esac
}
