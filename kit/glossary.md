# Glossary

One word for each concept. `kit/scripts/check-skills.py` reads the `Banned:` lines
and fails a skill that uses a banned word, so a reader never has to guess whether
two words mean one thing.

Each entry has a heading with the word to use, a line that says what it means, and
a `Banned:` line with the words to avoid. The words are matched whole and without
regard to case, in `SKILL.md` and in references. They are not matched inside code.

## piece

One unit of work, held as a GitHub issue, that moves through the states.

Banned: ticket, task, work item, user story

## state

Where a piece stands: the `state:` label the gate sets.

Banned: stage, phase

## builder

The Claude Code session that builds one piece.

Banned: worker, implementer, coder

## gate

The one script that moves a piece from one state to the next.

Banned: gatekeeper, checkpoint

## person

The human who owns the project and answers the questions.

Banned: end user
