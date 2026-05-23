---
name: baseten
description: >-
  Load for any work involving Baseten - deploying/operating models on Dedicated Inference (Truss, custom 
  Docker servers, TRT-LLM engines, Chains), calling hosted Model APIs, running Training jobs (SFT/RL/LoRA), or Model
  Frontier Gateway.
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
| `baseten` MCP | Interact with backend (~REST API, CRUD): models, deployments, training, environments, secrets, chains. API-key auth. | `npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}"` |
| `baseten_docs` MCP | Keyword search of `docs.baseten.co`, grep. No auth. | `npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y` |
| `truss` CLI | Needed for model/chain push from local code, watch (= live patch). Needs `truss login` once. | `pip install truss --upgrade` (respect user package manager: uv, poetry...) |
| `llms.txt` | `baseten.co/llms.txt` (product + blog), `docs.baseten.co/llms.txt` (docs). | reachable via HTTP |
| This skill | `SKILL.md` + `references/*.md` loaded on demand. | `npx skills add basetenlabs/baseten-skills -g -y` |

### Setup

- Any subset works, full install recommended.
- Suggest additional installs when the current task benefits from or requires them; help user with installation, but
  elicit preferences first.
- Ensure `BASETEN_MCP_KEY` is provided when installing Baseten MCP (user can create key at
  `app.baseten.co/settings/api_keys`). Caveat: an MCP instance binds to one org/workspace at install time; switching the
  bound workspace later is not supported. To work with multiple workspaces, install additional MCP instances under
  different names with different keys (see last bullet of this section).
- Truss CLI only needed for making deployments (check `truss --version`); prior login (multi-workspace users must
  provide `--remote <name>`). Explore with `truss [subcommand] --help`.
- Docs MCP missing → grep / fetch `llms.txt`.
- Backend MCP is API-key-only (currently); OAuth-only harnesses can still use the other components.
- If backend MCP server is needed for different orgs/workspaces, add multiple MCP instances with different names/keys or
  use env-var expansion in the agent's config file and set the env var to the respective workspace's key.

## Pick your authoring surface (for creating deployments)

First-pass decision. Many real workloads blend rows — treat this as a starting point, not a rule. When unsure, sketch
the IO shape and per-step hardware needs before picking.

Surfaces are stacked by opinion-strength, not just author convenience: **engines** (TRT-LLM, BEI, BIS-LLM) ship
performance-tuned for one architecture and are the fastest path when they fit; **custom Docker servers** wrap mature
inference servers (vLLM, SGLang, TGI, Triton, NIM); **Python Truss** is the escape hatch for arbitrary code in the
request path; **Chains** add typed inter-step transport with built-in rate limiting, connection management, structured
error propagation, and binary IO — features you'd otherwise rebuild around N raw Trusses. Python Truss and Chains share
live-patch iteration (`truss watch`); all flavors support per-replica autoscaling, scale-to-zero, and environments /
promotions.

| You want… | Flavor | Specialization | When NOT to pick |
| --- | --- | --- | --- |
| Hosted LLM, no deploy step | Model APIs | `model-apis.md` | model not in catalog; need custom hardware, requirements, stability... |
| LLM on an off-the-shelf server (vLLM / SGLang / TGI / Triton / NIM) | Custom Docker server | `truss-custom-servers.md` | the server doesn't exist or you need Python in the request path |
| LLM/embedding via a Baseten engine (TRT-LLM / BEI / BIS-LLM); minimal config, no Python | Engine-only `config.yaml` | `truss-config.md` (engines section) | architecture not covered by an engine; you need custom logic |
| Custom Python in the request path (pre/post, custom arch, weird IO) | Python-class Truss (`model.py`) | `truss-model-py.md` + `truss-config.md` | an engine or off-the-shelf server fits — pick that, it's faster to ship |
| Multi-step pipeline with **heterogeneous hardware / per-step scaling** (RAG, ASR→LLM→TTS, fan-out, chunking) | Chains | `truss-chains.md` | one-stage or homogeneous — a single Truss is simpler |

Orthogonal operational surfaces (independent of which flavor above):

