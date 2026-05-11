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

## Toolkit

| Component | Provides | Add |
|---|---|---|
| `baseten` MCP | Backend (≈REST API): models, deployments, training, environments, secrets, chains. API-key auth. | `npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_API_KEY}"` |
| `baseten_docs` MCP | Semantic search of `docs.baseten.co`. No auth. | `npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y` |
| `truss` CLI | Push from local code, watch dev, logs. Needs `truss login`. | `pip install truss --upgrade` (respect user PM: uv, poetry, asdf) |
| `llms.txt` | `baseten.co/llms.txt` (product + blog), `docs.baseten.co/llms.txt` (docs). HTTP, no auth. | n/a |
| This skill | `SKILL.md` + `references/*.md` loaded on demand. | `npx add-skill basetenlabs/baseten-skills -g -y` |

API key: `app.baseten.co/settings/api_keys` (human UI — ask the user to fetch it).

### Behavior

- Any subset works. Use what the harness exposes; suggest installs only when the current task needs them; don't re-suggest if declined this session.
- Probes are harness-specific: MCP tools appear as `mcp__baseten_…` / `mcp__baseten_docs_…` in the tool list; CLI via `truss --version`; prior login via `~/.trussrc`.
- Backend MCP missing → fall back to direct REST over HTTPS with `Authorization: Api-Key $BASETEN_API_KEY`.
- Docs MCP missing → grep / fetch `llms.txt`.
- Backend MCP is API-key-only — OAuth-only harnesses can still use docs MCP.
- Never inline a literal API key in tool calls or logs. Always reference `$BASETEN_API_KEY`.

### Update check

Compare local skill commit (per-harness install path under `~/.<harness>/skills/baseten/`) against upstream `main` via `git ls-remote https://github.com/basetenlabs/baseten-skills HEAD`. Behind → `npx add-skill update -y basetenlabs/baseten-skills`, then ask user to restart the session so the new content loads. Equal or undeterminable → silent.

## Routing

- Product / blog → `baseten.co/llms.txt`.
- Technical docs → `baseten_docs` MCP, else `docs.baseten.co/llms.txt`.
- Backend ops (deployments, training, environments, …) → `baseten` MCP, else direct REST.
- Local push/patch → `truss` CLI.
- Per-task playbooks → `references/*.md` (table populated next).
