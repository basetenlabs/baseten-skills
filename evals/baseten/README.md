# Baseten evaluations

Use this guide to compare skill versions and review the latest results. Each dated report records an experiment's prompts, findings, and metrics.

## Latest results

The [September 9 report](results/2026-09-09.md) contains 63 initial executions: 21 tasks × three configurations × one repetition, using `zai-org/GLM-5.2-Fast` through Baseten's Anthropic-compatible API. Every configuration enabled both the backend and documentation Model Context Protocol (MCP) servers.

| Configuration | Mean assertion pass rate across tasks |
| --- | ---: |
| No skill | 85.7% |
| June skill | 85.7% |
| Initial September skill | 81.7% |

The comparison **does not establish a quality improvement**. An obsolete async rubric and shared live-fixture history limit interpretation. After correcting client guidance and assertions, tasks 50 and 51 passed in all three configurations: six fresh executions. Those follow-ups cover the final skill guidance on two tasks, not the full suite. A full run of the final revision remains outstanding.

The report preserves both iterations separately. Do not merge their scores because their assertions differ. One repetition per task also cannot establish repeatability.

## Reports and statistics

| Date | Experiment | Committed statistics |
| --- | --- | --- |
| [September 9, 2026](results/2026-09-09.md) | GLM-5.2-Fast; 21-task version comparison plus two-task corrected follow-up | [69 executions](results/2026-09-09-stats.jsonl) |
| [May 26, 2026](results/2026-05-26.md) | Opus 4.7; 16 tasks, five skill/MCP configurations, four repetitions | [320 executions](results/stats.jsonl) |
| [April 17, 2026](results/2026-04-17.md) | Sonnet pilot; five prompts, with and without skill; includes April 20 rerun | Metrics in report |

The May sweep was previously mislabeled April; its statistics record May 26. These experiments use different models, suites, and configurations, so their scores are not a time series of skill quality. `results/stats.jsonl` belongs only to the May benchmark.

## Prepare a new run

Run commands from the repository root. You need `uv`, Python 3.12 or newer, the Claude Code CLI (`claude`) on `PATH`, and credentials for the executor and grader and Baseten eval workspace. September used Claude Code 2.1.260; record the version used for new runs.

```sh
uv sync --project evals/baseten/harness
bash evals/baseten/bin/fetch_skill_creator.sh
```

The fetch script installs the pinned upstream skill-creator grader and viewer under `third_party/`, which Git ignores. See the [contribution guidelines](../../CONTRIBUTING.md) for the evaluation and reporting requirements.

Store credentials in the environment or in `evals/baseten/.env`, which Git ignores, never in tracked files or command arguments:

- `BASETEN_MCP_KEY`: credential for the dedicated eval workspace, used for MCP and fixture operations.
- `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`: executor and grader credential.
- `ANTHROPIC_BASE_URL`: set for an Anthropic-compatible provider; omit for the default Anthropic API.
- `ANTHROPIC_MODEL`: provider model ID, or pass `--model`.

The September provider and model was `https://inference.baseten.co` and `zai-org/GLM-5.2-Fast`. The runner reports cost as unavailable for custom providers because Claude Code's price table is not that provider's billing data.

Use an external artifact directory with no ancestor `.claude/skills` or `.agents/skills` directories. The runner rejects skills inherited from parent directories at that location. It isolates each execution's home and exposes only the selected Baseten skill body and references, excluding eval definitions. Built-in Claude skills remain available across configurations. Making the skill available does not guarantee the agent reads it.

For live tasks, prepare dedicated fixtures and pass an external JSON mapping with `--fixtures-path`. Use the checked-in [fixture map](../../skills/baseten/evals/fixtures.json) as a schema reference. Replace its model IDs with IDs from your eval workspace. Verify ownership and required deployments before running. Include `FIXTURE_MODEL_NAME` for broken-deployment resets. The runner skips tasks with missing fixture mappings; the comparison's completeness check must pass before claiming full-suite coverage.

Fixture locks serialize resets and execution against the same model and credential, but resets retain deployment history and counters. This shared state can affect operational results across configurations. The runner does not automatically create independent, matched fixtures for each configuration. After live runs, verify and deactivate dedicated deployments; the runner does not perform final resource cleanup.

## Compare skill versions

