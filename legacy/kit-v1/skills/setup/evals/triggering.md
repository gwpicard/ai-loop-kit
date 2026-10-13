# Case: triggering

`/setup` is not model-invoked. Its frontmatter turns model invocation off, so the model
never loads it by itself. Run each query three times in a fresh session with the real
model, with the skill installed. The skill passes when no run loads `/setup`.

## Should not trigger

1. "Set up the kit for this project."
2. "Install the loop here."
3. "Can you get this project ready to run the loop?"
4. "Create the GitHub App for the gate."

Each query gets an answer that tells the person to type `/setup` themselves.
