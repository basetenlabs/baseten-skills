# Baseten inference API

Calling deployed models and Chains over HTTPS. Pre-hosted Model APIs (the OpenAI-compatible catalog of managed LLMs like
DeepSeek, GLM, Kimi) live on a separate endpoint and are covered in `model-apis.md`. This file covers **custom
deployments**: models and chains the user packaged with Truss and deployed to their workspace.

- OpenAPI spec (authoritative): <https://api.baseten.co/inference-spec>
- Reference overview: <https://docs.baseten.co/reference/inference-api/overview>

**Prerequisites:** `deployment-lifecycle.md` (deployments, environments, dev vs published — route paths reflect these
concepts).

## Authentication

Every request sends an `Authorization: Api-Key $BASETEN_API_KEY` header. API keys are created at
<https://app.baseten.co/settings/api_keys>.

## Endpoint URL shape

**Models:**

```
https://model-{model_id}.api.baseten.co/{target}/{endpoint}
```

**Chains:**

```
https://chain-{chain_id}.api.baseten.co/{target}/{endpoint}
```

`{target}` is one of:

- `production` - the model's production environment.
- `environments/{env_name}` - a named environment.
- `development` - the development deployment.
- `deployment/{deployment_id}` - a specific deployment by ID.

`{endpoint}` is the action: `predict`, `async_predict`, `wake`, `async_queue_status`, or (for custom servers)
`sync/{route}`. Chains use `run_remote` and `async_run_remote` in place of `predict` / `async_predict`.

### Models: predict endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /production/predict` | Call production. |
| `POST /environments/{env_name}/predict` | Call a named environment. |
| `POST /development/predict` | Call the development deployment. |
| `POST /deployment/{deployment_id}/predict` | Call a specific deployment. |

`async_predict` variants exist at the same paths. See below for async semantics.

### Chains: run_remote endpoints

Same paths with `run_remote` / `async_run_remote` in place of `predict` / `async_predict`.

### Regional endpoints

When regional environments are enabled for the organization, the environment name moves into the hostname and paths
become bare:

```
https://model-{model_id}-{env_name}.api.baseten.co/predict
https://chain-{chain_id}-{env_name}.api.baseten.co/run_remote
```

Path-based environment selection is rejected on regional hostnames.

## Synchronous `predict`

Minimal Python example (Python-class Truss):

```python
import os
import requests

model_id = os.environ["MODEL_ID"]
api_key = os.environ["BASETEN_API_KEY"]

response = requests.post(
    f"https://model-{model_id}.api.baseten.co/environments/production/predict",
    headers={"Authorization": f"Api-Key {api_key}"},
    json={"messages": [{"role": "user", "content": "Hello"}]},
    timeout=60,
)
response.raise_for_status()
print(response.json())
```

The JSON body is forwarded directly to the model's `predict` function, or to a custom server's `predict_endpoint`, or to
the chain entrypoint's `run_remote`.

## Streaming

If the deployed model's `predict` returns a generator (or a custom server emits chunked responses), the response is an
HTTP stream. Read it incrementally:

```python
with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
    response.raise_for_status()
    for chunk in response.iter_content(chunk_size=None):
        print(chunk.decode(), end="")
```

For OpenAI-style Server-Sent Events, use the OpenAI SDK (below) or an SSE parser. Full details:
<https://docs.baseten.co/inference/streaming>.

## OpenAI SDK (engine-only and OpenAI-compatible servers)

Engine-only deploys (Engine-Builder-LLM, BIS-LLM) and OpenAI-compatible custom servers (vLLM, SGLang, etc. when
configured that way) expose OpenAI-shaped routes. Point the OpenAI SDK at the model's **sync** path:

```python
import os
from openai import OpenAI

model_id = os.environ["MODEL_ID"]
client = OpenAI(
    base_url=f"https://model-{model_id}.api.baseten.co/environments/production/sync/v1",
    api_key=os.environ["BASETEN_API_KEY"],
)

response = client.chat.completions.create(
    model="baseten",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True,
)
for chunk in response:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="")
```

