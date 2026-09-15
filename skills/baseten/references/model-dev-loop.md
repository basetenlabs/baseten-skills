# Iterating on a deployment

Agent-flavored notes for post-first-deploy iteration on a Truss model or Chain. Conceptual model and feature reference
live in the docs — this file covers what the docs don't: the agent-specific watcher recipe and exact log markers.

**Prerequisites:** `deployment-lifecycle.md` (especially dev vs published — the watch loop only patches a dev
deployment); `baseten-cli.md` (flag reference for `baseten model push --watch` / `baseten model watch`); `truss-cli.md`
and `truss-chains.md` if iterating on a Chain.

Docs: <https://docs.baseten.co/development/model/deploy-and-iterate> (general),
<https://docs.baseten.co/development/chain/localdev> (Chains local dev).

## Three cost tiers — pick the cheapest valid one

| Tier | What runs | Wall time | Triggered by |
| --- | --- | --- | --- |
| **Image rebuild** | Docker build + push + deploy + `load()` | minutes (3-10) | a small set of unpatchable config keys: `python_version`, `resources` (compute/instance type), `live_reload`; removing `config.yaml`; and any change under the `data/` directory. The watcher detects and refuses these — see "When to drop the watcher" below. |
| **Live patch + reload** | File sync, server restart, `load()` re-runs | seconds (10-60) | everything else: `model.py` / Chainlet code, `requirements`, `system_packages`, env vars, `external_data`, `model_metadata`, `build_commands`, bundled packages |
| **Hot-reload** (models only) | In-process class swap; `__init__` / `load` do **not** re-run | sub-second to ~2s | `predict()`-only changes, dev deployment started with `--watch-hot-reload` |

Chains have tiers 1 and 2 only; no hot-reload.

## Watcher recipe for agents

The watch loop was built for humans saving files in an IDE. An agent edits in discrete bursts and knows when it is ready
to test. Neither CLI has a one-shot patch verb — patches only happen as a side effect of a running watch loop
(`baseten model push --watch` / `baseten model watch` for models, `truss chains push --watch` for Chains). The robust
pattern for an agent is **one watcher per edit**: start the watcher, wait for the patch marker, kill it, test. Each
cycle is self-contained, no long-lived background process for the harness to lose track of, recovery from any mid-loop
failure is trivial (re-edit, re-run).

The watch loop always runs against a **development deployment** — mutable, single replica, scales to zero when idle, no
autoscaling, one per model. Live patching is only possible against this slot, never against a published deployment. See
`deployment-lifecycle.md` for the full dev-vs-published distinction.

Per edit (adapt to your harness — Bash, Python job control, etc.):

```bash
# 1. Edit the file (atomic write — most editor/agent tools already do this).

# 2. Start the watcher in the background, fresh log per cycle.
baseten model watch --dir ./my-model > /tmp/watch.log 2>&1 &
WATCH_PID=$!
# First cycle (creates the dev deployment):  baseten model push --watch > /tmp/watch.log 2>&1 &
# Chain:  truss chains push --watch --remote <name> chain.py > /tmp/watch.log 2>&1 &

# 3. Wait for a terminal patch marker (see "Log markers" below). Includes the
#    no-op so a file that diffs clean still terminates the loop. Hard timeout
#    prevents an infinite hang if the watcher silently stalls.
deadline=$((SECONDS + 300))
while [ $SECONDS -lt $deadline ]; do
  grep -qE \
    'Applied patch to development deployment|Patch failed|Cannot patch|Patch not applied|No changes to patch|patched successfully|Failed to patch|Nothing to do for Chainlet' \
    /tmp/watch.log && break
  sleep 2
done

# 4. Kill the watcher; the next edit gets a fresh one.
kill "$WATCH_PID" 2>/dev/null

# 5. Test the dev endpoint with a foreground call. On failure, fetch deployment
#    logs via the MCP / management API — don't guess.
```

The watcher's ~5-15s of startup per cycle is in the noise next to the tier-2 patch wait (10-60s) and the test call.
Trading that for the robustness of stateless cycles is worth it.

