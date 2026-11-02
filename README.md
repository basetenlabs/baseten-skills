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

- Install Node.js 18 or later to run the installation tools.
- A Baseten account. The backend MCP server uses OAuth, so you sign in with your account instead of creating an API key.

### Install the toolkit

#### Install with your agent

Paste the following prompt into your agent:

```text
Install the Baseten agent toolkit globally for every coding agent on this machine:

1. Install the `baseten` skill: `npx skills add basetenlabs/baseten-skills -g -y`
2. Add the backend MCP server: `npx add-mcp https://api.baseten.co/mcp -g -y`
   Don't add an Authorization header or API key. The server uses OAuth, and I'll sign in to Baseten in my browser when it first connects.
3. Add the docs MCP server: `npx add-mcp https://docs.baseten.co/mcp -n baseten_docs -g -y`

If `add-mcp` stops because Claude Desktop doesn't support remote servers, rerun both `add-mcp` commands with an `-a` flag for each coding agent I use, such as `-a claude-code -a cursor`.

Then tell me how to sign in to the backend server, how to verify the setup, and whether I need to restart my agent.
```

#### Install manually

```bash
npx skills add basetenlabs/baseten-skills -g -y
npx add-mcp https://api.baseten.co/mcp -g -y
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y
```

- `-g` installs globally. `-y` confirms installation for all detected agents.
- If Claude Desktop is installed, `add-mcp` stops without configuring any agent, because Claude Desktop accepts
  remote servers only as connectors. Name the agents you use with `-a` instead, such as
  `npx add-mcp https://api.baseten.co/mcp -g -y -a claude-code -a cursor`. Run `npx add-mcp list-agents` for the
  other agent names.
- Some agents prompt before reading skill reference files (they live outside your workspace). In Claude Code,
  allow these reads in `settings.json`: `"permissions": { "allow": ["Read(~/.claude/skills/**)"] }`.

#### Connect with an API key

Agents that run without a browser, such as agents in CI, can't complete the sign-in. Connect them with a dedicated [API key with management permissions](https://app.baseten.co/settings/api_keys) instead. Store the key in the `BASETEN_MCP_KEY` environment variable, for example from your CI secret store, so it stays out of your shell history:

```bash
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}"
```

To create deployments, install the [Baseten CLI](https://docs.baseten.co/reference/cli/baseten/overview). `baseten model push` is the default path for creating and updating deployments:

```bash
brew tap basetenlabs/baseten
brew install baseten
```

Install the [Truss CLI](https://docs.baseten.co/reference/cli/truss/overview) as well only when you author Chains, or when you want the truss commands directly. You can install the skill, either MCP server, and the CLIs separately.

## Use the toolkit

After installation, follow your agent's instructions to reload its configuration. If your agent supports `/mcp` or `/mcps`, use that command to sign in to the backend server and check the MCP connections. The backend server acts as you. It works in your account's workspace and has your account's permissions.

Ask your agent to explain Baseten documentation, create a deployment, or manage your workspace. Agents that support automatic skill selection can load the skill when needed. If your agent supports skill commands, you can also invoke `/baseten`.

## Evaluation results

The [September 9 evaluation](evals/baseten/results/2026-09-09.md) compared the refreshed skill, the June skill, and no skill on the same model with both MCP servers enabled.

| Configuration | Mean assertion pass rate across 21 tasks |
| --- | ---: |
| No skill | 85.7% |
| June skill | 85.7% |
| Initial September skill | 81.7% |

This 63-execution sweep used one repetition per configuration and task. It did **not establish a quality improvement**. After correcting client guidance and assertions, all six follow-up executions on tasks 50 and 51 passed. The final skill revision has only that targeted coverage; it has not received a full 21-task sweep. Rubric errors and shared fixture history limit the initial comparison.

The [evaluation guide](evals/baseten/README.md) covers running a new comparison and indexes the dated reports, including earlier experiments with different models and suites.
