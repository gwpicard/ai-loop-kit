# Plan

Every agent reads this file before it starts. The person adds to it while
shaping. Where an issue and this file differ, this file wins.

## Decisions

One line per decision, with the date and the reason.

## Product rules

What must always hold, for example: spelling, tone, supported platforms,
data that must never be lost, how screens are checked.

## Stops

An agent that needs one of these ends its reply with
`PARK: <question> | <recommended answer>` and stops work on the issue:

- spending money or changing billing
- credentials, secrets or access rights
- permissions, repository or service settings
- irreversible data changes
- anything that makes the project public
- a new dependency, or a change to a protected path
- any decision only the person can make

Add the rules of this project below.

## Deviations

Builders append here when they take the closest approach to a decision the
plan did not make: the issue, what they chose, and why.
