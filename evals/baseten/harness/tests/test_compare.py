import unittest
import json
import tempfile
from pathlib import Path

from baseten_skills_evals.compare import compare, paired_delta, read_rows


def row(eid, mode, score, sha):
    return dict(eval_id=eid, mode=mode, weighted_pass_rate=score, pass_rate=score, wall_s=10,
                gross_input_tokens=100, output_tokens=10, model='test', provider='test',
                evals_sha256='same', fixtures_sha256='same', skill_sha256=sha)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.current = [row(i, m, 1, 'new') for i in [1, 2] for m in ['s0b1d1', 's1b1d1']]
        self.previous = [row(i, 's1b1d1', 0.5, 'old') for i in [1, 2]]

    def test_paired_effect_and_constant_interval(self):
        r = compare(self.current, self.previous, {1, 2})
        self.assertEqual(r['refreshed_minus']['previous']['weighted_pass_rate'], {'mean': 0.5, 'ci95': [0.5, 0.5]})

    def test_incomplete_or_different_tasks_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.current, self.previous[:1], {1, 2})
        with self.assertRaises(ValueError):
            paired_delta({1: 1}, {2: 1})

    def test_changed_rubric_rejected(self):
        self.previous[0]['evals_sha256'] = 'different'
        with self.assertRaises(ValueError):
            compare(self.current, self.previous, {1, 2})

    def test_unbalanced_repetitions_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.current, self.previous + self.previous[:1], {1, 2})

    def test_aggregation_uses_exact_counts(self):
        data = dict(isolation_passed=True, grader_status="ok", errors=0,
                    passed=2, total=3, pass_rate=0.67,
                    weighted_passed=2, weighted_total=3, weighted_pass_rate=0.6667)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'stats.jsonl'
            path.write_text(json.dumps(data) + '\n')
            result = read_rows(path)[0]
        self.assertEqual(result['pass_rate'], 2 / 3)
        self.assertEqual(result['weighted_pass_rate'], 2 / 3)
