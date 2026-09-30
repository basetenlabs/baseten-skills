# Baseten Skills

Use the [`baseten` skill](skills/baseten/) with the [Baseten](https://www.baseten.co) backend and documentation Model Context Protocol (MCP) servers to work with Baseten from your coding agent.

You can ask your agent to:

- Diagnose deployment failures by inspecting logs and proposing fixes.
- Promote deployments, update autoscaling, and test inference.
- Check the status of models in your workspace.
- Find product guidance in the Baseten documentation.
- Write deployment configurations and API clients.

See [evaluation results](#evaluation-results) for measured performance and coverage.

## Set up the toolkit

### Requirements

- To interact with your Baseten workspace, create an [API key with management permissions](https://app.baseten.co/settings/api_keys). Use a dedicated key so you can revoke it without affecting other work.
- Install Node.js 18 or later to run the installation tools.

### Install the toolkit

#### Install with your agent

Set the `BASETEN_MCP_KEY` environment variable in your shell. Replace `...` with your API key.

On Linux or macOS:

```bash
export BASETEN_MCP_KEY=...
```

On Windows with PowerShell:

```powershell
$env:BASETEN_MCP_KEY = "..."
```

On Windows with Command Prompt:

```bat
set BASETEN_MCP_KEY=...
```

Then paste the following instructions into your agent:

```text
Install the Baseten agent toolkit following instructions from `github.com/basetenlabs/baseten-skills`.

- use `npx skills add` and `npx add-mcp`
- all global and for all agents (`-g -y`)
- The baseten backend server needs auth header `Authorization: Bearer $BASETEN_MCP_KEY` (or `Authorization: Bearer $env:BASETEN_MCP_KEY` in PowerShell). Run the install commands in a shell that has `BASETEN_MCP_KEY` set so the env var expands; don't read or inline the key value.
```

#### Install manually

On Linux or macOS:

```bash
export BASETEN_MCP_KEY=...
npx skills add basetenlabs/baseten-skills -g -y
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}"
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y
```

On Windows with PowerShell:

```powershell
$env:BASETEN_MCP_KEY = "..."
npx skills add basetenlabs/baseten-skills -g -y
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer $env:BASETEN_MCP_KEY"
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y
```

- `-g` installs globally. `-y` confirms installation for all detected agents.
- If your agent supports environment variable interpolation, reference `$BASETEN_MCP_KEY` in its MCP configuration.
- Some agents prompt before reading skill reference files (they live outside your workspace). In Claude Code,
  allow these reads in `settings.json`: `"permissions": { "allow": ["Read(~/.claude/skills/**)"] }`.

To create deployments, install the [Baseten CLI](https://docs.baseten.co/reference/cli/baseten/overview). `baseten model push` is the default path for creating and updating deployments:

```bash
brew tap basetenlabs/baseten
brew install baseten
```

Install the [Truss CLI](https://docs.baseten.co/reference/cli/truss/overview) as well only when you author Chains, or when you want the truss commands directly. You can install the skill, either MCP server, and the CLIs separately.

## Use the toolkit

After installation, follow your agent's instructions to reload its configuration. If your agent supports `/mcp` or `/mcps`, use that command to check the MCP connections. If the backend connection fails, verify `BASETEN_MCP_KEY` in the agent's configuration.

Ask your agent to explain Baseten documentation, create a deployment, or manage your workspace. Agents that support automatic skill selection can load the skill when needed. If your agent supports skill commands, you can also invoke `/baseten`.

## Evaluation results

The [September 30 targeted check](evals/baseten/results/2026-09-30.md) covers managed Loops execution and native
`--tail` behavior. All three with-skill answers passed their assertions in one manual sample per task. This does
not establish general improvement or verify live execution; the final SSH prerequisite received source review only.

The [Loops discovery follow-up](evals/baseten/results/2026-09-28.md#catalog-to-reference-discovery-follow-up) checks
whether an agent finds the dedicated reference from the skill catalog and entrypoint. Both tasks passed in the
final manual sample. This is not a live integration test or an installed-plugin activation benchmark.

The [September 28 targeted evaluation](evals/baseten/results/2026-09-28.md) covers managed Loops client execution and checkpoint deployment safety, with follow-ups for sandbox networking, CLI deployment previews, and preserving checkpoint teams when pushing edited configs. The initial comparison was withdrawn because its baseline could read skill files. See the report for the isolated follow-ups and their limitations. These checks do not replace the full-suite comparison below.

The [September 9 evaluation](evals/baseten/results/2026-09-09.md) compared the refreshed skill, the June skill, and no skill on the same model with both MCP servers enabled.

| Configuration | Mean assertion pass rate across 21 tasks |
| --- | ---: |
| No skill | 85.7% |
| June skill | 85.7% |
| Initial September skill | 81.7% |

This 63-execution sweep used one repetition per configuration and task. It did **not establish a quality improvement**. After correcting client guidance and assertions, all six follow-up executions on tasks 50 and 51 passed. The final skill revision has only that targeted coverage; it has not received a full 21-task sweep. Rubric errors and shared fixture history limit the initial comparison.

The [evaluation guide](evals/baseten/README.md) covers running a new comparison and indexes the dated reports, including earlier experiments with different models and suites.
