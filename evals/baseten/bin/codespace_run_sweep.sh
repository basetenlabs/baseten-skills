#!/usr/bin/env bash
# Run the eval sweep from a Codespace (or any cloud VM).
# Single-worker by default — concurrent runs throttle on the test workspace.
#
# Usage: evals/baseten/bin/codespace_run_sweep.sh [extra args forwarded to runner]
set -euo pipefail

eval_root=$(cd "$(dirname "$0")/.." && pwd)
repo_root=$(cd "$eval_root/../.." && pwd)
cd "$repo_root"

[[ -f "$eval_root/.env" ]] || { echo "no .env in $eval_root"; exit 1; }
set -a; source "$eval_root/.env"; set +a

# Drop any baseten-routing env vars so claude CLI talks to real Anthropic. If we
# ever want to run DeepSeek-via-Baseten, set ANTHROPIC_BASE_URL/AUTH_TOKEN/MODEL
# explicitly *after* this script (or pass via runner CLI override).
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL

[[ -n "${BASETEN_MCP_KEY:-}" ]] || { echo "BASETEN_MCP_KEY empty — set the Codespace secret"; exit 1; }

if [[ ! -f skills/baseten/evals/fixtures.json ]]; then
  echo "→ fixtures.json missing; provisioning"
  evals/baseten/bin/provision_fixtures.sh
fi

cd "$eval_root/harness"
exec uv run python -m baseten_skills_evals.runner --skill baseten --num-workers 1 "$@"
