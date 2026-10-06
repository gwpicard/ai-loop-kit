#!/usr/bin/env sh
# recipe-nextjs-supabase-on-vercel.sh: guard the recipe for Next.js and hosted
# Supabase on Vercel, offline.
#
# A recipe is what the kit checks a live tool against, so a rule that quietly
# leaves it is a launch step nobody checks. The rules held hardest are the ones
# whose loss would look harmless: previews never touch the live database,
# migrations run before the build that needs them and only add, a rollback
# stops later pushes going live until somebody promotes again, the image Vercel
# ignores still answers on this machine before a merge, and the secrets check
# reads names and never a value. The health route and the container live in a
# shared part, guarded here and by the Coolify recipe's rehearsal.
#
# It also runs every command the recipe writes against stand-ins for its
# tools, and holds the recipe out of the menu until its real run is recorded.
# The recipe file is recipes/nextjs-supabase-on-vercel.md.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$ROOT/tests/lib/rule-shape.sh"
. "$ROOT/tests/lib/recipe-rehearsal.sh"

rs_init "Next.js and Supabase on Vercel recipe"
rr_locate "$ROOT/kit/recipes/nextjs-supabase-on-vercel.md"

# The free plan's limit. Two foundings for a work team missed it, and one
# called the account free. Founding says this line to a work team, so it has
# to stay, with the plan a work team needs and the page it was read from.
rs_rule "the free plan is personal and non-commercial" 'plan terms: vercel.s free hobby plan is for personal, non-commercial use only'
rs_rule "a work team needs the paid plan" 'so a work team needs the paid pro plan'
rs_rule "the terms name the page and date they were read" '\(read [0-9]{4}-[0-9]{2}-[0-9]{2} at https://vercel\.com/docs/limits/fair-use-guidelines#commercial-usage\)'
rr_shape

# Preview, and the first launch that sets the project up. A real run on a
# private repository met all three of these: Vercel's GitHub app could not see
# the repository, the new project had no framework, and linking the folder
# wrote to it. Each needed a hand fix, and the first tempted the kit into
# deploying from a local copy, which reports no commit and never deploys again.
# A later run proved the steps and found two more things: GitHub asks the
# person to confirm who they are before it shows the app's page, and the kit
# can read a protected preview's health itself, which it did.
rs_rule "a private repository is the person's step" 'when the github repository is private, the person first lets vercel.s github app see it, because only somebody who owns the repository can grant that'
rs_rule "the person hears where to grant it" 'settings, then applications, then installed github apps, and choose configure beside vercel'
rs_rule "GitHub asks the person to confirm first" 'github asks them to confirm who they are, with a passkey or their password, before it shows that page'
rs_rule "an organisation's repository has its own page" 'the organisation.s settings, then third-party access, then github apps'
rs_rule "the person adds only this repository" 'under repository access they pick only select repositories, add the repository, and save'
rs_rule "the connect failure is named" '.vercel git connect --yes. fails with "failed to connect"'
rs_rule "the project is created with no framework" '.vercel project add <project>., which sets no framework'
rs_rule "the framework is set before the first deploy" 'then sets one with .vercel project update <project> --framework nextjs --yes.'
rs_rule "the missing framework's failure is named" 'no output directory named "public" found'
rs_rule "the folder is linked to the project" '.vercel link --project <project> --yes.'
rs_rule "the kit never deploys from a local copy" 'the kit never deploys from a local copy of the folder in place of that connection'
rs_rule "the first-launch steps' own run is recorded" 'a third run the same day, on a new private repository with vercel cli 60\.0\.0, ran those first-launch steps'
rs_rule "main goes first" 'the first push to a new vercel project is .main., before any other branch'
rs_rule "a generated address answers 302" 'such an address answers 302 to anyone not signed in'
rs_rule "the production domain stays public" 'the production domain, .<project>\.vercel\.app., stays public'
rs_rule "previews never reach the live database" 'a second supabase project kept for previews, never at the live one'
rs_rule "the preview database gets the branch's migrations" 'before each preview, the kit gives that project the branch.s migrations with .supabase link --project-ref <preview project ref>. and .supabase db push.'
rs_rule "the kit waits for the preview to be ready" 'waits until .vercel inspect <preview address>. reports the deployment as ready'
rs_rule "a preview is protected by a sign-in" 'vercel protects each generated deployment address with a sign-in by default'
rs_rule "the kit can read a protected preview's health" 'the kit can read the preview.s health with .vercel curl /api/health --deployment <preview address> --yes., which gets past that sign-in'
rs_rule "the command is named as beta" 'that command is marked beta'
rs_rule "the bypass token is named" 'it creates a deployment protection bypass token on the project\. the token stays on the project and is never printed'
rs_rule "the kit asks before making the token" 'so the kit asks the person before running the command the first time'
rs_rule "the kit reads it only after a yes" 'read by the kit through that command after the person.s yes, or opened by the person signed in'
rs_rule "without it the person opens the preview signed in" 'when the person says no, or the command is missing or fails, the person opens the address in their own browser, signed in to vercel'
rs_rule "the preview answers from its own project" 'a .project. that is not the live project.s reference'

