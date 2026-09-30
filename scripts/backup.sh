#!/usr/bin/env sh
# Dump the database to ./backups/parking-YYYYmmdd-HHMMSS.sql.gz and keep the newest 14.
# Schedule with cron, e.g.:  0 2 * * *  cd /path/to/project && ./scripts/backup.sh
set -eu

KEEP=${KEEP:-14}
STAMP=$(date +%Y%m%d-%H%M%S)
FILE="parking-$STAMP.sql.gz"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists | gzip > /backups/'"$FILE"
echo "backup written: backups/$FILE"

ls -1t backups/parking-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
