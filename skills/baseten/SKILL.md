---
name: baseten
description:
  Skill for anything Baseten - deploying/operating models on Dedicated Inference (Truss, custom Docker servers, TRT-LLM
  engines, Chains), calling pre-hosted Model APIs, running Training jobs (SFT/RL/LoRA), or Model Frontier Gateway.
---

## Baseten Product Overview

Production AI inference platform - serve and scale open-source, custom, and fine-tuned models with the fastest runtimes,
cross-cloud HA, and seamless developer workflows.

- **Dedicated Inference** - deploy any model, performance-optimized + horizontally scaled. Authored as auto-wrapped
  Truss server, custom Docker server, or compound/orchestrated deployment via Chains.
- **Model APIs** - pre-optimized hosted APIs for popular models. Path to graduate to dedicated.
- **Training** - managed training + fine-tuning (SFT, RL, LoRA). Multi-node, 1T+ params, 10TB+ datasets, 256k seq
  lengths on H100/H200/B200. BYO scripts or recipes. W&B / HF / S3.
- **Frontier Gateway** - operate your own foundation model B2C.

## Agent DX Toolkit

| Component | Provides | Install |
| --- | --- | --- |
| `baseten` MCP | Backend (~REST API): models, deployments, training, environments, secrets, chains. API-key auth. | `npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}"` |
| `baseten_docs` MCP | Semantic search of `docs.baseten.co`. No auth. | `npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y` |
| `truss` CLI | Needed for model/chain push from local code, watch (= live patch). Needs `truss login` once. | `pip install truss --upgrade` (respect user package manager: uv, poetry...) |
| `llms.txt` | `baseten.co/llms.txt` (product + blog), `docs.baseten.co/llms.txt` (docs). | reachable via HTTP |
| This skill | `SKILL.md` + `references/*.md` loaded on demand. | `npx add-skill basetenlabs/baseten-skills -g -y` |

### Setup

- Any subset works, the more the better.
- Suggest additional installs when the current task benefits from them; help user run command, but elicit preferences
  first.
- Make sure `BASETEN_MCP_KEY` is set/provided when installing Baseten MCP (user can create new key at
  `app.baseten.co/settings/api_keys`). Caveat: this binds the MCP to an org/workspace.
- If backend MCP server is needed for different workspaces, add multiple MCP instances with different names/keys or use
  env-var expansion in the agent's config file and set the env var to the respective workspace's key.
- CLI via `truss --version`; prior login (multi-workspace users must provide `--remote <name>`).
- Docs MCP missing → grep / fetch `llms.txt`.
- Backend MCP is API-key-only (currently); OAuth-only harnesses can still use the other components.

## Routing

**Backend / local ops:**

- `baseten` MCP: interact with backend, list, manage, observe.
- `truss` CLI: push models/chains from local files / watch (~ live patch). `truss [subcommand] --help`.

**Skill References** (`ls references/` in skill dir, complementary to hosted docs):

- `references/truss-cli.md`: `truss push` / `watch` / iterate. Most-used. Deep dive: `references/truss-config.md`.
- `references/truss-model-py.md`: Python-class flavor (custom pre/post, non-engine architectures).
- `references/truss-custom-servers.md`: `docker_server` flavor (vLLM / TGI / SGLang / Triton; most common modern-LLM
  path).
- `references/truss-chains.md`: multi-step pipelines (RAG, ASR→LLM→TTS, chunked audio/video) with per-step HW +
  autoscaling.
- `references/model-apis.md`: shared pre-hosted endpoints (DeepSeek, GLM, Kimi, ...). Fastest when one fits.
- `references/inference-api.md`: calling **custom** deployments. async / streaming / wake / OpenAI-compat sync routes.
- `references/management-api.md`: programmatic control plane (models, deployments, envs, secrets). What `truss` CLI uses
  under the hood.
- `references/deployment-lifecycle.md`: Model / Deployment / Environment semantics + promotion + autoscaling.
- `references/model-dev-loop.md`: post-first-deploy iteration. rebuild / patch / hot-reload cost tiers, agent-vs-human
  watch loop.

## Gotchas

### Source heterogeneity & drift

Content lives across systems that don't overlap cleanly and drift independently. No single source is authoritative; for
any non-trivial claim ("supported", perf numbers, recommended approach), **triangulate across ≥2 sources**. Surface
contradictions to the user; don't paper over.

| Source | Strength | Gap / quirk |
| --- | --- | --- |
| `baseten_docs` MCP / `docs.baseten.co` | API specs, protocol details, knobs | Lags product; no perf numbers |
| `baseten.co/library/<id>` (marketing) | Flagship managed models, perf claims | Some entries are sales-gated, not self-serve |
| `baseten` MCP `list_library_models` | What's actually one-click API-deployable | Doesn't include every marketing-library entry; lacking tags |
| `baseten.co/blog/` | Concrete latency / cost / vs-competitor numbers, technical deep dives | Unstructured; **not in** docs MCP. Discover via `baseten.co/llms.txt` |
| `baseten.co/solutions/...` | High-level pitch | May describe flagship features that need a Baseten engagement |
| `truss-examples` GitHub repo | Working code patterns | **Often outdated / broken / drifted.** Consult with caution, last resort. Might need fixups before deploy works. |

- Library page exists but model absent from `list_library_models` → likely managed/flagship; tell the user it may need
  to reach out to Baseten support.
- Perf numbers found only in a blog → cite as blog claim.
- Two sources disagree: try to determine which is newer/more accurate, otherwise flag uncertainty, let user decide.
- Can't find something via docs MCP → fetch `baseten.co/llms.txt` or `docs.baseten.co/llms.txt` as index, then fetch the
  page directly.

### Non-obvious placements within `references/`

- Engine-only deploys (TensorRT-LLM, BEI, BIS-LLM) → `truss-config.md` engines section (also owns `model_cache`,
  secrets, resources).
- Authoring-flavor decision: single deployment → top of `truss-config.md`; multiple coordinated → `truss-chains.md`.
- Training (SFT / RL / LoRA) and Frontier Gateway: no reference. Use `baseten` MCP + `baseten_docs` MCP.

### Tool quirks

- **Full doc pages: `curl https://docs.baseten.co/<path>.md`, not the docs MCP.** Any docs page is served as rendered
  markdown at that URL (no auth). Faster, ~half the bytes, bug-free. The docs MCP `cat`/`head` on certain `.mdx`
  **inflates content quadratically**. Use the MCP filesystem tool only for `rg` / `tree` / `find` discovery when you
  don't know the path.
- **`baseten_docs` MCP search is lexical.** "speech to text" can rank TTS above STT (because of "speech" hits). Be
  cautious.
- **`list_library_models` tags are sparse** (mostly empty or `openai-compatible`); no modality tags. Filter by
  `display_name` / `hf_repo_id` substrings.
- **Blog content is not in the docs MCP.** Fetch `baseten.co/llms.txt` to enumerate blog URLs by topic, then `WebFetch`
  the post.