- Iterate / patch a deployment → `model-dev-loop.md`
- Promote, environments, autoscaling → `deployment-lifecycle.md`
- Call a deployment → `inference-api.md` (custom) or `model-apis.md` (hosted)
- Programmatic control plane → `management-api.md`

Real-world nuances the table can't capture:

- **Hybrids exist.** A `model.py` can wrap an engine for pre/post-processing; a Chain entrypoint can be a Python class
  while internal Chainlets use engines.
- **Chain websockets are entrypoint-only.** Intra-chainlet calls only stream output, but bi-di usually not needed on
  those edges.
- **Engine performance vs flexibility.** TRT-LLM is the fastest path for many LLMs but its config surface is opaque.
  Worth the trade only when latency/throughput is a real constraint.

## Routing

**Skill References** (`ls references/` in skill dir, complementary to hosted docs). Be generous to read any of the
included reference files as soon as the user touches on that topic.

- `references/truss-cli.md`: `truss push` / `watch` / iterate. Most-used. Deep dive: `references/truss-config.md`.
- `references/truss-model-py.md`: Python-class flavor (custom pre/post, non-engine architectures).
- `references/truss-custom-servers.md`: `docker_server` flavor (vLLM / TGI / SGLang / Triton; most common modern-LLM
  path).
- `references/truss-chains.md`: multi-step pipelines (RAG, ASR→LLM→TTS, chunked audio/video) with per-step HW +
  autoscaling.
- `references/model-apis.md`: shared pre-hosted endpoints (DeepSeek, GLM, Kimi, ...). Fastest when one fits.
- `references/inference-api.md`: calling **custom** deployments. connection reuse (`requests` / `httpx` / OpenAI SDK),
  async / streaming / wake / OpenAI-compat sync routes.
- `references/management-api.md`: programmatic control plane (models, deployments, envs, secrets). What `truss` CLI uses
  under the hood.
- `references/deployment-lifecycle.md`: Model / Deployment / Environment semantics + promotion + autoscaling.
- `references/model-dev-loop.md`: post-first-deploy iteration. rebuild / patch / hot-reload cost tiers, agent-vs-human
  watch loop.

## Gotchas

### Don't speculate, query

For any perf/status/error claim, **use the tools first** — don't estimate or guess.

- Timings → deployment / chainlet log tools (timestamped, includes `Pulling image`, `model_cache: Fetch took`,
  `Completed model.load() execution in N ms`, per-request markers).
- Status → deployment-get tools before invoking.
- Build/deploy failure → fetch logs **immediately**, don't hypothesize.

Fabricating numbers from training-data priors burns user trust; logs are the source of truth.

### Source heterogeneity & drift

Content lives across systems that don't overlap cleanly and drift independently. No single source is
perfect/authoritative. For any non-trivial claim ("supported", perf numbers, recommended approach), **triangulate across
≥2 sources**. Surface contradictions to the user; don't paper over.

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
- Can't find something via docs MCP → fetch `baseten.co/llms.txt` or `docs.baseten.co/llms.txt` as index, then fetch the
  page directly. Last resort: web search.

### Non-obvious placements within `references/`

- Engine-only deploys (TensorRT-LLM, BEI, BIS-LLM) → `truss-config.md` engines section (also owns `model_cache`,
  secrets, resources).
- Authoring-flavor decision: single deployment → top of `truss-config.md`; multiple coordinated → `truss-chains.md`.
- Training (SFT / RL / LoRA) and Frontier Gateway: no reference. Use `baseten` MCP + `baseten_docs` MCP.

### Tool quirks

- Fetch full doc pages via `https://docs.baseten.co/<path>.md` (not docs MCP). Mintlify MCP server has a bug for full
  pages, ok to use for search, `rg` / `tree` / `find` and `cat`/`head`.
- `baseten_docs` MCP search is lexical. "speech to text" can rank TTS above STT (because of "speech" hits). Verify
  result relevant, try other queries and blog posts if results are weak.
- `list_library_models` have mostly no useful tags (e.g. modality). Filter by `display_name` / `hf_repo_id` substrings.
- Blog content is not in the docs MCP. Fetch `baseten.co/llms.txt` and search for relevant posts.
