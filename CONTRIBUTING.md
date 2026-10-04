# Contributing

This repository is the public copy of AI Build Kit. Every released file can be
read here and compared between version tags.

## Report a problem

Open a public issue with the kit version, installation route, what you expected,
and what happened instead. Add the smallest set of steps that reproduces the
problem. Remove passwords, tokens, personal data, and private project details
before posting.

## Suggest a change

Open a feature request and describe the situation in which you would use it.
Explain what you would expect to see or do. You do not need to propose a
technical design.

## Pull requests

Target `main`. That is where work merges, and where a numbered release is cut
from. People install from `stable`, a separate branch that only a release
moves, so a pull request opened against `stable` would be asking to change a
release that has already gone out. If a new pull request arrives with anything
other than `main` filled in as its base, change it before asking for a review.

Do not open a pull request against the generated release files. A later release
would replace the edit. Start with an issue instead. Accepted changes appear in
a numbered release with public notes.
