---
name: review-public-docs
description: Review the shipped prose and the release notes draft before a release. Load by path.
---

# Review public docs

Run before preparing a release. The shipped prose is `README.md`,
`docs/DESIGN.md`, `CONTRIBUTING.md`, `SECURITY.md` and every Markdown file under
`kit/`, plus the version's notes draft in `docs/release-notes/`. Split it into
at most three parts, and include the relevant source files with each part.

Give each part to a fresh reviewer that has not seen another review. Ask it to
check claims in this order: code and checks, release notes, then the docs. Look
for stale terms, contradictions, wrong counts, broken references and
unsupported claims, such as an old version number or a feature that has
changed. A reviewer must confirm each finding in the code or a check before
reporting it. Otherwise it reports the concern as unconfirmed.

Collect the reports in `.agents/tmp/public-docs-review/` and combine confirmed
findings into one list for the maintainer. A release waits until each finding
is fixed or the maintainer accepts it. Keep accepted findings and their reasons
with the review record.

This review checks that claims are true. The version's notes file also gets a
review against the release-notes standard, before the release pull request.
`.agents/maintainer-skills/release-notes/SKILL.md` says how.

## The printout

One line for each finding, most serious first:
`file:line` | kind (stale, contradiction, count, reference, unsupported) |
what the code or check shows, with its `file:line` | the fix in one line |
confirmed or unconfirmed.

Under the list, give the count of each kind and the findings the maintainer
already accepted, with the reason. This review reports and changes nothing.

## Done when

Every part has had one fresh reviewer, every confirmed finding is on the list,
and the maintainer has fixed or accepted each one before the release is
prepared.
