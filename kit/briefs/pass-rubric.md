Your job: the rubric review of the batch. The prompt gives the batch diff command.
Check the changed code for: readability a new reader can follow; errors that
are swallowed or reach the person as a traceback; tests that only restate
constants or the code; fixed sleeps and other timing guesses; dead code and
unused names. Give `file:line` evidence in every finding.

Report only real problems with evidence; do not report taste. One finding per
line, each as `<short title> | <what is wrong and the evidence> | <path>`;
leave the path empty unless the task asks for one. End your reply with this
block and nothing after it, writing `none` when there is nothing:

FINDINGS:
<title> | <file:line and what is wrong> |
