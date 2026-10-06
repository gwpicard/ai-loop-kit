Scaffold the project and its test runner, so every later piece has a judge.

<!-- spec:start version=1 -->
Path: quick

## Goal
The project has a structure to build in and one command that runs its tests.

## Expected flow
FL-1 The person runs the test command and sees the one first test pass.

## Edge cases
EC-1 When the test command runs on a clean copy of the branch "main", then it passes.

## Must stay the same
The README stays as it is (README.md).
Check: test -f README.md

## Judge
Kind: scaffold
Command: {{TEST_COMMAND}}
Proves: FL-1, EC-1

## Links
Touches: project-records
<!-- spec:end -->
