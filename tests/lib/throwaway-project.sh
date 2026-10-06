# throwaway-project.sh: build a project for an end-to-end test. Source it.
#
#   . "$ROOT/tests/lib/throwaway-project.sh"
#   tp_new demo                       # a project called demo
#   tp_app                            # give the project the stand-in App
#   tp_issue "Title" "Body"           # open an issue through the GitHub stand-in
#   tp_claude_script '<json>'         # script the next Claude stand-in session
#
# The project uses the GitHub stand-in (`gh`), a stand-in App key and the Claude
# stand-in (`claude`), so a test needs no network, no GitHub account, no real
# App and no model. Nothing here deletes anything. The folder is made with
# mktemp -d and is left in place for you to read after the test.
#
# After tp_new these are set and exported:
#   TP_BASE        the throwaway folder that holds everything below
#   TP_ROOT        the project (a Git repository on main, with a bare origin)
#   TP_DATA        the local data folder (AI_LOOP_KIT_DATA)
#   TP_APP_KEY     the stand-in App key, where loop/paths.py says it belongs
#   FAKE_GH_STATE, FAKE_GH_LOG, FAKE_CLAUDE_LOG
# and PATH starts with a folder that holds `gh` and `claude`.

: "${ROOT:?source throwaway-project.sh after setting ROOT to the repository}"

tp_new() {
  # tp_new <name>
  tp_name=${1:?tp_new needs a project name}
  TP_BASE=$(mktemp -d)
  TP_ROOT="$TP_BASE/$tp_name"
  TP_DATA="$TP_BASE/data"
  TP_BIN="$TP_BASE/bin"
  mkdir -p "$TP_ROOT" "$TP_DATA" "$TP_BIN"

  # Git: a private identity and no outside configuration, so the host's hooks
  # and signing settings cannot change a test.
  : > "$TP_BASE/gitconfig"
  GIT_CONFIG_GLOBAL="$TP_BASE/gitconfig"
  GIT_CONFIG_SYSTEM=/dev/null
  GIT_AUTHOR_NAME="Test Person"
  GIT_AUTHOR_EMAIL="test@example.com"
  GIT_COMMITTER_NAME="Test Person"
  GIT_COMMITTER_EMAIL="test@example.com"
  export GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL \
    GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL

  git init -q --bare -b main "$TP_BASE/origin.git"
  git init -q -b main "$TP_ROOT"
  git -C "$TP_ROOT" remote add origin "$TP_BASE/origin.git"
  printf '# %s\n\nA throwaway project.\n' "$tp_name" > "$TP_ROOT/README.md"
  git -C "$TP_ROOT" add README.md
  git -C "$TP_ROOT" commit -q -m "Start the project"
  git -C "$TP_ROOT" push -q origin main

  # The stand-ins, first on PATH.
  ln -s "$ROOT/tests/stand-ins/fake-github/gh" "$TP_BIN/gh"
  ln -s "$ROOT/tests/stand-ins/fake-claude/claude" "$TP_BIN/claude"
  PATH="$TP_BIN:$PATH"
  FAKE_GH_STATE="$TP_BASE/gh-state.json"
  FAKE_GH_LOG="$TP_BASE/gh.log"
  FAKE_CLAUDE_LOG="$TP_BASE/claude.log"
  AI_LOOP_KIT_DATA="$TP_DATA"
  export PATH FAKE_GH_STATE FAKE_GH_LOG FAKE_CLAUDE_LOG AI_LOOP_KIT_DATA TP_BASE TP_ROOT TP_DATA

  # The stand-in App key goes where loop/paths.py says the key belongs, so the
  # test checks that place and not a copy of it.
  TP_APP_KEY=$(PYTHONPATH="$ROOT/kit/scripts" python3 -c '
import sys
from pathlib import Path
from loop.paths import Paths
print(Paths.for_project(Path(sys.argv[1])).app_key_file)
' "$TP_ROOT")
  "$ROOT/tests/stand-ins/fake-app/make-key.sh" "$(dirname -- "$TP_APP_KEY")" >/dev/null
  export TP_APP_KEY
}

tp_app() {
  # tp_app: give the project the stand-in App's settings, so the kit acts on
  # the GitHub stand-in as the App. Without it the kit has no App.
  mkdir -p "$TP_ROOT/.agents/loop"
  python3 - "$ROOT/tests/stand-ins/fake-app/app.json" "$TP_ROOT/.agents/loop/local.json" <<'PYEOF'
import json, sys
app = json.load(open(sys.argv[1]))
json.dump({"github_app": {"app_id": app["app_id"], "installation_id": app["installation_id"],
                          "slug": app["slug"]}}, open(sys.argv[2], "w"))
PYEOF
  FAKE_APP_KEY=$TP_APP_KEY
  export FAKE_APP_KEY
}

tp_issue() {
  # tp_issue <title> [body]: prints the address of the new issue.
  (cd "$TP_ROOT" && gh issue create --title "$1" --body "${2:-}")
}

tp_claude_script() {
  # tp_claude_script <json>: the next stand-in session replays this.
  printf '%s\n' "$1" > "$TP_BASE/claude-script.json"
  FAKE_CLAUDE_SCRIPT="$TP_BASE/claude-script.json"
  export FAKE_CLAUDE_SCRIPT
}
