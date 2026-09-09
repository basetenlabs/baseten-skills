import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from baseten_skills_evals import runner


class RunnerTests(unittest.TestCase):
    def test_token_auth_and_environment_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'ANTHROPIC_AUTH_TOKEN': 'provider-secret', 'BASETEN_MCP_KEY': 'test-key',
            'AWS_SECRET_ACCESS_KEY': 'do-not-forward', 'BASETEN_API_KEY': 'personal-key',
        }, clear=True):
            runner.require_auth()
            env = runner._subproc_env(Path(directory) / 'run')
            self.assertEqual(env['ANTHROPIC_AUTH_TOKEN'], 'provider-secret')
            self.assertEqual(env['BASETEN_API_KEY'], 'test-key')
            self.assertNotIn('AWS_SECRET_ACCESS_KEY', env)
            self.assertEqual(Path(env['HOME']).stat().st_mode & 0o777, 0o700)
            self.assertEqual((Path(env['HOME']) / '.trussrc').stat().st_mode & 0o777, 0o600)
            self.assertEqual(runner.sanitize('provider-secret test-key'), '[REDACTED] [REDACTED]')

    def test_missing_auth_fails(self):
        with patch.dict(os.environ, {'BASETEN_MCP_KEY': 'test-key'}, clear=True):
            with self.assertRaises(ValueError):
                runner.require_auth()

    def test_artifacts_cannot_live_in_repository(self):
        with self.assertRaises(ValueError):
            runner.external_path(runner.REPO / 'evals' / 'runs')

    def test_historical_skill_excludes_current_and_old_rubrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / 'old' / 'baseten'
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('historical content')
            (skill / 'evals').mkdir()
            (skill / 'evals' / 'evals.json').write_text('rubric')
            digest = runner.skill_hash(skill)
            (skill / 'evals' / 'evals.json').write_text('changed rubric')
            self.assertEqual(digest, runner.skill_hash(skill))
            runner.setup_workdir(root / 'work', skill)
            exposed = root / 'work' / '.claude' / 'skills' / 'baseten'
            self.assertEqual((exposed / 'SKILL.md').read_text(), 'historical content')
            self.assertFalse((exposed / 'evals').exists())

    def test_artifact_root_rejects_ancestor_project_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ambient = root / '.claude' / 'skills' / 'personal'
            ambient.mkdir(parents=True)
            (ambient / 'SKILL.md').write_text('ambient skill')
            with self.assertRaisesRegex(ValueError, 'inherits ambient skills'):
                runner.reject_ambient_skill_ancestors(root / 'workspace' / 'runs')

    def test_clean_artifact_root_passes_ancestor_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            runner.reject_ambient_skill_ancestors(Path(directory))

    def test_transport_error_is_not_a_successful_result(self):
        self.assertFalse(runner.result_success(None))
        self.assertFalse(runner.result_success({'type': 'result', 'subtype': 'success', 'is_error': True}))
        self.assertTrue(runner.result_success({'type': 'result', 'subtype': 'success', 'is_error': False}))

    def test_grading_rejects_missing_or_inconsistent_assertions(self):
        grade = {'expectations': [{'text': 'works', 'passed': True, 'evidence': 'output'}],
                 'summary': {'passed': 1, 'failed': 0, 'total': 1, 'pass_rate': 1.0}}
        runner.validate_grading(grade, ['works'])
        with self.assertRaises(ValueError):
            runner.validate_grading(grade, ['different'])
        grade['summary']['pass_rate'] = 0
        with self.assertRaises(ValueError):
            runner.validate_grading(grade, ['works'])

    def test_grader_example_allows_rounded_pass_rate(self):
        grade = {'expectations': [
            {'text': str(i), 'passed': i < 2, 'evidence': 'output'} for i in range(3)
        ], 'summary': {'passed': 2, 'failed': 1, 'total': 3, 'pass_rate': 0.67}}
        runner.validate_grading(grade, ['0', '1', '2'])

    def test_fixture_lock_identity_is_shared_by_remote_model(self):
        with patch.dict(os.environ, {'BASETEN_MCP_KEY': 'workspace-one'}, clear=True):
            key = runner.fixture_lock_key('fixture-a', 'model-one')
            self.assertEqual(key, runner.fixture_lock_key('different-label', 'model-one'))
            self.assertNotEqual(key, runner.fixture_lock_key('fixture-a', 'model-two'))
            self.assertNotIn('workspace-one', key)
        with patch.dict(os.environ, {'BASETEN_MCP_KEY': 'workspace-two'}, clear=True):
            self.assertNotEqual(key, runner.fixture_lock_key('fixture-a', 'model-one'))

    def test_fixture_lock_blocks_other_process_and_releases_after_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'BASETEN_MCP_KEY': 'workspace-one',
        }, clear=True), patch.object(runner.tempfile, 'gettempdir', return_value=directory):
            path = Path(directory) / 'baseten-skills-evals-locks' / (runner.fixture_lock_key('fixture', 'model') + '.lock')
            probe = [sys.executable, '-c',
                     'import fcntl,sys; f=open(sys.argv[1], "w"); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)', str(path)]
            with self.assertRaisesRegex(RuntimeError, 'executor failed'):
                with runner.fixture_execution_lock('fixture', 'model'):
                    self.assertNotEqual(subprocess.run(probe, capture_output=True).returncode, 0)
                    raise RuntimeError('executor failed')
            self.assertEqual(subprocess.run(probe, capture_output=True).returncode, 0)

    def test_pre_hook_waits_for_deployment_and_sanitizes_logs(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'BASETEN_MCP_KEY': 'test-key',
        }, clear=True), patch.object(runner.subprocess, 'run') as run, patch.object(runner.Path, 'exists', return_value=True):
            run.return_value.returncode = 0
            run.return_value.stdout = 'test-key output'
            run.return_value.stderr = 'test-key warning'
            root = Path(directory)
            runner._run_pre_hook('broken-deployment', 'model-id', 'model-name', root)
            self.assertGreaterEqual(run.call_args.kwargs['timeout'], 330)
            self.assertTrue(run.call_args.kwargs['capture_output'])
            self.assertEqual(run.call_args.kwargs['env']['FIXTURE_MODEL_NAME'], 'model-name')
            self.assertEqual((root / 'pre_hook_stdout.txt').read_text(), '[REDACTED] output')
            self.assertEqual((root / 'pre_hook_stderr.txt').read_text(), '[REDACTED] warning')
            run.return_value.returncode = 1
            with self.assertRaisesRegex(RuntimeError, 'exit code 1'):
                runner._run_pre_hook('broken-deployment', 'model-id', 'model-name', root)

    def test_executor_error_records_evidence_and_unavailable_provider_cost(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'ANTHROPIC_AUTH_TOKEN': 'provider-secret', 'BASETEN_MCP_KEY': 'test-key',
            'ANTHROPIC_BASE_URL': 'https://inference.baseten.co',
        }, clear=True), patch.object(runner.subprocess, 'Popen') as popen:
            process = popen.return_value
            process.returncode = 1
            events = [
                {'type': 'system', 'subtype': 'init', 'skills': [], 'mcp_servers': []},
                {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': 'test-key evidence'}]}},
                {'type': 'result', 'subtype': 'error_during_execution', 'is_error': True, 'total_cost_usd': 99},
            ]
            process.communicate.return_value = ('\n'.join(map(json.dumps, events)).encode(), b'provider-secret error')
            root = Path(directory) / 'run'
            status = runner.run_executor(eval_item={'prompt': 'test'}, work_root=root,
                                         mode=runner.Mode(False, False, False), skill_dir=Path('/unused/baseten'),
                                         model='provider-model', preamble=None)
            self.assertFalse(status['executor_ok'])
            self.assertIsNone(json.loads((root / 'timing.json').read_text())['cost_usd'])
            self.assertIn('Tool result:', (root / 'transcript.md').read_text())
            self.assertNotIn('test-key', (root / 'events.jsonl').read_text())
            self.assertEqual((root / 'stderr.txt').read_text(), '[REDACTED] error')
            self.assertFalse((root / 'mcp.json').exists())


if __name__ == '__main__':
    unittest.main()
