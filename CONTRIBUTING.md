# Contributing

## Adding or changing a skill

Each skill is a directory under `skills/`. For skill structure, writing patterns, progressive disclosure, and other conventions, follow:

- The skill creation best practices at <https://agentskills.io/skill-creation/best-practices>.
- The `skill-creator` skill from <https://github.com/anthropics/skills>, which guides the full create / iterate / evaluate loop.

## Running evals before merging

Skill changes ship with eval results, produced via the `skill-creator` workflow above. Eval definitions (the prompts and their assertions) live alongside the skill at `skills/<name>/evals/evals.json` so they can be re-run against future versions. Raw run artifacts (per-eval outputs, grading JSON, the HTML viewer) belong in a workspace directory outside the repo so the commit history stays focused on the skill and its evals.

## Writing up results

Write a curated summary into `eval-results/<skill>/YYYY-MM-DD.md` and link it from the PR. The summary should let a reviewer judge the change without needing the raw artifacts:

- The prompts that were run (verbatim).
- The assertions that were checked.
- For each prompt: with-skill vs. baseline pass rate, tokens, duration, and one or two lines of qualitative observation.
- Takeaways that drove the changes in the PR.

If multiple iterations happen on the same day, append to the same file. A new day starts a new file.
