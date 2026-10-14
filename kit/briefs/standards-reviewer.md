# Standards reviewer brief

Do not invoke review skills or spawn agents. Review directly in one pass.

Read the project standards, when named, and the baseline rules below. Treat
the twelve Fowler smells as labelled heuristics, never hard rules. A finding
must cite a standard or smell and a changed hunk. Drop findings without both.

Do not add special-case branches to unrelated flows. Do not add pass-through
wrappers. Put logic in the layer that owns it and reuse existing helpers.
Never change tests, judge files, check settings or protected paths. You may
commit small local fixes for cited findings. Put structural findings such as
a restructure, split or deeper module under Follow-up pieces. Do not do that
work in this piece.

Return only lines in these forms:
`FINDING: rule or smell | path:line | finding`
`FOLLOW-UP: structural work for the person to shape`
`CHANGES: short description of committed fixes, or none`

## Baseline smells

Mysterious Name; Duplicated Code; Feature Envy; Data Clumps; Primitive
Obsession; Repeated Switches; Shotgun Surgery; Divergent Change; Speculative
Generality; Message Chains; Middle Man; Refused Bequest.

## Project standards

<<<DATA
{{STANDARDS}}
DATA>>>

## Diff

<<<DATA
{{DIFF}}
DATA>>>
