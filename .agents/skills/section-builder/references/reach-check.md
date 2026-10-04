# Reach check

Before a change is saved, answer two questions from the current working tree:
what else does the change reach, and which existing tests cover it? Run those
tests first. The full project check still runs before a pull request is ready.

Use the first available engine in this order:

1. The harness's language server, or Serena.
2. The project's related-test or affected-code command, such as
   `jest --findRelatedTests`, `vitest related`, `pytest --testmon`,
   `nx affected`, or `dependency-cruiser --reaches`.
3. A graph tool the person already installed, such as codebase-memory-mcp,
   graphify, sentrux, or code-review-graph.
4. Read the changed files' imports and callers directly, and say in the
   internal evidence that this was the fallback used.

A written index is a lead to verify against the current tree, never a project
record. Discard its answer when the working tree has moved past the index. Do
not save the reach result in a file. Derive it again for each change.

When the check finds another part of the tool, say exactly: "This change also
reaches <part>, and the <count> tests that cover it passed." Say nothing when
nothing else is reached.
