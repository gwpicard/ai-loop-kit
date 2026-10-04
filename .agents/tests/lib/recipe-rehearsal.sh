#!/usr/bin/env sh
# recipe-rehearsal.sh: what the rehearsal of each recipe shares.
#
# Source it after rule-shape.sh. It gives a recipe rehearsal three things.
#
# 1. Where the recipe is. A recipe joins the menu, ship/recipes/, only after
#    its real run is recorded, and there is no draft state. Until then it waits
#    in .agents/tests/recipes-awaiting-run/, which ships nowhere. rr_locate
#    finds it in one place or the other and refuses it in both.
#
# 2. Its shape. On the menu it must pass the shipped shape check outright.
#    Waiting, it must fail that check on its real run and on nothing else, so a
#    recipe is never waiting on anything but the run.
#
# 3. Its commands, run against stand-ins. Every command a recipe or a part it
#    links writes in backticks, whose first word is one of the recipe's
#    command-line tools, is run against a stand-in that answers only the
#    subcommands and options those tools document. A mistyped option or an
#    invented subcommand is refused, which is the mistake a recipe read by eye
#    lets through. The stand-ins reach no network and no account. Each tool the
#    recipe names must be used by at least one command, so the tooling check
#    never asks a person to install something nothing runs.
#
# The three Supabase parts are guarded here too, once for every recipe that
# links them, by rr_guard_supabase_parts. The third is the settings the launch
# review reads with the public key before it asks the person about them.

RR_CHECKER="$ROOT/.agents/tools/check-recipes.sh"
RR_MENU="$ROOT/.agents/skills/ship/recipes"
RR_WAITING="$ROOT/.agents/tests/recipes-awaiting-run"
RR_PARTS="$ROOT/.agents/skills/ship/recipes/parts"

rr_locate() {
  # rr_locate <menu path of the recipe>: sets RR_RECIPE and RR_ON_MENU.
  rr_name=$(basename -- "$1")
  if [ -f "$1" ] && [ -f "$RR_WAITING/$rr_name" ]; then
    rs_fail "$rr_name is on the menu and still waiting for its real run; one copy has to go"
  fi
  if [ -f "$1" ]; then
    RR_RECIPE=$1
    RR_ON_MENU=yes
  elif [ -f "$RR_WAITING/$rr_name" ]; then
    RR_RECIPE="$RR_WAITING/$rr_name"
    RR_ON_MENU=no
  else
    rs_fail "$rr_name is neither on the menu nor waiting for its real run"
  fi
}

rr_shape() {
  [ -z "${RS_LIST:-}" ] || return 0
  if [ "$RR_ON_MENU" = yes ]; then
    "$RR_CHECKER" "$RR_RECIPE" >&2 ||
      rs_fail "$rr_name is on the menu without the shape the format asks for"
    rs_ok "$rr_name is on the menu with its real run recorded"
    return 0
  fi
  if rr_out=$("$RR_CHECKER" "$RR_RECIPE" 2>&1); then
    rs_fail "$rr_name passed the shape check while waiting, so a real run is recorded and it belongs on the menu"
  fi
  rr_want="$RR_RECIPE: Real run is not a real date written YYYY-MM-DD: awaiting the first real run"
  if [ "$rr_out" != "$rr_want" ]; then
    printf '%s\n' "$rr_out" >&2
    rs_fail "$rr_name is waiting on something besides its real run"
  fi
  rs_ok "$rr_name has every part the format asks for and waits only on its real run"
}

# --- the stand-ins ---------------------------------------------------------

