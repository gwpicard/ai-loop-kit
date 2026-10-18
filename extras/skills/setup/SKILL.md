---
name: setup
description: Show the installed extras path and how to use it with AI Loop Kit.
---
# Mutation tools and gauntlet critics

## Extra path
!`echo "EXTRAS=${CLAUDE_PLUGIN_ROOT}"`

Show the person the EXTRAS path above. Set `AI_LOOP_KIT_EXTRAS_ROOT` to that
full path in the shell that starts the gate or run. Prefix each gate or run
command with `AI_LOOP_KIT_EXTRAS_ROOT="<EXTRAS>"` when shell exports do not
persist between commands. Keep this value when resuming a run.

The same path supplies gauntlet critics and their brief. Ready and claim
refuse a gauntlet piece when either file is missing.

For mutation testing, run `/ai-loop-kit:setup` to agree the mutation Quality
command. It uses
`python3 "$AI_LOOP_KIT_ROOT/quality/mutmut-check.py" origin/main` as before.
The extra requires mutmut 3.8 or later, configured source paths and tests
that call the changed code in-process. Do not add a Quality command until
the person agrees and doctor passes it on a fresh copy of main.