# Going live.
rs_rule "the kit links back to live before going live" 'the kit links back to the live project with .supabase link --project-ref <live project ref>.'
rs_rule "migrations run before the build that needs them" 'applies new migrations to the live database before the build that needs them, because vercel does not run them'
rs_rule "a dry run lists the migrations first" '.supabase db push --dry-run. lists what would change'
rs_rule "a migration in a release only adds" 'a migration in a release only adds'
rs_rule "the kit lists tables with row-level security off" 'select tablename from pg_tables where schemaname = .public. and not rowsecurity;'
rs_rule "the connection string is the session pooler, built in the shell" '.supabase_db_url. is the session pooler address from .supabase/\.temp/pooler-url. with the database password added, built in the person.s shell, and the kit never shows it'
rs_rule "the query passes on no rows" 'the row-level security query returns no rows, or each table it returns is on the record'
rs_rule "the advisor is only a second read" 'is an optional second read, since that endpoint is marked experimental'
rs_rule "the live commit is the one on main" 'its .commit. equals .git rev-parse origin/main.'

# Rollback.
rs_rule "rollback reaches back one build on Hobby" 'on the hobby plan only the build just before is eligible'
rs_rule "a rollback stops later pushes going live" 'stops moving new pushes to production until a newer build is promoted with .vercel promote <deployment>.'
rs_rule "the person hears that in the same reply" 'the kit says so in the same reply'
rs_rule "a rollback leaves migrations alone" 'a rollback does not undo database migrations'
rs_rule "the rollback is read back from the health route" 'is the earlier commit rather than the one rolled back'

# Backup and restore come from the shared parts.
rs_rule "backup links the shared part" '## backup shared part: \[backup on hosted supabase\]\(parts/supabase-backup\.md\)'
rs_rule "restore links the shared part" '## restore shared part: \[restore on hosted supabase\]\(parts/supabase-restore\.md\)'

# Secrets.
rs_rule "the service role key never reaches the browser" 'the service role key stays on the server and never carries that prefix'
rs_rule "supabase/.temp is kept out of the repository" '.supabase init. does not add .supabase/\.temp. to .\.gitignore., and that folder holds the project reference and the pooler address, so the kit adds it before the first commit'
rs_rule "a value never sits on a command line" 'the kit pipes it into vercel so that it never sits on a command line'
rs_rule "a public name is typed as config" 'printf .%s. "\$value" \| vercel env add <name> production --type config --yes. for a name that starts with .next_public_.'
rs_rule "a secret keeps the sensitive type" 'which keeps vercel.s default sensitive type'
rs_rule "the ignore is checked" '.git check-ignore supabase/\.temp. names the folder'
rs_rule "linking adds two lines to .gitignore" 'it adds two lines to .\.gitignore., .\.vercel. and .\.env\*., and the kit keeps both'
rs_rule "the .env* line is named as hiding .env.example" 'the .\.env\*. line also matches .\.env\.example., which the repository needs'
rs_rule "the kit looks for .env.example being hidden" 'after linking, the kit runs .git check-ignore --no-index -v \.env\.example.'
rs_rule "the kit lets .env.example back in" 'the kit adds .!\.env\.example. on the line below it'
rs_rule "the fix is checked with the form that names nothing" '.git check-ignore --no-index \.env\.example. names nothing and exits with status 1'
rs_rule "the local run of the fix is recorded" 'secrets, local run: on 2026-09-25 the .\.env\.example. step was run on this computer'
rs_rule "linking writes a token into .env.local" 'it also writes .vercel_oidc_token., a short-lived token that lets this machine reach vercel as the project, into .\.env\.local.'
rs_rule "both files are checked as ignored" '.git check-ignore \.vercel \.env\.local. names both'
rs_rule "production values are never pulled" 'never runs .vercel env pull. for production'
rs_rule "the secrets check reads names only" 'lists every name in .\.env\.example. and no value'
rs_rule "no public name carries a secret" 'no name that starts with .next_public_. contains .service_role. or .secret.'

# Logs.
rs_rule "errors are read from production, on every branch" 'vercel logs --environment production --level error --since 1h --no-branch --json. prints one json object'
rs_rule "the log command reads one branch unless told" 'reads only the current [a-z]+ branch unless told otherwise, so the kit passes .--no-branch.'
rs_rule "Hobby keeps runtime logs for an hour" 'the hobby plan keeps runtime logs for one hour'
rs_rule "an error from the new build is named" 'names to the person any error from the new build'

# Health, and the container Vercel ignores. The project keeps the same
# Dockerfile as on a host that runs containers, so the local check matches
# production and moving host later changes nothing else.
rs_rule "the build stack carries a dockerfile vercel ignores" 'with a dockerfile that vercel ignores'
rs_rule "the local container answers before the merge" 'before the merge, the kit runs the local container check from the health part'
rs_rule "the commit comes from the build" 'the health route reports the commit from .vercel_git_commit_sha.'
rs_rule "health links the shared part" '## health shared part: \[the next\.js container and its health route\]\(parts/nextjs-container\.md\)'
rs_guard "$RR_RECIPE" "the Vercel recipe"

# Who runs each check. Only the preview is left to a person, because Vercel
# puts a sign-in in front of it; every other check the kit can run itself.
rr_who=$(sed -n 's/^Who runs it: //p' "$RR_RECIPE" | sort | uniq -c | tr -s ' ' | sed 's/^ //')
rs_report "the preview is the one check a person looks at, and the kit runs the rest" \
  "$([ "$rr_who" = "$(printf '1 a person looking\n4 the kit')" ] && echo yes || echo no)"

rr_guard_container_part
rr_guard_supabase_parts
rr_stand_ins
rs_done
