#!/usr/bin/env bash
# Move a finished index from one machine to another, so the target does not have to embed the
# corpus again (hours on a small CPU server).
#
#   scripts/transfer_index.sh export ./index_export      # on the machine that has the index
#   scripts/transfer_index.sh import ./index_export      # on the target, after the stack is up
#
# `export` writes the corpus tables of Postgres (documents, articles, index bookkeeping) and a
# snapshot of the live Qdrant collection. Query logs, feedback and admin users are not exported.
# `import` loads both and points the `legal_chunks` alias at the restored collection.
# The target must run the same pipeline (same `index_compat_id`), or search stays on the
# full-text fallback.
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
ALIAS="${QDRANT_ALIAS:-legal_chunks}"
MODE="${1:?usage: transfer_index.sh export|import <directory>}"
DIR="${2:?usage: transfer_index.sh export|import <directory>}"
CORPUS_TABLES="documents articles index_state"

cd "$(dirname "$0")/.."

qdrant() { # qdrant <python expression using `call(method, path, body=None)`>
  $COMPOSE exec -T backend python -c "
import json, urllib.request
def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request('http://qdrant:6333' + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=1800))['result']
$1
"
}

case "$MODE" in
  export)
    mkdir -p "$DIR"
    collection="$(qdrant "print(next((a['collection_name'] for a in call('GET', '/aliases')['aliases'] if a['alias_name'] == '$ALIAS'), ''))")"
    [ -n "$collection" ] || { echo "no live collection behind the alias $ALIAS"; exit 1; }

    echo "postgres: corpus tables"
    tables=""
    for table in $CORPUS_TABLES; do tables="$tables --table=$table"; done
    $COMPOSE exec -T postgres sh -c \
      'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --data-only '"$tables"' --file=/backups/corpus_export.dump'
    docker cp "$($COMPOSE ps -q postgres):/backups/corpus_export.dump" "$DIR/corpus.dump"

    echo "qdrant: snapshot of $collection"
    snapshot="$(qdrant "print(call('POST', '/collections/$collection/snapshots')['name'])")"
    docker cp "$($COMPOSE ps -q qdrant):/qdrant/snapshots/$collection/$snapshot" "$DIR/collection.snapshot"
    echo "$collection" > "$DIR/collection.txt"
    ls -l "$DIR"
    echo "export done: copy $DIR to the target machine"
    ;;

  import)
    [ -f "$DIR/corpus.dump" ] && [ -f "$DIR/collection.snapshot" ] && [ -f "$DIR/collection.txt" ] \
      || { echo "$DIR is not an export directory"; exit 1; }
    collection="$(cat "$DIR/collection.txt")"

    echo "postgres: corpus tables"
    docker cp "$DIR/corpus.dump" "$($COMPOSE ps -q postgres):/backups/corpus_import.dump"
    $COMPOSE exec -T postgres sh -c \
      'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qc "truncate index_state, articles, documents cascade" && pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --disable-triggers /backups/corpus_import.dump'

    echo "qdrant: restoring $collection"
    $COMPOSE exec -T -u 0 qdrant mkdir -p /qdrant/snapshots/import
    docker cp "$DIR/collection.snapshot" "$($COMPOSE ps -q qdrant):/qdrant/snapshots/import/collection.snapshot"
    qdrant "call('PUT', '/collections/$collection/snapshots/recover', {'location': 'file:///qdrant/snapshots/import/collection.snapshot'})
actions = [{'delete_alias': {'alias_name': '$ALIAS'}}, {'create_alias': {'collection_name': '$collection', 'alias_name': '$ALIAS'}}]
try:
    call('POST', '/collections/aliases', {'actions': actions})
except Exception:
    call('POST', '/collections/aliases', {'actions': actions[1:]})
print('points:', call('GET', '/collections/$collection')['points_count'])"
    $COMPOSE restart backend
    echo "import done: run scripts/smoke.sh against this stack"
    ;;

  *)
    echo "usage: transfer_index.sh export|import <directory>"; exit 1 ;;
esac
