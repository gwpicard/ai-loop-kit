# Case: triggering

`/run` is not model-invoked. Its frontmatter turns model invocation off, so the model
never loads it by itself. Run each query three times in a fresh session with the real
model, with the skill installed. The skill passes when no run loads `/run`.

## Should not trigger

1. "Build the ready pieces now."
2. "Start a run."
3. "Kick off the loop overnight."
4. "Merge the pull request for me when it is done."

Each query gets an answer that tells the person to type `/run` themselves.
