# `truss` CLI

The `truss` CLI builds, deploys, and live-patches Trusses. The published reference is at
<https://docs.baseten.co/reference/cli/truss/overview>.

This file covers Truss model commands only. For the `truss chains` subcommand group, see `truss-chains.md`. The
`truss train` group (Truss Train) is not covered here; see <https://docs.baseten.co/reference/cli/training>.

**Prerequisites:** `truss-config.md` (what's in `config.yaml`); `deployment-lifecycle.md` (default push is published,
`--watch` makes a dev deployment — the distinction matters).

## Install

`uv tool install truss` (or `uvx truss <command>` to run without installing); `pip install truss` also works. Respect
the user's preferred package manager.

## Authenticate

`truss login` is a top-level alias for `truss auth login`; both accept `--browser`, `--api-key TEXT`, and
`--remote TEXT`.

```
truss login
```

In an interactive terminal, this prompts you to either paste an API key from <https://app.baseten.co/settings/api_keys>
or log in via browser (OAuth). Pass `--browser` to start the OAuth device flow directly, or pass `--api-key TEXT` to
authenticate with an API key; the two flags are mutually exclusive.

In a non-interactive run, you must pass one of those flags explicitly. Otherwise, Truss errors with:

```
Specify --browser or --api-key when running non-interactively.
```

In CI, set `BASETEN_API_KEY` and use `--remote` to select the saved remote name; Truss falls back to that env var when
the saved remote has no stored key. To create the remote itself non-interactively, run
`truss login --api-key "$BASETEN_API_KEY"` — `--api-key` is a `login` flag, not a `push` flag. Verify the active remote
with:

```
truss auth status
```

Sample output:

```
remote: baseten
remote_url: https://app.baseten.co
auth_type: api_key (plaintext)
source: trussrc-inline
```

When only one remote is configured, `--remote <name>` is inferred. With multiple remotes in `.trussrc`, pass it
explicitly or the command errors with `Multiple remotes available. Please specify one with --remote.` The `source` field
is `trussrc-inline` for credentials stored in `.trussrc` and `keyring` for credentials stored in the OS keyring.

## `truss init` - scaffold

```
truss init my-model
```

Creates a starter Truss directory:

```
my-model/
├── config.yaml
├── model/
│   ├── __init__.py
│   └── model.py
├── data/
└── packages/
```

Edit `model/model.py` (Python class flavor), or replace it with `docker_server` config (custom server flavor), or remove
it entirely and add an engine block (engine-only).

## `truss push` - the main flow

`truss push` is the workhorse. Default behavior creates a **published** deployment (immutable snapshot). Use flags to
change target, control live reload, wait for completion, and stream logs.

### Common patterns

Iterative dev loop (live-patches code on save):

```
truss push --watch --tail
```

CI-friendly publish that waits and streams logs:

```
truss push --wait --tail
```

CI-friendly publish with machine-readable output (intended for automation):

```
truss push --output json --wait
```

Promote straight to production:

```
truss push --promote
```

Promote to a named environment:

```
truss push --environment staging
```

### Key flags

- `--watch`: create a **development** deployment and watch for source changes, applying live patches. The dev model
  stays warm by default (no scale-to-zero) while watching.
- `--watch-hot-reload`: with `--watch`, swap the model class in-process instead of restarting the server. Faster
  iteration; preserves loaded weights and caches; does **not** re-run `__init__` or `load`. Use when you only changed
  `predict` logic.
- `--promote`: published deployment, promoted to production even if a production deployment already exists.
- `--environment <name>`: published deployment, promoted into the named environment. When set, `--promote` is ignored.
- `--preserve-previous-production-deployment`: with `--promote`, inherit the previous production deployment's
  autoscaling settings.
- `--preserve-env-instance-type` / `--no-preserve-env-instance-type`: with `--environment`, keep the environment's
  configured instance type instead of the Truss config's `resources`. Default is to preserve.
