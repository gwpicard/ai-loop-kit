#!/usr/bin/env sh
# loop-modules.sh: guard the written rules of the build loop.
#
# A piece labelled loop:build is built with nobody there. The scripts hold what
# a machine can judge: the gate routes each status, the run script counts the
# attempts and keeps failed work, and builder-status-rehearsal.sh drives them.
# What is left is prose an agent reads: that every attempt is a fresh builder
# carrying a note and no conversation, that it ends with exactly one status,
# that a finding which would change the contract ends the attempt rather than
# being acted on, and that the run script never starts a model session. A
# builder that quietly finished a piece by rewriting its Done when would look
# the same as one that met it. So each rule is read back here and taken out in
# turn to prove it is needed, in the loop's reference, in section-builder, in
# WORKFLOW.md and in the design note.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

LOOP="$ROOT/.agents/skills/section-builder/references/build-loop.md"
SECTION="$ROOT/.agents/skills/section-builder/SKILL.md"
RUN="$ROOT/.agents/skills/implement/scripts/run.py"
WORKFLOW="$ROOT/WORKFLOW.md"
NOTE="$ROOT/docs/design/agentic-loop.md"

rs_init "Build loop checks"
rs_exists "$LOOP" "$SECTION" "$RUN" "$WORKFLOW" "$NOTE"

# --- the build loop's reference --------------------------------------------

rs_rule "it is loaded for a loop:build piece in place of steps 4 and 5" \
  'load it for a piece labelled `loop:build`, in place of steps 4 and 5'
rs_rule "the acceptance checks are shown failing through the gate's before evidence" \
  'gate\.py evidence <number> --phase before -- <command>'
rs_rule "the builder builds until every acceptance check passes" \
  'builds until every acceptance check passes'
rs_rule "each attempt ends with exactly one status" \
  'ends each attempt with exactly one status'
rs_rule "the five statuses are named" \
  '`done`, `done_with_concerns`, `needs_context`, `blocked` or `environment_failed`'
rs_rule "the result goes to the run's results folder in the main folder" \
  '\.agents/runs/<run name>/results/<number>-attempt-<n>\.json'
rs_rule "outside .agents/pieces/, which the deny rules guard" \
  'outside `\.agents/pieces/`, which the deny rules guard'
rs_rule "every attempt is a fresh builder with the bounded brief" \
  'every attempt is a fresh builder, started with the bounded brief'
rs_rule "carrying the previous attempt's note and nothing of its conversation" \
  'carrying the previous attempt.s note and nothing of its conversation'
rs_rule "the run script never starts a model session" \
  'the run script never starts a model session itself'
rs_rule "it writes a start request into the run record" \
  'writes a start request into the run record'
rs_rule "the coordinating session starts the builder with its subagent tool" \
  'starts the builder with its own subagent tool'
rs_rule "and writes the subagent's id back" \
  'writes the subagent.s id back into the request'
rs_rule "a builder researches and repairs by itself within the limits" \
  'within the limits the builder researches and repairs by itself'
rs_rule "a finding that would change the contract ends the attempt as needs_context" \
  'a finding that would change a `done when` line, a `decided` line or the boundary ends the attempt as `needs_context`'
rs_rule "and is never acted on" 'rather than being acted on'
rs_rule "a builder never claims, pushes, reviews, opens a pull request or merges" \
  'a builder never claims, pushes, reviews, opens a pull request or merges'
rs_rule "a failed attempt is defined" \
  'a failed attempt is a `done` whose checks fail when the gate runs them, or no result once the builder is known to have ended'
rs_rule "environment_failed does not count" \
  '`environment_failed` does not count'
rs_rule "the limits come from the project's settings" \
  'three attempts and a piece budget of 120 minutes, from `\.agents/loop-settings\.json`'
rs_rule "the budget is time alone" 'the budget is time alone'
rs_rule "at the limit the piece goes to research, or spec for a check that cannot be met" \
  'at the limit the gate kicks the piece back to `shaping:research`, or to `shaping:spec` when'
rs_rule "a failed attempt's work is kept before the next starts" \
  'keeps the failed attempt.s work with `recovery\.py preserve`'
