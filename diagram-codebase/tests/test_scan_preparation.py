"""验证扫描准备汇总和可选进度的边界,避免试错与不可归因等待.

使用 unittest 在临时工程中调用真实 CLI/解析流程,缺包和超时用模拟复现;
不安装依赖,不扫描用户工程,不执行目标程序.
"""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('diagram_cli', Path(__file__).resolve().parents[1] / 'scripts/analyze.py')
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)
scan = cli.scanlib


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / '.cache/index.json'
        guard = patch.object(scan, 'cache_path', return_value=self.cache)
        guard.start()
        self.addCleanup(guard.stop)

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def run_cli(self, *options):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(['scan', '--mode', 'configured', '--root', str(self.root), *options])
        return code, out.getvalue(), err.getvalue()

    def config(self):
        self.put('src/app.py', 'def entry(): return 1\n')
        self.put('build.cfg', 'selected')
        path = self.root / 'docs/architecture/analysis-config.json'
        scan.prepare_config(self.root, {'schema_version': 1, 'status': 'ready', 'context': 'test scope',
            'scan': {'scopes': ['src']}, 'sources': [{'path': 'build.cfg'}]}, path)
        return path

    def test_all_known_preparation_issues_are_stable_and_do_not_touch_cache(self):
        for name in ['a.c', 'a.md', 'a.sv', 'a.va']:
            self.put('src/'+name, '')
        bad = self.put('bad.json', '{')
        self.put('.cache/index.json', 'previous success')
        self.put('.cache/index.partial.json', 'previous partial')
        before = {p.name: p.read_bytes() for p in self.cache.parent.iterdir()}
        def version(name):
            if name == 'libclang':
                return '0'
            raise scan.importlib.metadata.PackageNotFoundError(name)
        with patch.object(scan.importlib.metadata, 'version', side_effect=version), patch.object(scan.subprocess, 'run') as worker:
            result = self.run_cli('--scope', 'src', '--config', str(bad), '--progress')
            worker.assert_not_called()
        code, out, err = result
        self.assertEqual(code, 1)
        self.assertEqual(out, '')
        ordered = ['no offline adapter', 'dependency [c]', 'dependency [hdl]', 'dependency [markdown]', 'configuration:']
        self.assertEqual(sorted(ordered, key=err.index), ordered)
        for package in ['libclang', 'pyslang', 'markdown-it-py', 'mdurl']:
            self.assertIn(package, err)
        self.assertIn('version mismatch', err)
        self.assertIn('status="blocked"', err)
        self.assertEqual(err.count('event=preparation_start'), 1)
        self.assertEqual(err.count('event=preparation_end'), 1)
        self.assertNotIn('event=file_', err)
        self.assertNotIn('event=cache_', err)
        self.assertEqual({p.name: p.read_bytes() for p in self.cache.parent.iterdir()}, before)

    def test_unreadable_or_invalid_config_without_scope_never_invents_range(self):
        for name, content in [('missing.json', None), ('invalid.json', '{'), ('shape.json', '[]')]:
            path = self.root / name
            if content is not None:
                self.put(name, content)
            with self.subTest(name=name), patch.object(scan, 'inventory', side_effect=AssertionError('must not walk')):
                code, out, err = self.run_cli('--config', str(path), '--progress')
            self.assertEqual(code, 1)
            self.assertEqual(out, '')
            self.assertNotIn('must not walk', err)
            self.assertIn('event=preparation_end', err)
            self.assertIn('status="blocked"', err)
            self.assertFalse(self.cache.exists())

    def test_pending_stale_and_edited_config_block_before_workers(self):
        path = self.config()
        original = path.read_bytes()
        for kind in ['pending', 'stale', 'edited']:
            path.write_bytes(original)
            self.put('build.cfg', 'selected')
            if kind == 'pending':
                value = {'schema_version': 1, 'status': 'pending', 'context': 'waiting',
                         'scan': {'scopes': ['src']}, 'missing': ['target required']}
                scan.prepare_config(self.root, value, path, scan.digest(path))
            elif kind == 'stale':
                self.put('build.cfg', 'changed')
            else:
                value = json.loads(path.read_text(encoding='utf-8'))
                value['context'] = 'changed without review'
                path.write_text(json.dumps(value), encoding='utf-8')
            before = path.read_bytes()
            with self.subTest(kind=kind), patch.object(scan.subprocess, 'run') as worker:
                code, _, err = self.run_cli('--config', str(path), '--progress')
                worker.assert_not_called()
            self.assertEqual(code, 1)
            self.assertIn({'pending': 'CONFIG_PENDING', 'stale': 'STALE_CONFIG', 'edited': 'CONFIG_EDITED'}[kind], err)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(self.cache.exists())

    def test_progress_preserves_stdout_index_and_ready_config(self):
        path = self.config()
        self.put('src/中文 文件.py', 'def helper(): return 2\n')
        self.put('src/interface.h', '/* include-only, no parser required */')
        before = path.read_bytes()
        results = []
        # Equal clocks permit exact comparison of the existing elapsed metadata.
        with patch.object(scan.time, 'monotonic', return_value=100.0):
            for progress in [False, True]:
                code, out, err = self.run_cli('--config', str(path), *(['--progress'] if progress else []))
                self.assertEqual(code, 0, err)
                results.append((out, err, self.cache.read_bytes()))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(results[0][2], results[1][2])
        self.assertEqual(results[0][1], '')
        err = results[1][1]
        self.assertEqual(err.count('event=file_start'), 2)
        self.assertEqual(err.count('event=file_end'), 2)
        self.assertIn('file="src/中文 文件.py"', err)
        self.assertNotIn('interface.h', err)
        self.assertNotIn(str(self.root), err)
        self.assertNotIn('def helper', err)
        self.assertIn('elapsed_seconds=0.0', err)
        for event in ['preparation_start', 'preparation_end', 'cache_write_start', 'cache_write_end']:
            self.assertEqual(err.count('event='+event), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_timeout_and_parse_error_are_distinct_and_preserve_success(self):
        self.put('app.py', 'pass\n')
        self.put('.cache/index.json', 'previous success')
        cases = [('timeout', subprocess.TimeoutExpired('private compiler args', 1)),
                 ('parse_error', subprocess.CompletedProcess([], 1, '', 'parse failure'))]
        for outcome, action in cases:
            with self.subTest(outcome=outcome), patch.object(scan.subprocess, 'run') as worker:
                if isinstance(action, Exception):
                    worker.side_effect = action
                else:
                    worker.return_value = action
                code, out, err = self.run_cli('--progress')
            self.assertEqual(code, 1)
            self.assertIn('scan=partial', out)
            self.assertIn(f'status="{outcome}"', err)
            self.assertNotIn('private compiler args', err)
            self.assertEqual(self.cache.read_text(), 'previous success')
            self.assertIn('index_status="partial"', err)
            self.assertTrue(self.cache.with_name('index.partial.json').exists())

    def test_real_syntax_error_is_not_reported_as_timeout(self):
        self.put('invalid.py', 'def broken(:')
        code, _, err = self.run_cli('--progress')
        self.assertEqual(code, 1)
        self.assertIn('status="parse_error"', err)
        self.assertNotIn('status="timeout"', err)

    def test_cache_failure_reports_stage_and_cleans_temporary_file(self):
        self.put('app.py', 'pass\n')
        self.put('.cache/index.json', 'previous success')
        for operation in ['dump', 'replace']:
            with self.subTest(operation=operation):
                target = scan.json if operation == 'dump' else scan.os
                with patch.object(target, operation, side_effect=PermissionError('simulated write denial')):
                    code, _, err = self.run_cli('--progress')
                self.assertEqual(code, 1)
                self.assertIn('event=cache_write_start', err)
                self.assertIn('event=cache_write_end status="error"', err)
                self.assertEqual(self.cache.read_text(), 'previous success')
                self.assertEqual(list(self.cache.parent.iterdir()), [self.cache])

    def test_cache_directory_failure_has_end_event(self):
        self.put('app.py', 'pass\n')
        self.put('.cache', 'not a directory')
        code, _, err = self.run_cli('--progress')
        self.assertEqual(code, 1)
        self.assertIn('event=cache_write_end status="error"', err)

    def test_file_launch_failure_has_end_event_without_cache_write(self):
        self.put('app.py', 'pass\n')
        with patch.object(scan.subprocess, 'run', side_effect=OSError('cannot launch')):
            code, _, err = self.run_cli('--progress')
        self.assertEqual(code, 1)
        self.assertIn('event=file_end', err)
        self.assertIn('status="error"', err)
        self.assertNotIn('event=cache_write_start', err)

    def test_progress_flushes_and_escapes_file_name(self):
        with patch('builtins.print') as output:
            scan.report_progress(True, 'file_start', file='中文\n文件.py', status='running')
        self.assertTrue(output.call_args.kwargs['flush'])
        self.assertIs(output.call_args.kwargs['file'], scan.sys.stderr)
        self.assertIn('中文\\n文件.py', output.call_args.args[0])
        self.assertNotIn('\n', output.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
