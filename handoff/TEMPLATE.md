# Slice <N>: <title: what a person will be able to do, in plain words>

Labels (today's set): enhancement or documentation, area:<skills|docs|tests|release>, ready-able once shaped. Release label for the PR: release-minor unless stated.
Parent: the "AI Loop Kit v1" epic. Blocked by: slices <list> (by slice number and title).

## So that
One outcome for the person, one sentence.

## Done when
### Works
- <rule>. Check: <the machine check that proves it, named by the rehearsal file it lives in, e.g. `.agents/tests/<name>.sh`, or "guided check: <what a person does and sees>">
- (each line false on today's main and true after this slice alone)
### When it is not the normal case
- <state or failure>: <what happens>. Check: <...>   (or "does not arise, because ...")

## Masterplan change
For this repository there is no masterplan; write "Design note: <which section of docs/design/agentic-loop.md this realises>" and any change the note needs.

## Not in this piece
- <what a reader might expect here but belongs to another slice, naming that slice>

## Decided
- <every choice a person would notice, with its reason; quote the decision record number where it comes from>

## Data
<records, files or labels written or changed: where they live, who else writes them, limits, migration of older projects; or "No stored data changes, because ...">

## Leaves the tool
<what goes to GitHub or anywhere outside the computer, or "Nothing new leaves the tool, because ...">

## Must still hold
- <existing rules, checks and limits this slice must not break, with the check that guards each, e.g. the AGENTS.md ceiling (standing-instructions.sh), no issue numbers in tracked files (validate-kit.sh)>

## Relies on
- <existing files, scripts or earlier slices it uses, each confirmed to exist on main today or produced by a named earlier slice>

## Reach and risk
Boundary: <kit areas this slice may change, by skill or document name, never file paths>
Reaches: <areas it affects without changing, each with the existing rehearsals that guard them by name, or "no test covers it">
If it breaks: <who notices what, and how it is undone>
Depends on: <slice numbers>
Loop module: build (or fix, goal, gauntlet) and why
Crew: default for the module, or the change and its reason

## Under the hood
<the build approach in a few lines: which skills, references, scripts and rehearsals change or are added; what is reused from the overnight batch branch (recovery.py, task handoff, browser rule, force-push rules, question box, same-turn continuation) or from main; the existing rehearsals this slice is expected to change and why; the kit's own rules that apply (five questions in PHILOSOPHY for a canonical skill change, SOURCES.md credit, adapters rebuilt, validator, humanizer, no issue numbers)>

## Evidence
<the kind of proof: rehearsals with rule-shape load-bearing checks, scripts run in throwaway repositories, replay scenario(s), or a recorded real run>

## Size
<one sitting / two sittings; if bigger, say how it splits into parts>
