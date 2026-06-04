#!/usr/bin/env bash
# Pre-run reset for eval 11 (operate-traffic-spike).
#
# Eval 11 mutates autoscaling. Without a reset, run 2 sees the post-mutation
# state and the agent's "raise 5x" math breaks. PATCH to baseline and bail
# loudly on anything other than HTTP 200/202 — silent failures here corrupt
# multiple subsequent runs.
#
# Field names: API takes singular `min_replica`/`max_replica` (plural form is
# silently 400'd as extra_forbidden). Apply is async; the platform converges
# in a few seconds.
#
# Required env: BASETEN_MCP_KEY, FIXTURE_MODEL_ID
set -euo pipefail
: "${BASETEN_MCP_KEY:?required}"
: "${FIXTURE_MODEL_ID:?required}"

url="https://api.baseten.co/v1/models/$FIXTURE_MODEL_ID/deployments/production/autoscaling_settings"

http=$(curl -sS -o /tmp/baseten-prerun-patch.json -w '%{http_code}' \
  -X PATCH -H "Authorization: Api-Key $BASETEN_MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"min_replica":0,"max_replica":1,"concurrency_target":1}' \
  "$url")

if [[ "$http" != "200" && "$http" != "202" ]]; then
  echo "[pre_run eval-11] PATCH failed: HTTP $http" >&2
  cat /tmp/baseten-prerun-patch.json >&2
  exit 1
fi

# Give the platform a few seconds to converge before the eval starts inspecting.
sleep 5
echo "[pre_run eval-11] reset: min_replica=0 max_replica=1 ct=1 (HTTP $http)"
