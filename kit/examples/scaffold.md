# Scaffold example

For an empty project, the first piece sets up the test runner. Use the
confirmed Test command from setup. This Python example uses unittest.

Use one Tests check under `## Exit`, with `Kind: scaffold`. Ready skips
Prepare and the regression check on main, and allows the runner to be
missing. After the build, the runner must pass with at least one test.
The older Judge form keeps the same rules.

```markdown
## Intent
Set up the test runner so later pieces can prove their behaviour.

Out of scope:
- Product features.

## Contract
- D1: Running `python3 -m unittest discover -s tests -v` passes and runs at least one test.

## Risks
Protected paths: none
New dependency: none
Shared files: none
Needs services: none
Open choices: none

## Exit
### Tests
Kind: scaffold
Command: `python3 -m unittest discover -s tests -v`
```

The builder adds the runner and its first test, so this example has no
frozen judge files under `Files:`. Do not add a separate `Keep:` that needs
the missing runner on main. Later pieces use ordinary Tests checks in
[the spec format](../spec-format.md).
