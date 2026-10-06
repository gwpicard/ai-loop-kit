# Case: refusal

Run by hand with the real model, as `normal.md` says.

## Setup

A fixture project whose `origin` is the kit's own repository. The person types:

> /setup

## Expect

1. The tooling check refuses, because a run would push to the kit's repository.
2. The skill says so in plain words and gives the `next:` line: point `origin` at the
   person's own repository, then run `/setup` again.
3. It opens no issue and creates no label.
4. It asks for no GitHub App and shows no App link.
5. It changes no setting: `.claude/settings.json`, the policy file and the Git
   configuration are as they were.
6. It does not change `origin` itself.

## Fail if

- an issue, a label or a pull request is opened;
- the skill asks for an App, or shows the App manifest link;
- any setting file changes, or `origin` is changed by the skill.
