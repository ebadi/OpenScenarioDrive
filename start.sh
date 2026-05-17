#!/usr/bin/env bash
set -euo pipefail


docker compose build --build-arg BUILD_JOBS=4 gui

docker compose run test
docker compose run --rm -e SCENARIO=/app/esmini/resources/xosc/highway_merge_advanced.xosc gui
# docker compose run --rm gui
