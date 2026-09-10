# Contributing

## Add or change a skill

Each skill is a directory under `skills/`. For skill structure, writing patterns, progressive disclosure, and other conventions, follow:

- The [skill creation best practices](https://agentskills.io/skill-creation/best-practices).
- The [`skill-creator` skill](https://github.com/anthropics/skills), which guides skill creation, iteration, and evaluation.

Skills are not the authoritative home for any content. If a skill needs a product fact, API detail, or code example that isn't already in [Baseten documentation](https://docs.baseten.co) or a sample repository, add it there first and have the skill draw from that source. Restating upstream content in a skill is fine; originating it in a skill is not.

## Run evaluations before merging

Include evaluation results with skill changes. Use the `skill-creator` workflow to produce them. Eval definitions (the prompts and their assertions) live alongside the skill at `skills/<name>/evals/evals.json` so they can be rerun against future versions. Raw run artifacts (per-eval outputs, grading JSON, the HTML viewer) belong in a workspace directory outside the repository so the commit history stays focused on the skill and its evals.

## Write a results report

Write a curated summary into `evals/<skill>/results/YYYY-MM-DD.md` and link it from the PR. The summary should let a reviewer judge the change without needing the raw artifacts:

- The prompts that were run (verbatim).
- The assertions that were checked.
- For each prompt: with-skill vs. baseline pass rate, tokens, duration, and one or two lines of qualitative observation.
- Takeaways that drove the changes in the PR.

If multiple iterations happen on the same day, append to the same file. A new day starts a new file.

Keep `evals/<skill>/README.md` as the current run guide and index of dated reports. Link new results there and update the root README's evaluation summary. Keep earlier experiments in their dated reports rather than mixing their tables into the current summary. For Baseten, start with the [evaluation guide](evals/baseten/README.md).

Name committed statistics by date and link them from the matching report. Record the model and provider, skill and rubric snapshots, tool configuration, repetitions, and fixture limitations. Separate targeted follow-ups from full-suite results, especially when assertions change. State which revision each run evaluates and whether the comparison establishes improvement. Do not combine scores from different rubrics.
