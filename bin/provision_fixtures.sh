#!/usr/bin/env bash
# Push all eval fixtures to the test workspace and write fixtures.json.
# Idempotent: re-running just re-pushes (truss handles existing models).
#
# Requires:
#   - BASETEN_MCP_KEY env var (test-workspace key)
#   - truss CLI (use the one in evals/.venv: ./evals/.venv/bin/truss)
set -euo pipefail

[[ -n "${BASETEN_MCP_KEY:-}" ]] || { echo "BASETEN_MCP_KEY required"; exit 1; }

repo_root=$(cd "$(dirname "$0")/.." && pwd)
fixtures=$repo_root/evals/fixtures
truss=$repo_root/evals/.venv/bin/truss
api=https://api.baseten.co/v1
export TRUSS_API_KEY=$BASETEN_MCP_KEY

# Isolated trussrc: single remote pointing at the CI workspace, so `truss push`
# doesn't ask which remote to use and can't accidentally hit the personal account.
fake_home=$(mktemp -d -t baseten-fixtures-home.XXXX)
trap 'rm -rf "$fake_home"' EXIT
cat > "$fake_home/.trussrc" <<TRUSSRC
[baseten]
remote_provider = baseten
api_key = $BASETEN_MCP_KEY
remote_url = https://app.baseten.co
TRUSSRC
export HOME=$fake_home

get_id() {
  local name=$1
  curl -sS -H "Authorization: Api-Key $BASETEN_MCP_KEY" "$api/models" \
    | "$repo_root/evals/.venv/bin/python" -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    if m.get('name') == '$name':
        print(m['id']); break
"
}

has_production() {
  local model_id=$1
  [[ -z "$model_id" ]] && return 1
  curl -sS -H "Authorization: Api-Key $BASETEN_MCP_KEY" \
    "$api/models/$model_id/deployments/production" \
    | grep -q '"id"'
}

push() {
  # push <dir> [publish]
  # If publish requested AND production already exists, skip — `truss push --publish`
  # would create a new production deployment and trigger a rollout we don't want.
  local dir=$1 publish=${2:-no}
  local name flags="--trusted"
  name=$(awk '/^model_name:/ {print $2; exit}' "$dir/config.yaml")
  if [[ "$publish" == "publish" ]]; then
    local id; id=$(get_id "$name")
    if has_production "$id"; then
      echo "→ skipping $dir (production already exists on model $name=$id)"
      return 0
    fi
    flags="$flags --publish"
  fi
  echo "→ pushing $dir (${publish})"
  "$truss" push $flags "$dir"
}

push "$fixtures/broken-deployment"
push "$fixtures/deployment-no-model-cache"
push "$fixtures/model-with-dev-deployment"
push "$fixtures/two-deployments-regression/good" publish
push "$fixtures/two-deployments-regression/regression"
push "$fixtures/model-low-replicas" publish

# Set the low-baseline autoscaling on model-low-replicas / production. Eval 11
# mutates this; cleanup hook should reset it (see TODO in evals.json).
low_id=$(get_id polite-axolotl)
echo "→ setting autoscaling baseline on $low_id (production)"
# API takes singular min_replica/max_replica — plural form is silently 400'd.
http=$(curl -sS -o /tmp/provision-autoscaling.json -w '%{http_code}' -X PATCH \
  -H "Authorization: Api-Key $BASETEN_MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"min_replica":0,"max_replica":1,"concurrency_target":1}' \
  "$api/models/$low_id/deployments/production/autoscaling_settings")
if [[ "$http" != "200" && "$http" != "202" ]]; then
  echo "  autoscaling PATCH failed: HTTP $http" >&2
  cat /tmp/provision-autoscaling.json >&2
  exit 1
fi

# Emit fixtures.json so the runner can resolve FIXTURE_MODEL_ID placeholders.
cat > "$repo_root/skills/baseten/evals/fixtures.json" <<EOF
{
  "broken-deployment":          {"FIXTURE_MODEL_ID": "$(get_id cheerful-otter)"},
  "two-deployments-regression": {"FIXTURE_MODEL_ID": "$(get_id mellow-koala)"},
  "deployment-no-model-cache":  {"FIXTURE_MODEL_ID": "$(get_id breezy-walrus)"},
  "model-with-dev-deployment":  {"FIXTURE_MODEL_ID": "$(get_id jolly-narwhal)"},
  "model-low-replicas":         {"FIXTURE_MODEL_ID": "$low_id"}
}
EOF
echo "✓ wrote $repo_root/skills/baseten/evals/fixtures.json"
