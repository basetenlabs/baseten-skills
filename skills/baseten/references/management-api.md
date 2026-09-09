# Baseten management API

Programmatic control plane for models, deployments, environments, autoscaling, secrets, API keys, teams, and billing.
The `truss` CLI uses this API under the hood for push and promotion operations.

- Base URL: `https://api.baseten.co`
- OpenAPI spec (authoritative): <https://api.baseten.co/v1/spec>
- Reference docs (grouped by resource): <https://docs.baseten.co/reference/management-api/overview>

## How to call it

1. **`baseten` MCP** (preferred).
2. Use an installed `baseten` CLI for workspace operations; see `baseten-cli.md`.
3. Otherwise use the **REST API** Spec: <https://api.baseten.co/v1/spec>. Overview:
   <https://docs.baseten.co/reference/management-api/overview>. Non-trivial integrations → generate from the spec.

### Authentication

```
Authorization: Bearer $BASETEN_API_KEY
```

Keys: <https://app.baseten.co/settings/api_keys>.

### Resource shape

All paths under `/v1`:

- **Models** / **Chains**: list, get, delete.
- **Deployments**: list, get, delete, activate, deactivate, retry, promote, terminate replica.
- **Environments**: create, list, get, update (autoscaling, settings). Rolling deployment controls (`pause_promotion`,
  `resume_promotion`, `force_*`, `cancel_promotion`) live on the environment path.
- **Autoscaling**: PATCH on deployment / environment.
- **Instance types**: `/v1/instance_types`, `/v1/instance_type_prices` — authoritative valid-resources list for
  `config.yaml`.
- **Secrets**: `/v1/secrets` (workspace), `/v1/teams/{team_id}/secrets` (team-scoped). Upsert by name.
- **API keys**, **Teams**, **Billing** (`/v1/billing/usage_summary`), **Training** (`/v1/training_projects/...` — see
  <https://docs.baseten.co/reference/training-api>).

Full endpoint table: <https://docs.baseten.co/reference/management-api/overview>.

### Python (for user-facing code)

```python
import os
import requests

BASE_URL = "https://api.baseten.co"
HEADERS = {"Authorization": f"Bearer {os.environ['BASETEN_API_KEY']}"}


def list_deployments(model_id: str) -> list[dict]:
    """Return all deployments for a model."""
    response = requests.get(
        f"{BASE_URL}/v1/models/{model_id}/deployments",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
```

For anything non-trivial, generate the client from <https://api.baseten.co/v1/spec>.

## Chains differences

Chain management mirrors models with `/v1/chains/...`. Notable:

- Chain deployments have a combined environment update endpoint for chainlet settings (instance types, autoscaling).
- **Rolling deployments are not supported for Chains** — promotion is an immediate traffic swap.

## Gotchas

- **`production` endpoints vs environment endpoints differ.** `/v1/models/{id}/deployments/production/...` addresses the
  production deployment directly; `/v1/models/{id}/environments/{env_name}/...` addresses an environment (production is
  one). Pick the right one.
- **Rolling deployments suspend autoscaling** for the environment for their duration; PATCHing mid-rollout won't behave
  as expected.
- **One active promotion per environment at a time.** Subsequent requests rejected until the current one
  completes/pauses/cancels.
- **Production cannot be deleted** unless the model itself is deleted.
- **Deleted deployments / environments → 404** on subsequent calls; deactivation is the reversible option.
- **Secrets API upserts by name.** Reusing a name overwrites the existing value.
- **Authentication:** current docs use `Bearer`; legacy `Api-Key` remains accepted. A 401 is not evidence that the
  Bearer scheme is wrong. Check the key and the authentication requirements in the endpoint documentation.

## Further reading

- Endpoint overview: <https://docs.baseten.co/reference/management-api/overview>
- OpenAPI spec: <https://api.baseten.co/v1/spec>
- Deployment lifecycle concepts: `deployment-lifecycle.md`.
- CLI (wraps many of these endpoints): `truss-cli.md`.
