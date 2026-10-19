# Quality results

One row per real quality run. No runs have been recorded yet. The local
fixture checks prove the seeds and oracles work; they are not field runs.
Keep the historical scenario results in `RESULTS.md`.

Record the kit commit tested, the backend and the fixture scenario. Describe
the expected bad behaviour. For `false-alarm`, say that no application defect
is expected and name the unsupported review block being tested.

Use `yes` or `no` for escaped to approval and false block. Escaped to approval
means known bad work reached approval. False block means correct work was
blocked. Human repairs counts interventions beyond shaping, approval and
merge. Record the number of builder attempts and elapsed duration in seconds.
If a value could not be measured, write `unknown` with the reason. Do not
leave cells blank. Write a literal pipe in prose as `&vert;`.

Check the table without GitHub access:

```
python3 tests/field/audit.py --quality tests/field/QUALITY.md
```

| Date | Kit commit | Backend | Scenario | Expected bad behaviour | Escaped to approval | False block | Human repairs | Attempts | Duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
