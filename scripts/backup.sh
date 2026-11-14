#!/usr/bin/env bash
# Back up the production stack: a Postgres dump and a snapshot of the live Qdrant collection.
#
#   scripts/backup.sh                 # writes into the `backups` volume, keeps 7 days of dumps
#   scripts/backup.sh --copy ./out    # also copies the new files to a host directory
#
# Run it nightly from cron on the server (see docs/tech/deployment.md) and after every reindex.
# Restore: docs/tech/runbook.md, "Restore from a backup".
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
KEEP_DAYS="${KEEP_DAYS:-7}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
COPY_TO=""
if [ "${1:-}" = "--copy" ]; then COPY_TO="${2:?--copy needs a directory}"; fi

cd "$(dirname "$0")/.."

echo "postgres: dumping to /backups/postgres_$STAMP.dump"
$COMPOSE exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file="/backups/postgres_'"$STAMP"'.dump"'
$COMPOSE exec -T postgres sh -c \
  'find /backups -name "postgres_*.dump" -mtime +'"$KEEP_DAYS"' -delete'

# The alias target is the collection that serves search. Qdrant keeps snapshots in its own
# storage volume (/qdrant/storage/snapshots/<collection>/).
collection="$($COMPOSE exec -T backend python -c "
import json, urllib.request
aliases = json.load(urllib.request.urlopen('http://qdrant:6333/aliases'))['result']['aliases']
print(next((a['collection_name'] for a in aliases if a['alias_name'] == 'legal_chunks'), ''))
")"
if [ -n "$collection" ]; then
  echo "qdrant: snapshot of $collection"
  $COMPOSE exec -T backend python -c "
import json, urllib.request
request = urllib.request.Request('http://qdrant:6333/collections/$collection/snapshots', method='POST')
print(json.load(urllib.request.urlopen(request, timeout=600))['result']['name'])
"
else
  echo "qdrant: no live collection, nothing to snapshot"
fi

if [ -n "$COPY_TO" ]; then
  mkdir -p "$COPY_TO"
  container="$($COMPOSE ps -q postgres)"
  docker cp "$container:/backups/postgres_$STAMP.dump" "$COPY_TO/"
  echo "copied the dump to $COPY_TO"
fi
echo "backup done"
