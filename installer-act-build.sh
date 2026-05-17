#!/usr/bin/env bash
# Resolve the esmini release tag on the host (unauthenticated public API),
# then pass it into act so the workflow skips its own authenticated lookup.
# A GITHUB_TOKEN is therefore not required for normal use.
#
# Usage:
#   ./installer-act-build.sh                    # latest esmini release
#   ESMINI_REF=v2.37.8 ./installer-act-build.sh  # pin a specific version
set -euo pipefail

if [ -z "${ESMINI_REF:-}" ]; then
    printf 'Resolving latest esmini release tag...\n'
    ESMINI_REF=$(curl -fsSL \
        https://api.github.com/repos/esmini/esmini/releases/latest \
        | python3 -c 'import sys,json; print(json.load(sys.stdin)["tag_name"])')
    printf 'Using esmini %s\n' "$ESMINI_REF"
fi

mkdir -p dist/appimage
export ESMINI_REF
exec docker compose run --rm act-build
