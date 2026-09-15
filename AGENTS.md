# Notes for agents working on this repo

- Skill content lives under `skills/<name>/` (`SKILL.md` + `references/*.md`).
  Conventions and the source-of-truth rule (docs/samples first, skill draws
  from there) are in [CONTRIBUTING.md](CONTRIBUTING.md).
- Markdown under `skills/<name>/SKILL.md` and `skills/<name>/references/` is
  normalized by `bin/markdown_llm_preprocessor` via pre-commit. Run
  `pre-commit run --all-files` before pushing. CI enforces it.
- Evaluation harness, methodology, and reproduction commands are in
  [`evals/baseten/README.md`](evals/baseten/README.md).
  Each dated report links its own statistics. `evals/baseten/results/stats.jsonl`
  belongs only to the May 26, 2026 benchmark; do not overwrite it with new runs.
  Skill changes that affect agent behavior should ship with a rerun;
  see [Run evaluations before merging](CONTRIBUTING.md#run-evaluations-before-merging).
