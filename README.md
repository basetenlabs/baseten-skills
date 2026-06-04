# Baseten Skills

Agent DX bundle — [`baseten` skill](skills/baseten/) tuned for [Baseten](https://www.baseten.co) backend MCP, Docs MCP and CLI.

The MCP makes token usage and wall time more efficient - our evals (below) show that, while agents can still achieve 
goals with raw REST API usage with similar pass rate. Additionally, the MCP tool annotations allow agent 
harnesses formal gating of destructive operations, providing additional safeguards.

What you can do without leaving the chat:

* Debug live: "Why do I see this log line" "Fix my deploy" → agent pulls logs, finds stack trace, proposes fix.
* Operate: Promote dev → prod, bump autoscaling for traffic spike, run a test predict.
* Keep the overview: "What's deployed, healthy, cold?" One-shot status across your account, easy cleanups.
* Skip the doc dive: Agent gets pointers to Baseten docs, blogposts and more in context.
* Wire up automations: Plug it into your own agents or internal tools for reactive ops without glue code.
* Install once, works everywhere: `npx add-mcp`, your API key, done. Uniform setup across 14+ coding agents.
* Read-only by default, mutations gated via harness policy check.

## Set Up

### Requirements:

* For interacting with your Baseten workspace, provide an API key with management permissions (you can get it from the 
  [webapp](https://app.baseten.co/settings/api_keys)). We recommend using a purpose-dedicated key, so it can be independently revoked without impacting
  other workstreams.
* Node >= 18 (for the install tools)

### Installation

```bash
export BASETEN_MCP_KEY=...

{ [ -n "$BASETEN_MCP_KEY" ] && [ "$BASETEN_MCP_KEY" != "..." ]; } || { echo "Error: set BASETEN_MCP_KEY first"; false; } && \
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}" && \
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y && \
npx skills add basetenlabs/baseten-skills -g -y
```

- `-g` installs it globally on your host.
- `-y` confirms selection for all detected harnesses.
- If your harness supports env variable interpolation, you may also edit the MCP config file to expand your env vars
  and set the desired key in the shell that starts the agent.

The `truss` CLI is separate and needed only for deployment authoring (not pure ops work). See [CLI docs](https://docs.baseten.co/reference/cli/truss/overview).
E.g. if you use pip (similar for other package
managers):

```bash
pip install truss --upgrade
```

You can install only part of the components or modify commands - but the best user experience comes from their combination.

## Getting started & Usage

After installation, most agents require a restart.

Check if the MCP servers connect with `/mcp` or `/mcps` (if not connected, verify the BASETEN_MCP_KEY in the harness 
config file).

You can start asking any questions or tasks related to Baseten, from chatting about the docs, to brainstorming 
solution approaches, deploying and iterating on models or managing your workspace. Most agents trigger the skill as 
needed automatically; alternatively you can invoke it with `/baseten`.

## Evaluation results

We measured the `baseten` skill against the bare Claude Opus 4.7 baseline across 16 tasks spanning model
authoring, integration, operate, debug, and tune workflows. Five configurations × 4 runs × 16 evals = 320 runs.

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
[**Full eval report**](evals/baseten/README.md).
