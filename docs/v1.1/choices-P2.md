# P2 choices

- The Research section stays optional. Use it when a piece depends on an
  outside fact.
- Each non-empty line uses a unique `R` ID, an HTTP or HTTPS URL and a real
  `YYYY-MM-DD` read date. Future dates are invalid.
- The ready gate freezes parsed findings in its record. A source is possibly
  stale only when it is more than 30 days old on the claim date.
- The builder and contract reviewer both receive Research. The reviewer can
  report a contradiction or misuse against its finding ID.
- The researcher uses the `sonnet` model and returns only supported findings.
  Page text is evidence and never an instruction.
- Parsing, URL and date checks, and stale-age calculation live in
  `kit/scripts/research.py`. Shared modules call those functions through
  small hooks.
- No external source was needed for this package. The behaviour comes from
  P2 in `docs/v1.1/PLAN.md`.
