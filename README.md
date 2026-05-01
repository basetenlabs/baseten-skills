# Baseten Skills

Agent skills for working with [Baseten](https://www.baseten.co).

## Purpose

These skills teach AI coding agents how to use Baseten effectively, grounded in Baseten's own docs, Truss source, and published examples. They route the agent to the right surface for the task (Truss authoring, the truss CLI, Model APIs, the inference and management APIs) and surface the non-obvious details an agent would otherwise get wrong.

## Skills

- [`baseten`](skills/baseten) - deploying, configuring, calling, and operating models on Baseten. Covers Truss authoring (`config.yaml`, Python `model.py`, custom Docker servers, engine-only deploys), the `truss` CLI, Chains, environments and rolling deployments, pre-hosted Baseten Model APIs, and custom deployments via the inference and management APIs.

## Install

### Using the skills CLI

```
npx skills add basetenlabs/baseten-skills
```

### Manual (Claude Code)

```
git clone https://github.com/basetenlabs/baseten-skills.git
ln -s "$(pwd)/baseten-skills/skills/baseten" ~/.claude/skills/baseten
```

Copy the directory instead of symlinking if you prefer.

## Layout

Each skill is a directory under `skills/` with a `SKILL.md` entry point and an optional `references/` directory. `SKILL.md` is always loaded when the skill is triggered; reference files are loaded on demand per the routing in `SKILL.md`.
