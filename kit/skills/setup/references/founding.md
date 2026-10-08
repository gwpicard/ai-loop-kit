# Founding

What the first half of `/setup` asks, writes and leaves alone.

## Contents

- The questions
- What the script writes
- What stays as it is
- The tools
- After the first half

## The questions

Ask them in one batch. Each has a recommended answer. A skipped answer never stops founding: the script writes it as an open question.

1. What does the product do, and who is it for? Recommended: read the README and the code first, then write your own guess and ask the person to correct it. This fills `docs/overview.md`.
2. What command runs every test? Recommended: the language's usual one. An empty project has none, and the first piece sets it up. Pass it as `--test-command` to `first-piece`. Pass the chosen command to `found` too, even in an empty project. `first-piece` sets the generated hosted check's scaffold command to this same command, including when it was unknown at founding. The policy stays empty until the runner exists. The person commits and merges the foundation pull request, then updates local main before capture. A command chosen or changed afterwards needs a person-reviewed, person-merged preparation pull request first.
3. Which language? The script detects it from the files. Pass `--language` only when the project is empty and the person knows.
4. Do you pay for Claude by subscription or by API key? Recommended: subscription. With an API key, ask for a spend cap for one piece and one for a whole run, and pass `--billing-mode api_key --spend-cap-piece N --spend-cap-run N`.
5. Is the repository private, and is the GitHub plan free? Pass `--repo-visibility` and `--plan`. A private repository on the free plan gets a plain warning: GitHub gives it no server-side rules, so the local guards carry every rule.

## What the script writes

It writes each file only when the file is absent.

- `AGENTS.md` and `CLAUDE.md`, with the kit's absolute path in the commands.
- `docs/overview.md`, `docs/README.md` and `docs/area-map`.
- `CHANGELOG.md` and `.github/workflows/checks.yml`.
- `.claude/settings.json`: the guards, merged into the person's own.
- `.githooks/pre-push`, and `core.hooksPath` set to `.githooks`.
- `.agents/loop/policy.json` and `.agents/loop/network-allowlist.json`. The list holds the package registry and the toolchain hosts for the language, and no GitHub host.
- `.agents/guard/blocked-commands.md`.
- `.gitignore`: the lines it lacks are added after the person's own.
- `docs/open-questions.md`, when an answer was missing.

## What stays as it is

`found` keeps each existing file. When `first-piece` captures the scaffold, it updates only the generated `SCAFFOLD_TEST_COMMAND` entry in `checks.yml`. It preserves the rest of the workflow, including uncommitted changes. Capture and the actual gate branch both require the selected entry in committed main. A local update alone is refused, including on a repeated call. A custom workflow without this entry stays as it is.

The person's settings rules stay, and the kit's rules are added beside them. The script copies nothing of the kit into the project. The kit runs from its plugin folder.

## The tools

The kit needs Git, python3 and openssl. The check names the install line for each. Install a tool only when the person asks. The GitHub command line tool is reported but never required in this half.

## After the first half

The person can shape and run locally. Every GitHub write waits for the person: the gate queues it, and `gate.py sync` sends it from the person's own terminal. The GitHub App is made in the second half of `/setup`. Until then an unattended run and a pre-approved merge are refused.