rr_write_stand_ins() {
  # rr_write_stand_ins <bin>: one stand-in per tool. Each writes what it was
  # asked to a log and refuses anything outside the documented surface.
  mkdir -p "$1"
  cat > "$1/vercel" <<'SH'
#!/usr/bin/env sh
echo "vercel $*" >> "$RR_CALLS"
refuse() { echo "vercel stand-in: not a documented command: vercel $*" >&2; exit 64; }
# One deployment, given as an address or an id, and only the options the
# command documents. A misspelt option is refused rather than taken for the
# deployment.
one_deployment() {
  command=$1
  shift
  target=""
  while [ "$#" -gt 0 ]; do
    case "$command $1" in
      "inspect --logs"|"inspect --wait"|"promote --yes"|"rollback --yes") shift ;;
      "inspect --timeout"|"promote --timeout"|"rollback --timeout")
        [ -n "${2:-}" ] || refuse "$command" "$@"; shift 2 ;;
      "$command -"*) refuse "$command" "$@" ;;
      *) [ -z "$target" ] || refuse "$command" "$@"; target=$1; shift ;;
    esac
  done
  [ -n "$target" ] || refuse "$command"
}
case "$1" in
  inspect) one_deployment "$@"; echo "status  Ready" ;;
  promote|rollback) one_deployment "$@" ;;
  curl)
    # A path, then only the options vercel curl documents. It is marked beta,
    # and it answers a protected deployment through a bypass token.
    shift
    path=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --yes|-y|--json|--trace) shift ;;
        --deployment|--protection-bypass) [ -n "${2:-}" ] || refuse curl "$@"; shift 2 ;;
        -*) refuse curl "$@" ;;
        *) [ -z "$path" ] || refuse curl "$@"; path=$1; shift ;;
      esac
    done
    [ -n "$path" ] || refuse curl
    echo '{"status":"ok","database":"ok"}' ;;
  project)
    # Only the options vercel project documents: add takes a name and no
    # option, and update takes one name and the settings it lists.
    case "${2:-}" in
      add) [ "$#" -eq 3 ] && case "$3" in -*) false ;; *) true ;; esac || refuse "$@" ;;
      update)
        shift 2
        name=""
        while [ "$#" -gt 0 ]; do
          case "$1" in
            --yes|-y|--json) shift ;;
            --framework|--build-command|--install-command|--output-directory|--root-directory|--node-version)
              [ -n "${2:-}" ] || refuse project update "$@"; shift 2 ;;
            -*) refuse project update "$@" ;;
            *) [ -z "$name" ] || refuse project update "$@"; name=$1; shift ;;
          esac
        done ;;
      *) refuse "$@" ;;
    esac ;;
  link)
    shift
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --yes|-y) shift ;;
        --project|-p|--team) [ -n "${2:-}" ] || refuse link "$@"; shift 2 ;;
        *) refuse link "$@" ;;
      esac
    done ;;
  git)
    case "${2:-}" in
      connect)
        shift 2
        while [ "$#" -gt 0 ]; do
          case "$1" in
            --yes|-y|--confirm) shift ;;
            --project) [ -n "${2:-}" ] || refuse git connect "$@"; shift 2 ;;
            *) refuse git connect "$@" ;;
          esac
        done ;;
      *) refuse "$@" ;;
    esac ;;
  env)
    case "$2 ${3:-} ${4:-}" in
      "ls  "|"ls production "|"ls preview "|"pull  ") ;;
      "add "*" production"|"add "*" preview"|"add "*" production "*|"add "*" preview "*)
        # A name, an environment, then only documented options. The value
        # arrives on standard input, never as an argument.
        name=$3 environment=$4
        shift 4
        case "$name" in -*) refuse env add "$name" ;; esac
        while [ "$#" -gt 0 ]; do
          case "$1" in
            --yes|--sensitive|--no-sensitive|--force) shift ;;
            --type) case "${2:-}" in config|sensitive|encrypted|plain) shift 2 ;; *) refuse env add "$name" "$environment" "$@" ;; esac ;;
            *) refuse env add "$name" "$environment" "$@" ;;
          esac
        done ;;
      *) refuse "$@" ;;
    esac ;;
  logs)
    shift
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --environment) case "${2:-}" in production|preview) shift 2 ;; *) refuse logs "$@" ;; esac ;;
        --level) case "${2:-}" in error|warning|info|fatal) shift 2 ;; *) refuse logs "$@" ;; esac ;;
        --since|--until|--limit|--deployment|--query|--branch) [ -n "${2:-}" ] || refuse logs "$@"; shift 2 ;;
        --json|--expand|--follow|--no-branch) shift ;;
        *) refuse logs "$@" ;;
      esac
    done ;;
  *) refuse "$@" ;;
esac
SH
  cat > "$1/supabase" <<'SH'