rs_rule "uncommitted work is put away, never thrown away" \
  'git stash push --include-untracked'
rs_rule "the branch keeps every attempt's history" \
  'so the branch keeps every attempt.s history'
rs_rule "nothing resets, checks out or forces" \
  'never runs `git reset --hard`, `git checkout \.`, `git restore \.` or a force push'
rs_rule "a module switch goes only through the gate" \
  'only through `gate\.py switch-module <number> <module>`'
rs_rule "the build never asks for an acceptance" \
  'never asks for an acceptance and never writes an `accepted:` line'
rs_rule "the stop hook sends a done builder back once" \
  'sends the builder back once'
rs_rule "with no fresh builder the run stops where it can resume" \
  'cannot start a fresh builder, the run stops at a point it can resume from'
rs_guard "$LOOP" "the build loop's reference"

# --- section-builder points to it --------------------------------------------

rs_require_load_bearing "step 4 points a loop:build piece to the build loop" "$SECTION" \
  'for a piece labelled `loop:build`, load `references/build-loop\.md`'
rs_require_load_bearing "step 5 builds a loop:build piece in the loop's attempts" "$SECTION" \
  'a `loop:build` piece is built in the attempts `references/build-loop\.md` runs'
rs_require_load_bearing "step 8 reaches a loop:build piece only after the gate routed done" "$SECTION" \
  'a `loop:build` piece reaches this step only once the gate has routed its builder.s `done`'
rs_require_load_bearing "section-builder loads the task handoff for each attempt" "$SECTION" \
  'load `references/task-handoff\.md`'
rs_require_absent "the old three attempts paragraph is gone" "$SECTION" \
  'a piece whose build fails three attempts stops there'

# --- the run script starts no model session ---------------------------------

rs_require "run.py says it never starts a model session" "$RUN" \
  'never starts a model session'
rs_require_absent "run.py calls no coding agent's command line" "$RUN" \
  '"(claude|codex|gemini|cursor-agent)"'
rs_require_absent "run.py calls no model service" "$RUN" 'anthropic|openai'

# --- WORKFLOW.md section 5 ---------------------------------------------------

rs_require_order "WORKFLOW.md tells the build loop in its Day to day section" "$WORKFLOW" \
  '^## 5\. Day to day' 'A ready piece is built without you'
rs_require_order "and before its Evidence section" "$WORKFLOW" \
  'A ready piece is built without you' '^## 6\. Evidence'
rs_require_load_bearing "a ready piece is built without you" "$WORKFLOW" \
  'a ready piece is built without you'
rs_require_load_bearing "every attempt ends with one of five endings" "$WORKFLOW" \
  'every attempt ends in one of five ways'
rs_require_load_bearing "done goes on to the checks and the review" "$WORKFLOW" \
  'done goes on to the gate.s own run of the checks, then the review'
rs_require_load_bearing "done with concerns goes to your review" "$WORKFLOW" \
  'done with concerns does the same, and the piece then waits for your review'
rs_require_load_bearing "needs context and blocked go back to shaping" "$WORKFLOW" \
  'needs context and blocked send the piece back to shaping'
rs_require_load_bearing "environment failed is tried once more, then the build stops" "$WORKFLOW" \
  'environment failed is tried once more, and if it fails again the build stops'
rs_require_load_bearing "three failed attempts or two hours is a kickback" "$WORKFLOW" \
  'after three failed attempts, or two hours, the piece goes back to shaping with a `## kickback` section'

# --- the design note ---------------------------------------------------------

rs_reset
rs_rule "a build loop at its limit goes to research, or spec" \
  'a build loop at its limit goes back to `research`, or to `spec` when a check cannot be met as written'
rs_rule "the budget is one of time, usage left to Computer resources" \
  'a budget of time, whichever comes first\. usage is left to computer resources'
rs_rule "the run script writes a start request the coordinating session acts on" \
  'the run script writes a start request for each fresh builder, and the coordinating session starts it with its subagent tool, so the run script never starts a model session itself'
rs_guard "$NOTE" "the design note's Loop modules section"
rs_require_absent "the design note no longer counts tokens against a loop" "$NOTE" \
  'a budget of time or tokens'

rs_done
