#!/usr/bin/env sh
# recipe-nextjs-supabase-on-coolify.sh: guard the recipe for Next.js and hosted
# Supabase on Coolify, offline.
#
# On this pair the app runs on a server the kit never contacts. So the rule
# held hardest is who runs each check: every check that needs the server is run
# by the hosting companion or the person, and the kit reads back what they
# paste. A section that slid back to "the kit" would have the kit reaching for
# a server it has promised never to touch. The data half is the same hosted
# Supabase as the Vercel recipe, and the kit runs those checks itself.
#
# The image that makes the app hostable at all, a standalone Next.js build
# bound to 0.0.0.0 on an image that carries wget, is the shared container part,
# which the Vercel recipe uses too. This check holds what is Coolify's own: the
# health check switched on, and the two hosting request fields, Build and Bind.
#
# It runs every command the recipe writes against stand-ins for its tools. The
# real run is recorded, so the recipe is on the menu and must pass the shape
# check outright. The recipe file is recipes/nextjs-supabase-on-coolify.md.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"
. "$ROOT/.agents/tests/lib/recipe-rehearsal.sh"

rs_init "Next.js and Supabase on Coolify recipe"
rr_locate "$ROOT/.agents/skills/ship/recipes/nextjs-supabase-on-coolify.md"
rr_shape

# Preview.
rs_rule "each pull request gets its own preview" 'coolify builds each pull request into its own container on the pull request.s commit'
rs_rule "previews start off on a new app" 'previews start off on every new app'
rs_rule "the person switches previews on" 'switches them on with enable preview deployments on the app.s preview deployments page'
rs_rule "the companion's tools cannot set it" 'the companion.s own tools cannot set it'
rs_rule "a preview has an address only with a domain" 'a preview has an address only when the app has a domain: coolify fills its preview template, by default .\{\{pr_id\}\}\.\{\{domain\}\}., from that domain'
rs_rule "a preview nobody can open is a warning" 'the kit says once that the person cannot open the preview, as a warning, and does not wait for an address'
rs_rule "without a second project, previews get no migrations" 'gives a preview no migrations, since they would change the live database before the merge'
rs_rule "a preview needing a migration is warned about" 'a preview whose code needs a new migration then fails against the live database, and the warning says so'
rs_rule "the preview database gets the branch's migrations" 'before each preview, the kit gives that project the branch.s migrations with .supabase link --project-ref <preview project ref>. and .supabase db push.'
rs_rule "previews never reach the live database" 'a second supabase project kept for previews, unless no second project can exist'
rs_rule "the kit never contacts the server" 'the kit never contacts the server, so the person or the hosting companion reads the preview'
rs_rule "the preview answers from its own project" 'a .project. that is not the live project.s reference'

# Going live.
rs_rule "the kit links back to live before going live" 'the kit links back to the live project with .supabase link --project-ref <live project ref>.'
rs_rule "migrations run before the build that needs them" 'applies new migrations to the live database before the build that needs them, because coolify does not run them'
rs_rule "a migration in a release only adds" 'a migration in a release only adds'
rs_rule "the kit lists tables with row-level security off" 'select tablename from pg_tables where schemaname = .public. and not rowsecurity;'
rs_rule "the connection string is the session pooler, built in the shell" '.supabase_db_url. is the session pooler address from .supabase/\.temp/pooler-url. with the database password added, built in the person.s shell, and the kit never shows it'
rs_rule "the query passes on no rows" 'the row-level security query returns no rows, or each table it returns is on the record'
rs_rule "the advisor is only a second read" 'is an optional second read, since that endpoint is marked experimental'
rs_rule "the local container answers before the merge" 'before the merge, the kit runs the local container check from the health part, so an image that fails to build, bind or answer is found on the person.s machine'
rs_rule "a rolling update needs no host port and no custom name" 'a rolling update cannot happen when the app publishes a port on the host or has a custom container name'
rs_rule "the new container waits for its health check" 'swaps the new container in once its health check passes'
rs_rule "the request says how it builds" 'build: dockerfile at root, image has curl or wget'
rs_rule "the request says it binds to every address" 'bind: 0\.0\.0\.0'
rs_rule "the live commit is the one on main" 'a .commit. equal to .git rev-parse origin/main.'