#!/usr/bin/env sh
echo "supabase $*" >> "$RR_CALLS"
refuse() { echo "supabase stand-in: not a documented command: supabase $*" >&2; exit 64; }
case "$*" in
  "init"|"start"|"stop"|"stop --no-backup"|"link"|"db push"|"db push --dry-run") ;;
  "link --project-ref "*) [ "$#" -eq 3 ] || refuse "$@" ;;
  "db dump"*)
    shift 2
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --linked|--local|--role-only|--data-only|--use-copy|--dry-run) shift ;;
        -f|--file|-s|--schema|-x|--exclude|-p|--password) [ -n "${2:-}" ] || refuse db dump "$@"; shift 2 ;;
        *) refuse db dump "$@" ;;
      esac
    done ;;
  *) refuse "$@" ;;
esac
SH
  cat > "$1/psql" <<'SH'
#!/usr/bin/env sh
echo "psql $*" >> "$RR_CALLS"
refuse() { echo "psql stand-in: not an option psql has: $*" >&2; exit 64; }
while [ "$#" -gt 0 ]; do
  case "$1" in
    --single-transaction|--tuples-only) shift ;;
    --variable|--file|--command|--dbname) [ -n "${2:-}" ] || refuse "$@"; shift 2 ;;
    *) refuse "$@" ;;
  esac
done
SH
  cat > "$1/curl" <<'SH'
#!/usr/bin/env sh
echo "curl $*" >> "$RR_CALLS"
refuse() { echo "curl stand-in: not an address or option a recipe may use: $*" >&2; exit 64; }
url=""
headers=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -fsS) shift ;;
    -H) [ -n "${2:-}" ] || refuse "$@"; headers="$headers|$2"; shift 2 ;;
    https://*|http://localhost:3000/*) url=$1; shift ;;
    *) refuse "$@" ;;
  esac
done
case "$url" in
  https://api.supabase.com/v1/projects/*/database/backups) echo '{"backups":[]}' ;;
  https://api.supabase.com/v1/projects/*/advisors/security) echo '{"lints":[]}' ;;
  # The sign-in settings answer to the public key alone, sent as apikey. A
  # bearer token is how a secret key or a signed-in session would be sent, and
  # a settings read must never carry one. The run gives each secret key a value
  # of its own, so a read sending one as apikey is refused by what it sent.
  https://*.supabase.co/auth/v1/settings)
    case "$headers" in "|apikey: "?*) ;; *) refuse "$url" "headers$headers" ;; esac
    case "$headers" in *"|apikey: "*"|"*) refuse "$url" "headers$headers" ;; esac
    case "$headers" in *service-role-stand-in*|*secret-stand-in*) refuse "$url" "a secret key sent as apikey" ;; esac
    echo '{"external":{"email":true},"disable_signup":false,"mailer_autoconfirm":false}' ;;
  https://*/api/health|http://localhost:3000/api/health) echo '{"status":"ok","database":"ok"}' ;;
  *) refuse "$url" ;;
esac
SH
  cat > "$1/docker" <<'SH'
#!/usr/bin/env sh
echo "docker $*" >> "$RR_CALLS"
case "$*" in
  "info"|"build ."|"build -t "*" .") ;;
  "run -d --name "*" -p 3000:3000 --env-file .env.container "*) [ "$#" -eq 9 ] || { echo "docker stand-in: not a command a recipe may use: docker $*" >&2; exit 64; } ;;
  "rm -f "*) [ "$#" -eq 3 ] || { echo "docker stand-in: not a command a recipe may use: docker $*" >&2; exit 64; } ;;
  *) echo "docker stand-in: not a command a recipe may use: docker $*" >&2; exit 64 ;;
esac
SH
  cat > "$1/git" <<'SH'
#!/usr/bin/env sh
echo "git $*" >> "$RR_CALLS"
case "$*" in
  "rev-parse origin/main") echo 0000000 ;;
  "check-ignore supabase/.temp") echo supabase/.temp ;;
  "check-ignore .vercel .env.local") printf '.vercel\n.env.local\n' ;;
  # Right after vercel link, before the kit lets the file back in.
  "check-ignore --no-index -v .env.example") printf '.gitignore:10:.env*\t.env.example\n' ;;
  # Once the kit has let it back in: nothing named, and status 1, which is how
  # git check-ignore says no path is ignored.
  "check-ignore --no-index .env.example") exit 1 ;;
  "add .env.example") ;;
  *) echo "git stand-in: not a command a recipe may use: git $*" >&2; exit 64 ;;