Freeze the current and previous skill directories outside the repository before starting. Both need `SKILL.md` and `references/`. Keep the checkout's [eval definitions](../../skills/baseten/evals/evals.json) unchanged throughout both runs: `--skill-source` changes only the skill, not the prompts or assertions. Archive a copy of the definitions with your artifacts.

The following template runs all tasks with identical MCP settings. Replace the paths with your prepared snapshots and fixture map. Use a fresh statistics path for each new sweep; five repetitions are an example for a new run, not September's one-repetition setup.

1. Set the path to your prepared evaluation workspace.

   ```sh
   EVAL_WORKSPACE=/absolute/path/outside/repo/evaluation
   ```

2. Run the current skill and the no-skill baseline.

   ```sh
   uv run --project evals/baseten/harness python -m baseten_skills_evals.runner \
     --skill baseten --skill-source "$EVAL_WORKSPACE/snapshots/current/baseten" \
     --fixtures-path "$EVAL_WORKSPACE/fixtures.json" \
     --modes s0b1d1,s1b1d1 --runs 5 --num-workers 1 \
     --artifact-root "$EVAL_WORKSPACE/current-artifacts" \
     --stats-path "$EVAL_WORKSPACE/current-stats.jsonl"
   ```

3. Run the previous skill.

   ```sh
   uv run --project evals/baseten/harness python -m baseten_skills_evals.runner \
     --skill baseten --skill-source "$EVAL_WORKSPACE/snapshots/previous/baseten" \
     --fixtures-path "$EVAL_WORKSPACE/fixtures.json" \
     --modes s1b1d1 --runs 5 --num-workers 1 \
     --artifact-root "$EVAL_WORKSPACE/previous-artifacts" \
     --stats-path "$EVAL_WORKSPACE/previous-stats.jsonl"
   ```

4. Compare the results.

   ```sh
   uv run --project evals/baseten/harness python -m baseten_skills_evals.compare \
     --current "$EVAL_WORKSPACE/current-stats.jsonl" \
     --previous "$EVAL_WORKSPACE/previous-stats.jsonl" \
     --evals skills/baseten/evals/evals.json \
     --out "$EVAL_WORKSPACE/comparison.json"
   ```

The comparison command writes the report to `$EVAL_WORKSPACE/comparison.json`. Check that it includes every selected task before reporting results.

Here `s` enables the skill, `b` the backend MCP, and `d` the docs MCP. Thus `s0b1d1` is the no-skill baseline with both MCPs, and `s1b1d1` adds the skill. The runner also supports other combinations for separately designed MCP experiments.

For a targeted run, add the same `--ids 50 51` to both runner commands and the comparison. Label the result as a subset. To resume an interrupted run, use `--resume` with its emitted benchmark directory and the same inputs and options. The runner skips completed executions and rejects changes to the recorded run inputs.

The comparison requires complete task sets, equal repetitions, and matching models, providers, rubric hashes, and fixture maps. It recomputes assertion scores from counts and reports task means and paired task-bootstrap intervals. Tokens and duration describe executor activity, excluding grading. Provider failures and invalid grading are execution failures, not zero-quality answers; investigate them before reporting a completed comparison.

To recompute an archived experiment, use that experiment's frozen definitions and statistics. The current suite contains September's corrected assertions and cannot reproduce the first iteration's comparison unchanged.

## Review and publish results

Review per-task outputs and grading evidence alongside the aggregate comparison. Keep raw outputs, grading JSON, snapshots, and the skill-creator HTML viewer outside the repository. Record model and provider, CLI version, hashes, repetitions, actual task coverage, rubric changes, and fixture limitations in a dated report. Include verbatim prompts and assertions and per-task quality, tokens, duration, and observations as required by the contribution guidelines.

Commit curated statistics under a dated name, link them from the report, and update this index and the root README summary. Preserve earlier results as dated evidence. State whether the final revision received a full sweep or only targeted follow-ups.

## Legacy helpers

[The Codespaces wrapper](bin/codespace_run_sweep.sh) clears alternate-provider settings and is Anthropic-only. Use the direct runner commands above for other model APIs. [The fixture provisioning script](bin/provision_fixtures.sh) uses fixed model names and writes the checked-in fixture map; it does not prepare independent matched fixtures for a version comparison. Neither helper reproduces the September setup by itself.
