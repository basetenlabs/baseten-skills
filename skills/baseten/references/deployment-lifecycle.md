# Deployment lifecycle

How a deployed model moves from first push to production, how traffic and autoscaling work, and what the platform gives
you for safe rollouts. This is platform-level information that applies to any Truss deployed on Baseten (Python-class,
custom server, or engine-only).

Authoritative docs live under <https://docs.baseten.co/deployment/>. This file summarizes the shape and flags what
matters most.

## The hierarchy

- **Model**: the top-level entity in a workspace. Has a stable model ID.
- **Deployment**: a containerized instance of a model serving HTTP. Has its own deployment ID. A model can have many
  deployments simultaneously.
- **Environment**: a named slot (e.g. `production`, `staging`) that a deployment can be promoted into. The environment
  owns the autoscaling settings and the stable endpoint URL.

Every deployment has a REST endpoint automatically. Environment-attached deployments also get a stable URL under
`/environments/{name}/predict`.

## Development vs published deployments

A **development deployment** is a mutable slot meant for iteration:

- Created with `truss push --watch` (or `truss chains push --watch`).
- Single replica, scales to zero when idle.
- Live reload via `truss watch` patches code in place.
- No autoscaling; no zero-downtime updates.
- Can be promoted later.

A **published deployment** is immutable:

- Created with plain `truss push` (or with `--promote` / `--environment`).
- Has autoscaling.
- Can be promoted to environments and rolled out safely.
- Is the right target for any non-exploratory work.

## Environments

Environments provide logical isolation and stable endpoints for a deployment lifecycle (dev, staging, production, etc.).

- `production` exists by default, cannot be deleted unless the entire model is removed, and its name is reserved (no
  other environment can be called `production`).
- Create custom environments from the dashboard or via the management API
  (<https://docs.baseten.co/reference/management-api/environments/create-an-environment>).
- Deployments do not have to be in an environment to be callable. Environments add autoscaling control, stable routing,
  and rollout features on top.

### Environment in `model.py`

`Model.__init__` can accept an `environment` keyword argument; Truss injects the current environment context there. Use
it to drive per-environment behavior in `load`:

```python
def __init__(self, **kwargs):
    self._environment = kwargs["environment"]

def load(self):
    if self._environment and self._environment.get("name") == "production":
        ...
```

If you do this, enable **Re-deploy when promoting** on the environment (dashboard or management API) so `load()`
actually re-runs when the deployment moves into a new environment. Otherwise the original `load` state is reused.

## Promotion

Promoting a deployment attaches it to an environment. Three ways to do it:

- `truss push --promote` - publish and promote straight to production in one step.
- `truss push --environment <name>` - publish and promote into a named environment.
- Dashboard or management API - promote an existing deployment after the fact.

Semantics:

- If the source deployment can be reused, promotion is an in-place attachment and is fast.
- A new deployment is created when: the source is already attached to another environment, the target environment has a
  different instance type or resource profile, or the environment has "Re-deploy on promotion" enabled.
- On promotion, the new deployment inherits the previous environment deployment's autoscaling settings; the previous
  deployment is demoted (but kept).
- Only one active promotion per environment at a time.

## Rolling deployments

When promoting a published deployment into an environment that already has one, the rollout can be **rolling**: scale up
the candidate, shift traffic proportionally, scale down the previous. Pause / resume / cancel / force-complete are
available.

Details: <https://docs.baseten.co/deployment/rolling-deployments>.

Key points:

- Autoscaling is **suspended during a rolling deployment** for the whole environment. Use `replica_overhead_percent` to
  pre-provision capacity if traffic is expected to grow mid-rollout.
- Rolling deployments are **not supported for Chains**.
- "Canary deployments" are deprecated in favor of rolling deployments.

## Autoscaling

Each environment's autoscaling controls independently:

- `min_replicas` (default 0 enables scale-to-zero).
- `max_replicas`.
- `concurrency_target` per replica.
- `autoscaling_window` (smoothing period).
- `scale_down_delay` (how long to wait before reducing replicas).

Set per environment from the dashboard or the management API
(<https://docs.baseten.co/reference/management-api/deployments/autoscaling/updates-a-deployments-autoscaling-settings>).

Full concept docs: <https://docs.baseten.co/deployment/autoscaling/overview>.

## Regional environments

Regional environments restrict inference traffic to a specific geographic region for data residency compliance. When
enabled for the organization, each environment gets a dedicated regional endpoint whose hostname embeds the environment
name:

```
https://model-{id}-{env}.api.baseten.co/predict
```

Path-based environment selection (`/environments/{name}/predict`, `/production/predict`, `/deployment/{id}/predict`) is
rejected on regional endpoints. Contact the Baseten account team to enable. Full details:
<https://docs.baseten.co/deployment/regional-environments>.

## Managing deployments

- **Naming**: custom deployment names via `truss push --deployment-name <name>` or the dashboard. Names are cosmetic;
  APIs still address by ID.
- **Deactivating**: suspends serving while preserving config. No compute cost; inference returns 404. Reactivate
  anytime.
- **Deleting**: permanent. Production deployments must be replaced before deletion.

Programmatic equivalents live in `management-api.md`.

## CI/CD

The normal CI/CD shape is `truss push` with some mix of `--wait`, `--tail`, `--json`, `--environment`,
`--include-git-info`, and `--labels`. See `truss-cli.md` for specifics. <https://docs.baseten.co/deployment/ci-cd> has
worked examples.

## Logs and observability

Per-deployment logs are available in the dashboard under each deployment. The CLI can also tail them:

- `truss push --tail` during a push.
- `truss watch` during development.
- `truss model-logs <model-id>` for a one-shot fetch.

Per-request log correlation uses the `X-Baseten-Request-Id` header returned on every response. Standard Python Trusses
log this automatically; custom servers must format JSON logs with a top-level `request_id` field (see
`truss-custom-servers.md`).

Broader observability (metrics export, alerting, tracing): <https://docs.baseten.co/observability>.

## Gotchas

- **Rolling deployments suspend autoscaling** for the environment for their whole duration. If replicas look wrong
  during a rollout, this is why.
- **`production` is reserved** and cannot be deleted without deleting the model.
- **Development deployments scale to zero** (unless a `truss watch` is active, which keeps them warm). Published
  deployments do not scale to zero unless autoscaling is configured that way.
- **Promotion may or may not create a new deployment.** If you need `load()` to re-run on promotion, enable "Re-deploy
  when promoting" on the environment.
- **Chains cannot use rolling deployments.** Promotions for Chains are immediate traffic swaps.
- **Only one active promotion per environment at a time.** Queue or wait if another rollout is in flight.

## Further reading

- Deployments: <https://docs.baseten.co/deployment/deployments>
- Environments: <https://docs.baseten.co/deployment/environments>
- Rolling deployments: <https://docs.baseten.co/deployment/rolling-deployments>
- Autoscaling: <https://docs.baseten.co/deployment/autoscaling/overview>
- Regional environments: <https://docs.baseten.co/deployment/regional-environments>
- CI/CD: <https://docs.baseten.co/deployment/ci-cd>
- Programmatic control: `management-api.md`.
