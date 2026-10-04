# _common.sh: what the shell stand-ins in this folder share.
#
# stand_in_or_real <name> "$@" decides who answers the call.
#
# - FAKE_HOST_STATE not set at all: the run is not one of the scenarios this
#   folder serves, so the real command answers.
# - FAKE_HOST_STATE set, its file missing: a replay whose preparation failed.
#   The real command may be signed in to somebody's account, so it never
#   answers. The call is answered as a tool signed in to nothing, and only
#   --version and --help succeed.
# - Otherwise it logs the call, with any secret it carried masked, and
#   returns, and the caller answers.
stand_in_or_real() {
  sr_name=$1
  shift
  if [ -z "${FAKE_HOST_STATE:-}" ]; then
    sr_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
    sr_old_ifs=$IFS
    IFS=:
    for sr_dir in $PATH; do
      [ -n "$sr_dir" ] || continue
      sr_real=$(CDPATH= cd -- "$sr_dir" 2>/dev/null && pwd -P) || continue
      [ "$sr_real" = "$sr_here" ] && continue
      if [ -f "$sr_dir/$sr_name" ] && [ -x "$sr_dir/$sr_name" ]; then
        IFS=$sr_old_ifs
        exec "$sr_dir/$sr_name" "$@"
      fi
    done
    IFS=$sr_old_ifs
    echo "$sr_name: command not found" >&2
    exit 127
  fi
  if [ ! -f "$FAKE_HOST_STATE" ]; then
    case "${1:-}" in
      --version|-v|-V) echo "$sr_name (replay stand-in, signed in to nothing)"; exit 0 ;;
      --help|-h) echo "Usage: $sr_name [options] [command]"; exit 0 ;;
    esac
    echo "$sr_name: not signed in, and no account is reachable from this run" >&2
    exit 1
  fi
  printf 'CALL\t%s %s\n' "$sr_name" "$*" \
    | sed -E \
      -e 's#(postgres(ql)?://)[^[:space:]"'"'"']+#\1[masked]#g' \
      -e 's#(--dbname[= ])[^[:space:]]+#\1[masked]#g' \
      -e 's#((--token|-t)[= ])[^[:space:]]+#\1[masked]#g' \
      -e 's#([Aa]uthorization:[[:space:]]*).*#\1[masked]#' \
      -e 's#([Bb]earer[[:space:]]+)[^[:space:]]+#\1[masked]#g' \
    >> "${FAKE_HOST_LOG:-$FAKE_HOST_STATE.log}"
}