- `--deployment-name <name>`: name the published deployment (alphanumeric, `.`, `-`, `_`). Ignored for `--watch`.
- `--model-name <name>`: temporarily override `model_name` without editing `config.yaml`.
- `--wait` / `--no-wait`: block until the deploy finishes; exit non-zero on failure.
- `--tail`: stream deployment logs after push. Combines with `--wait` and with `--watch`.
- `--output [text|json]`: select the output format. `json` writes structured JSON to stdout and progress and logs to
  stderr, which is suitable for CI parsing.
- `--labels '{"k":"v"}'`: attach searchable key/value labels to the deployment.
- `--include-git-info`: attach git sha, branch, and tag.
- `--no-cache`: force a full rebuild without using cached layers.
- `--timeout-seconds <n>`: client-side polling timeout when `--wait`-ing.
- `--deploy-timeout-minutes <n>`: server-side deploy timeout.
- `--remote <name>`: pick a remote from `.trussrc`. Useful in CI with multiple workspaces.
- `--config <path>`: use a non-default config file.
- `--team <name>`: deploy to a specific team (organizations with teams enabled).

## `truss watch` - re-attach to a dev deployment

```
truss watch
```

Re-attaches to an existing development deployment and applies live patches when files change. Equivalent to running
`truss push --watch` once and resuming the watch loop later.

`truss watch` keeps the dev deployment **warm** (prevents scale-to-zero) while it is running. If the user expects the
dev deployment to scale to zero while a watch is active, surface this so they understand why replicas are still running.

Other flags:

- `--hot-reload`: in-process model swap, same semantics as `--watch-hot-reload` on push.
- `--remote`, `--config`, `--team`, `--model-name`: same meanings as on `push`.

## `truss container` - local debugging

`truss container` builds and runs the Truss as a Docker container locally. Use this to reproduce build failures or
inspect the model server outside of Baseten.

## `truss image` - build and manage images

`truss image build` produces the Docker image without deploying. Useful for checking what gets shipped, or for offline
image distribution.

## `truss model-logs` - fetch deployment logs

```
truss model-logs <model-id>
```

Fetches recent logs for a deployment. For continuous streaming during a push, prefer `truss push --tail`.

## `truss configure`, `truss whoami`, `truss cleanup`

Workspace and account utilities. `whoami` prints the current authenticated user. `configure` opens `$EDITOR` on
`~/.trussrc` via `click.edit()` and blocks until the editor exits. Use `truss login` / `truss auth login` to add a
remote and `truss auth logout` to remove one without opening an editor. `cleanup` removes locally cached deployment
artifacts.

## Gotchas

- **Default `truss push` is a published deployment, not a dev one.** For an iterative dev loop, use `--watch` (or
  `truss watch` afterwards).
- **`truss watch` keeps the dev deployment warm by default.** Replicas do not scale to zero while the watch is running.
  Stop the watch (or accept the cost) accordingly.
- **`--watch-hot-reload` does not re-run `__init__` or `load`.** If your change relies on new state set up there, do a
  full reload (omit `--watch-hot-reload`) instead.
- **Bare `truss login` errors in a non-interactive run.** Pass either `--browser` or `--api-key`; otherwise it errors
  with `Specify --browser or --api-key when running non-interactively.`
- **`truss configure` blocks on `$EDITOR`.** It opens `~/.trussrc` via `click.edit()` and waits for the editor to exit,
  so do not run it from a non-interactive agent.
- **`.trussrc` holds credentials.** Do not commit it. In CI / scripted flows, prefer `BASETEN_API_KEY` plus
  `--remote <name>` over committing `.trussrc`. Truss is moving toward OS keyring storage; if asking for a key, ask the
  user to export it as an env var rather than reading or writing credential files yourself.

## Further reading

- CLI overview: <https://docs.baseten.co/reference/cli/truss/overview>
- `truss push` reference: <https://docs.baseten.co/reference/cli/truss/push>
- `truss watch` reference: <https://docs.baseten.co/reference/cli/truss/watch>
- Deploy and iterate guide: <https://docs.baseten.co/development/model/deploy-and-iterate>
- Calling deployed models (when ready to test from outside the CLI): see `inference-api.md`.
