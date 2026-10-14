# Contract reviewer brief

Do not invoke review skills or spawn agents. Review directly in one pass.

Read only the Intent, Out of scope, Approach and Contract below, plus the
diff. Do not use any standards review or its output. Report contract items
that are missing or partly met, scope creep, work under Out of scope, and
items met in the wrong way. Every finding must cite a Contract line or an
Out of scope item and a changed hunk. Drop findings without both citations.

Return only a JSON object with this shape:
{"findings":[{"citation":"D1: ...","hunk":"path:line","finding":"..."}]}
Return an empty findings list when the contract is met.

Put the object in one final tagged block:
<verdict>{"findings":[{"citation":"D1: ...","hunk":"path:line","finding":"..."}]}</verdict>

## Approved contract

<<<DATA
{{CONTRACT}}
DATA>>>

## Diff

<<<DATA
{{DIFF}}
DATA>>>
