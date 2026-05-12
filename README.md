# Baseten Skills

Agent skills for working with [Baseten](https://www.baseten.co).

## Purpose

Teach AI coding agents to use Baseten effectively - route to the right tools for the task and surface the non-obvious
details an agent would otherwise get wrong.

## Skills

- [`baseten`](skills/baseten) - deploying, configuring, calling, and operating models on Baseten. Covers Truss
  authoring, the `truss` CLI, Chains, environments / rolling deployments, pre-hosted Model APIs, and the inference +
  management APIs.

## Install

Below command sets you up for all common coding harnesses. For interacting with your Baseten workspace, provide an
API key (you can get it from the [webapp](https://app.baseten.co/settings/api_keys)):

```bash
export BASETEN_API_KEY=...
npx add-mcp https://api.baseten.co/mcp -g -y --header "Authorization: Bearer ${BASETEN_API_KEY}" && \
npx add-mcp https://docs.baseten.co/mcp -n "baseten_docs" -g -y && \
npx add-skill basetenlabs/baseten-skills -g -y
```

`-g` installs it globally on your host and `-y` confirms selection for all detected harnesses.

The `truss` CLI is separate - needed for pushing models / chains from local code, see
[CLI docs](https://docs.baseten.co/reference/cli/truss/overview). E.g. if you use pip (similar for other package
managers):

```bash
pip install truss --upgrade
```

You can install only part of the components or modify commands (esp. leaving the CLI out if you don't plan to deploy
models from your local files) - but the best user experience comes from their combination.

## Getting started & Usage

After installation, most agents require a restart. You can start asking any questions or tasks related to Baseten,
from chatting about the docs to brainstorming solution approaches, deploying and iterating on models, or managing your
workspace. Most agents trigger the skill as needed automatically; alternatively you can invoke it with `/baseten`.
