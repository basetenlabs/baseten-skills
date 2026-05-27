#!/usr/bin/env bash
# Pre-run cleanup for eval 10 (operate-promote-to-staging).
# Deletes a 'staging' environment on this model if it exists, so the eval
# starts from a clean slate every run.
#
# Required env: BASETEN_MCP_KEY, FIXTURE_MODEL_ID
set -euo pipefail
: "${BASETEN_MCP_KEY:?required}"
: "${FIXTURE_MODEL_ID:?required}"
api=https://api.baseten.co/v1
hdr="Authorization: Api-Key $BASETEN_MCP_KEY"
# DELETE returns 204 if existed, 404 if not. Either is fine.
curl -sS -o /dev/null -w "" -X DELETE -H "$hdr" \
  "$api/models/$FIXTURE_MODEL_ID/environments/staging" || true
