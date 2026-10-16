# Upgrade to 1.2

This note is for projects moving from AI Loop Kit 1.0 or 1.1 to 1.2. Update
the plugin, then review the loop settings in your project's `AGENTS.md` and
the specs on open issues.

## Loop settings

The 1.2 loop recognises three additional settings. Add them under `## The
loop` in `AGENTS.md` where they apply:

```markdown
Keep limit: 15
Sandbox domains: pypi.org, files.pythonhosted.org
Secret paths: config/private.json, ../shared/credentials.json
```

- `Keep limit:` sets the maximum time in minutes for the Keep check. It
  defaults to 15, so add it when the project's check needs a different limit.
- `Sandbox domains:` lists the package registry hosts the person has agreed
  to allow during a walk-away run. Add it only when walk-away needs network
  access. The gate refuses walk-away when no domains are recorded.
- `Secret paths:` lists extra files that walk-away agents must not read.
  Separate paths with commas. Paths may be in the project or outside it.

## Issue specs

New specs use `## Exit` to name the checks that prove the contract and `##
Risks` to record protected paths, dependencies, shared files, services and
open choices. For a test check, list its command and the files it uses. The
gate still accepts older `Kind:` specs, so open issues do not all need an
immediate rewrite. Use the new sections when shaping or revising a spec.

```markdown
## Exit
### Tests
Command: `python -m pytest tests/judge/test_piece.py -q`
Files:
- tests/judge/test_piece.py

## Risks
Protected paths: none
New dependency: none
Shared files: none
Needs services: none
Open choices: none
```
