# Baseten Skills

Agent skills for working with [Baseten](https://www.baseten.co).

## Purpose

Instruct AI coding agents to use Baseten effectively - route to the right tools and mention common gotchas.

## Skills

- [`baseten`](skills/baseten) - deploying, configuring, calling, and operating models on Baseten. Covers Truss
  authoring, the `truss` CLI, Chains, environments / rolling deployments, pre-hosted Model APIs, and the inference +
  management APIs.

## Install

Below command performs setup for all common coding harnesses. For interacting with your Baseten workspace, provide an
API key (you can get it from the [webapp](https://app.baseten.co/settings/api_keys)):

```bash
export BASETEN_MCP_KEY=...

{ [ -n "$BASETEN_MCP_KEY" ] && [ "$BASETEN_MCP_KEY" != "..." ]; } || { echo "Error: set BASETEN_MCP_KEY first"; false; } && \
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_MCP_KEY}" && \
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y && \
npx add-skill basetenlabs/baseten-skills -g -y
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

Check if the MCP servers connect with `/mcp` or `/mcps` (if not connected, verify the BASETEN_MCP_KEY in the harness config file).

You can start asking any questions or tasks related to Baseten, from chatting about the docs to brainstorming solution approaches, deploying and iterating on models, or managing your
workspace. Most agents trigger the skill as needed automatically; alternatively you can invoke it with `/baseten`.
