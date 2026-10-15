# v1.1 rehearsal results

Plan: `docs/v1.1/rehearsal-plan.md`.

Sonnet sessions used: 0.

| Item | Result | Evidence and findings |
| --- | --- | --- |
| A1 | NOT RUN | Step 1 did not finish. GitHub refused draft PR creation with HTTP 403 because the integration cannot access the pull request endpoint. |
| A2 | NOT RUN | Step 1 did not finish. No rehearsal work began. |
| A3 | NOT RUN | Step 1 did not finish. No rehearsal work began. |
| A4 | NOT RUN | Step 1 did not finish. No rehearsal work began. |
| B1 | NOT RUN | Step 1 did not finish. No interactive Claude session began. |
| C1 | NOT RUN | Step 1 did not finish. The walk-away sandbox probe was not started. |
| C2 | NOT RUN | Step 1 did not finish. No unattended run began. |

The branch was pushed at `49287afb7520c8e754548bbab1b3d6888da00a48`. The GitHub
REST check-runs endpoint returned zero check runs for that commit. No draft PR
exists, so its four CI jobs could not run. The branch integration and local
checks passed, but the rehearsal gate remained unmet.

Not in this round: the Node scenario, kill during review and a second
walk-away night.
