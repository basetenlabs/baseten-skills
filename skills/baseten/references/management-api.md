# Baseten management API

The management API is the programmatic control plane for models, deployments, environments, autoscaling, secrets, API
keys, teams, and billing. Use it from scripts and CI when the truss CLI or the dashboard do not fit the workflow. The
`truss` CLI itself uses this API under the hood for push and promotion operations.

- Base URL: `https://api.baseten.co`
- OpenAPI spec (authoritative): <https://api.baseten.co/v1/spec>
- Reference docs (grouped by resource): <https://docs.baseten.co/reference/management-api/overview>

Prefer generating a client from the OpenAPI spec for non-trivial integrations rather than hand-rolling HTTP calls.

## Authentication

Every request needs an API key in the `Authorization` header:

```
Authorization: Api-Key $BASETEN_API_KEY
```

API keys are created at <https://app.baseten.co/settings/api_keys> (user keys) or programmatically via the API Key
endpoints.

## Resource shape at a glance

All paths are under `/v1`. The surface divides cleanly:

- **Models**: `/v1/models`, `/v1/models/{model_id}` (list, get, delete).
- **Chains**: `/v1/chains`, `/v1/chains/{chain_id}` (list, get, delete).
- **Deployments** (per-model and per-chain): list, get, delete, activate, deactivate, retry, promote, terminate replica.
- **Environments** (per-model and per-chain): create, list, get, update (autoscaling and settings).
- **Autoscaling**: PATCH endpoints on each deployment / environment.
- **Instance types**: `/v1/instance_types` (list), `/v1/instance_type_prices` (pricing).
- **Secrets**: `/v1/secrets` (list, create/update), and `/v1/teams/{team_id}/secrets` for team-scoped secrets.
- **API keys**: `/v1/api_keys` (list, create, delete), `/v1/teams/{team_id}/api_keys`.
- **Teams**: `/v1/teams` (list).
- **Billing**: `/v1/billing/usage_summary`.
- **Training**: `/v1/training_projects/...` (training jobs and checkpoints). Out of scope for this skill; see
  <https://docs.baseten.co/reference/training-api>.

The full endpoint table with per-endpoint links is at <https://docs.baseten.co/reference/management-api/overview>.

## Common patterns

### List all deployments of a model

```bash
curl -H "Authorization: Api-Key $BASETEN_API_KEY" \
  https://api.baseten.co/v1/models/$MODEL_ID/deployments
```

### Promote a deployment into an environment

```bash
curl -X POST \
  -H "Authorization: Api-Key $BASETEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"deployment_id": "$DEPLOYMENT_ID"}' \
  https://api.baseten.co/v1/models/$MODEL_ID/environments/production/promote
```

Related rolling-deployment controls on the same `environments/{env_name}` path: `pause_promotion`, `resume_promotion`,
`force_cancel_promotion`, `force_roll_forward_promotion`, `cancel_promotion`.

### Update autoscaling on production

```bash
curl -X PATCH \
  -H "Authorization: Api-Key $BASETEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"min_replicas": 1, "max_replicas": 10, "concurrency_target": 1}' \
  https://api.baseten.co/v1/models/$MODEL_ID/deployments/production/autoscaling_settings
```

Development, production, and arbitrary deployment IDs each have their own PATCH endpoints; see the overview reference.

### Activate or deactivate

```bash
curl -X POST \
  -H "Authorization: Api-Key $BASETEN_API_KEY" \
  https://api.baseten.co/v1/models/$MODEL_ID/deployments/$DEPLOYMENT_ID/deactivate
```

Deactivation suspends serving (API returns 404) without deleting the deployment; reactivate with the matching
`/activate` endpoint.

### Manage secrets

```bash
# Create or update a workspace secret (idempotent upsert).
curl -X POST \
  -H "Authorization: Api-Key $BASETEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "HF_ACCESS_TOKEN", "value": "hf_..."}' \
  https://api.baseten.co/v1/secrets
```

Team-scoped secrets live under `/v1/teams/{team_id}/secrets` with the same shape.

### List instance types (valid resources)

```bash
curl -H "Authorization: Api-Key $BASETEN_API_KEY" \
  https://api.baseten.co/v1/instance_types
```

Useful when `config.yaml`'s `instance_type` field is unclear; the returned list is the authoritative set of valid values
for the workspace.

## Chains

Chain management mirrors models with `/v1/chains/...` in place of `/v1/models/...`. Notable differences:

- Chain deployments have a combined environment update endpoint for chainlet settings (instance types, autoscaling).
- Rolling deployments are **not supported for Chains**; promotion is an immediate traffic swap.

See the Chains tab in the overview reference for the full endpoint set.

## Python usage

Plain `requests` is fine:

```python
import os
import requests

BASE_URL = "https://api.baseten.co"
HEADERS = {"Authorization": f"Api-Key {os.environ['BASETEN_API_KEY']}"}


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

For anything non-trivial, generate a client from <https://api.baseten.co/v1/spec> rather than hand-rolling more methods.
The spec is authoritative and moves faster than prose docs.

## Gotchas

- **`production` endpoints and environment endpoints are different surfaces.**
  `/v1/models/{id}/deployments/production/...` addresses the production deployment directly;
  `/v1/models/{id}/environments/{env_name}/...` addresses an environment (which production is one of). Pick the right
  one for the intended operation.
- **Rolling deployments suspend autoscaling** for the environment for their whole duration; PATCHing autoscaling
  mid-rollout will not behave as expected.
- **Only one active promotion per environment at a time.** Subsequent promotion requests are rejected until the current
  one completes, pauses, or is cancelled.
- **Production cannot be deleted** unless the model itself is deleted.
- **Deleted deployments and environments return 404** for subsequent API calls; deactivation is the reversible option.
- **Secrets API upserts by name.** Reusing a name overwrites the existing secret's value.
- **Authorization errors come back as 401 with `Api-Key` prefix stripped or malformed.** Double-check the prefix and the
  exact header name if a valid-looking key is being rejected.

## Further reading

- Endpoint overview: <https://docs.baseten.co/reference/management-api/overview>
- OpenAPI spec: <https://api.baseten.co/v1/spec>
- Deployment lifecycle concepts: `deployment-lifecycle.md`.
- CLI (wraps many of these endpoints): `truss-cli.md`.
