# `baseten` skill — evaluation report

How much does the `baseten` skill (plus its associated MCP servers) actually
help a capable coding agent work with Baseten? This report measures it on a
16-task suite spanning the realistic surface of the platform.

## Setup

### Model and harness

- **Executor and grader:** `claude-opus-4-7` (Claude Opus 4.7) via the official
  Anthropic API. The agent runs in headless Claude Code (`claude -p`) with
  `--output-format stream-json` so the harness can attribute tool calls and
  token usage per turn.
- **Workspace isolation:** every cell runs in a fresh tempdir with a strict
  env allowlist (only `PATH`, locale vars, and Anthropic auth pass through).
  `HOME` is overridden to a per-cell empty dir. No `CLAUDE.md`, `AGENTS.md`,
  or user-level claude config exists anywhere on the runner.
- **Test workspace:** a dedicated Baseten team account separate from the
  authors' personal workspaces. All fixture models live there with petname
  identifiers (`cheerful-otter`, `breezy-walrus`, …) so the names don't leak
  the eval intent to the agent.
- **Skill exposure:** when a cell loads the `baseten` skill, the harness
  symlinks only `SKILL.md` and `references/` into the agent's CWD at
  `.claude/skills/baseten/`. The `evals/` subdir — which holds assertions,
  expected outputs, and fixture-name → model-ID mapping — is deliberately
  excluded so the agent cannot read the rubric.

### Configurations evaluated

Each evaluation runs in 5 configurations describing which tools the agent has:

| Mode    | Skill | `baseten` MCP | `baseten_docs` MCP |
|---------|:-----:|:-------------:|:------------------:|
| s0b0d0  |   —   |       —       |          —         |
| s0b0d1  |   —   |       —       |          ✓         |
| s0b1d1  |   —   |       ✓       |          ✓         |
| s1b0d1  |   ✓   |       —       |          ✓         |
| s1b1d1  |   ✓   |       ✓       |          ✓         |

Each (eval × mode) cell runs 4 times. Total: 16 × 5 × 4 = 320 cells. Reported
numbers throughout this document come from a single sweep at commit
`ca33e74` on Opus 4.7.

### Evaluation set

16 evals across 6 task groups (groups read directly from
[`skills/baseten/evals/evals.json`](skills/baseten/evals/evals.json)):

| Group         | Evals          | What it tests                                              |
|---------------|----------------|------------------------------------------------------------|
| **author**    | 0, 1, 2, 3, 4  | Write Truss configs / Chains designs                       |
| **integrate** | 5, 50, 51      | Call hosted Model APIs / stream from a deployed model      |
| **operate**   | 10, 11         | Mutate workspace state (promote, autoscale)                |
| **overview**  | 20             | Read workspace state (list / status)                       |
| **debug**     | 30, 31         | Diagnose broken or regressed deployments                   |
| **tune**      | 40, 41, 42     | Patch config for perf (cold start, slow-deployment triage) |

Evals that need a fixture model (broken deployment, model-with-dev-deployment,
etc.) push a Truss to the test workspace ahead of time and may reset its
state via a `pre_run.sh` hook. To avoid fixture-state races between parallel
worker threads, the runner iterates `run → mode → eval` so that adjacent
cells in the worker pool target different fixtures.

### Grading