The `model=` argument in the SDK is a placeholder (`"baseten"` is idiomatic); the actual model is the one deployed at
that URL.

## Sync endpoint (custom servers)

Custom-server Trusses can expose any route their server implements via the `sync` path:

```
https://model-{model_id}.api.baseten.co/environments/production/sync/{route}
```

Example mappings:

- `/sync/health` hits the server's `/health` route.
- `/sync/v1/models` hits `/v1/models` (used alongside `/sync/v1/chat/completions` for full OpenAI-compat).

See `truss-custom-servers.md` for how `predict_endpoint` interacts with `sync` routing.

## Async inference

Async is a fire-and-forget pattern: submit a request, get a `request_id` back immediately, receive the result at a
webhook later. Use for long-running work or batch processing.

```
POST /production/async_predict
{
  "model_input": { ... },
  "webhook_endpoint": "https://your-app.example.com/baseten-callback",
  "max_time_in_queue_seconds": 600
}
```

Key properties:

- `max_time_in_queue_seconds` controls queue timeout; maximums move over time, so confirm current limits in the docs.
- **Async is not compatible with streaming output.**
- **Baseten does not store model outputs.** If webhook delivery fails after all retries, the result is lost. Design your
  webhook to be idempotent and, if durability matters, have it persist the payload before returning 200. See
  <https://docs.baseten.co/inference/async#webhook-delivery> for current retry behavior.
- The webhook POST includes `X-BASETEN-REQUEST-ID` and a signature header. Verify signatures; see
  <https://docs.baseten.co/inference/async#webhook-delivery>.
- Priority queuing is supported via a `priority` field (lower numbers take precedence); consult the async docs for the
  current priority scale.
- For Chains, use `async_run_remote`. Chainlet-to-Chainlet calls stay synchronous; only the entrypoint is queued.

Full docs: <https://docs.baseten.co/inference/async>.

### Status and cancellation

| Endpoint | Purpose |
| --- | --- |
| `GET /async_request/{request_id}` | Get current status. Available for ~1 hour after completion. |
| `DELETE /async_request/{request_id}` | Cancel a queued async request. |
| `GET {target}/async_queue_status` | Queue metrics for a deployment target. |

## Wake endpoints

If a deployment is scaled to zero, `POST {target}/wake` triggers a warm-up without sending an inference request. Useful
for pre-warming right before a latency-sensitive workload.

## Gotchas

- **URL structure matters.** `/environments/production/predict` is different from `/production/predict`. Both hit
  production, but the former names the environment explicitly; the latter is the shorthand. Regional endpoints accept
  neither and require the bare-path form.
- **The `model=` field in the OpenAI SDK is a placeholder.** The actual model is determined by the base URL. Setting it
  to something descriptive is fine; setting it to the name of an unrelated model does not change routing.
- **Async never streams.** If the user needs both (long job with incremental output), this is a design constraint, not a
  client bug.
- **Failed webhook delivery after retries loses the result.** Log and persist on the webhook side before returning 200.
- **Request timeouts are on your client.** Long `predict` calls need a client timeout large enough (or use async).
- **Gates on `development` targets return 404 when the dev deployment has scaled to zero** between requests.
  `truss watch` keeps it warm; outside of `watch`, consider `/wake` or the scale-to-zero behavior.
- **Custom server `sync` routing only works for routes the server actually exposes.** `predict_endpoint` is the shortcut
  for the primary inference route; everything else uses `/sync/{route}`.

## Further reading

- Calling deployed models: <https://docs.baseten.co/inference/calling-your-model>
- Inference API overview: <https://docs.baseten.co/reference/inference-api/overview>
- Streaming: <https://docs.baseten.co/inference/streaming>
- Async and webhooks: <https://docs.baseten.co/inference/async>
- OpenAPI spec: <https://api.baseten.co/inference-spec>
- Pre-hosted Model APIs: `model-apis.md`.
