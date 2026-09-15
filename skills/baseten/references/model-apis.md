# Baseten Model APIs

Model APIs are Baseten's managed catalog of pre-hosted LLMs (DeepSeek, GLM, Kimi, and others). OpenAI-compatible, with
an Anthropic Messages API in beta. No deployment step. Pay per million tokens. Pick this over a custom Truss deployment
whenever a supported model does the job; you avoid packaging, infra choices, and scaling decisions entirely.

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

Discover current slugs with `/v1/models` or `baseten model-api list` before choosing a model. A 404 means model not
found; check the slug and current catalog rather than assuming workspace enablement is the cause. Consult
<https://docs.baseten.co/inference/model-apis/deprecation> when a previously working model disappears.

## Call pattern

Use the official OpenAI SDK pointed at the Baseten base URL:

```python
import os
from openai import OpenAI

# Reuse this client for all calls in the process (do not construct per request).
client = OpenAI(
    base_url="https://inference.baseten.co/v1",
    api_key=os.environ["BASETEN_API_KEY"],
)

response = client.chat.completions.create(
    model="zai-org/GLM-5.2",
    messages=[
        {"role": "system", "content": "You are a concise technical writer."},
        {"role": "user", "content": "What is gradient descent?"},
    ],
)
print(response.choices[0].message.content)
```

Use a current catalog slug for `model=`. On Model APIs it selects the hosted model. On a custom deployment it must match
the name served by that deployment; see `inference-api.md`.

Create the `OpenAI` client once per process (module scope, app singleton, or dependency injection) and reuse it for
every `chat.completions.create` call. The SDK pools HTTP connections via `httpx` under the hood; constructing a new
`OpenAI()` per request discards that pooling and adds TLS handshake latency on each call. For `requests` or `httpx`
against custom deployments, see **Connection reuse** in `inference-api.md`.

## Streaming

Same as the OpenAI SDK:

```python
stream = client.chat.completions.create(
    model="zai-org/GLM-5.2",
    messages=[{"role": "user", "content": "Write a haiku."}],
    stream=True,
)
for chunk in stream:
    if not chunk.choices:
        continue
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="")
```

## Anthropic Messages API

Use this when the caller needs the Anthropic SDK. It is beta; the docs recommend OpenAI Chat Completions for production.
The Anthropic base URL has no `/v1` suffix. Override `Authorization` because the SDK's default `x-api-key` header alone
does not authenticate to Baseten.

```python
import os
import anthropic

key = os.environ["BASETEN_API_KEY"]
client = anthropic.Anthropic(
    base_url="https://inference.baseten.co",
    api_key=key,
    default_headers={"Authorization": f"Bearer {key}"},
)
response = client.messages.create(
    model="zai-org/GLM-5.2",
    max_tokens=1024,
    messages=[{"role": "user", "content": "What is gradient descent?"}],
)
for block in response.content:
    if block.type == "text":
        print(block.text)
```

Source: <https://docs.baseten.co/inference/model-apis/overview#use-the-anthropic-sdk>.

## Migrating from OpenAI

Three changes to existing OpenAI code:

1. API key → a Baseten key.
2. `base_url` → `https://inference.baseten.co/v1`.
3. Model name → a Baseten model slug.

Everything else (tool calling, structured outputs, streaming, vision where supported) is the same API shape.

## Feature support

- **Tool calling**: supported by all models.
- **Structured outputs**: supported by all currently listed models; check the live matrix when selecting a model.
- **Reasoning / extended thinking**: model-specific (see <https://docs.baseten.co/inference/model-apis/reasoning>).
- **Vision**: model-specific.
- **Audio, `top_p`, `top_k`**: model-specific. Check the current feature table rather than assuming family-wide support.

Current per-model support matrix is at <https://docs.baseten.co/inference/model-apis/overview#feature-support>.

## Listing models

```
curl https://inference.baseten.co/v1/models \
  -H "Authorization: Bearer $BASETEN_API_KEY"
```

Returns current slugs with metadata (context lengths, pricing, features).

## Pricing

Pricing moves; defer to the current table at <https://docs.baseten.co/inference/model-apis/pricing-and-limits>.

## Error codes

Standard HTTP:

| Code | Meaning |
| --- | --- |
| 400 | Invalid request (check parameters) |
| 401 | Invalid or missing API key |
| 402 | Payment required |
| 404 | Model not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Gotchas

- **Catalogs change.** Verify the requested slug before invoking it and report deprecation without silently substituting
  a model.
- **The base URL differs from custom deployments.** Model APIs live at `inference.baseten.co`; custom deployments live
  at `model-{id}.api.baseten.co`. Swapping one for the other will fail.
- **Use the right model name.** Model APIs require a catalog slug; custom deployments require the server's served name.
- **Authentication:** use `Authorization: Bearer …`, including with the Anthropic SDK. Custom-deployment and management
  APIs also support Bearer; existing legacy `Api-Key` clients remain supported.
- **Prefix caching is on by default.** Requests sharing a prefix with a recent request will see cache behavior; see the
  pricing docs for how that maps to billing.
- **Reuse the OpenAI client.** A new `OpenAI()` per request loses connection pooling; keep one client per process for
  agents and high-QPS loops.

## Further reading

- Model APIs overview: <https://docs.baseten.co/inference/model-apis/overview>
- Chat completions reference: <https://docs.baseten.co/reference/inference-api/chat-completions>
- Structured outputs: <https://docs.baseten.co/inference/structured-outputs>
- Tool calling: <https://docs.baseten.co/inference/function-calling>
- Reasoning: <https://docs.baseten.co/inference/model-apis/reasoning>
- Rate limits and budgets: <https://docs.baseten.co/inference/model-apis/pricing-and-limits>
- Custom deployments (when a managed model is not a fit): `inference-api.md`.