### Log markers

Model markers are from the Baseten CLI's watch loop; Chain markers are from truss (Chains still run through it).

| Surface | Success | No-op | Failure | Cycle done |
| --- | --- | --- | --- | --- |
| Model (Baseten CLI) | `Applied patch to development deployment.` | `No changes to patch.` | `Patch failed: <err>` | `Watching for changes. Press Ctrl-C to stop.` |
| Model (Baseten CLI) | — | `Development deployment already up to date.` | `Patch not applied: <reason>` / `Cannot patch (<reason>); run 'baseten model push --develop' to redeploy.` | — |
| Chain | `✅ Patched Chainlet \`<name>\`.` | `💤 Nothing to do for Chainlet \`<name>\`.` | `❌ Failed to patch Chainlet \`<name>\`.` | `👀 Watching for new changes.` |
| Model (truss) | `Model <name> patched successfully.` | (silent skip) | `Failed to patch. ...` / `Patch failed: ...` | (rely on success/failure line) |

`Cannot patch (...)` is terminal for that edit: the change needs a full redeploy, so stop the watcher and run
`baseten model push --develop`.

### Useful flags

- **`--watch-hot-reload`** on `baseten model push --watch`, or **`--hot-reload`** on `baseten model watch` — swap the
  Model class in-process without re-running `__init__`/`load`. Faster, but only valid when **all** of: only `predict()`
  changed; no new module-level imports; no new state in `load()`; not debugging cold start. When unsure, drop the flag.
  Pair with a `VERSION` sentinel logged from `predict()` so silent no-op swaps are detectable.
- **`--watch-no-keepalive`** (push) / **`--no-keepalive`** (watch) — let the dev deployment scale to zero. The truss
  equivalents are `--watch-no-sleep` / `--no-sleep`.
- **`truss chains push --watch --experimental-watch-chainlets <Name1>,<Name2>`** — restrict patching to specific
  Chainlets. Useful when iterating on a sibling of a heavy-`load()` Chainlet.
- **`--remote <name>`** (truss only) — required on multi-remote setups.

### When to drop the watcher

The watcher cannot rebuild the image. If your change touches one of the unpatchable keys (`python_version`, `resources`,
`live_reload`), or if the log shows `Cannot patch (<reason>)` /
`Failed to calculate patch. Change type might not be supported.`: do a one-shot plain deploy (`baseten model push`, or
`truss [chains] push` for a Chain — no `--watch`, exits when upload completes), wait for the deployment to reach
`ACTIVE`, then resume the one-shot watcher recipe. Don't enumerate every "is this patchable?" up front — try the patch,
fall back on the warning.

## Publish step

After iteration: do one clean `baseten model push` without `--watch` (or `truss [chains] push` for a Chain) so
production starts from a fresh image, not a patched-on-top-of-patched dev state. Then promote to the target environment
with `baseten model deployment promote`.

## Inference SSH

Full terminal in a running model container — debug, inspect files, run commands, `scp`/`sftp`. Requires org enablement
(contact support) and `runtime.remote_ssh.enabled: true` in `config.yaml`. MCP tool `sign_ssh_certificate_training_job`
covers the training-job equivalent. Docs: `inference/ssh.mdx`.

## Gotchas

- **Watch keeps the dev deployment warm by default.** Disable with `--watch-no-keepalive` on push or `--no-keepalive` on
  watch, and stop the watcher when you're not iterating. Keep-warm only lasts so long either way: the CLI stops
  keepalive after 24 hours and warns 30 minutes before it stops.
- **Atomic edits**: file writes that rename-into-place are seen by the watcher as one FS event. Bursts may collapse into
  one patch — usually fine; if it matters, wait for the marker between edits.
- **Multi-remote setups** (truss) require `--remote <name>`. If a push errors with "Multiple remotes available," check
  `~/.trussrc`.
- **`baseten model watch` requires an existing dev deployment.** If the model has none, run
  `baseten model push --develop` (or `--watch`) first.
