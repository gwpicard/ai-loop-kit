# P3 choices

- Goal targets use the four numeric operators `<`, `<=`, `>` and `>=`.
- Measure commands print a finite number on the last line. The gate runs each
  command three times and compares the median.
- Gauntlet capture commands write files under `.loop/capture/`. A reference is
  either a local path or a URL, as named in the spec.
- A critic returns one tagged JSON object with a winner and a reason for each
  criterion. Three separate `claude -p` sessions judge the same capture pair.
- A URL reference is fetched once per comparison set and shown to critics as
  a local artefact, so its address does not reveal which side it is.
- The builder records one hypothesis per goal attempt at `.loop/hypothesis`.
  The run saves each result with its attempt log and includes the results in
  the pull request facts.
