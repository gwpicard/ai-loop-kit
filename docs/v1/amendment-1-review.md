# v1 amendment (from the maintainer's review notes)

Apply these. Fold A into W6 if you have not finished W6; do B to F as a new package W11 after W10. Add W11 to docs/V1-PLAN.md and update docs/V1.md to match.

A. Reviewer: two axes, two fresh sessions (after Matt Pocock's code-review).
- Standards reviewer: reads the project's standards file if `Standards:` names one; if none, it uses a built-in baseline of Fowler's twelve smells (Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest), each as a labelled heuristic, never a hard rule. Plus these hard points (after Cursor's thermo-nuclear review): no new ad-hoc special-case branches in an unrelated flow, no pass-through wrappers, logic in the layer that owns it, reuse existing helpers. The review always runs; it does not need a standards file.
- Contract reviewer: reads only Intent, Out of scope, Approach and Contract plus the diff. Reports missing or partly met items, scope creep (anything under Out of scope, or beyond the Contract), and items met in a wrong way. It does not see the standards reviewer's output.
- Every finding cites a standards rule or a named smell with the hunk, or a line of the contract. A finding without a citation is dropped.
- One pass each. Never loop until clean. Both briefs say: "Do not invoke review skills or spawn agents. Review directly."
- The standards reviewer may commit small, local fixes for cited findings. Structural findings (a restructure, a split, a deeper module) are never done in the piece: they go in the pull request under "Follow-up pieces" for the person to shape.
- A contract finding that an item is missing or met wrongly means the judge let it through: the run records the type `judge-gap` on the piece record (a seventh reason type, counted by `gate.py report`) and lists the finding at the top of the pull request.
- After review commits, the gate runs every submit check again; on any failure drop the review commits, as already planned.

B. File size: at submit the gate fails an attempt that takes a file from under 1000 lines to 1000 or more, unless the Judge section has `Large file: <path>`. The pull request risk list names any file over 1000 lines.

C. CRAP on changed functions, Python: `kit/quality/crap.py`, stdlib only. Cyclomatic complexity per function from `ast`; coverage per function from coverage.py's `coverage json` output (the project runs coverage; the script does not). CRAP = complexity^2 * (1 - coverage)^3 + complexity. Only functions overlapping `git diff -U0` ranges. Fail at 30 or more; also fail when a changed existing function's CRAP rises above its value on main. Plain output: one line per function over the line. Setup offers it as a Quality command for Python projects. For Node, setup offers ESLint's `complexity` rule only; CRAP for Node waits.

D. testlint also flags judge tests that import a private name (leading underscore) from the project's own code, as structure-sensitive. Judges test the public interface.

E. Waiting limit: the run builds no new piece while 3 or more pieces wait in approval (`Waiting limit:` in the loop section changes the number). It says so in one line with a `next:` step. Verification must keep up with building.

F. Builder context: before an attempt the run lists the project files that import the modules or files named under Approach (the same import scan as the pull request facts) and puts that list in the brief as "Code that depends on what you change".
