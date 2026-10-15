# v1 amendment 2: do as W12 after W11. Add W12 to docs/V1-PLAN.md and update docs/V1.md.

A. Tests that fail for the right reason (from kata's "testing without tautologies"). Add to the judge-writer brief and the standards reviewer brief, short:
- Ask of each test: "What production change should make this test fail?" If there is none, delete the test.
- Expected values are literals, never computed with the code under test.
- A fake never accepts any input; use separate doubles for the success and the error path.
- Never mock the subject under test. Prefer a local stand-in (temporary folder, in-memory store) over a mock.
- No test that only greps a source file or asserts a symbol is absent, except a "the old path is gone" item the Contract names.
- Mechanical part, in testlint.py: flag a judge test whose only assertion compares against the result of calling the same function twice, and flag tests that read a project source file as text (open(...) or readFileSync on a path under the project's source folders) unless the Contract item says the check is about the file.

B. Deep modules (from Matt Pocock's codebase-design). Add to the judge-writer brief and the standards reviewer checklist, short:
- Judges call the module's interface only: what a caller must know (types, invariants, ordering, errors), not internals. A judge that must reach past the interface means the module has the wrong shape: report it in the PR as a follow-up piece.
- Standards reviewer checklist: does a new abstraction pass the deletion test (delete it: does complexity vanish, or reappear in callers)? Does a new seam have two real adapters, or is it hypothetical? Are tests on a removed shallow module deleted rather than layered ("replace, don't layer")?
- In the shape skill, the Approach section names the module and its interface when the piece adds or changes one.

C. Structured verdicts. The judge writer and both reviewers end with one tagged JSON block (for example <verdict>{...}</verdict>). run.py takes the last match, allows a code fence, checks the fields, and fails loudly on bad JSON (the run records type environment for the piece, with the raw tail in the log). Never guess a verdict from free text.

D. Idle timeout. run.py kills a builder or reviewer attempt after 10 minutes with no output (configurable `Idle limit:` in the loop section), records it as builder-failed with "idle" in the reason, and goes on. The existing hard timeout stays.

E. Dirty build folder. Before each attempt, if the build folder has uncommitted changes the run did not make, it refuses that piece with a next: line and type environment. It never resets or cleans the folder.
