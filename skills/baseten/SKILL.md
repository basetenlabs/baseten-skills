---
name: baseten
description: Skill for anything Baseten — deploying/operating models on Dedicated Inference (Truss, custom Docker servers, TRT LLM engines, Chains), calling pre-hosted Model APIs, running Training jobs (SFT/RL/LoRA), or Model Frontier Gateway.
---

# Baseten

Production AI inference platform — serve and scale open-source, custom, and fine-tuned models with the fastest runtimes, cross-cloud HA, and seamless developer workflows.

## Products

- **Dedicated Inference** — deploy any model, performance-optimized + horizontally scaled. Authored as auto-wrapped Truss server, custom Docker server, or compound/orchestrated deployment via Chains.
- **Model APIs** — pre-optimized hosted APIs for popular models. Path to graduate to dedicated.
- **Training** — managed training + fine-tuning (SFT, RL, LoRA). Multi-node, 1T+ params, 10TB+ datasets, 256k seq lengths on H100/H200/B200. BYO scripts or recipes. W&B / HF / S3.
- **Frontier Gateway** — operate your own foundation model B2C.

## Agent DX Toolkit

| Component | Provides | Install |
|---|---|---|
| `baseten` MCP | Backend (≈REST API): models, deployments, training, environments, secrets, chains. API-key auth. | `npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_API_KEY}"` |
| `baseten_docs` MCP | Semantic search of `docs.baseten.co`. No auth. | `npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y` |
| `truss` CLI | Needed for model/chain push from local code, watch (= live patch). Needs `truss login`. | `pip install truss --upgrade` (respect user package manager: uv, poetry...) |
| `llms.txt` | `baseten.co/llms.txt` (product + blog), `docs.baseten.co/llms.txt` (docs). HTTP, no auth. | reachable via HTTP |
| This skill | `SKILL.md` + `references/*.md` loaded on demand. | `npx add-skill basetenlabs/baseten-skills -g -y` |

API key from `app.baseten.co/settings/api_keys` (ask the user to create key).

### Setup

- Any subset works, but with varying features.
- Suggest additional installs when the current task benefits from them; help user run command, but elicit 
  preferences first.
- CLI via `truss --version`; prior login (multi-workspace users will need `--remote <name>`).
- Docs MCP missing → grep / fetch `llms.txt`.
- Backend MCP is API-key-only (currently) — OAuth-only harnesses can still use the other components.

## Routing

**Backend / local ops:**

- `baseten` MCP — interact with backend, manage, observe
- `truss` CLI — push models/chains from local files / watch (~ live patch). Use `truss [subcommand] --help` to explore

**Per-task guides** (`ls references/`, complementary to hosted docs):

- `references/truss-cli.md` — `truss push` / `watch` / iterate. Most-used. Deep dive: `references/truss-config.md`.
- `references/truss-model-py.md` — Python-class flavor (custom pre/post, non-engine architectures).
- `references/truss-custom-servers.md` — `docker_server` flavor (vLLM / TGI / SGLang / Triton — most common modern-LLM path).
- `references/truss-chains.md` — multi-step pipelines (RAG, ASR→LLM→TTS, chunked audio/video) with per-step HW + autoscaling.
- `references/model-apis.md` — shared pre-hosted endpoints (DeepSeek, GLM, Kimi, …). Fastest when one fits.
- `references/inference-api.md` — calling **custom** deployments: async / streaming / wake / OpenAI-compat sync routes.
- `references/management-api.md` — programmatic control plane (models, deployments, envs, secrets). What `truss` CLI uses under the hood.
- `references/deployment-lifecycle.md` — Model / Deployment / Environment semantics + promotion + autoscaling.
- `references/model-dev-loop.md` — post-first-deploy iteration: rebuild / patch / hot-reload cost tiers, agent-vs-human watch loop.

## Gotchas

High-signal section, accreted from real failures. Grow over time rather than rewriting earlier sections.

### Source heterogeneity & drift

Content lives across systems that don't overlap cleanly and drift independently. No single source is authoritative; for any non-trivial claim ("supported", perf numbers, recommended approach), **triangulate across ≥2 sources**. Surface contradictions to the user rather than papering over them.

| Source | Strength | Gap / quirk |
|---|---|---|
| `baseten_docs` MCP / `docs.baseten.co` | API specs, protocol details, knobs | Lags product; no perf numbers |
| `baseten.co/library/<id>` (marketing) | Flagship managed models, perf claims | Some entries are sales-gated, not self-serve |
| `baseten` MCP `list_library_models` | What's actually one-click API-deployable | Doesn't include every marketing-library entry; sparse tags |
| `baseten.co/blog/` | Concrete latency / cost / vs-competitor numbers | Unstructured; **not in** docs MCP — discover via `baseten.co/llms.txt` |
| `baseten.co/solutions/...` | High-level pitch | May describe flagship features that need a Baseten engagement |
| `truss-examples` GitHub repo | Working code patterns | **Often outdated / drifted from current API.** Consult with caution, as a last resort. Don't sink time fixing broken examples — pick another path. |

- Library page exists but model absent from `list_library_models` → likely managed/flagship; tell the user it may need engagement.
- Perf numbers found only in a blog → cite as blog claim, not as official spec.
- If two sources disagree → tell the user; let them decide which to trust.
- Can't find something via docs MCP → `WebFetch` `baseten.co/llms.txt` or `docs.baseten.co/llms.txt` for an index, then fetch the page directly.

### Non-obvious placements within `references/`

- Engine-only deploys (TensorRT-LLM, BEI, BIS-LLM) → `truss-config.md` engines section (also owns `model_cache`, secrets, resources).
- Authoring-flavor decision: single deployment → top of `truss-config.md`; multiple coordinated → `truss-chains.md`.
- Training (SFT / RL / LoRA) and Frontier Gateway: no reference — use `baseten` MCP + `baseten_docs` MCP.

### Tool quirks

- **`baseten_docs` MCP `cat`/`head` duplicates content.** Long `.mdx` files come back with cumulative-context preamble — the same section body repeated many times in one read. Use `rg -n <pattern>` for targeted reads; avoid full `cat` on long pages. If a local `docs/` checkout exists, read `.mdx` from disk instead.
- **`baseten_docs` MCP search is lexical.** "speech to text" can rank TTS above STT. When modality matters, query by path (`rg -l streaming-transcription /reference`) or use specific jargon.
- **`list_library_models` tags are sparse** (mostly empty or `openai-compatible`) — no modality tags. Filter by `display_name` / `hf_repo_id` substrings.
- **Blog content is not in the docs MCP.** Fetch `baseten.co/llms.txt` to enumerate blog URLs by topic, then `WebFetch` the post.
