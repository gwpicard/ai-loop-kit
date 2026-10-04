#!/usr/bin/env sh
# state-guard.sh: refuse a direct change to a piece's state labels.
#
# A piece's state lives in its state:, shaping: and review: labels, and only
# the gate script, .agents/tools/gate.py, changes them, after it checks that
# the move is allowed. Claude Code runs this before each Bash command and each
# GitHub tool call. It refuses one that adds, removes, creates, edits or
# deletes one of those labels, and names the gate command to use instead.
#
# It reads the hook's input, works out the tool and what it would do, and
# exits 2 to refuse, which Claude Code shows to the agent. Anything it cannot
# read is let through, so a fault here never blocks every command. The written
# rule in blocked-commands.md, and `gate.py report`, still hold.
#
# The gate calls GitHub itself, so its own commands pass. A command that runs
# the gate and also writes a state label by hand is refused all the same.

set -u

input=$(cat)

# The tool's name on the first line, then the command for Bash, or one label
# per line for a GitHub tool call that carries labels.
parsed=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    sys.exit(3)
if not isinstance(data, dict):
    sys.exit(3)
name = str(data.get("tool_name") or "")
args = data.get("tool_input") or {}
if not isinstance(args, dict):
    args = {}
print(name)
if name == "Bash":
    print(str(args.get("command") or ""))
elif name.lower().startswith("mcp__") and "github" in name.lower() and "labels" in args:
    def walk(value):
        if isinstance(value, str):
            for part in value.split(","):
                print(part.strip())
        elif isinstance(value, dict):
            walk(value.get("name", ""))
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(args["labels"])
' 2>/dev/null) || exit 0

tool=$(printf '%s\n' "$parsed" | sed -n 1p)
rest=$(printf '%s\n' "$parsed" | sed 1d)

family='(state|shaping|review)(:|%3a)'

refuse() {
  {
    echo "The state guard refused this: it changes a state:, shaping: or review: label directly."
    echo "Only the gate script moves a piece, after it checks that the move is allowed."
    echo "Run instead: $1"
    echo "Never reach the same change another way. If the gate refuses, tell the person what it said."
    echo "blocked-commands.md lists what is refused, under \"Changing a piece's state by hand\"."
  } >&2
  exit 2
}

case "$tool" in
  Bash) ;;
  mcp__*|MCP__*)
    if printf '%s\n' "$rest" | grep -Eiq "^$family"; then
      refuse ".agents/tools/gate.py move <number> <target>, or .agents/tools/gate.py capture for a new piece"
    fi
    exit 0 ;;
  *) exit 0 ;;
esac

# The command on one line, so an option and its value split across lines by a
# backslash still sit together.
command=$(printf '%s\n' "$rest" | tr '\n' ' ')

# gh, called by its name or its full path, inside another shell or after
# another command.
gh='(^|[[:space:];&|(/"'"'"'])gh[[:space:]]'
quote="[\"']"
not_quote="[^\"']"
# A label option, then a state label as its value, alone, quoted, after an
# equals sign, or anywhere in a comma-joined list.
label_value="[[:space:]](--add-label|--remove-label|--label|-l)(=|[[:space:]]+)($quote($not_quote*[,[:space:]])?|([^[:space:]\"']*,)?)$family"

matches() {
  printf '%s\n' "$command" | grep -Eiq -- "$1"
}

if matches "$gh(.*[[:space:]])?issue[[:space:]]+create([[:space:]]|\$)" && matches "$label_value"; then
  refuse ".agents/tools/gate.py capture --title <title> --body-file <file>, then .agents/tools/gate.py move"
fi
if matches "$gh(.*[[:space:]])?issue[[:space:]]+edit([[:space:]]|\$)" && matches "$label_value"; then
  refuse ".agents/tools/gate.py move <number> <target>"
fi
if matches "$gh(.*[[:space:]])?label[[:space:]]+(create|edit|delete)[[:space:]]+(-[^[:space:]]*[[:space:]]+)*$quote?$family"; then
  refuse ".agents/tools/gate.py labels, which creates the kit's labels and changes nothing else"
fi
if matches "$gh(.*[[:space:]])?api[[:space:]]" && matches "issues/[^[:space:]/]+/labels"; then
  if matches "$family" || \
     matches "(-X|--method)(=|[[:space:]]+)$quote?(POST|PUT|PATCH|DELETE)" || \
     matches "[[:space:]](-f|-F|--field|--raw-field|--input)([[:space:]=]|\$)"; then
    refuse ".agents/tools/gate.py move <number> <target>"
  fi
fi

exit 0
