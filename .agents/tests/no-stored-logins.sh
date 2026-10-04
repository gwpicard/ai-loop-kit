#!/usr/bin/env sh
# no-stored-logins.sh: guard what the kit may use to reach a service, and what
# waits for the person before a live service changes.
#
# A real first launch needed a sign-in setting changed on the live data
# service. The kit told the person it could not see that setting and asked
# them to change it on the service's own page. When the person asked it to
# try, it read the service tool's stored login out of the computer's keychain
# and used it to read and change the setting. That login reaches every project
# on the account, not only this tool's. The same run, while building its first
# piece, pushed a local settings file to the live service and switched off a
# setting it could not switch back on, without asking first. It also wrote
# every key, the secret one included, to a shared temporary folder to fill the
# project's key file.
#
# Each rule here is prose an agent reads. Its absence would not show on screen
# until the next run did the same thing again, so each is proved load-bearing
# in every file it lives in.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SHIP="$ROOT/.agents/skills/ship/SKILL.md"
SECOND="$ROOT/.agents/skills/second-opinion/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Stored-login and live-change rules"
rs_exists "$SHIP" "$SECOND" "$BUILDER" "$FOUNDATION" "$WORKFLOW"

# /ship is where the keychain was read, in the launch review.
rs_rule "the login rule reaches every step that reaches a service" 'this holds for the launch review and for every step in this skill that reaches a service'
rs_rule "only the tool's own commands and the browser's keys" 'the kit uses only what a tool offers through its own commands, and the keys the tool already sends to the browser'
rs_rule "never a stored login from the keychain or another tool's files" 'it never reads a stored login, token or password out of the keychain, a credential store, or another tool.s own files'
rs_rule "never the management API with such a login" 'it never calls a service.s management api with such a login'
rs_rule "a tool's own sign-in is never taken out of it" 'the kit never takes that sign-in out to use it another way'
rs_rule "what it cannot reach is said truthfully, naming the page" 'when the kit cannot read or change a setting that way, it says so truthfully and asks the person, naming the page where the setting lives'
rs_rule "never cannot-read followed by a read" 'once it has said it cannot read something, it never reads it another way'
rs_rule "a key the person gave the project is the project's own" 'a key the person gave this project, kept where the masterplan records it, belongs to the project'
rs_rule "a live change waits for a yes that names it and says whether it can be undone" 'a command that changes a live service.s settings or data, other than saving code through the save route, waits for a yes that names the change and says whether it can be undone'
rs_rule "not knowing whether it can be undone is said" 'where the kit does not know whether the change can be undone, it says that'
rs_rule "ship names everything the command changes, from its preview" 'name every setting or record the command will change, not only the one you meant to change, taken from the command.s own preview where it has one'
rs_rule "ship knows a settings push changes all that differs" 'pushing a whole local settings file changes everything in it that differs from the live project'
rs_rule "the recipe's own commands, in any section, need no further yes" 'the commands the project.s recipe names, in any section, are the launch the person asked for, and need no further yes'
rs_rule "anything the recipe does not name, and any settings push, still waits" 'anything the recipe does not name, and any push of a settings file, waits for the named yes'
rs_rule "a whole-account token is for the recipe's reads only" 'a token in the person.s environment that reaches the whole account is used only for the reads the recipe names'
rs_rule "a change with that token waits for the yes" 'a change made with it waits for the yes above'
rs_rule "migrations to the live project are a live change in ship" 'applying migrations to the live project'
rs_rule "no secret key in a shared temporary folder" 'a secret key is never written to a shared temporary folder such as `/tmp`'
rs_rule "a key goes straight into the file that uses it" 'write what a step needs straight into the git-ignored file that uses it'
rs_rule "the setting read goes through the tool's own commands" 'a command-line tool this session is already signed in to, through that tool.s own commands'
rs_guard "$SHIP" "ship's login and live-change rules"
rs_require_order "the login rule follows the setting rule" "$SHIP" '^#### A setting the kit can read$' '^#### A login the kit does not own$'
rs_require_order "the live-change rule comes before the secret rule" "$SHIP" '^#### A change to a live service$' '^#### A secret a check needs$'

