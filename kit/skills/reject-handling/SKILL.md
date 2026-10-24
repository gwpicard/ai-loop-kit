---
name: reject-handling
description: Handle a person's rejected pull request as a judge-gap or person-rejected hand-back, preserving their reason.
user-invocable: false
---
# Rejected pull request

Ask: was something missing from the contract?

If yes, use `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" move <n> shaping --type judge-gap --reason "<what was missing>"`. Use `/ai-loop-kit:shape` to add an exit check or a `(stays)` item, then take the piece through ready again. The gate permits contract edits only in shaping.

If the rejection is a matter of taste, use `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" move <n> shaping --type person-rejected --reason "<their words>"`. Leave the pull request open so the next build retries with that reason.

Done when: the piece is in shaping with the person's reason on the issue, or the missing check has been shaped and the gate accepts ready again. Never change a state label by hand or merge the pull request.
