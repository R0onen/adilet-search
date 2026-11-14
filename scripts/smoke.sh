#!/usr/bin/env bash
# Smoke test of a running stack. Run it after every deployment.
#
#   scripts/smoke.sh http://localhost:8000        # dev stack (backend port)
#   scripts/smoke.sh https://example.kz           # production (through the reverse proxy)
#
# Checks: health, one search per language, an article, a streamed answer, and that the admin
# login rejects bad credentials. Needs curl and jq. Exit code 0 = all passed.
set -uo pipefail

BASE="${1:?usage: smoke.sh <base_url>}"
API="${BASE%/}/api/v1"
FAILED=0
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT

pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAILED=1; }
check() { if "${@:2}"; then pass "$1"; else fail "$1"; fi; }

post() { # post <path> <json> <output file>; prints the HTTP status
  curl -sS -o "$3" -w '%{http_code}' --max-time 120 -X POST "$API$1" \
    -H 'Content-Type: application/json; charset=utf-8' --data-binary "$2"
}

# 1. health
status="$(curl -sS -o "$TMP/health.json" -w '%{http_code}' --max-time 20 "$API/health")"
check "health answers 200 (got $status)" test "$status" = "200"
check "health status is ok or degraded: $(jq -c '.components' "$TMP/health.json" 2>/dev/null)" \
  jq -e '.status == "ok" or .status == "degraded"' "$TMP/health.json" >/dev/null
printf '      pipeline %s, app %s\n' \
  "$(jq -r '.pipeline_version' "$TMP/health.json")" "$(jq -r '.app_version' "$TMP/health.json")"

# 2. search, Russian and Kazakh
status="$(post /search '{"query": "Основания расторжения трудового договора", "top_k": 5}' "$TMP/ru.json")"
check "search (ru) answers 200 (got $status)" test "$status" = "200"
check "search (ru) returns results in Russian" \
  jq -e '.lang == "ru" and (.results | length) > 0' "$TMP/ru.json" >/dev/null
if jq -e '.degraded | length > 0' "$TMP/ru.json" >/dev/null 2>&1; then
  printf '      note: search is degraded: %s\n' "$(jq -c '.degraded' "$TMP/ru.json")"
fi

status="$(post /search '{"query": "Еңбек демалысының ұзақтығы қанша", "top_k": 5}' "$TMP/kk.json")"
check "search (kk) answers 200 (got $status)" test "$status" = "200"
check "search (kk) detects Kazakh and returns results" \
  jq -e '.lang == "kk" and (.results | length) > 0' "$TMP/kk.json" >/dev/null

# 3. the first result's article can be opened
article_id="$(jq -r '.results[0].article.article_id // empty' "$TMP/ru.json")"
if [ -n "$article_id" ]; then
  status="$(curl -sS -o "$TMP/article.json" -w '%{http_code}' --max-time 20 "$API/articles/$article_id")"
  check "article $article_id opens (got $status)" test "$status" = "200"
  check "article has text" jq -e '.text | length > 0' "$TMP/article.json" >/dev/null
else
  fail "no article id to open"
fi

# 4. streamed answer ends with a `done` event
status="$(post /answer '{"query": "Какова продолжительность ежегодного трудового отпуска?"}' "$TMP/answer.sse")"
check "answer answers 200 (got $status)" test "$status" = "200"
check "answer stream has sources" grep -q '^event: sources' "$TMP/answer.sse"
if grep -q '^event: done' "$TMP/answer.sse"; then
  pass "answer stream ends with done"
elif grep -q 'generation_unavailable' "$TMP/answer.sse"; then
  fail "answer: the generator is unavailable (sources were returned)"
else
  fail "answer stream has no done event"
fi

# 5. admin is protected
status="$(post /admin/login '{"username": "smoke-test", "password": "wrong-password"}' "$TMP/login.json")"
check "admin login rejects bad credentials (got $status)" test "$status" = "401"
status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$API/admin/stats")"
check "admin stats need a token (got $status)" test "$status" = "401"

# 6. /metrics must not be reachable through a reverse proxy (it is on the backend port only)
case "$BASE" in
  *:8000*) ;;
  *)
    status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "${BASE%/}/metrics")"
    if [ "$status" = "200" ] && curl -sS --max-time 20 "${BASE%/}/metrics" | grep -q '^# HELP'; then
      fail "/metrics is exposed publicly"
    else
      pass "/metrics is not exposed"
    fi
    ;;
esac

if [ "$FAILED" = 0 ]; then echo "smoke test passed"; else echo "smoke test FAILED"; fi
exit "$FAILED"
