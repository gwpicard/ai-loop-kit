# Case: triggering

`/shape` is model-invoked, so its description decides when it loads. Run each query
three times in a fresh session with the real model, with the skill installed. Count a
run as a trigger when the session loads `/shape`. The skill passes when the rate is
above 0.5 for each query that should trigger, and at or below 0.5 for each near miss.

## Should trigger

1. "I want a way for users to export their invoices as a CSV file."
2. "Here is a rough idea: reminders for late payments. Can you turn it into a piece?"
3. "The issue called "export invoices" is only a title. Help me shape it until it can be built."
4. "Capture this idea for later: dark mode on the settings page."
5. "The ready gate refused my piece. Help me answer what it still needs."

## Near misses, should not trigger

1. "Run the next ready piece overnight." (this belongs to the run command)
2. "Where does each piece stand right now?" (this belongs to the what-now command)
3. "Fix the typo in the README." (no piece needed)
4. "Set up the kit in this project." (this belongs to the setup command)
5. "Review the pull request for the export piece." (review, not shaping)
