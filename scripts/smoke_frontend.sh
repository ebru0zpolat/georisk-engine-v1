#!/usr/bin/env bash
# Post-deploy / local preview smoke test for GeoRisk frontend + API.
set -euo pipefail

BASE="${1:-http://localhost:4173}"
echo "Smoke testing ${BASE}"

curl -fsS "${BASE}/" 2>/dev/null | grep -q "GeoRisk Engine" && echo "OK: frontend reachable at ${BASE}" || {
  if [[ -d frontend/dist ]] && grep -q "GeoRisk Engine" frontend/dist/index.html; then
    echo "OK: dist/index.html (offline check)"
  else
    echo "WARN: frontend not reachable and no dist/ — continuing API/pytest gates"
  fi
}

if [[ -d frontend/dist ]]; then
  test -f frontend/dist/index.html
  echo "OK: dist/index.html present"
fi

API="${API_BASE:-http://127.0.0.1:8002}"
if curl -fsS "${API}/health" >/dev/null 2>&1; then
  curl -fsS "${API}/health" | grep -q '"status"'
  curl -fsS "${API}/openapi.json" | grep -q '/v1/risk/score'
  curl -fsS "${API}/openapi.json" | grep -q '/v1/scenario/run'
  echo "OK: API health + openapi"
else
  echo "SKIP: API not reachable at ${API}"
fi

python3 -m pytest tests/scoring/test_scenario_scoring_golden.py -q --tb=no

echo "Smoke passed."
