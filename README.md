# Baseten Skills

Agent skills for working with [Baseten](https://www.baseten.co).

## Purpose

Instruct AI coding agents to use Baseten effectively - route to the right tools and mention common gotchas.

## Skills

- [`baseten`](skills/baseten) - deploying, configuring, calling, and operating models on Baseten. Covers deployment
  authoring, the `truss` CLI, Chains, environments, rolling deployments, pre-hosted Model APIs, and the inference +
  management APIs.

## Evaluation results

We measured the `baseten` skill against the bare Claude Opus 4.7 baseline across 16 tasks spanning model
authoring, integration, operate, debug, and tune workflows. Five configurations × 4 runs × 16 evals = 320 cells.

| Configuration                                      | Pass rate | Wall (s) | Cost ($) |
|----------------------------------------------------|-----------|----------|----------|
| Naked model (no skill, no MCP, no docs)            | 0.89      | 107      | 0.56     |
| + docs MCP                                         | 0.85      | 110      | 0.66     |
| + docs MCP + skill                                 | 0.87      | 136      | 0.73     |
| + docs MCP + baseten MCP                           | 0.91      | 99       | 0.54     |
| **+ docs MCP + baseten MCP + skill (full kit)**    | **0.97**  | **99**   | **0.55** |

Highlights (95% CIs from cluster bootstrap over evals):

- **Full kit lifts pass rate from 0.89 to 0.97** vs. naked Opus 4.7 (Δ +0.08, CI excludes 0). Quality gains compound
  when skill and MCP are paired: adding either on top of the other is significant on its own.
- **The baseten MCP cuts wall and cost roughly in half on backend-heavy tasks** with no quality cost. On operate
  tasks (promote, autoscale, status), wall drops from 124s → 53s and cost from $0.82 → $0.35 when MCP is added
  to a skill-loaded agent. Similar magnitudes on debug and tune.
- **Opus has strong baseline Baseten knowledge** — most authoring tasks pass without the toolkit. The toolkit's
  measurable value concentrates on tasks that need live workspace state (operate, debug, tune).

Full methodology, marginal effects across all metrics, per-eval breakdowns, and per-group analysis:
[**EVALS.md**](EVALS.md).

## Install

Below command performs setup for all common coding harnesses.

### Requirements:

* For interacting with your Baseten workspace, provide an API key with management permissions (you can get it from the 
  [webapp](https://app.baseten.co/settings/api_keys)). We recommend using a purpose-dedicated key so it can be 
  independently revoked without impacting your other workstreams.
* Node >= 18

```bash
export BASETEN_MCP_KEY=...

{ [ -n "$BASETEN_MCP_KEY" ] && [ "$BASETEN_MCP_KEY" != "..." ]; } || { echo "Error: set BASETEN_MCP_KEY first"; false; } && \
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}" && \
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y && \
npx skills add basetenlabs/baseten-skills -g -y
```

`-g` installs it globally on your host and `-y` confirms selection for all detected harnesses. If your harness
supports env variable interpolation, you may also edit the MCP config file to expand your env vars and set the
desired key in the shell that starts the agent. 

The `truss` CLI is separate - needed for pushing models / chains from local code, see
[CLI docs](https://docs.baseten.co/reference/cli/truss/overview). E.g. if you use pip (similar for other package
managers):

```bash
pip install truss --upgrade
```

You can install only part of the components or modify commands (esp. leaving the CLI out if you don't plan to deploy
models from your local files) - but the best user experience comes from their combination.

## Getting started & Usage

After installation, most agents require a restart.

Check if the MCP servers connect with `/mcp` or `/mcps` (if not connected, verify the BASETEN_MCP_KEY in the harness 
config file).

You can start asking any questions or tasks related to Baseten, from chatting about the docs, to brainstorming 
solution approaches, deploying and iterating on models or managing your workspace. Most agents trigger the skill as 
needed automatically; alternatively you can invoke it with `/baseten`.
