# The evidence run

Used by ship before anything goes live. Findings come with fresh output; no claims from memory. Skip a section
below only when it genuinely doesn't apply to this tool, and say so rather
than leaving it silently blank.

## 1. Promised behaviour

For each main journey named in the masterplan: the evidence type used, the
command or user action taken, the expected result, the actual result, and a
pass or fail.

## 2. Failure behaviour

Test whichever of these are relevant: invalid input, a duplicate action,
unauthorised access, an external service failing, an action interrupted
partway, two people acting at once, a large or malformed input, a retry, and
an offline or unavailable dependency. Narrate each probe in plain words; a
line saying "I tried two people pressing save at once" teaches the habit of
expecting failure better than any instruction to have it.

## 3. Data and access

Where applicable: secrets absent from the repository and from anything sent
to the browser, permissions checked across more than one user, test and live
data kept separate, a migration rehearsed on a copy, a backup actually
restored, and deletion or export behaviour checked.

## 4. Operations

Where applicable: alerts arrive, the named owner reads them, service and
billing ownership are known, the manual fallback works, and the rollback or
disable process works. On a project with a recipe, the rollback, backup,
restore, secrets, logs and health checks are the recipe's own, and ship runs
them as its "On a recipe" steps say rather than repeating them here.

## 5. Review and flagged work

Independent review completed, its blocking findings resolved, any caution
condition completed, and the review's scope and limitations recorded rather
than implied.

Where a review names its reviewer, check that person did it. A substitute is a
gap, not a completed review, and it is recorded as one. Where a risk was
accepted instead, the build-path section carries the `Accepted:` line, and the
launch report says plainly which review did not happen.

## 6. Report honesty

End with what passed, what failed, what was not checked at all, what
remains a human judgement rather than a proven fact, and whether the current
build path permits shipping this.
