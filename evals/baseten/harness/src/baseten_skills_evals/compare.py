"""Compare a refreshed skill, its predecessor, and a matched no-skill baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def read_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"No completed runs in {path}")
    if any(not r.get("isolation_passed") or r.get("grader_status") != "ok" or r.get("errors") for r in rows):
        raise ValueError(f"Invalid execution rows in {path}; resolve infrastructure failures first")
    # Graders may round displayed rates to two decimals. Aggregate exact counts.
    for row in rows:
        row["pass_rate"] = row["passed"] / row["total"]
        row["weighted_pass_rate"] = row["weighted_passed"] / row["weighted_total"]
    return rows


def paired_delta(left: dict[int, float], right: dict[int, float]) -> dict:
    if left.keys() != right.keys() or not left:
        raise ValueError("Comparisons require the same nonempty task set")
    values = np.array([left[k] - right[k] for k in sorted(left)])
    rng = np.random.default_rng(20260909)
    samples = rng.choice(values, size=(10000, len(values)), replace=True).mean(axis=1)
    return {"mean": float(values.mean()), "ci95": np.quantile(samples, [0.025, 0.975]).tolist()}


def compare(current: list[dict], previous: list[dict], expected_ids: set[int]) -> dict:
    rows = current + previous
    for field in ("model", "provider", "evals_sha256", "fixtures_sha256"):
        values = {r.get(field) for r in rows}
        if None in values or len(values) != 1:
            raise ValueError(f"All arms require identical recorded {field}")
    arms = {
        "no_skill": [r for r in current if r["mode"] == "s0b1d1"],
        "refreshed": [r for r in current if r["mode"] == "s1b1d1"],
        "previous": [r for r in previous if r["mode"] == "s1b1d1"],
    }
    grouped = {}
    for arm, arm_rows in arms.items():
        by_id = defaultdict(list)
        for row in arm_rows:
            by_id[row["eval_id"]].append(row)
        if by_id.keys() != expected_ids:
            raise ValueError(f"Incomplete {arm}: missing {sorted(expected_ids - by_id.keys())}; extra {sorted(by_id.keys() - expected_ids)}")
        if len({r.get('skill_sha256') for r in arm_rows}) != 1:
            raise ValueError(f"Mixed skill versions in {arm}")
        grouped[arm] = by_id
    for eid in expected_ids:
        if len({len(grouped[a][eid]) for a in arms}) != 1:
            raise ValueError(f"Unequal repetitions for task {eid}")
    metrics = ("pass_rate", "weighted_pass_rate", "wall_s", "gross_input_tokens", "output_tokens")
    tasks = {
        arm: {eid: {"n": len(rs), **{m: float(np.mean([r[m] for r in rs])) for m in metrics}} for eid, rs in groups.items()}
        for arm, groups in grouped.items()
    }
    means = {a: {m: float(np.mean([t[m] for t in tasks[a].values()])) for m in metrics} for a in arms}
    deltas = {
        other: {m: paired_delta({i: t[m] for i, t in tasks['refreshed'].items()}, {i: t[m] for i, t in tasks[other].items()}) for m in metrics}
        for other in ("no_skill", "previous")
    }
    return {"model": rows[0]['model'], "tasks": tasks, "means": means, "refreshed_minus": deltas,
            "method": "Equal task weighting; paired bootstrap over tasks, 10000 draws, seed 20260909. Does not estimate within-task model variance at one repetition."}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--current', type=Path, required=True)
    ap.add_argument('--previous', type=Path, required=True)
    ap.add_argument('--evals', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--ids', type=int, nargs='+', help='Explicit task subset for a targeted comparison')
    args = ap.parse_args()
    ids = {e['id'] for e in json.loads(args.evals.read_text())['evals']}
    if args.ids:
        requested = set(args.ids)
        if not requested <= ids:
            raise ValueError('Requested task IDs are missing from the eval definition')
        ids = requested
    current, previous = read_rows(args.current), read_rows(args.previous)
    expected_hash = hashlib.sha256(args.evals.read_bytes()).hexdigest()
    if any(row["evals_sha256"] != expected_hash for row in current + previous):
        raise ValueError("The supplied eval definition differs from the recorded rubric")
    result = compare(current, previous, ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'means': result['means'], 'refreshed_minus': result['refreshed_minus']}, indent=2))


if __name__ == '__main__':
    main()
