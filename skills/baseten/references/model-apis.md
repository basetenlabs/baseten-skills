# Baseten Model APIs

Model APIs are Baseten's managed catalog of pre-hosted LLMs (DeepSeek, GLM, Kimi, and others). OpenAI-compatible. No
deployment step. Pay per million tokens. Pick this over a custom Truss deployment whenever a supported model does the
job; you avoid packaging, infra choices, and scaling decisions entirely.

This is a distinct surface from the inference API for custom deployments (see `inference-api.md`). Both speak
OpenAI-compatible chat completions on their respective endpoints, but Model APIs live at a single shared endpoint
regardless of which model you call, whereas custom deployments are on per-model subdomains.

## Base URL and auth

```
https://inference.baseten.co/v1
```

Header on every request:

```
Authorization: Bearer $BASETEN_API_KEY
```

`Bearer` is what the OpenAI SDK sets and what the docs prescribe for MAPI — use it.

API keys are created at <https://app.baseten.co/settings/api_keys>. Inference-scoped keys are sufficient for MAPI calls
(don't grant management scope for end-user inference clients).

Model APIs require the specific model to be **enabled** in the workspace from <https://app.baseten.co/model-apis/create>
before it can be called. A 404 on the model slug usually means the model is valid but not enabled in this workspace.

## Call pattern

Use the official OpenAI SDK pointed at the Baseten base URL:

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://inference.baseten.co/v1",
    api_key=os.environ["BASETEN_API_KEY"],
)

response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-V3.1",
    messages=[
        {"role": "system", "content": "You are a concise technical writer."},
        {"role": "user", "content": "What is gradient descent?"},
    ],
)
print(response.choices[0].message.content)
```

Substitute any enabled model slug for the `model=` argument. Unlike the custom-deployment sync endpoint (where `model=`
is a placeholder), **on Model APIs the `model=` field actively selects which model serves the request** - get it right.

## Streaming

Same as the OpenAI SDK:

```python
stream = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-V3.1",
    messages=[{"role": "user", "content": "Write a haiku."}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="")
```

## Migrating from OpenAI

Three changes to existing OpenAI code:

1. API key → a Baseten key.
2. `base_url` → `https://inference.baseten.co/v1`.
3. Model name → a Baseten model slug.

Everything else (tool calling, structured outputs, streaming, vision where supported) is the same API shape.

## Feature support

- **Tool calling**: supported by all models.
- **Structured outputs**: supported by most models.
- **Reasoning / extended thinking**: model-specific (see <https://docs.baseten.co/inference/model-apis/reasoning>).
- **Vision**: model-specific.
- **`top_p`, `top_k`**: GLM models and Nemotron Super support these; other models may not.

Current per-model support matrix is at <https://docs.baseten.co/inference/model-apis/overview#feature-support>.

## Listing models

```
curl https://inference.baseten.co/v1/models \
  -H "Authorization: Bearer $BASETEN_API_KEY"
```

Returns current slugs with metadata (context lengths, pricing, features).

## Pricing

Pricing moves; defer to the current table at <https://docs.baseten.co/inference/model-apis/overview#pricing>.

## Error codes

Standard HTTP:

| Code | Meaning |
| --- | --- |
| 400 | Invalid request (check parameters) |
| 401 | Invalid or missing API key |
| 402 | Payment required |
| 404 | Model not found (or not enabled in this workspace) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Gotchas

- **Models must be enabled in the workspace** before they can be called. 404 on a valid slug usually means "not enabled
  here", not "does not exist on Baseten".
- **The base URL differs from custom deployments.** Model APIs live at `inference.baseten.co`; custom deployments live
  at `model-{id}.api.baseten.co`. Swapping one for the other will fail.
- **The `model=` field is meaningful here.** It picks the model. (On custom deployments it is a placeholder.)
- **Auth scheme differs by endpoint.** MAPI (OpenAI-compatible, this file) uses `Authorization: Bearer …`.
  Custom-deployment endpoints (`model-{id}.api.baseten.co`, see `inference-api.md`) use `Authorization: Api-Key …`.
  Don't generalize one to the other.
- **Prefix caching is on by default.** Requests sharing a prefix with a recent request will see cache behavior; see the
  pricing docs for how that maps to billing.

## Further reading

- Model APIs overview: <https://docs.baseten.co/inference/model-apis/overview>
- Chat completions reference: <https://docs.baseten.co/reference/inference-api/chat-completions>
- Structured outputs: <https://docs.baseten.co/inference/structured-outputs>
- Tool calling: <https://docs.baseten.co/inference/function-calling>
- Reasoning: <https://docs.baseten.co/inference/model-apis/reasoning>
- Rate limits and budgets: <https://docs.baseten.co/inference/model-apis/rate-limits-and-budgets>
- Custom deployments (when a managed model is not a fit): `inference-api.md`.
