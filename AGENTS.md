# Notes for agents working on this repo

- Skill content lives under `skills/<name>/` (`SKILL.md` + `references/*.md`).
  Conventions and the source-of-truth rule (docs/samples first, skill draws
  from there) are in [CONTRIBUTING.md](CONTRIBUTING.md).
- Markdown under `skills/<name>/SKILL.md` and `skills/<name>/references/` is
  normalised by `bin/markdown_llm_preprocessor` via pre-commit. Run
  `pre-commit run --all-files` before pushing — CI enforces it.
- Evaluation harness, methodology, and reproduction commands are in
  [`evals/baseten/README.md`](evals/baseten/README.md).
  Canonical numbers live in `evals/baseten/results/stats.jsonl`.
  Skill changes that affect agent behavior should ship with a re-run;
  see CONTRIBUTING.md "Running evals before merging".
