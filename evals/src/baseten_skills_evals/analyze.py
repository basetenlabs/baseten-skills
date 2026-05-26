"""Analyze a clean sweep of stats.jsonl into the canonical report.

Outputs three levels (global, per-group, per-eval) × three metrics
(pass_rate, wall_s, cost_usd, with gross_input_tokens as appendix).

Inferential machinery:
- Per-cell (eval × mode): mean over runs + SE = sd/√n.
- Aggregates: cluster bootstrap over evals (the natural unit of variation
  given pairing structure), 2000 resamples, 95% percentile CIs.
- Marginal Δ between modes: per-eval paired delta, then cluster bootstrap.
- "Effect non-zero" ⇔ 95% CI excludes 0.

Usage:
    python -m baseten_skills_evals.analyze --stats <path-to-stats.jsonl> \\
        [--sha <commit-prefix>] [--out report.md]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

MODES_ORDER = ["s0b0d0", "s0b0d1", "s0b1d1", "s1b0d1", "s1b1d1"]
BOOT_N = 2000
SEED = 42

# Group order for report tables. Groups not listed are appended in sort order.
GROUP_ORDER = ["author", "integrate", "operate", "overview", "debug", "tune"]


def _eval_groups(evals_path: pathlib.Path) -> dict[int, str]:
    """Read eval_id → group directly from evals.json (single source of truth)."""
    data = json.loads(evals_path.read_text())
    return {int(e["id"]): e["group"] for e in data["evals"]}


def load(stats_path: pathlib.Path, evals_path: pathlib.Path, sha: str | None) -> pd.DataFrame:
    """Read stats.jsonl into a DataFrame; filter to model+sha if given."""
    rows = [
        json.loads(line)
        for line in stats_path.read_text().splitlines()
        if line.strip()
    ]
    df = pd.DataFrame(rows)
    if sha:
        df = df[df["sha"].str.startswith(sha)]
    df = df[df["grader_status"] == "ok"].copy()
    eval_group = _eval_groups(evals_path)
    df["category"] = df["eval_id"].map(eval_group)
    missing = df[df["category"].isna()]["eval_id"].unique().tolist()
    assert not missing, f"eval_id(s) in stats.jsonl missing from evals.json: {missing}"
    return df


def _ordered_groups(df: pd.DataFrame) -> list[str]:
    present = set(df["category"].unique())
    ordered = [g for g in GROUP_ORDER if g in present]
    extras = sorted(present - set(ordered))
    return ordered + extras


def cluster_boot_ci(df: pd.DataFrame, metric: str, n_resamples: int = BOOT_N) -> tuple[float, float, float]:
    """Cluster bootstrap over evals: resample evals with replacement, mean of cell-means.

    df is filtered to one mode and one scope (group or global).
    """
    if df.empty:
        return (float("nan"),) * 3
    # cell mean = mean of `metric` across runs for one (eval, mode)
    cell_means = df.groupby("eval_id")[metric].mean()
    evals = cell_means.index.to_numpy()
    vals = cell_means.values
    if len(evals) <= 1:
        return (float(vals.mean()), float(vals.mean()), float(vals.mean()))
    rng = np.random.default_rng(SEED)
    boots = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, len(evals), size=len(evals))
        boots[i] = vals[idx].mean()
    return float(vals.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def cluster_boot_paired_delta(df: pd.DataFrame, metric: str, mode_a: str, mode_b: str,
                              n_resamples: int = BOOT_N) -> tuple[float, float, float]:
    """Paired Δ = mean over evals of (mean(mode_a) - mean(mode_b)). Cluster bootstrap over evals."""
    sub = df[df["mode"].isin([mode_a, mode_b])]
    if sub.empty:
        return (float("nan"),) * 3
    # per-eval mean for each mode
    by = sub.groupby(["eval_id", "mode"])[metric].mean().unstack("mode")
    by = by.dropna(subset=[mode_a, mode_b])
    if by.empty:
        return (float("nan"),) * 3
    deltas = (by[mode_a] - by[mode_b]).to_numpy()
    if len(deltas) <= 1:
        d = float(deltas.mean())
        return (d, d, d)
    rng = np.random.default_rng(SEED)
    boots = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, len(deltas), size=len(deltas))
        boots[i] = deltas[idx].mean()
    return float(deltas.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def fmt(value: float, *, lo: float | None = None, hi: float | None = None, fmt_spec: str = ".2f") -> str:
    if np.isnan(value):
        return "—"
    if lo is None or hi is None:
        return f"{value:{fmt_spec}}"
    # Symmetric half-width if approx symmetric, otherwise asymmetric.
    half = (hi - lo) / 2
    return f"{value:{fmt_spec}} ±{half:{fmt_spec}}"


def fmt_delta(value: float, lo: float, hi: float, fmt_spec: str = "+.2f") -> str:
    if np.isnan(value):
        return "—"
    sig = "*" if (lo > 0 or hi < 0) else " "
    half = (hi - lo) / 2
    return f"{value:{fmt_spec}} ±{half:.2f}{sig}"


# ──────────────────────────────────────────────────────────────────────────────
# Report sections.
# ──────────────────────────────────────────────────────────────────────────────


def section_overview(df: pd.DataFrame) -> str:
    n_cells = len(df.groupby(["eval_id", "mode"]))
    n_runs = len(df)
    modes = sorted(df["mode"].unique().tolist(), key=lambda m: MODES_ORDER.index(m) if m in MODES_ORDER else 99)
    evals = sorted(df["eval_id"].unique().tolist())
    sha = df["sha"].iloc[0] if len(df) else "?"
    model = df["model"].iloc[0] if len(df) else "?"
    return (
        f"## Sweep\n\n"
        f"- model: `{model}`  sha: `{sha[:7]}`\n"
        f"- modes ({len(modes)}): {', '.join(modes)}\n"
        f"- evals ({len(evals)}): {', '.join(map(str, evals))}\n"
        f"- cells: {n_cells}  runs: {n_runs}\n"
    )


def table_global(df: pd.DataFrame, metric: str, fmt_spec: str) -> str:
    """One row per mode: mean ± CI across all evals (cluster-boot)."""
    out = [f"### Global — {metric}", "", "| mode | value (mean ± CI) |", "|---|---|"]
    for m in MODES_ORDER:
        sub = df[df["mode"] == m]
        if sub.empty: continue
        mean, lo, hi = cluster_boot_ci(sub, metric)
        out.append(f"| {m} | {fmt(mean, lo=lo, hi=hi, fmt_spec=fmt_spec)} |")
    return "\n".join(out) + "\n"


def table_per_group(df: pd.DataFrame, metric: str, fmt_spec: str) -> str:
    out = [f"### Per task-group — {metric}", "", "| group | " + " | ".join(MODES_ORDER) + " |", "|---|" + "---|" * len(MODES_ORDER)]
    for cat in _ordered_groups(df):
        row = [cat]
        for m in MODES_ORDER:
            sub = df[(df["mode"] == m) & (df["category"] == cat)]
            if sub.empty:
                row.append("—")
                continue
            mean, lo, hi = cluster_boot_ci(sub, metric)
            row.append(fmt(mean, lo=lo, hi=hi, fmt_spec=fmt_spec))
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out) + "\n"


def table_per_eval(df: pd.DataFrame, metric: str, fmt_spec: str) -> str:
    out = [f"### Per eval — {metric}", "", "| eval | " + " | ".join(MODES_ORDER) + " |", "|---|" + "---|" * len(MODES_ORDER)]
    for eid in sorted(df["eval_id"].unique()):
        row = [str(eid)]
        for m in MODES_ORDER:
            sub = df[(df["mode"] == m) & (df["eval_id"] == eid)]
            if sub.empty:
                row.append("—")
                continue
            # Cell-level SE = sd/√n; report mean ± SE here (n typically too small for boot).
            vals = sub[metric].values
            if len(vals) <= 1:
                row.append(fmt(float(vals.mean()), fmt_spec=fmt_spec))
            else:
                m_ = float(vals.mean())
                se = float(vals.std(ddof=1) / np.sqrt(len(vals)))
                row.append(f"{m_:{fmt_spec}} ±{se:.2f}")
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out) + "\n"


def table_marginals(df: pd.DataFrame, metric: str, fmt_spec: str = "+.2f", *,
                    pairs: list[tuple[str, str, str]] | None = None,
                    scope_label: str | None = None) -> str:
    if pairs is None:
        pairs = [
            ("skill (no MCP)",      "s1b0d1", "s0b0d1"),
            ("skill (with MCP)",    "s1b1d1", "s0b1d1"),
            ("baseten MCP (no skill)", "s0b1d1", "s0b0d1"),
            ("baseten MCP (with skill)", "s1b1d1", "s1b0d1"),
            ("docs MCP only",       "s0b0d1", "s0b0d0"),
            ("full vs naked",       "s1b1d1", "s0b0d0"),
        ]
    header = f"### Marginal effects — {metric}"
    if scope_label:
        header += f" ({scope_label})"
    out = [header, "", "| comparison | Δ (mean ± CI) |", "|---|---|"]
    for label, a, b in pairs:
        d, lo, hi = cluster_boot_paired_delta(df, metric, a, b)
        out.append(f"| {label} = {a} − {b} | {fmt_delta(d, lo, hi, fmt_spec)} |")
    out.append("")
    out.append("\\* CI excludes 0 (effect is non-zero at α=0.05).")
    return "\n".join(out) + "\n"


def table_marginals_per_group(df: pd.DataFrame, metric: str, fmt_spec: str = "+.2f") -> str:
    pairs = [
        ("ΔSkill | no MCP", "s1b0d1", "s0b0d1"),
        ("ΔSkill | + MCP",  "s1b1d1", "s0b1d1"),
        ("ΔMCP | no skill", "s0b1d1", "s0b0d1"),
        ("ΔMCP | + skill",  "s1b1d1", "s1b0d1"),
        ("Δfull vs naked",  "s1b1d1", "s0b0d0"),
    ]
    out = [f"### Marginals per task-group — {metric}", "", "| group | " + " | ".join(p[0] for p in pairs) + " |", "|---|" + "---|" * len(pairs)]
    for cat in _ordered_groups(df):
        sub = df[df["category"] == cat]
        row = [cat]
        for label, a, b in pairs:
            d, lo, hi = cluster_boot_paired_delta(sub, metric, a, b)
            row.append(fmt_delta(d, lo, hi, fmt_spec))
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    out.append("\\* in any cell: CI excludes 0.")
    return "\n".join(out) + "\n"


def write_report(df: pd.DataFrame, out_path: pathlib.Path) -> None:
    sections: list[str] = [section_overview(df)]

    for metric, label, fmt_spec, delta_spec in (
        ("pass_rate", "pass rate", ".2f", "+.2f"),
        ("wall_s",    "wall (s)",  ".0f", "+.0f"),
        ("cost_usd",  "cost ($)",  ".3f", "+.3f"),
    ):
        sections.append(f"\n## {label.title()}\n")
        sections.append(table_global(df, metric, fmt_spec))
        sections.append(table_per_group(df, metric, fmt_spec))
        sections.append(table_marginals(df, metric, delta_spec, scope_label="global"))
        sections.append(table_marginals_per_group(df, metric, delta_spec))
        sections.append(table_per_eval(df, metric, fmt_spec))

    # Appendix: gross_input_tokens (cache-agnostic complexity).
    sections.append("\n## Appendix — gross input tokens (cache-agnostic complexity)\n")
    sections.append(table_global(df, "gross_input_tokens", ".0f"))
    sections.append(table_per_group(df, "gross_input_tokens", ".0f"))

    sections.append("\n## Methodology notes\n")
    sections.append(
        "- Cell stat (per eval × mode): mean over runs.\n"
        "- Aggregate (group/global × mode): mean of cell-means; 95% CI via cluster bootstrap "
        f"over evals ({BOOT_N} resamples, percentile).\n"
        "- Marginal Δ (mode_a − mode_b): per-eval paired delta, then cluster bootstrap.\n"
        "- Per-eval × mode: cell mean ± SE (sd/√n). n is small (≤ runs); use these as directional.\n"
        "- `*` next to a marginal = its 95% CI excludes 0.\n"
        "- Single-shot grader per cell; grader stochasticity not separately bounded.\n"
    )

    out_path.write_text("\n".join(sections))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, type=pathlib.Path)
    ap.add_argument("--evals", type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[3] / "skills/baseten/evals/evals.json",
                    help="Path to evals.json (source of eval_id → group).")
    ap.add_argument("--sha", default=None, help="Commit prefix to filter (e.g. abcdef0)")
    ap.add_argument("--out", default="report.md", type=pathlib.Path)
    args = ap.parse_args(argv)

    df = load(args.stats, args.evals, args.sha)
    if df.empty:
        print("No rows matched filter.", file=sys.stderr)
        return 1
    write_report(df, args.out)
    print(f"wrote {args.out}  ({len(df)} runs, {df['eval_id'].nunique()} evals, {df['mode'].nunique()} modes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
