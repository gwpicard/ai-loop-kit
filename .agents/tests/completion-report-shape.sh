#!/usr/bin/env sh
# completion-report-shape.sh: guard the shape of the /setup completion report.
#
# Scenario 24 (the completion report) cannot be replayed from scratch: founding
# runs many steps and a trivial idea is correctly diverted before any software is
# built, so a fixed short conversation never reaches the report.
# The behaviour is watched by hand before a release. This deterministic check
# guards its source instead: the rules that give the report its shape live in
# completion-report.md, so a change that weakens them fails here on every push.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

REPORT="$ROOT/.agents/skills/setup-ai-build-kit/references/completion-report.md"

rs_init "Completion-report shape checks"

rs_rule "lead with what is ready" "lead with what.?s ready"
rs_rule "never lead with technical state" "never lead with"
rs_rule "checkpoint reference stays at the end" "checkpoint reference.*(end|bottom)"
rs_rule "end on a clean cut, not an offer to build" "clean cut"
rs_rule "do not offer to build in this session" "not offer to build"
# Founding takes each piece no further than spec, because writing a piece's
# acceptance checks pushes a branch and founding uploads no code. So the report
# names the pieces waiting there and points at /shape, never at /implement,
# which would find nothing ready to build.
rs_rule "name the pieces waiting in spec" "name the pieces waiting in spec"
rs_rule "point at /shape" "point at .?/shape.? to take the first piece on from there"
rs_rule "the template sends the person to /shape" "type .?/shape.? to take it on from there"
rs_rule "do not tell the person to push the founding checkpoint" \
  "do not tell the person to push"
# The report once said "Everything's set up and saved" over a project holding
# nothing but its opening commit. The reference is the thing that cannot be
# written without the checkpoint existing, so it is required rather than
# optional, and the report waits on a save rather than describing one.
rs_rule "the checkpoint reference is never skipped" \
  "the one line that is never skipped"
rs_rule "the checkpoint is read back before the report is written" \
  "read the checkpoint back before writing"
rs_rule "and its reference carried in from what was read" \
  "carry its reference into the report"
rs_rule "no checkpoint means no report yet" "the report is not due"
rs_rule "meaning to save is not saving" \
  "on the strength of having meant to save it"
rs_rule "and naming it is what makes the claim impossible to fake" \
  "no reference to name for a checkpoint that was never taken"
# Founding opens the pieces as issues online, so "Nothing was uploaded" was
# untrue on every founded project. The report names what went online and what
# did not.
rs_rule "the report says no code was uploaded, not that nothing was" \
  "no code was uploaded or published\. the build steps are listed as issues"
rs_rule "the pieces going online is translated for the person" \
  "the pieces were opened as issues -> "
# The first build pushes the code online, and a real run did that straight
# after this report said nothing was uploaded. The report now says the code
# waits for the person's yes, and only where none of the code is online yet,
# since an adopted project may already be on GitHub.
rs_rule "the report says the first build asks before the code goes online" \
  "only where the online repository holds none of the project.s code yet:\] the code stays on this computer until your first build asks you before putting it online\. \[state"
rs_rule "that line is translated for the person" \
  "holds none of the project.s code yet, so the first push waits for a yes -> "
rs_guard "$REPORT" "the shipped completion-report.md"

rs_require_absent "the report no longer points at /implement for the first piece" \
  "$REPORT" "point at .?/implement.? to build the first piece"

rs_done
