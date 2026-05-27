#!/usr/bin/env bash
# Codespace bootstrap. Idempotent — safe to re-run.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

echo "→ installing uv"
pip install --user --upgrade uv

echo "→ installing claude CLI"
npm install -g @anthropic-ai/claude-code

echo "→ fetching pinned skill-creator"
bash bin/fetch_skill_creator.sh

echo "→ uv sync evals/"
(cd evals && uv sync)

# Write .env from Codespace secrets if not already present. Secrets are
# exposed as remoteEnv in devcontainer.json; this file just lets local
# scripts that `source .env` keep working.
if [[ ! -f .env ]]; then
  echo "→ writing .env from environment"
  cat > .env <<EOF
BASETEN_MCP_KEY=${BASETEN_MCP_KEY:-}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
EOF
fi

echo "✓ bootstrap done. Run: bin/codespace_run_sweep.sh"
