#!/usr/bin/env bash
# Pre-run rehydration for eval 30 (debug-broken-deployment).
# Re-pushes the broken truss to ensure the deployment is in its broken state
# (eval 30 agents that successfully fix it would otherwise leave it healthy
# for the next run). Idempotent — replaces production each time.
#
# Required env: BASETEN_MCP_KEY (parent runner has it; we forward via trussrc).
set -euo pipefail
: "${BASETEN_MCP_KEY:?required}"
: "${FIXTURE_MODEL_NAME:?required}"

script_dir=$(cd "$(dirname "$0")" && pwd)
eval_root=$(cd "$script_dir/../../.." && pwd)
fixture_dir="$script_dir"
truss="$eval_root/harness/.venv/bin/truss"

# Self-contained, scoped trussrc — does NOT touch ~/.trussrc.
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/.trussrc" <<EOF
[baseten]
remote_provider = baseten
api_key = $BASETEN_MCP_KEY
remote_url = https://app.baseten.co
EOF

# Keep the embedded name aligned with the target, including downloaded configs.
cp -R "$fixture_dir" "$tmp/fixture"
"$eval_root/harness/.venv/bin/python" - "$tmp/fixture/config.yaml" "$FIXTURE_MODEL_NAME" <<'PYTHON'
import sys
from pathlib import Path
import yaml
path = Path(sys.argv[1])
config = yaml.safe_load(path.read_text())
config["model_name"] = sys.argv[2]
path.write_text(yaml.safe_dump(config, sort_keys=False))
PYTHON

HOME="$tmp" "$truss" push --promote --wait --timeout-seconds 300 --model-name "$FIXTURE_MODEL_NAME" --remote baseten "$tmp/fixture" >/dev/null 2>&1
