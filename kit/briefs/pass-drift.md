Your job: the drift review of the batch. The prompt gives the batch diff command.
Read the diff and AGENTS.md, then check: the project's rules still hold; budgets
and size limits are met; the same logic is not written twice across issues;
docs and comments describe what the code now does; every source folder or build target changed in the batch is built,
type-checked or tested by the commands the prompt names (Test command, and Check
command when one is given). Report each one they skip as a finding, with the
path and the evidence.

Report only real problems with evidence; do not report taste. One finding per
line, each as `<short title> | <what is wrong and the evidence> | <path>`;
leave the path empty unless the task asks for one. End your reply with this
block and nothing after it, writing `none` when there is nothing:

FINDINGS:
<title> | <evidence> |

If the settings' Red-team surfaces list is empty, also end with a block
`SURFACES:` of at most four parts of the project a red team should attack,
one per line (a command, an input format, a screen).
