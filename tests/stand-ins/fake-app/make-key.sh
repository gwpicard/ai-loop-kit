#!/usr/bin/env sh
# make-key.sh: make the stand-in App private key in a folder you name.
#
# Usage: make-key.sh <folder>        writes <folder>/app-key.pem and prints its path
#        make-key.sh --help
#
# The key is made at test time with openssl, in the folder you give (a throwaway
# folder). No private key is committed. It is idempotent: an existing key is
# kept, so a second run prints the same path and changes nothing.

set -eu

case "${1:-}" in
  -h | --help)
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  '')
    echo "make-key.sh: needs a folder. next: make-key.sh --help" >&2
    exit 2
    ;;
esac

dir=$1
command -v openssl >/dev/null 2>&1 || {
  echo "make-key.sh: openssl is not installed. next: install openssl, then run this again" >&2
  exit 4
}
mkdir -p "$dir"
key="$dir/app-key.pem"
if [ ! -f "$key" ]; then
  umask 077
  openssl genrsa -out "$key" 2048 >/dev/null 2>&1
fi
chmod 600 "$key"
printf '%s\n' "$key"