# Rollback.
rs_rule "two images survive the nightly cleanup" 'until its nightly cleanup, which leaves the two newest by default'
rs_rule "cleanup can remove the image a rollback needs" 'the cleanup of unused images can remove the one a rollback needs'
rs_rule "the rollback is a click on the rollback page" 'the rollback is always a click on that page'
rs_rule "the earlier image is confirmed first" 'confirms the earlier image is still listed in coolify'
rs_rule "a rollback reuses a kept image" 'coolify reuses the kept image, with no new build'
rs_rule "a rollback leaves migrations alone" 'a rollback does not undo database migrations'
rs_rule "the rollback is read back from the health route" 'is the earlier commit rather than the one rolled back'

# Backup and restore come from the shared parts.
rs_rule "backup links the shared part" '## backup shared part: \[backup on hosted supabase\]\(parts/supabase-backup\.md\)'
rs_rule "restore links the shared part" '## restore shared part: \[restore on hosted supabase\]\(parts/supabase-restore\.md\)'

# Secrets.
rs_rule "the request carries names and never a value" 'the hosting request carries the names of the environment variables and never a value'
rs_rule "the service role key never reaches the browser" 'the service role key stays on the server and never carries that prefix'
rs_rule "supabase/.temp is kept out of the repository" '.supabase init. does not add .supabase/\.temp. to .\.gitignore., and that folder holds the project reference and the pooler address, so the kit adds it before the first commit'
rs_rule "the pasted list carries names only" 'pastes back the list of names set in coolify, with no values'
rs_rule "no public name carries a secret" 'no name that starts with .next_public_. contains .service_role. or .secret.'

# Logs.
rs_rule "the kit cannot read the server's logs" 'the kit cannot read it, since it never contacts the server'
rs_rule "an error from the new build is named" 'names to the person any error from the new build'
rs_rule "coolify's own build lines are not the tool's errors" 'those are not the tool.s errors'

# Health comes from the shared container part. What is Coolify's own is the
# health check setting, which is off until somebody switches it on.
rs_rule "health links the shared part" '## health shared part: \[the next\.js container and its health route\]\(parts/nextjs-container\.md\)'
rs_rule "the health check is off until switched on" 'coolify.s health check is off by default'
rs_rule "it is switched on for the route, port and host" 'with path ./api/health., port 3000 and host .127\.0\.0\.1.'
rs_rule "coolify's setting is the only check" 'the image carries no .healthcheck. line, as the health part says, so coolify.s setting is the only check'
rs_rule "the settings are read back" 'the check switched on for ./api/health. on port 3000 and host .127\.0\.0\.1., healthy'
rs_rule "the commit comes from the server" 'the health route reports the commit from .source_commit.'
rs_guard "$RR_RECIPE" "the Coolify recipe"

# Who runs each check. The kit never contacts the server, so every section
# written in this recipe is run by the companion or the person and read back.
# The three parts are the kit's: two reach Supabase, and the container check
# runs on the person's own machine.
rr_who=$(sed -n 's/^Who runs it: //p' "$RR_RECIPE" | sort -u)
rs_report "every check this recipe writes is run by the companion or the person and read back" \
  "$([ "$rr_who" = "a companion or the person, result read back" ] && echo yes || echo no)"
rr_count=$(grep -c '^Who runs it: ' "$RR_RECIPE" || true)
rs_report "all five sections that need the server say so" "$([ "$rr_count" -eq 5 ] && echo yes || echo no)"
awk '!done && /^Who runs it: / { print "Who runs it: the kit"; done = 1; next } { print }' "$RR_RECIPE" > "$rs_dir/kit-runs-it.md"
rr_who=$(sed -n 's/^Who runs it: //p' "$rs_dir/kit-runs-it.md" | sort -u)
rs_report "a copy where the kit runs a server check is caught" \
  "$([ "$rr_who" != "a companion or the person, result read back" ] && echo yes || echo no)"

rr_guard_container_part
rr_guard_supabase_parts
rr_stand_ins
rs_done
