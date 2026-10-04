#!/usr/bin/env sh
# secret-location.sh: guard where a secret's location is written down, and what
# the kit says when it does not know it.
#
# A person named the file holding their database password while a piece was
# being built. The project's AGENTS.md kept only that the password lived outside
# the project. A later /ship could not find it, skipped the backup, the restore
# and the database guard, and wrote into the changelog that the password was not
# on this computer. The file was there the whole time. So the location is
# recorded, a check reads it before it needs the secret, and not knowing where
# a secret is never becomes a claim that it is gone.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
FIT="$ROOT/.agents/skills/setup-ai-build-kit/references/fit-check.md"
MASTERPLAN="$ROOT/.agents/skills/setup-ai-build-kit/templates/masterplan.md"
SHIP="$ROOT/.agents/skills/ship/SKILL.md"
FIX="$ROOT/.agents/skills/fix/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Secret-location rules"
rs_exists "$FOUNDATION" "$FIT" "$MASTERPLAN" "$SHIP" "$FIX" "$MAINTAIN" "$WORKFLOW"

# Every session reads the project's AGENTS.md, so the rule that writes the
# location down and the rule that reads it back both live there. That file sits
# at its line ceiling, so it carries the short form; /ship, the fit check and
# the masterplan section carry the detail.
rs_rule "the project's own secrets stay in .env" 'keys, passwords, and tokens live in `\.env`\.'
rs_rule "a secret kept elsewhere has its location written down" 'record where any other secret lives, never its value, in the masterplan.s "how it stays running", and read it there'
rs_rule "an unrecorded location is asked about once" 'if none is recorded, ask once'
rs_rule "a secret given as a reply is rotated" 'rotate a secret that appears where it should not, even one given as a reply'
rs_rule "a secret given as a reply is recorded nowhere and its location asked for" 'record it nowhere, say it is now in this chat, and ask for its location'
rs_rule "an unknown location is never a missing secret" 'a secret with no known location is never called absent'
rs_guard "$FOUNDATION" "the project's Secrets rule"
rs_require "values still stay out of documents" "$FOUNDATION" 'keys, passwords, and tokens.*never print, commit, or copy'

# /ship is where the false claim was written, so its own rule names the checks
# that need a secret and the wording of the warning.
rs_reset
rs_rule "the rule holds on and off a recipe" 'this holds at every go-live, on a recipe or off one'
rs_rule "the backup, restore and database guard are named" 'such as the database password for the backup, the restore or the database guard'
rs_rule "ship reads the recorded location first" 'read where that secret lives from the masterplan.s "how it stays running" section'
rs_rule "the secret is passed by its location" 'pass it by its location, as a command built in the person.s shell or read inside a script'
rs_rule "the value is never read or shown" 'never read, print or show the value'
rs_rule "checking the record never reads the secret" 'checking the record means checking that the file or variable exists, never reading it'
rs_rule "ship asks once when the location is unknown or wrong" 'when no location is recorded, or nothing is where the record says, ask the person once where it lives'
rs_rule "a secret given as the answer is recorded nowhere" 'if the answer is the secret itself, record it nowhere'
rs_rule "the person hears it is in the conversation and is asked to rotate it" 'say plainly that it is now in this conversation, ask the person to rotate it, and ask for its location instead'
rs_rule "ship records the answer as a location" 'record their answer in that section as a location, never a value, and run the check'
rs_rule "no answer is an ordinary warning" 'if they cannot say, the check could not run, and that is a warning like any other'
rs_rule "the warning says the location is unknown" 'its line and its changelog entry say that the kit does not know where the secret is kept'
rs_rule "the warning never calls the secret absent" 'never write that the secret is absent, missing or not on this computer'
rs_rule "no unconfirmed reason is given" 'give no reason for a skipped check that the kit did not itself confirm'
rs_guard "$SHIP" "ship's rule for a secret a check needs"
rs_require_order "the secret rule sits before merging" "$SHIP" '^#### A secret a check needs$' '^#### Merging and deploying$'

rs_reset
rs_rule "a credential's ownership fact is its location" 'for a credential, the fact is where it lives: a file path, a password manager entry.s name, or an environment variable.s name, and never its value'
rs_rule "the fit check points at the Secrets rule" 'agents\.md.s secrets rule says how a later session reads it'
rs_guard "$FIT" "the fit check's ownership rule for credentials"

rs_reset
rs_rule "the masterplan section takes a location" 'where a secret lives outside the project goes here as its location only'
rs_rule "the masterplan section names the kinds of location, never a value" 'a file path, a password manager entry.s name, or an environment variable.s name\. never a value'
rs_guard "$MASTERPLAN" "the masterplan's running section"

rs_require_load_bearing "fix reads the location first" "$FIX" 'a step that needs a secret reads where it lives from the masterplan first'
rs_require_load_bearing "fix asks once when it is unknown" "$FIX" 'asks once when that is unknown'
rs_require_load_bearing "maintain reads the location before a backup check" "$MAINTAIN" 'a check that needs a secret reads where it lives from the masterplan first, asks once when that is unknown, and never calls the secret absent'
rs_require_load_bearing "WORKFLOW says where the location is written" "$WORKFLOW" 'it writes down where, never the secret itself, in the masterplan.s "how it stays running" section'
rs_require_load_bearing "WORKFLOW says a later ship reads it" "$WORKFLOW" 'a later /ship reads that line before the backup, restore or database check'
rs_require_load_bearing "WORKFLOW says what an unknown location sounds like" "$WORKFLOW" 'the warning says the kit does not know where the secret is kept, and never that it is gone'

rs_done
