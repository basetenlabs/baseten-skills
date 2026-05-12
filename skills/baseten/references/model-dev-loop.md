# Iterating on a deployment

How to evolve a Truss model or Chain after the first deploy. Covers `truss push` vs `--watch` vs `--watch-hot-reload`,
when each is admissible, and how the agent loop differs from the human watch loop the CLI was originally designed for.

For flag-level reference see `truss-cli.md` (Trusses) and `truss-chains.md` (Chains). This file is the workflow layer
above those.

## The three cost tiers

Every change to a Truss/Chain falls into one of three tiers. Pick the cheapest valid tier for the change.

| Tier | What runs | Wall time (typical) | Triggered by |
| --- | --- | --- | --- |
| **Image rebuild** | Docker build, push, deploy, `load()` | minutes (3-10) | any `config.yaml` / `RemoteConfig` change: `system_packages`, `requirements`, `python_version`, `base_image`, `build_commands`, `docker_image`, `compute` |
| **Live patch + reload** | File sync into container, server restart, `load()` re-runs | seconds (10-60) | any change to `model.py`, packages dir, or Chainlet `run_remote` / `__init__` |
| **Hot-reload (Trusses only)** | In-process Model class swap; weights and caches preserved; `__init__` / `load` do **not** re-run | sub-second to ~2s | changes to `predict()` only, on a dev deployment started with `--watch-hot-reload` |

Chains have tiers 1 and 2 only. There is no hot-reload for Chainlets — `truss chains push --watch` does live patches;
there is no equivalent of `--watch-hot-reload`.

## Robust baseline recipe

Conservative, always-correct, then refine for speed.

1. **Bootstrap** — `truss push` (or `truss chains push`) once to a published deployment. Wait for ACTIVE. Establishes a
   known-good image with current deps.
2. **Debug loop** — start a development deployment with `--watch` (no hot-reload). Every edit to model code triggers
   tier 2 (patch + `load()` re-run). Works for all model.py / Chainlet changes; never wrong.
3. **Refinement (Trusses only)** — once iteration is narrowed to `predict()` logic and `load()` is expensive (LLMs,
   large weights), restart the watcher with `--watch-hot-reload`. Drop a version sentinel in `predict()` (e.g.
   `logger.info("predict v=2026-05-11.3")`) so each iteration confirms the swap took.
4. **Dep change escape hatch** — if a change touches `config.yaml` / `RemoteConfig`, the watcher cannot help. Stop the
   watcher, do a full `truss push`, restart the watcher when ACTIVE.
5. **Publish** — final `truss push` (no `--watch`) so production is a clean cold start, not a patched-on-top-of-patched
   in-memory state. Then promote to environment / production.

## Agent vs human loop

The CLI's `--watch` was designed for a human editor: continuous FS watching is convenient when a person saves a file
every few seconds in an IDE. An agent edits in discrete bursts and _knows_ when it is ready to test. Two implications:

1. **Discrete patches would be cleaner than continuous watch.** Truss does not currently expose a one-shot `truss patch`
   verb — patches happen only as a side effect of `truss watch` / `truss chains push --watch`. The available primitive
   is "start the watcher, let your discrete edits flow through it, stop it when done."
2. **The natural Claude Code shape** for the debug loop is:
   - `Bash run_in_background` launches `truss watch --tail [--hot-reload]` (or `truss chains push --watch` with
     `--include-git-info` etc.). Output redirected to a log file. One backgrounded process owns the watch.
   - `Monitor` tails the log file with a grep filtered to terminal markers:
     `"Completed model.load|patched|sync|Exception|Traceback|FAILED|Replica terminated"`. One notification per outcome —
     keep filter alternation covering failures too (see Monitor coverage rule).
   - Each `Edit` to model code → debounced FS event → watcher patches → Monitor fires with success or failure.
   - `TaskStop` kills the watcher when debugging is done.
3. **Edit atomicity matters.** The Edit tool writes atomically (write-temp + rename), so the watcher sees one coherent
   event per Edit. Multiple Edits in quick succession may collapse into one patch (usually fine; if it matters, wait for
   the Monitor event between edits).

## Hot-reload admissibility (Trusses only)

`--watch-hot-reload` swaps the **Model class** in-process without re-running `__init__` or `load`. Faster, but narrower
applicability. Use it when **all** of these hold:

- Only `predict()` (or methods called from it) changed.
- No change to imports already resolved in the live process. Hot-reload swaps the class, not module globals —
  re-imported modules may still bind to the old version.
- No new state needs to be set up in `load()`. New tensors, file handles, opened sockets, downloaded files — none of
  these will appear.
- Not debugging cold-start behavior. Hot-reload defeats the purpose.
- No stateful resources need teardown (GPU memory leaks, file handle exhaustion). The old class instance and any
  references it owns persist until GC.

When in doubt, drop `--watch-hot-reload`. Tier 2 (patch + reload) is 10-60s — annoying, not catastrophic.

**Version sentinel pattern.** Always include something like `logger.info(f"predict version={VERSION}")` and bump
`VERSION` on each edit. Without it, a silent hot-reload no-op (e.g. due to module caching) is indistinguishable from a
successful swap.

## Chains specifics

- Chains use `truss chains push [--watch]` instead of `truss push`. Same tier-1 / tier-2 model; no tier 3.
- `--experimental-watch-chainlets <name,...>` restricts patching to specific Chainlets — useful when one Chainlet has a
  slow `load()` and you are iterating on another. Treat as experimental; not a substitute for stable workflow.
- **Each Chainlet is independent** for rebuild purposes. Changing one Chainlet's `RemoteConfig` only rebuilds that
  Chainlet's image. Use this to keep iteration cost down: stabilize heavy Chainlets first, then iterate on lighter ones.
- **No rolling deployments for Chains.** A new published deploy is a hard cutover. Plan accordingly when promoting from
  the dev-watch deployment to production.
- **`Heavy-dependency imports inside Chainlet methods** (not module top) means the local watcher does not need GPU
  libraries to run. Standard Chains idiom; keep doing it.

## Gotchas

- **Watch keeps the dev deployment warm** — no scale-to-zero while watching. Stop the watcher when not iterating, or
  accept the cost.
- **Watch breaks on `config.yaml` / `RemoteConfig` changes.** The watcher cannot perform a tier-1 rebuild. Stop it,
  push, restart it.
- **Hot-reload silently failing to apply.** The version-sentinel pattern is the only reliable defense — don't assume the
  swap took.
- **Final push before publish.** Production deploys should start from a clean image, not a watched dev deployment
  patched 47 times. Always do a non-watch `truss push` as the publish step.
- **Multi-remote setups** require `--remote <name>`. If `truss push` errors with "Multiple remotes available," check
  `~/.trussrc`.
- **Cached truss credentials live in `~/.trussrc`.** Do not scrape it for the API key — set `BASETEN_API_KEY` explicitly
  or ask the user.

## Further reading

- `truss-cli.md` — flag reference for `truss push` and `truss watch`.
- `truss-chains.md` — Chainlet model and `truss chains push` reference.
- Deploy-and-iterate guide: <https://docs.baseten.co/development/model/deploy-and-iterate>
- Chains local development: <https://docs.baseten.co/development/chain/localdev> — `chains.run_local()` lets you iterate
  Chainlet logic without a deploy at all; orthogonal to the watch loop but often the right first step for pure-Python
  logic changes.