esac
SH
  cat > "$1/npx" <<'SH'
#!/usr/bin/env sh
echo "npx $*" >> "$RR_CALLS"
case "$*" in
  "next build"|"next start") ;;
  *) echo "npx stand-in: not a command a recipe may use: npx $*" >&2; exit 64 ;;
esac
SH
  chmod +x "$1/vercel" "$1/supabase" "$1/psql" "$1/curl" "$1/docker" "$1/git" "$1/npx"
}

rr_tools() {
  # rr_tools <recipe>: the command-line tools it names, one to a line.
  sed -n 's/^Command-line tools: //p' "$1" | tr ',' '\n' | sed 's/^ *//; s/ *$//' | grep -v '^none$' || true
}

rr_commands() {
  # rr_commands <recipe>: every backticked command in the recipe and the parts
  # it links whose first word is one of its tools, placeholders filled in.
  rr_dir=$(dirname -- "$1")
  rr_files=$1
  for rr_part in $(sed -n 's/^Shared part: .*](\(parts\/[^)]*\)).*/\1/p' "$1"); do
    rr_files="$rr_files $rr_dir/$rr_part"
  done
  rr_tools "$1" > "$rs_dir/tools"
  # shellcheck disable=SC2086
  awk '
    NR == FNR { tool[$0] = 1; next }
    {
      rest = $0
      while (match(rest, /`[^`]+`/)) {
        span = substr(rest, RSTART + 1, RLENGTH - 2)
        rest = substr(rest, RSTART + RLENGTH)
        # A tool named on its own, such as `curl`, is a mention, not a command.
        if (split(span, word, " ") < 2) continue
        # A value piped in with printf counts when the command it feeds is one
        # of the tools, since that is how a recipe keeps a value off the
        # command line.
        first = word[1]
        if (first == "printf" && split(span, piece, "[|] ") == 2) { split(piece[2], word, " "); first = word[1] }
        if (first in tool) { gsub(/<[^>]*>/, "stand-in", span); print span }
      }
    }
  ' "$rs_dir/tools" $rr_files
}

rr_run_commands() {
  # rr_run_commands <recipe>: 0 when every command is accepted and every tool
  # is used; otherwise names what went wrong and returns 1.
  RR_CALLS="$rs_dir/calls"
  export RR_CALLS
  : > "$RR_CALLS"
  rr_write_stand_ins "$rs_dir/bin"
  mkdir -p "$rs_dir/work"
  rr_status=0
  rr_commands "$1" > "$rs_dir/commands"
  [ -s "$rs_dir/commands" ] || { echo "  no command in the recipe uses one of its tools"; return 1; }
  while IFS= read -r rr_cmd; do
    rr_exit=0
    (cd "$rs_dir/work" && PATH="$rs_dir/bin:$PATH" SUPABASE_ACCESS_TOKEN=stand-in SUPABASE_DB_URL=stand-in VALUE=stand-in \
      NEXT_PUBLIC_SUPABASE_ANON_KEY=public-stand-in SUPABASE_SERVICE_ROLE_KEY=service-role-stand-in \
      SUPABASE_SECRET_KEY=secret-stand-in sh -c "$rr_cmd") >/dev/null 2>"$rs_dir/refusal" || rr_exit=$?
    # git check-ignore answers status 1 when no path is ignored, which is the
    # answer a recipe's check can ask for. Every other command must succeed.
    case "$rr_exit $rr_cmd" in "1 git check-ignore "*) rr_exit=0 ;; esac
    if [ "$rr_exit" -ne 0 ]; then
      echo "  refused: $rr_cmd"
      sed 's/^/    /' "$rs_dir/refusal"
      rr_status=1
    fi
  done < "$rs_dir/commands"
  while IFS= read -r rr_tool; do
    grep -q "^$rr_tool " "$RR_CALLS" || grep -qx "$rr_tool" "$RR_CALLS" || {
      echo "  the recipe names $rr_tool, and no command it writes uses it"
      rr_status=1
    }
  done < "$rs_dir/tools"
  return $rr_status
}

rr_stand_ins() {
  # rr_stand_ins: run the recipe's commands, then prove the run notices an
  # invented subcommand and a named tool that nothing uses.
  [ -z "${RS_LIST:-}" ] || return 0
  if ! rr_run_commands "$RR_RECIPE"; then
    rs_fail "$rr_name writes a command its tools do not have"
  fi
  rr_count=$(wc -l < "$rs_dir/commands" | tr -d ' ')
  rs_ok "every one of the $rr_count commands $rr_name writes is one its tools document"

  mkdir -p "$rs_dir/copy"
  ln -s "$RR_PARTS" "$rs_dir/copy/parts"
  awk '!done && sub(/`supabase db push`/, "`supabase db advisors --type security`") { done = 1 } { print }' \
    "$RR_RECIPE" > "$rs_dir/copy/$rr_name"
  cmp -s "$RR_RECIPE" "$rs_dir/copy/$rr_name" && rs_fail "the invented-command copy changed nothing"
  rr_run_commands "$rs_dir/copy/$rr_name" >/dev/null &&
    rs_fail "a copy writing a subcommand nobody documents was not refused"
  rs_ok "a copy writing a subcommand nobody documents is refused"

  sed 's/^Command-line tools: .*/&, flyctl/' "$RR_RECIPE" > "$rs_dir/copy/$rr_name"
  rr_run_commands "$rs_dir/copy/$rr_name" >/dev/null &&
    rs_fail "a copy naming a tool no command uses was not refused"
  rs_ok "a copy naming a tool no command uses is refused"

  # A misspelt option must fail rather than be taken for the deployment, and
  # the options each command documents must still pass. vercel project add
  # documents no framework option, so a recipe that sets the framework there
  # is refused and has to use project update.
  for rr_probe in "rollback --timout 5m stand-in" "inspect --wiat stand-in" "promote --yse stand-in" \
    "rollback" "inspect one two" "project add stand-in --framework nextjs" \
    "project update stand-in --framwork nextjs" "link --projet stand-in" "git connect --yse" \
    "curl" "curl /api/health --deploymnet stand-in" "curl /api/health --deployment"; do
    # shellcheck disable=SC2086
    if PATH="$rs_dir/bin:$PATH" vercel $rr_probe >/dev/null 2>&1; then
      rs_fail "the vercel stand-in accepted 'vercel $rr_probe'"
    fi
  done
  for rr_probe in "rollback --timeout 5m stand-in" "inspect --wait stand-in" "promote --yes stand-in" \
    "project update stand-in --framework nextjs --yes" "link --project stand-in --yes" "git connect --yes" \
    "curl /api/health --deployment stand-in --yes"; do
    # shellcheck disable=SC2086
    PATH="$rs_dir/bin:$PATH" vercel $rr_probe >/dev/null 2>&1 ||
      rs_fail "the vercel stand-in refused 'vercel $rr_probe'"
  done
  rs_ok "the vercel stand-in refuses a misspelt option and keeps the documented ones"

  # The settings read goes out with the public key alone. Without it, with a
  # bearer token beside it, or at an address the service does not answer in
  # public, the stand-in refuses.
  rr_settings=https://stand-in.supabase.co/auth/v1/settings
  PATH="$rs_dir/bin:$PATH" curl -fsS -H "apikey: stand-in" "$rr_settings" >/dev/null 2>&1 ||
    rs_fail "the curl stand-in refused the settings read with the public key"
  for rr_probe in "" "Authorization: Bearer stand-in"; do
    if [ -z "$rr_probe" ]; then
      set -- curl -fsS "$rr_settings"
    else
      set -- curl -fsS -H "apikey: stand-in" -H "$rr_probe" "$rr_settings"
    fi
    if PATH="$rs_dir/bin:$PATH" "$@" >/dev/null 2>&1; then
      rs_fail "the curl stand-in accepted a settings read '$*'"
    fi
  done
  if PATH="$rs_dir/bin:$PATH" curl -fsS -H "apikey: stand-in" https://stand-in.supabase.co/auth/v1/admin/users >/dev/null 2>&1; then
    rs_fail "the curl stand-in accepted a read of the admin address"
  fi
  rs_ok "the curl stand-in answers the settings read with the public key alone"

  # And a recipe whose settings read carried a secret instead is refused as a
  # whole, which proves the read is among the commands the run tries.
  if grep -qF 'parts/supabase-settings.md' "$RR_RECIPE"; then
    mkdir -p "$rs_dir/secret/parts"
    cp "$RR_PARTS"/*.md "$rs_dir/secret/parts/"
    cp "$RR_RECIPE" "$rs_dir/secret/$rr_name"
    for rr_secret in SUPABASE_SERVICE_ROLE_KEY SUPABASE_SECRET_KEY; do
      sed "s#apikey: \$NEXT_PUBLIC_SUPABASE_ANON_KEY#apikey: \$$rr_secret#" \
        "$RR_PARTS/supabase-settings.md" > "$rs_dir/secret/parts/supabase-settings.md"
      cmp -s "$RR_PARTS/supabase-settings.md" "$rs_dir/secret/parts/supabase-settings.md" &&
        rs_fail "the secret-key copy of the settings part changed nothing"
      rr_run_commands "$rs_dir/secret/$rr_name" >/dev/null &&
        rs_fail "a settings read sending $rr_secret was not refused"
    done
    rs_ok "a settings read sending the service role key or a secret key is refused"
  fi
}

# --- the Supabase parts ------------------------------------------------------

rr_guard_container_part() {
  # The Dockerfile and the health route every Next.js recipe shares, whichever
  # host runs the app, so the two recipes cannot drift apart on them.
  rs_reset
  rs_rule "the project always carries the same dockerfile" 'the project always carries the same dockerfile'
  rs_rule "a host that ignores it still gets a matching local check" 'it gives a local check that matches production'
  rs_rule "it keeps a way off the host" 'moving to a host that runs containers changes the host and nothing else'
  rs_rule "Next.js builds standalone" 'output: "standalone"'
  rs_rule "the server listens on every address" 'hostname=0\.0\.0\.0. and .port=3000.'
  rs_rule "the image carries wget" 'starts from a node alpine image, which carries .wget.'
  rs_rule "a slim image has neither tool" 'a .node:\*-slim. image has neither'
  rs_rule "one check on one route" 'it carries no .healthcheck. line: on a host that runs its own health check, such a line takes precedence over the host.s settings'
  rs_rule "the health route makes a real round trip" 'makes one real round trip to the database'
  rs_rule "it is never answered from a build-time copy" 'export const dynamic = "force-dynamic"'
  rs_rule "public variables are fixed at build" 'next\.js fixes public variables when it builds'
  rs_rule "the image answers locally before anything goes live" 'before anything goes live, the kit checks docker is running'
  rs_rule "the local answer is read" 'curl -fss http://localhost:3000/api/health.: 200, ."database":"ok".'
  rs_rule "a dead database gives 503" 'the same route answers 503 rather than claiming the tool is up'
  rs_rule "the container gets its own env file" 'the container gets its values from .\.env\.container., a file git ignores that holds only the names in .\.env\.example.'
  rs_rule "it never gets the local env file" 'it never gets .\.env\.local., because other tools write their own tokens there'
  rs_rule "the container file holds no stray name" '.\.env\.container. holds no name missing from .\.env\.example., its values never leave the machine'
  rs_guard "$RR_PARTS/nextjs-container.md" "the container part"
}

rr_guard_supabase_parts() {
  rs_reset
  rs_rule "Free takes no backup of its own" 'the free plan takes none'
  rs_rule "on Free the kit takes its own after each launch" 'on free the kit takes its own after each launch'
  rs_rule "the data is dumped with copy statements" 'supabase db dump --linked --data-only --use-copy -x storage\.buckets_vectors -x storage\.vector_indexes -f data\.sql'
  rs_rule "a dump needs the database password" 'from .supabase_db_password., from .-p., or from what .supabase link. stored'
  rs_rule "the password is never shown" 'never writes the password into a command it shows'
  rs_rule "point-in-time recovery hides the daily backups" 'with point-in-time recovery switched on, the listing shows no daily backups at all'
  rs_rule "the dump is kept outside the repository" 'into a dated folder outside the repository'
  rs_rule "the gap in a daily backup is named once" 'holds neither the passwords of custom roles nor the files in storage'
  rs_rule "a paid plan's backups are listed" 'api\.supabase\.com/v1/projects/<project ref>/database/backups. lists a backup taken in the last day'
  rs_rule "the access token is never printed" 'the kit never prints it or writes it down'
  rs_guard "$RR_PARTS/supabase-backup.md" "the backup part"

  rs_reset
  rs_rule "the restore test never touches the live database" 'the restore test never touches the live database'
  rs_rule "roles, schema and data are dumped" 'with .--role-only. into .roles\.sql., with no option into .schema\.sql., and with'
  rs_rule "the data dump leaves out the same tables" 'with .--data-only --use-copy -x storage\.buckets_vectors -x storage\.vector_indexes. into .data\.sql.'
  rs_rule "the project's own local database is stopped" 'stops the project.s own local database with .supabase stop., since the restore uses the same ports'
  rs_rule "it restores into an empty local database" 'in a throwaway folder outside the project it runs .supabase init.'
  rs_rule "the local services match live" 'copies the linked project.s .supabase/\.temp/\*-version. files into the throwaway folder.s .supabase/\.temp/., so the local services run the same versions as the live project'
  rs_rule "the whole stack starts" 'runs .supabase start. with the full stack, leaving no service out, because the auth and storage tables come from those services'
  rs_rule "the files load as supabase_admin" 'loads the three files as .supabase_admin. with .psql .*postgresql://supabase_admin:postgres.127\.0\.0\.1:54322/postgres., because .roles\.sql. grants settings the local .postgres. user may not grant'
  rs_rule "the project's migrations and seed stay out" 'would load its migrations, which clash with .schema\.sql., and its .supabase/seed\.sql., whose rows would be counted as restored'
  rs_rule "the load stops on the first error" 'psql --single-transaction --variable on_error_stop=1'
  rs_rule "triggers stay off while the data loads" 'set session_replication_role = replica'
  rs_rule "the restore time is written down" 'written down as the restore time'
  rs_rule "the rows are counted table by table" 'equals .select count\(\*\). on that table in the local database'
  rs_rule "a restore that loads nothing fails" 'at least one table holds rows'
  rs_rule "the local copy is removed" '.supabase stop --no-backup. in the throwaway folder removes the local copy'
  rs_guard "$RR_PARTS/supabase-restore.md" "the restore part"

  # The part the launch review reads before it asks the person about a
  # sign-in setting. A real run asked the person to open the dashboard for
  # "Confirm email", which this address answers to the public key.
  rs_reset
  rs_rule "the review reads before it asks" 'the launch review reads these settings itself before it asks the person about any of them'
  rs_rule "the settings answer to the public key" 'supabase answers a project.s sign-in settings to anyone holding its public key, which the tool already sends to the browser'
  rs_rule "the read is the settings address with the public key as apikey" 'curl -fss -h "apikey: \$next_public_supabase_anon_key" https://<project ref>\.supabase\.co/auth/v1/settings'
  rs_rule "the key comes from the project's own files" 'with .next_public_supabase_anon_key. taken from the project.s own .\.env\.local.'
  rs_rule "false means confirm email is on" '.false. means the dashboard.s "confirm email" setting is on, and .true. means it is off'
  rs_rule "the public key and nothing else" 'the kit sends the public key for this read and nothing else'
  rs_rule "a secret key is never sent" 'it never sends the service role key or a secret key, whatever the variable holding it is called'
  rs_rule "the redirect list is not in the answer" 'the list of addresses sign-in may send a person back to is not in this answer'
  rs_rule "the person is asked for the redirect list, and told why" 'so the kit asks the person to look at that list, and says that the public key cannot read it'
  rs_rule "no setting in the answer is asked about" 'asks the person about no setting this answer holds'
  rs_rule "the kit runs the read" 'who runs it: the kit'
  rs_guard "$RR_PARTS/supabase-settings.md" "the settings part"

  rs_reset
  rs_rule "the recipe links the settings part after health" '## settings the kit can read shared part: \[sign-in settings on hosted supabase\]\(parts/supabase-settings\.md\) ## proven'
  rs_guard "$RR_RECIPE" "$rr_name's settings section"
}
