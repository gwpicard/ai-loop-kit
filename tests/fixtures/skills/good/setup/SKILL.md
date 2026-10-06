---
name: setup
description: Installs the kit into a project. The person starts it by hand.
disable-model-invocation: true
---
# Setup
This fixture skill installs the kit and says what it left behind.

## Stops
- Stop before anything that changes access or money. Held by: the ask rules in the project settings.

## Steps
1. Run the tooling check.
   Done when: it exits 0.

## Gotchas
- A project that already has the kit needs an update, not an install.
