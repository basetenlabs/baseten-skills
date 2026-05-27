#!/usr/bin/env bash
# Run the eval sweep from a Codespace (or any cloud VM).
# Single-worker by default — concurrent runs throttle on the test workspace.
#
# Usage: bin/codespace_run_sweep.sh [extra args forwarded to runner]
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

[[ -f .env ]] || { echo "no .env; expected post-create.sh to have written one"; exit 1; }
set -a; source .env; set +a

# Drop any baseten-routing env vars so claude CLI talks to real Anthropic. If we
# ever want to run DeepSeek-via-Baseten, set ANTHROPIC_BASE_URL/AUTH_TOKEN/MODEL
# explicitly *after* this script (or pass via runner CLI override).
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL

[[ -n "${BASETEN_MCP_KEY:-}" ]] || { echo "BASETEN_MCP_KEY empty — set the Codespace secret"; exit 1; }

if [[ ! -f skills/baseten/evals/fixtures.json ]]; then
  echo "→ fixtures.json missing; provisioning"
  bin/provision_fixtures.sh
fi

cd evals
exec uv run python -m baseten_skills_evals.runner --skill baseten --num-workers 1 "$@"
