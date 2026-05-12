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

**Per-task guides:** `ls references/` in this skill directory. These are complementary (partially redundant) to hosted
docs (MCP / website).

Common entry points:

- `references/truss-cli.md` — `truss push` / `watch` / iterate. Most-used file for model development. Deep dive in 
  `references/truss-config.md`.
- `references/model-apis.md` — fastest path when a shared endpoint model fits the use case.
- `references/deployment-lifecycle.md` — Model / Deployment / Environment semantics + promotion + autoscaling.
- `references/truss-chains.md` — Chains: compound AI, orchestration, multi-step / multi-model pipelines (RAG, 
  transcribe → LLM → TTS, chunked audio/video) where each step has its own hardware, deps, and autoscaling.
- `references/model-dev-loop.md` — workflow for iterating on an existing Truss/Chain after the first deploy: 
  cost tiers (rebuild / patch / hot-reload), agent-vs-human watch-loop framing, hot-reload admissibility.

Non-obvious placements:

- Engine-only deploys (TensorRT-LLM, BEI, BIS-LLM) live in `references/truss-config.md` (engines section), not a 
  dedicated file. Same file owns `model_cache`, secrets, and resources.
- Authoring-flavor decision — for a single deployment (Python class / custom Docker server / engine-only):
  top of `references/truss-config.md`. For multiple coordinated deployments: `references/truss-chains.md`.
- Async / streaming / wake / OpenAI-compat sync routes for *custom* deployments — `inference-api.md` (not 
  `model-apis.md` = shared endpoints).
- `docker_server` custom-server flavor (vLLM / TGI / SGLang / Triton — most common path for modern LLMs) — `references/truss-custom-servers.md`.
- Training jobs (SFT / RL / LoRA) and Frontier Gateway — no reference; use `baseten` MCP + `baseten_docs` MCP.
