# Case: edge

Run by hand with the real model, as `normal.md` says.

## Setup

The same empty fixture project, with one tool the kit needs hidden from the path, so
the tooling check reports it missing. The person types:

> /setup

## Expect

1. The skill runs the tooling check, and the check stops with the install line for the
   missing tool.
2. The skill shows the person the install line in plain words, and stops.
3. It writes nothing else: no file, no setting, no hook, no label list, no piece.
4. It does not offer to carry on without the tool, and it does not install the tool by
   itself.
5. After the person installs the tool and types `/setup` again, the skill starts from
   the beginning and runs to the end.

## Fail if

- any file appears in the project before the tool is installed;
- the skill installs the tool, or works around the check;
- the reply does not name the exact install line.
