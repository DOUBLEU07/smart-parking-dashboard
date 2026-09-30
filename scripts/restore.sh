#!/usr/bin/env sh
# Restore a dump made by backup.sh:  ./scripts/restore.sh backups/parking-20260101-020000.sql.gz
set -eu

[ $# -eq 1 ] || { echo "usage: $0 backups/<file>.sql.gz" >&2; exit 1; }
NAME=$(basename "$1")

docker compose stop backend
docker compose exec -T db sh -c 'gunzip -c /backups/'"$NAME"' | psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose start backend
echo "restored from $1"