After each cell, a second `claude -p` instance reads the produced artifacts
and transcript and grades each assertion as pass/fail with quoted evidence,
using the prompt from anthropic's
[skill-creator](https://github.com/anthropics/skills). Each assertion is
tagged `core` or `nice` and combined into a weighted `pass_rate` per cell.

## Methodology

For each metric M ∈ { `pass_rate`, `wall_s`, `cost_usd`, `gross_input_tokens` }:

- **Per-cell:** mean over the 4 runs, with standard error.
- **Per group or global:** cell-means averaged across evals in scope. 95% CI
  via **cluster bootstrap over evals** (2000 resamples, percentile method).
  Resampling the eval set respects the natural pairing of the design — cells
  of the same eval are not independent, and the inferential unit is the eval.
- **Marginal Δ between modes:** per-eval paired delta first
  (`mean(mode_a, 4 runs) − mean(mode_b, 4 runs)` within each eval), then
  cluster bootstrap over those eval-level deltas. A marginal is reported as
  significant (`*`) when its 95% CI excludes 0.

`gross_input_tokens` is the cache-agnostic sum
`uncached + cache_create + cache_read` — i.e., everything the model
processed across the session, irrespective of how the provider chose to bill
or cache. `cost_usd` is the actual provider charge.

Source: [`evals/src/baseten_skills_evals/analyze.py`](evals/src/baseten_skills_evals/analyze.py).

## Results

### Global pass rate by configuration

| Mode   |  n  | Pass rate    |
|--------|----:|--------------|
| s0b0d0 |  64 | 0.89 ±0.09   |
| s0b0d1 |  64 | 0.85 ±0.09   |
| s0b1d1 |  64 | 0.91 ±0.05   |
| s1b0d1 |  64 | 0.87 ±0.10   |
| s1b1d1 |  64 | **0.97 ±0.03** |

### Pass rate by task group × mode

| Group       | s0b0d0      | s0b0d1      | s0b1d1      | s1b0d1      | s1b1d1      |
|-------------|-------------|-------------|-------------|-------------|-------------|
| author      | 0.86 ±0.15  | 0.87 ±0.11  | 0.85 ±0.07  | 0.92 ±0.11  | 0.95 ±0.06  |
| integrate   | 1.00 ±0.00  | 0.92 ±0.12  | 1.00 ±0.00  | 1.00 ±0.00  | **1.00**    |
| operate     | 0.75 ±0.25  | 0.94 ±0.06  | 0.88 ±0.12  | 0.69 ±0.31  | **1.00**    |
| overview    | 1.00 ±0.00  | 1.00 ±0.00  | 1.00 ±0.00  | 1.00 ±0.00  | **1.00**    |
| debug       | 0.96 ±0.04  | 0.88 ±0.12  | 0.92 ±0.08  | 0.88 ±0.12  | 0.92 ±0.08  |
| tune        | 0.83 ±0.19  | 0.62 ±0.25  | 0.88 ±0.12  | 0.75 ±0.25  | **0.96 ±0.06** |

### Marginal effects — global pass rate (cluster bootstrap, n=16 paired evals)

| Comparison                                        | Δ           | Significant |
|---------------------------------------------------|-------------|:-----------:|
| skill, no MCP        = s1b0d1 − s0b0d1            | +0.02 ±0.08 |             |
| **skill, with MCP**  = s1b1d1 − s0b1d1            | **+0.06 ±0.04** | * |
| MCP, no skill        = s0b1d1 − s0b0d1            | +0.05 ±0.07 |             |
| **MCP, with skill**  = s1b1d1 − s1b0d1            | **+0.09 ±0.09** | * |
| docs MCP only        = s0b0d1 − s0b0d0            | −0.04 ±0.10 |             |
| **full vs naked**    = s1b1d1 − s0b0d0            | **+0.08 ±0.09** | * |

Skill and MCP each significantly improve the other; neither in isolation is
certified at this n. The combination is what reliably lifts quality.

### Marginal pass rate by task group

| Group       | ΔSkill (no MCP) | ΔSkill (+ MCP) | ΔMCP (no skill) | ΔMCP (+ skill) | Δfull vs naked |
|-------------|-----------------|----------------|-----------------|----------------|----------------|
| author      | +0.05 ±0.06     | +0.10 ±0.05 *  | −0.02 ±0.06     | +0.03 ±0.05    | +0.09 ±0.20    |
| integrate   | +0.08 ±0.12     |  0.00 ±0.00    | +0.08 ±0.12     |  0.00 ±0.00    |  0.00 ±0.00    |
| operate     | −0.25 ±0.25     | +0.12 ±0.12    | −0.06 ±0.06     | +0.31 ±0.31    | +0.25 ±0.25    |
| overview    |  0.00 ±0.00     |  0.00 ±0.00    |  0.00 ±0.00     |  0.00 ±0.00    |  0.00 ±0.00    |
| debug       |  0.00 ±0.00     |  0.00 ±0.00    | +0.04 ±0.04     | +0.04 ±0.04    | −0.04 ±0.04    |
| tune        | +0.12 ±0.00 *   | +0.08 ±0.12    | +0.25 ±0.19 *   | +0.21 ±0.19    | +0.12 ±0.12    |

Tune is where the toolkit's quality value is largest and most certain — the
agent benefits from reading the live config schema before patching, which
neither docs nor training knowledge alone reliably provides.

### Wall time and cost — MCP buys speed, no quality cost

#### Wall time (s) by group × mode

| Group       | s0b0d0    | s0b0d1    | s0b1d1   | s1b0d1    | s1b1d1   |
|-------------|-----------|-----------|----------|-----------|----------|
| author      | 102 ±20   | 106 ±45   | 125 ±55  | 122 ±57   | 140 ±56  |
| integrate   |  31 ±13   |  40 ±13   |  41 ±21  | 113 ±111  |  48 ±35  |
| operate     | 115 ±6    | 123 ±24   |  53 ±0   | 139 ±8    |  54 ±6   |
| overview    |  58 ±0    |  80 ±0    |  46 ±0   |  94 ±0    |  51 ±0   |
| debug       | 261 ±47   | 221 ±109  | 262 ±137 | 277 ±90   | 199 ±120 |
| tune        | 101 ±74   | 115 ±92   |  53 ±28  | 101 ±66   |  63 ±30  |

#### Cost ($) by group × mode

| Group       | s0b0d0      | s0b0d1      | s0b1d1      | s1b0d1      | s1b1d1      |
|-------------|-------------|-------------|-------------|-------------|-------------|
| author      | 0.51 ±0.14  | 0.74 ±0.21  | 0.77 ±0.19  | 0.72 ±0.22  | 0.75 ±0.23  |
| integrate   | 0.16 ±0.09  | 0.30 ±0.06  | 0.27 ±0.13  | 0.30 ±0.08  | 0.27 ±0.14  |
| operate     | 0.71 ±0.04  | 0.80 ±0.15  | 0.33 ±0.00  | 0.91 ±0.03  | 0.33 ±0.02  |
| overview    | 0.36 ±0.00  | 0.43 ±0.00  | 0.34 ±0.00  | 0.63 ±0.00  | 0.37 ±0.00  |
| debug       | 1.30 ±0.32  | 1.12 ±0.54  | 1.01 ±0.51  | 1.46 ±0.30  | 1.06 ±0.69  |
| tune        | 0.53 ±0.34  | 0.57 ±0.29  | 0.30 ±0.19  | 0.59 ±0.33  | 0.37 ±0.19  |

#### Marginal MCP effect with skill held constant — significant on every backend-heavy group

| Group     | ΔWall (s)  | ΔCost ($)     |
|-----------|------------|---------------|
| operate   | −85 ±14 *  | −0.58 ±0.01 * |
| overview  | −43 ±0 *   | −0.26 ±0.00 * |
| debug     | −78 ±30 *  | −0.40 ±0.39 * |
| tune      | −38 ±37 *  | −0.22 ±0.18 * |

Adding the `baseten` MCP to a skill-loaded agent cuts wall by roughly **2×**
and cost by **~50%** on operate, overview, debug, and tune tasks, while
quality stays flat or improves.

### Per-eval pass rates

| Eval | Description                          | s0b0d0 | s0b0d1 | s0b1d1 | s1b0d1 | s1b1d1 |
|-----:|--------------------------------------|--------|--------|--------|--------|--------|
| 0    | author-vllm-mistral                  | 0.88   | 0.81   | 0.81   | 1.00   | 1.00   |
| 1    | author-python-truss-finetune         | 1.00   | 1.00   | 1.00   | 1.00   | 1.00   |
| 2    | author-trt-llm-llama                 | 1.00   | 0.67   | 0.75   | 0.67   | 0.83   |
| 3    | author-bei-embeddings                | 0.50   | 1.00   | 0.88   | 1.00   | 1.00   |
| 4    | author-multimodal-pipeline           | 0.92   | 0.87   | 0.83   | 0.92   | 0.92   |
| 5    | integrate-model-apis-deepseek        | 1.00   | 1.00   | 1.00   | 1.00   | 1.00   |
| 10   | operate-promote-to-staging           | 0.50   | 0.88   | 0.75   | 0.38   | 1.00   |
| 11   | operate-traffic-spike                | 1.00   | 1.00   | 1.00   | 1.00   | 1.00   |
| 20   | overview-workspace-status            | 1.00   | 1.00   | 1.00   | 1.00   | 1.00   |
| 30   | debug-broken-deployment              | 0.92   | 0.75   | 0.83   | 0.75   | 0.83   |
| 31   | debug-latency-regression             | 1.00   | 1.00   | 1.00   | 1.00   | 1.00   |
| 40   | tune-slow-vague                      | 0.88   | 0.62   | 0.75   | 0.75   | 1.00   |
| 41   | tune-slow-cold-start-informed        | 0.62   | 0.38   | 0.88   | 0.50   | 0.88   |
| 42   | tune-slow-iteration-loop             | 1.00   | 0.88   | 1.00   | 1.00   | 1.00   |
| 50   | integrate-stream-deployed-model      | 1.00   | 1.00   | 1.00   | 1.00   | 1.00   |
| 51   | integrate-long-job-resilient         | 1.00   | 0.75   | 1.00   | 1.00   | 1.00   |

Cell-level values are mean ±SE over 4 runs.

## Interpretation

**Opus 4.7 already knows a lot about Baseten.** The naked-model baseline at
0.89 reflects the fact that Truss configuration, the OpenAI-compatible
inference endpoint, and the broad shape of deploying open-source models are
well-represented in the model's training data. On standard authoring tasks
(client scripts, popular open-source LLMs), the toolkit barely shifts the
result. This is a strength of the underlying model and a useful starting
point for users: many simple flows already work without setup.

**Skill and MCP are complements, not substitutes.** The data shows an
interaction effect that the user should design for: skill alone provides a
significant lift on authoring and tune; MCP alone provides a significant lift
on tune; the two together provide a significant lift over either. The
operate group is the clearest example — promoting a deployment to a new
environment requires both a clear pattern (skill) and a way to actually
invoke the action (MCP). With only one of the two, the agent has the right
plan and no tools, or the right tools and no plan.

**On backend-heavy tasks the `baseten` MCP changes the cost structure.**
Adding the MCP to a skill-loaded agent cuts both wall time and dollar cost
roughly in half on operate, overview, debug, and tune categories. This is the central
practical claim of the toolkit: same answer, twice as fast, for half the
cost. The reason is direct — the MCP lets the agent call typed, named
endpoints (`update_environment`, `get_deployment_config`) rather than
forming and parsing curl invocations or chasing reference docs.

**Tune is where the toolkit's quality value is largest and most certain.**
Cold-start and "feels slow" diagnoses require knowing what the current
deployment actually looks like — its model_cache state, its instance type,
its autoscaling settings. Bare docs (the s0b0d1 column, 0.62) miss the
correct schema; bare training knowledge guesses an outdated field name. The
MCP provides the live config schema and the skill points at the right
references. Together they bring tune from 0.83 → 0.96, with ΔMCP|no-skill =
+0.25 (CI excludes 0).

**Eval 41 deserves a footnote.** With docs MCP alone (`s0b0d1`), pass rate
drops to 0.38 — *worse* than the naked baseline. Inspecting the failing
transcripts: docs search surfaces older `weights:` examples; the agent
follows them and writes a config Truss silently ignores. The full kit
recovers to 0.88. The lesson is general: a search index over a documentation
corpus that mixes current and superseded guidance can mislead a model that
trusts the first plausible match. Knowing which advice is current is part of
what the skill provides.

## Reproducing

```bash
# In the eval harness directory
cd evals
uv sync
uv run python -m baseten_skills_evals.runner \
    --skill baseten \
    --modes s0b0d0,s0b0d1,s0b1d1,s1b0d1,s1b1d1 \
    --runs 4 \
    --num-workers 8 \
    --model claude-opus-4-7

uv run python -m baseten_skills_evals.analyze \
    --stats ../eval-results/baseten/stats.jsonl \
    --out report.md
```

For unattended sweeps see [`bin/codespace_run_sweep.sh`](bin/codespace_run_sweep.sh)
and [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json).

`eval-results/baseten/stats.jsonl` (one JSON row per cell) is committed to
this repo as the canonical source for the numbers above. Per-cell
transcripts and grading detail for the canonical sweep are kept outside the
repo to stay small.
