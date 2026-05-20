# Iterating on a deployment

Agent-flavored notes for post-first-deploy iteration on a Truss model or Chain. Conceptual model and feature reference
live in the docs — this file covers what the docs don't: the agent-specific watcher recipe and exact log markers.

**Prerequisites:** `deployment-lifecycle.md` (especially dev vs published — `--watch` only patches a dev deployment);
`truss-cli.md` (flag reference for `truss push` / `truss watch`); `truss-chains.md` if iterating on a Chain.

Docs: <https://docs.baseten.co/development/model/deploy-and-iterate> (general),
<https://docs.baseten.co/development/chain/localdev> (Chains local dev).

## Three cost tiers — pick the cheapest valid one

| Tier | What runs | Wall time | Triggered by |
| --- | --- | --- | --- |
| **Image rebuild** | Docker build + push + deploy + `load()` | minutes (3-10) | a small set of unpatchable config keys: `python_version`, `resources` (compute/instance type), `live_reload`. The watcher detects and refuses these — see "When to drop the watcher" below. |
| **Live patch + reload** | File sync, server restart, `load()` re-runs | seconds (10-60) | everything else: `model.py` / Chainlet code, `requirements`, `system_packages`, env vars, `external_data`, `model_metadata`, `build_commands`, data dir, bundled packages |
| **Hot-reload** (Trusses only) | In-process class swap; `__init__` / `load` do **not** re-run | sub-second to ~2s | `predict()`-only changes, dev deployment started with `--watch-hot-reload` |

Chains have tiers 1 and 2 only; no hot-reload.

## Watcher recipe for agents

`--watch` was built for humans saving files in an IDE. An agent edits in discrete bursts and knows when it is ready to
test. Truss has no one-shot `truss patch` verb — patches only happen as a side effect of `truss [chains] push --watch`.
The robust pattern for an agent is **one watcher per edit**: start the watcher, wait for the patch marker, kill it,
test. Each cycle is self-contained, no long-lived background process for the harness to lose track of, recovery from
any mid-loop failure is trivial (re-edit, re-run).

`--watch` always produces a **development deployment** — mutable, single replica, scales to zero when idle, no
autoscaling, one per model. Live patching is only possible against this slot, never against a published deployment.
See `deployment-lifecycle.md` for the full dev-vs-published distinction.

Per edit (adapt to your harness — Bash, Python job control, etc.):

```bash
# 1. Edit the file (atomic write — most editor/agent tools already do this).

# 2. Start the watcher in the background, fresh log per cycle.
truss chains push --watch --remote <name> chain.py > /tmp/watch.log 2>&1 &
WATCH_PID=$!
# Single Truss:  truss watch --remote <name> > /tmp/watch.log 2>&1 &

# 3. Wait for the patch marker (see "Log markers" below for the alternatives).
while sleep 2; do
  grep -qE 'Patched Chainlet|Failed to patch|patched successfully' /tmp/watch.log && break
done

# 4. Kill the watcher; the next edit gets a fresh one.
kill "$WATCH_PID" 2>/dev/null

# 5. Test the dev endpoint with a foreground call. On failure, fetch chainlet /
#    deployment logs via the MCP / management API — don't guess.
```

The watcher's ~5-15s of startup per cycle is in the noise next to the tier-2 patch wait (10-60s) and the test call.
Trading that for the robustness of stateless cycles is worth it.

### Log markers (from truss source)

| Surface | Success | No-op | Failure | Cycle done |
| --- | --- | --- | --- | --- |
| Chain | `✅ Patched Chainlet \`<name>\`.` | `💤 Nothing to do for Chainlet \`<name>\`.` | `❌ Failed to patch Chainlet \`<name>\`.` | `👀 Watching for new changes.` |
| Truss | `Model <name> patched successfully.` | (silent skip) | `Failed to patch. ...` / `Patch failed: ...` | (rely on success/failure line) |

### Useful flags

- **`truss chains push --watch --experimental-watch-chainlets <Name1>,<Name2>`** — restrict patching to specific
  Chainlets. Useful when iterating on a sibling of a heavy-`load()` Chainlet.
- **`truss push --watch --watch-hot-reload`** (Trusses only) — swap the Model class in-process without re-running
  `__init__`/`load`. Faster, but only valid when **all** of: only `predict()` changed; no new module-level imports; no
  new state in `load()`; not debugging cold start. When unsure, drop the flag. Pair with a `VERSION` sentinel logged
  from `predict()` so silent no-op swaps are detectable.

### When to drop the watcher

The watcher cannot rebuild the image. If your change touches one of the unpatchable keys
(`python_version`, `resources`, `live_reload`), or if the log shows `Patching is not supported for: <key>` /
`Failed to calculate patch. Change type might not be supported.`: do a one-shot plain `truss [chains] push` (no
`--watch`, exits when upload completes), poll deployment status until `ACTIVE`, then resume the one-shot watcher recipe.
Don't enumerate every "is this patchable?" up front — try the patch, fall back on the warning.

## Publish step

After iteration: do one clean `truss [chains] push` without `--watch` so production starts from a fresh image, not a
patched-on-top-of-patched dev state. Then promote to the target environment.

## Gotchas

- **Watch keeps the dev deployment warm** — no scale-to-zero while watching. Stop it when not iterating.
- **Atomic edits**: file writes that rename-into-place are seen by the watcher as one FS event. Bursts may collapse
  into one patch — usually fine; if it matters, wait for the marker between edits.
- **Multi-remote setups** require `--remote <name>`. If `truss push` errors with "Multiple remotes available," check
  `~/.trussrc`.
