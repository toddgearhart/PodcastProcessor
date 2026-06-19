#!/bin/sh
set -eu

mkdir -p "${DATA_DIR:-/data}" "${PODCAST_DIR:-/podcasts}"
chown -R "${PUID:-99}:${PGID:-100}" "${DATA_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
  exec gosu "${PUID:-99}:${PGID:-100}" "$@"
fi
exec "$@"

