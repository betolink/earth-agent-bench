#!/usr/bin/env bash
# Fix ownership of run artifacts written by root containers (bind-mounted).
#
# Harbor runs trial containers as root, so files they write under runs/ land on
# the host as root:root and can't be removed by the local user. This chowns them
# back to the invoking user (UID/GID 1000) using a throwaway root container —
# no sudo required (works as long as the user is in the `docker` group).
#
# Usage: scripts/fix-perms.sh [dir ...]   (default: runs/ and harbor/generated/)
set -uo pipefail
cd "$(dirname "$0")/.."

UID_GID="$(id -u):$(id -g)"
dirs=("$@")
[ ${#dirs[@]} -eq 0 ] && dirs=(runs harbor/generated)

for d in "${dirs[@]}"; do
  [ -d "$d" ] || continue
  docker run --rm -v "$PWD/$d":/r alpine sh -c "chown -R $UID_GID /r" >/dev/null 2>&1 \
    && echo "fixed ownership: $d" || echo "skip (could not fix): $d"
done
echo "remaining root-owned under ${dirs[*]}: $(find "${dirs[@]}" -user root 2>/dev/null | wc -l)"
