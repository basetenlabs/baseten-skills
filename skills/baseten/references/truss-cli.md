# `truss` CLI

**Use the `baseten` CLI for everything except Chains — see `baseten-cli.md`.** The `truss` CLI stays as the Chains
authoring surface (`truss chains init` / `push` / `watch`), which also runs behind `baseten truss chains …`. Training
and Loops are Baseten CLI commands (`baseten train` / `baseten loops`); several of those delegate to truss internally,
but that is an implementation detail, not an interface to script against.

Model deploy and operation are out of scope here: `baseten-cli.md` owns `baseten model push`, the live-patch dev loop,
promotion, environments, and autoscaling. The `truss push` / `truss watch` flags this file used to document are
superseded there — for a legacy truss script, see the published reference at
<https://docs.baseten.co/reference/cli/truss/push>.

For the `truss chains` subcommand group itself, see `truss-chains.md`. The `truss train` group (Truss Train) is not
covered here; see <https://docs.baseten.co/reference/cli/training>.

**Prerequisites:** `truss-config.md` (what's in `config.yaml`); `truss-chains.md` (Chains authoring).

## Install

`uv tool install truss` (or `uvx truss <command>` to run without installing); `pip install truss` also works. Respect
the user's preferred package manager.

Prefer `baseten truss …` when the Baseten CLI is already installed: it runs truss through `uv tool run` and forwards the
Baseten CLI's credentials, so no separate `truss login` is needed. A truss command that imports your own Python code —
`chains push` on a chainlet with dependencies, for example — needs `--truss-executable` pointed at a truss installed
alongside those dependencies, because `uv tool run` uses an isolated environment that cannot see them.

## Authenticate

```
truss login
```

Paste an API key from <https://app.baseten.co/settings/api_keys> when prompted. Truss stores credentials in `.trussrc`
for future commands. In CI, set `BASETEN_API_KEY` and use `--remote` to select the saved remote name. Going through
`baseten truss` skips this step entirely, because credentials are forwarded for you.

## What the `truss` CLI still owns

| Task | Command |
| --- | --- |
| Scaffold a Chain | `truss chains init` |
| Push a Chain | `truss chains push` |
| Watch a Chain | `truss chains watch` |
| Debug a build locally | `truss container` — build and run the truss as a Docker container on your machine |
| Inspect what gets shipped | `truss image build` — produce the Docker image without deploying |

Everything else — model push and the dev loop, promotion, environments, autoscaling, replicas, training, Loops, org and
workspace management — has a first-class `baseten` command. See `baseten-cli.md`.

## Gotchas

- **`truss push` is not the default path for models.** Deploy with `baseten model push`: it is headless-safe, `--wait`
  returns the build verdict, and `--output json` / `--jq` make the result machine-readable.
- **`truss train` and `truss loops` still exist but are not the entry point.** Use `baseten train` and `baseten loops`.
- **`.trussrc` holds credentials.** Do not commit it. In CI and scripted flows, prefer `BASETEN_API_KEY` plus
  `--remote <name>` over committing `.trussrc`. Truss is moving toward OS keyring storage; if a key is needed, ask the
  user to export it as an env var rather than reading or writing credential files yourself.

## Further reading

- Truss CLI overview: <https://docs.baseten.co/reference/cli/truss/overview>
- `truss chains` reference: <https://docs.baseten.co/reference/cli/chains/chains-cli>
- `truss push` reference (legacy scripts): <https://docs.baseten.co/reference/cli/truss/push>
- Baseten CLI, the default: `baseten-cli.md`
