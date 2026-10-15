# What AI Loop Kit is for

AI Loop Kit is a small set of Claude Code skills and scripts for building
software in checked steps. An agent produces the work; the gate decides
whether it meets the contract; the person approves the contract and merge.

## The five principles

1. **Agents produce, scripts decide, the person approves.** The gate runs
   every check itself.
2. **A piece is a contract.** Work starts with intent, scope and a judge that
   fails on today's `main` for the right reason.
3. **Every state is a loop.** Each state has an entry check, work, an exit
   check and a way back with a reason.
4. **Hold rules in code, and label what is only words.** Important rules live
   in the gate or guard wherever a check can hold them.
5. **Grow from evidence.** After v1, a feature earns a place through a real
   failure, a test and a small change.

## The four parts

| Part | What it does |
| --- | --- |
| Engine | Moves each GitHub issue through states and checks each move. |
| Contract | Records intent, out of scope, approach and numbered outcomes. |
| Loop mechanisms | Repeats the build and judge, with typed hand-backs and bounded checks. |
| Roles | Shaper, judge writer, builder, reviewers, gate, run and person each have a clear job. |

The kit grew from v1's written plan. The earn rule is suspended for that
build. Once v1 merges, it applies again: write the observed failure in the
maintainer's ledger, add a test that reproduces it, then add the smallest fix.

## Read next

- `docs/V1.md`: the v1 definition.
- The maintainer's ledger holds the ideas the kit supports and what waits for
  evidence. The maintainer's lessons record what the first build taught us.
