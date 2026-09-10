# Baseten Skills

Agent DX bundle — [`baseten` skill](skills/baseten/) tuned for [Baseten](https://www.baseten.co) backend MCP, Docs MCP and CLI.

The skill brings Baseten guidance into your agent alongside the backend MCP, Docs MCP, and CLI.
See [evaluation results](#evaluation-results) for measured performance and coverage.

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

#### Agent-driven (recommended)

Set your key, then paste this into your agent:

Linux/Mac:
```bash
export BASETEN_MCP_KEY=...
```

Windows (PowerShell or cmd.exe):
```powershell
$env:BASETEN_MCP_KEY = "..."   # PowerShell
set BASETEN_MCP_KEY=...         # cmd.exe
```

Then paste this into the agent of your choice:
```
Install the Baseten agent toolkit following instructions from `github.com/basetenlabs/baseten-skills`.

- use `npx skills add` and `npx add-mcp`
- all global and for all agents (`-g -y`)
- The baseten backend server needs auth header `Authorization: Bearer $BASETEN_MCP_KEY` (or `Authorization: Bearer $env:BASETEN_MCP_KEY` in PowerShell). Run the install commands in a shell that has `BASETEN_MCP_KEY` set so the env var expands; don't read or inline the key value.
```

#### Manual

Linux/Mac:
```bash
export BASETEN_MCP_KEY=...
npx skills add basetenlabs/baseten-skills -g -y
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}"
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y
```

Windows:
```powershell
$env:BASETEN_MCP_KEY = "..."
npx skills add basetenlabs/baseten-skills -g -y
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer $env:BASETEN_MCP_KEY"
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y
```

- `-g` global, `-y` auto-confirms all detected harnesses.
- Harnesses that support env-var interpolation: point the MCP config at `$BASETEN_MCP_KEY` instead of baking the key in.
- Some agents prompt before reading skill reference files (they live outside your workspace). In Claude Code,
  pre-approve via `settings.json`: `"permissions": { "allow": ["Read(~/.claude/skills/**)"] }`.

The `truss` CLI is separate, needed for deployment authoring; see
[CLI docs](https://docs.baseten.co/reference/cli/truss/overview):

```bash
uv tool install truss
```

Components (skill, 2x MCPs, CLI) can be installed selectively, but work best in combination.

## Getting started & Usage

After installation, most agents require a restart.

Check if the MCP servers connect with `/mcp` or `/mcps` (if not connected, verify the BASETEN_MCP_KEY in the harness 
config file).

You can start asking any questions or tasks related to Baseten, from chatting about the docs, to brainstorming 
solution approaches, deploying and iterating on models or managing your workspace. Most agents trigger the skill as 
needed automatically; alternatively you can invoke it with `/baseten`.

## Evaluation results

The [September 9 evaluation](evals/baseten/results/2026-09-09.md) compared the refreshed skill, the June skill, and no skill on the same model with both MCP servers enabled.

| Configuration | Mean assertion pass rate across 21 tasks |
| --- | ---: |
| No skill | 85.7% |
| June skill | 85.7% |
| Initial September skill | 81.7% |

This 63-execution sweep used one repetition per configuration and task. It did **not establish a quality improvement**. After correcting client guidance and assertions, all six follow-up executions on tasks 50 and 51 passed. The final skill revision has only that targeted coverage; it has not received a full 21-task sweep. Rubric errors and shared fixture history limit the initial comparison.

The [evaluation guide](evals/baseten/README.md) covers running a new comparison and indexes the dated reports, including earlier experiments with different models and suites.
