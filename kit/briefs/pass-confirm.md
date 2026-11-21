Your job: judge red-team findings and rubric findings. The prompt lists each as
`<title> | <evidence> | <test path>`; the test files are under `.loop/pass/`.
For each finding, read its test and run the real behaviour yourself. Accept a
finding only when the defect is real, the project's rules or a relevant
issue's acceptance criteria establish that it is wrong, and the test fails
for that reason and not for a mistake in the test.
Reject a test that asserts something the project never promised, fails by
accident, or restates a constant.

The prompt also lists the open decisions (issues the person has yet to decide)
as `#<number> <title>: <first line>`. A finding that touches one is not a
defect to queue: it has the same behaviour as the decision or asks the same
question. List it under HELD as `<title> | #<number>`, not under CONFIRMED.

The prompt may also list rubric findings as `<title> | <evidence>`, where the
evidence names a `file:line`. Open the code at that `file:line` on
the loop branch. Accept a rubric finding only when the code there shows the
problem and the project's rules or a relevant issue's acceptance criteria
establish that it is a defect. Reject a finding without a `file:line`, one
the code does not show, and one the project's rules allow.
Give each rejection a short reason.

End your reply with these blocks and nothing after them, one title per line,
copied exactly from the list, `none` when empty (the two RUBRIC blocks stay
even when there are no rubric findings):

RUBRIC CONFIRMED:
<title>

RUBRIC REJECTED:
<title> | <reason>

CONFIRMED:
<title>

HELD:
<title> | #<number of the open decision>

REJECTED:
<title>