# The launch review itself runs in second-opinion.
rs_reset
rs_rule "the review reads through the tool's own commands" 'a command-line tool this session is already signed in to, through that tool.s own commands'
rs_rule "the review never reads a stored login" 'never read a stored login, token or password out of the keychain, a credential store, or another tool.s own files'
rs_rule "the review never calls the management API with one" 'never call a service.s management api with one'
rs_rule "the review never reads what it said it could not" 'once you have said you cannot read a setting, never read it another way'
rs_guard "$SECOND" "second-opinion's setting read"

# The live change and the temporary file both happened while building.
rs_reset
rs_rule "a build uses only the tool's own commands and the browser's keys" 'use only what a tool offers through its own commands, and the keys the tool already sends to the browser'
rs_rule "a build never reads a stored login" 'never read a stored login, token or password out of the keychain, a credential store, or another tool.s own files'
rs_rule "a build never calls the management API with one" 'never call a service.s management api with one'
rs_rule "a build says what it cannot reach, naming the page" 'when you cannot read or change something that way, say so truthfully and ask the person, naming the page where it lives'
rs_rule "a build never reads what it said it could not" 'once you have said you cannot read something, never read it another way'
rs_rule "a build's live change waits for a named yes" 'a command that changes a live service.s settings or data, other than saving code through the save route, waits for a yes that names the change and says whether it can be undone'
rs_rule "a build names everything the command changes, from its preview" 'name every setting or record the command will change, not only the one you meant to change, taken from the command.s own preview where it has one'
rs_rule "a build knows a settings push changes all that differs" 'pushing a whole local settings file changes everything in it that differs from the live project'
rs_rule "migrations to the live project need the yes during a build" 'applying migrations to the live project needs the yes too'
rs_rule "the yes comes first" 'ask before you run it, never after'
rs_rule "a key read through a tool is piped and never shown" 'a secret key read through a tool.s own commands is piped straight into that file and never shown'
rs_rule "an unattended run leaves it unrun" 'in an unattended run nobody is there to say yes, so leave it unrun and say so on the piece'
rs_rule "a build keeps secret keys out of /tmp" 'a secret key is never written to a shared temporary folder such as `/tmp`'
rs_rule "a build writes a key straight into its file" 'write what the build needs straight into the git-ignored file that uses it'
rs_guard "$BUILDER" "section-builder's service rules"

# Every session reads the project's AGENTS.md, which sits at its line ceiling,
# so it carries the short form.
rs_reset
rs_rule "the project writes no key to /tmp" 'or write one to `/tmp`'
rs_rule "the project never takes another tool's stored login" 'never take a login another tool stores for itself, as in the keychain or its files'
rs_rule "the project never uses such a login on an API" 'or use one on an api'
rs_rule "the project uses the tool's own commands or its own keys" 'use that tool.s own commands or the project.s own keys'
rs_rule "the project says so and asks, and never reads it another way" 'if you cannot, say so and ask; never then read it another way'
rs_rule "the project stops before a live setting changes, naming all it changes" 'such as a live service.s settings: name all it changes and if it can be undone'
rs_guard "$FOUNDATION" "the project's short form"

rs_require_load_bearing "WORKFLOW says no stored login is taken" "$WORKFLOW" 'the kit never takes a login another tool keeps for itself'
rs_require_load_bearing "WORKFLOW says no read after a cannot" "$WORKFLOW" 'once the kit has told you it cannot read a setting, it does not then read it some other way'
rs_require_load_bearing "WORKFLOW says everything it changes is named" "$WORKFLOW" 'the kit first names everything the command will change, not only the setting it meant to change'
rs_require_load_bearing "WORKFLOW says a live change waits for a yes" "$WORKFLOW" 'a command that changes a live service.s settings or data, other than saving code through the save route, waits for your yes'

rs_done
