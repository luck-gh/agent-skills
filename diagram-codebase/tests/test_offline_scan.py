"""验证离线先行,有界查询,失败与过期证据,不运行目标工程.

用 unittest 运行.标准库测试无第三方依赖;解析器实测只在已声明环境中启用.
"""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('offline_scan', Path(__file__).resolve().parents[1] / 'src' / 'offline_scan.py')
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / '.cache' / 'index.json'
        guard = patch.object(scan, 'cache_path', return_value=self.cache)
        guard.start()
        self.addCleanup(guard.stop)

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def python_scan(self):
        self.put('service.py', 'def entry(x):\n    if x:\n        return helper(x)\n    return None\n')
        return scan.scan(scan.inventory(self.root), None, 10)

    def test_even_one_small_file_requires_offline_scan(self):
        self.put('a.py', 'pass\n')
        data = scan.inventory(self.root)
        self.assertEqual(data['route'], 'offline-required')
        self.assertEqual(data['count'], 1)
        self.assertNotIn('pass', scan.inventory_text(data))

    def test_cache_is_readable_json_for_success_and_partial_results(self):
        self.put('service.py', 'def 中文入口():\n    return 1\n')
        for source in ['def 中文入口():\n    return 1\n', 'def invalid(:']:
            with self.subTest(source=source):
                self.put('service.py', source)
                data, cache = scan.scan(scan.inventory(self.root), None, 10)
                text = cache.read_text(encoding='utf-8')
                self.assertEqual(text, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
                self.assertEqual(json.loads(text), data)
                self.assertEqual(scan.load_index(cache), data)
                if data['status'] == 'ok':
                    self.assertIn('中文入口', text)

    def test_scope_excludes_generated_and_explicit_paths(self):
        self.put('src/a.py', 'pass')
        self.put('vendor/b.py', 'pass')
        self.put('src/no/c.py', 'pass')
        self.put('docs/architecture/overview.md', '# generated')
        data = scan.inventory(self.root, excludes=['src/no'])
        self.assertEqual([f['path'] for f in data['files']], ['src/a.py'])

    def test_scope_escape_is_rejected(self):
        with self.assertRaises(ValueError):
            scan.inventory(self.root, ['..'])

    def test_process_files_are_excluded_for_default_and_custom_outputs(self):
        self.put('src/app.py', 'pass')
        for output in ['docs/architecture', 'reports', '.']:
            with self.subTest(output=output):
                self.put(f'{output}/overview.md', '# generated')
                self.put(f'{output}/_work/overview/candidate/overview.md', '# candidate')
                self.put(f'{output}/_work/overview/helper.py', 'not source')
        exclusions = ['reports/overview.md', 'reports/_work', 'overview.md', '_work']
        data = scan.inventory(self.root, excludes=exclusions)
        self.assertEqual([f['path'] for f in data['files']], ['src/app.py'])

    def test_reusable_flags_keep_include_base_directory(self):
        for output in ['docs/architecture', 'reports']:
            with self.subTest(output=output):
                relative = '../' * len(Path(output).parts) + 'inc'
                config = self.put(f'{output}/compile_flags.txt', f'-std=c11\n-I{relative}\n')
                arguments, marker = scan.load_config(self.root, config, ['src/app.c'])
                self.assertEqual(arguments['src/app.c'], ['-std=c11', '-I' + str(self.root / 'inc')])
                self.assertEqual(marker['path'], str(config))
                self.assertEqual(marker['sha256'], scan.digest(config))

    def test_no_extra_c_configuration_does_not_require_a_file(self):
        flags, marker = scan.load_config(self.root, None, ['a.c'])
        self.assertEqual(flags, {'a.c': []})
        self.assertIsNone(marker)

    def config(self, extra=None):
        value = {'schema_version': 1, 'status': 'ready', 'context': '用户已确认当前范围',
                 'scan': {'scopes': ['src']}}
        value.update(extra or {})
        output = self.root / 'docs/architecture/analysis-config.json'
        scan.prepare_config(self.root, value, output)
        return output

    def test_config_prepare_check_reuse_does_not_rewrite_or_search(self):
        self.put('src/app.py', 'def f(): return 1')
        self.put('.cproject', '<project/>')
        output = self.config({'sources': [{'path': '.cproject'}]})
        before = output.read_bytes()
        with patch.object(scan.os, 'walk', side_effect=AssertionError('no search')):
            value = scan.analysis_config(self.root, output)
            scan.analysis_config(self.root, output)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(value['sources'][0]['sha256'], scan.digest(self.root / '.cproject'))
        self.assertEqual(before.decode(), json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    def test_config_without_project_sources_uses_confirmed_inputs(self):
        output = self.config({'c': {'arguments': ['-std=c11', '-I', 'inc']}})
        flags, marker = scan.load_config(self.root, output, ['src/a.c'])
        self.assertEqual(flags['src/a.c'], ['-std=c11', '-I', str(self.root / 'inc')])
        self.assertTrue(marker['analysis_config'])

    def test_config_sources_modified_or_deleted_block_reuse(self):
        source = self.put('.cproject', '<project/>')
        output = self.config({'sources': [{'path': '.cproject'}]})
        source.write_text('<changed/>', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'STALE_CONFIG.*.cproject'):
            scan.analysis_config(self.root, output)
        source.unlink()
        with self.assertRaisesRegex(ValueError, 'STALE_CONFIG'):
            scan.analysis_config(self.root, output)

    def test_environment_fingerprints_do_not_save_values_and_detect_changes(self):
        with patch.dict(scan.os.environ, {'DIAGRAM_TEST_TARGET': 'private-location'}):
            output = self.config({'environment': {'DIAGRAM_TEST_TARGET': None}})
            scan.analysis_config(self.root, output)
        self.assertNotIn('private-location', output.read_text())
        with patch.dict(scan.os.environ, {'DIAGRAM_TEST_TARGET': 'changed-location'}):
            with self.assertRaisesRegex(ValueError, 'STALE_CONFIG.*DIAGRAM_TEST_TARGET'):
                scan.analysis_config(self.root, output)

    def test_pending_is_saved_but_cannot_scan(self):
        output = self.config({'status': 'pending', 'missing': ['请确认目标']})
        with self.assertRaisesRegex(ValueError, 'CONFIG_PENDING.*请确认目标'):
            scan.load_config(self.root, output, [])

    def test_config_manual_edits_and_project_move_are_detected(self):
        output = self.config()
        value = json.loads(output.read_text())
        value['context'] = 'manually changed'
        output.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CONFIG_EDITED'):
            scan.analysis_config(self.root, output)
        with self.assertRaisesRegex(ValueError, 'project location changed'):
            scan.analysis_config(self.root / 'moved', output)

    def test_per_file_arguments_are_not_flattened_and_require_coverage(self):
        output = self.config({'c': {'files': {'src/a.c': ['-DMODE=1'], 'src/b.c': ['-DMODE=2']}}})
        flags, _ = scan.load_config(self.root, output, ['src/a.c', 'src/b.c'])
        self.assertNotEqual(flags['src/a.c'], flags['src/b.c'])
        with self.assertRaisesRegex(ValueError, 'missing 1 selected C'):
            scan.load_config(self.root, output, ['src/new.c'])

    def test_config_rejects_empty_unknown_and_conflicting_options(self):
        for extra in [{'scan': {}}, {'hdl': {'top': 'top'}}, {'verilog-a': {}},
                      {'c': {'arguments': [], 'files': {'a.c': []}}},
                      {'c': {'arguments': ['-Xclang', '-load', 'bad.dll']}},
                      {'status': 'ready', 'missing': ['target']}, {'scan': {'scopes': ['..']}}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.config(extra)

    def test_prepare_never_overwrites_unknown_or_failed_candidate(self):
        output = self.config()
        before = output.read_bytes()
        payload = {'schema_version': 1, 'status': 'ready',
                   'context': 'new selection', 'scan': {'scopes': ['other']}}
        with self.assertRaisesRegex(ValueError, 'existing output'):
            scan.prepare_config(self.root, payload, output)
        with self.assertRaisesRegex(ValueError, 'existing output'):
            scan.prepare_config(self.root, payload, output, 'incorrect')
        with patch.object(scan.os, 'replace', side_effect=PermissionError('write failed')):
            with self.assertRaises(PermissionError):
                scan.prepare_config(self.root, payload, output, scan.digest(output))
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(list(output.parent.iterdir()), [output])
        scan.prepare_config(self.root, payload, output, scan.digest(output))
        self.assertEqual(scan.analysis_config(self.root, output)['scan']['scopes'], ['other'])
        with self.assertRaisesRegex(ValueError, 'not a copied saved config'):
            scan.prepare_config(self.root, json.loads(output.read_text()), self.root / 'copy.json')

    def test_prepare_rejects_sources_changed_after_extraction(self):
        self.put('.cproject', '<project/>')
        with self.assertRaisesRegex(ValueError, 'source changed since'):
            self.config({'sources': [{'path': '.cproject', 'sha256': 'old-hash'}]})

    def test_prepare_does_not_mutate_payload_or_leave_partial_write(self):
        output = self.config()
        before = output.read_bytes()
        payload = {'schema_version': 1, 'status': 'ready', 'context': '用户确认',
                   'scan': {'scopes': ['src']}}
        original = json.dumps(payload)
        def fail_write(value, stream, **kwargs):
            stream.write('{"partial":')
            raise OSError('disk write failed')
        with patch.object(scan.json, 'dump', side_effect=fail_write), self.assertRaises(OSError):
            scan.prepare_config(self.root, payload, output, scan.digest(output))
        self.assertEqual(json.dumps(payload), original)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(list(output.parent.iterdir()), [output])

    def test_stdin_invalid_and_oversized_payload_create_no_files(self):
        output = self.root / 'reports/analysis-config.json'
        command = [sys.executable, '-I', '-X', 'utf8', '-B', str(scan.SKILL / 'scripts/analyze.py'),
                   'config-prepare', '--root', str(self.root), '--stdin', '--output', str(output)]
        for payload in [b'', b'{broken', b'[]', b' ' * (16 * 1024 * 1024 + 1)]:
            result = subprocess.run(command, input=payload, capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.parent.exists())

    def test_old_file_input_interface_is_rejected(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(scan.SKILL / 'scripts/analyze.py'),
            'config-prepare', '--root', str(self.root), '--input', 'draft.json',
            '--output', str(self.root / 'analysis-config.json')], input='',
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / 'analysis-config.json').exists())

    @unittest.skipUnless(shutil.which('pwsh'), 'requires existing PowerShell for documented pipe example')
    def test_powershell_stdin_unicode_quotes_and_single_persistent_file(self):
        output = self.root / 'reports/analysis-config.json'
        payload = {'schema_version': 1, 'status': 'ready', 'context': '用户确认中文参数',
                   'c': {'arguments': ['-DNAME="quoted value"', '-I', '目录 with spaces']}}
        def literal(value):
            return "'" + str(value).replace("'", "''") + "'"
        command = "$diagramPayload = @'\n" + json.dumps(payload, ensure_ascii=False) + "\n'@\n"
        command += '$diagramEncodingBefore = $OutputEncoding\ntry {\n'
        command += '$OutputEncoding = [System.Text.UTF8Encoding]::new($false)\n'
        command += (f'$diagramPayload | & {literal(sys.executable)} -I -X utf8 -B '
                    f'{literal(scan.SKILL / "scripts/analyze.py")} config-prepare '
                    f'--root {literal(self.root)} --stdin --output {literal(output)}\n'
                    'if ($LASTEXITCODE -ne 0) { throw "configuration not ready" }\n'
                    '} finally { $OutputEncoding = $diagramEncodingBefore }\n')
        result = subprocess.run([shutil.which('pwsh'), '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = scan.analysis_config(self.root, output)
        self.assertEqual(value['context'], payload['context'])
        self.assertEqual(value['c'], payload['c'])
        self.assertEqual(list(output.parent.rglob('*')), [output])

    def test_source_only_change_invalidates_index_not_analysis_config(self):
        self.put('src/app.py', 'def entry(): return 1')
        output = self.config()
        _, cache = scan.scan(scan.inventory(self.root, ['src']), output, 10, mode='configured')
        self.put('src/app.py', 'def entry(): return 2')
        scan.analysis_config(self.root, output)
        with self.assertRaisesRegex(ValueError, 'STALE_INDEX'):
            scan.load_index(cache)

    def test_query_rejects_stale_config_provenance_not_just_output_hash(self):
        self.put('src/app.py', 'def entry(): return 1')
        self.put('build.cfg', 'old')
        output = self.config({'sources': [{'path': 'build.cfg'}]})
        _, cache = scan.scan(scan.inventory(self.root, ['src']), output, 10, mode='configured')
        self.put('build.cfg', 'new')
        with self.assertRaisesRegex(ValueError, 'STALE_CONFIG'):
            scan.load_index(cache)

    def test_saved_scope_cannot_silently_conflict_with_scan(self):
        self.put('src/a.py', 'pass')
        output = self.config()
        with self.assertRaisesRegex(ValueError, 'conflicts with requested range'):
            scan.scan(scan.inventory(self.root), output, 10, mode='configured')

    def test_cli_config_lifecycle_and_scope_reuse(self):
        self.put('src/app.py', 'def f(): return 1')
        self.put('outside.py', 'invalid ! syntax')
        value = {'schema_version': 1, 'status': 'ready', 'context': 'confirmed scope',
                 'scan': {'scopes': ['src']}}
        output = self.root / 'docs/architecture/analysis-config.json'
        command = [sys.executable, '-I', '-B', str(scan.SKILL / 'scripts/analyze.py')]
        for tail in [['config-prepare', '--stdin', '--output', str(output)],
                     ['config-check', '--config', str(output)],
                     ['scan', '--mode', 'configured', '--config', str(output)]]:
            result = subprocess.run([*command, *tail, '--root', str(self.root)], input=json.dumps(value), capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('files=1', result.stdout)
        # CLI intentionally writes its own ignored cache; no project helper or flags is created.
        self.assertFalse((output.parent / 'compile_flags.txt').exists())
        self.assertEqual(list(output.parent.rglob('*')), [output])
        self.assertFalse((self.root / 'draft.json').exists())

    def test_scan_uses_current_files_without_git_or_gitignore(self):
        self.put('service.py', 'def entry(): return 1\n')
        self.put('.gitignore', 'service.py\n')
        self.put('.git/invalid.py', 'not valid Python at all')
        inventory = scan.inventory(self.root)
        self.assertEqual([f['path'] for f in inventory['files']], ['service.py'])
        run = scan.subprocess.run
        def parser_only(command, **kwargs):
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(Path(command[5]), scan.SKILL / 'scripts' / 'analyze.py')
            self.assertEqual(command[6], '_parse')
            return run(command, **kwargs)
        with patch.object(scan.subprocess, 'run', side_effect=parser_only):
            result, cache = scan.scan(inventory, None, 10)
        self.assertEqual(result['status'], 'ok')
        self.assertIn('entry', scan.query(scan.load_index(cache), '', '', 0, 1000))

    def test_plugin_response_and_command_flags_rejected(self):
        for flags in [['-Xclang', '-load', 'evil.dll'], ['@flags.txt'], ['-fplugin=evil'], ['-include', 'private.h']]:
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                scan.clang_flags(flags, self.root)

    def test_compdb_uses_arguments_and_relative_include(self):
        self.put('a.c', 'int main(void){return 0;}')
        db = self.put('compile_commands.json', json.dumps([{'directory': str(self.root), 'file': 'a.c', 'arguments': ['do-not-run.exe', '-Iinc', '-c', 'a.c', '-o', 'a.o']}]))
        flags, marker = scan.load_config(self.root, db, ['a.c'])
        self.assertEqual(flags['a.c'], ['-I'+str(self.root / 'inc')])
        self.assertTrue(marker['sha256'])

    def test_compdb_command_only_and_duplicate_variant_rejected(self):
        item = {'directory': str(self.root), 'file': 'a.c', 'command': 'echo should-not-run'}
        db = self.put('compile_commands.json', json.dumps([item]))
        with self.assertRaisesRegex(ValueError, 'arguments array'):
            scan.load_config(self.root, db, ['a.c'])
        item['arguments'] = ['cc', '-c', 'a.c']
        db.write_text(json.dumps([item, item]), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'multiple compilation'):
            scan.load_config(self.root, db, ['a.c'])

    def test_query_context_and_source_unchanged(self):
        data, cache = self.python_scan()
        self.assertEqual(data['status'], 'ok')
        text = scan.query(scan.load_index(cache), '', 'entry', 0, 1500)
        self.assertIn('call-expression-unresolved -> helper', text)
        self.assertNotIn('return helper(x)', text)
        self.assertIn('return helper(x)', scan.context(data, 'service.py', 2, 2, 1000))
        self.assertEqual(scan.digest(self.root / 'service.py'), data['files']['service.py']['sha256'])

    def test_same_size_source_edit_invalidates_cache(self):
        data, cache = self.python_scan()
        self.put('service.py', (self.root / 'service.py').read_text().replace('helper', 'worker'))
        with self.assertRaisesRegex(ValueError, 'STALE_INDEX'):
            scan.load_index(cache)

    def test_added_source_invalidates_cache(self):
        _, cache = self.python_scan()
        self.put('other.py', 'pass')
        with self.assertRaisesRegex(ValueError, 'file set changed'):
            scan.load_index(cache)

    def test_explicit_scope_still_respects_explicit_exclude(self):
        self.put('src/a.py', 'pass')
        self.assertEqual(scan.inventory(self.root, ['src'], ['src'])['count'], 0)

    def test_configuration_and_included_header_changes_invalidate(self):
        for key, filename in [('config', 'flags.txt'), ('dependencies', 'external.h')]:
            with self.subTest(key=key):
                data, cache = self.python_scan()
                dependency = self.put(filename, 'old')
                if key == 'config':
                    data[key] = {'path': str(dependency), 'sha256': scan.digest(dependency)}
                else:
                    data[key] = {str(dependency): scan.digest(dependency)}
                cache.write_text(json.dumps(data), encoding='utf-8')
                dependency.write_text('new', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'STALE_INDEX'):
                    scan.load_index(cache)

    def test_scanner_version_change_rejects_index(self):
        _, cache = self.python_scan()
        with patch.object(scan, 'implementation_hash', return_value='changed'), self.assertRaisesRegex(ValueError, 'version changed'):
            scan.load_index(cache)

    def test_missing_parser_stops_without_fallback(self):
        self.put('a.md', '# Heading')
        with patch.object(scan, 'require_package', side_effect=ImportError('missing parser')), self.assertRaisesRegex(ValueError, 'SCAN_PREPARATION_FAILED'):
            scan.scan(scan.inventory(self.root), None, 10)
        self.assertFalse(self.cache.exists())

    def test_failed_rescan_preserves_previous_success(self):
        _, cache = self.python_scan()
        before = cache.read_bytes()
        self.put('service.py', 'def invalid(:')
        data, failed = scan.scan(scan.inventory(self.root), None, 10)
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(failed.name, 'index.partial.json')
        self.assertEqual(cache.read_bytes(), before)

    def test_timeout_is_failure_not_empty_success(self):
        self.put('a.py', 'pass')
        with patch.object(scan.subprocess, 'run', side_effect=subprocess.TimeoutExpired('parser', 1)):
            data, _ = scan.scan(scan.inventory(self.root), None, 1)
        self.assertEqual(data['files']['a.py']['status'], 'failed')

    def test_budget_is_bounded_and_marks_omission(self):
        text = scan.budgeted('header', ['line '*100]*30, 1000)
        self.assertLessEqual(len(text), 1000)
        self.assertIn('omitted', text)

    def test_architecture_query_retains_control_and_calls_without_macro_flood(self):
        index, _ = self.python_scan()
        item = index['files']['service.py']
        owner = item['symbols'][0]['id']
        macros = [{'owner': owner, 'kind': 'macro_instantiation', 'target': 'NOISY_MACRO', 'line': 2} for _ in range(80)]
        essential = [{'owner': owner, 'kind': kind, 'target': target, 'line': 3}
                     for kind, target in [('return_stmt', ''), ('indirect-call-unresolved', 'callback'),
                                          ('function-reference-not-call', 'handler'), ('direct-call', 'commit_state')]]
        item['edges'] = macros + essential
        before = json.dumps(index, sort_keys=True)
        output = scan.query(index, '', 'entry', 0, 1500)
        self.assertIn('direct-call -> commit_state', output)
        self.assertIn('return_stmt', output)
        self.assertIn('indirect-call-unresolved -> callback', output)
        self.assertIn('function-reference-not-call -> handler', output)
        self.assertNotIn('macro_instantiation ->', output)
        self.assertIn('--view full', output)
        full = scan.query(index, '', 'entry', 0, 16000, view='full')
        self.assertIn('macro_instantiation -> NOISY_MACRO', full)
        self.assertIn('direct-call -> commit_state', full)
        self.assertEqual(json.dumps(index, sort_keys=True), before)
        incoming = scan.query(index, '', 'NOISY_MACRO', 0, 1500, incoming=True, view='full')
        self.assertIn('macro_instantiation', incoming)
        self.assertIn('NO_MATCH', scan.query(index, '', 'NOISY_MACRO', 0, 1500, incoming=True))

    def test_architecture_pagination_applies_after_filter(self):
        index, _ = self.python_scan()
        item = index['files']['service.py']
        item['edges'] = [{'owner': item['symbols'][0]['id'], 'kind': kind, 'target': target, 'line': 2}
                         for kind, target in [('macro_instantiation', 'M'), ('direct-call', 'first'), ('direct-call', 'last')]]
        output = scan.query(index, '', 'entry', 3, 1500)
        self.assertNotIn('direct-call -> first', output)
        self.assertIn('direct-call -> last', output)
        with self.assertRaisesRegex(ValueError, 'query view'):
            scan.query(index, '', '', 0, 1500, view='unknown')

    def test_cli_query_view_uses_existing_index_without_rewriting(self):
        _, cache = self.python_scan()
        before = cache.read_bytes()
        for view in ['architecture', 'full']:
            result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', str(scan.SKILL / 'scripts/analyze.py'),
                'query', '--index', str(cache), '--symbol', 'entry', '--view', view],
                capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('view='+view, result.stdout)
            self.assertIn('SYMBOL entry', result.stdout)
        self.assertEqual(cache.read_bytes(), before)

    def test_worker_does_not_import_target_python(self):
        path = self.put('unsafe.py', 'raise RuntimeError("must not execute")\ndef f(): return 1')
        result = scan.parse_python(path)
        self.assertEqual(result['symbols'][0]['name'], 'f')

    def test_unsupported_language_has_no_source_fallback(self):
        self.put('analog.va', 'module analog; endmodule')
        with self.assertRaisesRegex(ValueError, 'no offline adapter'):
            scan.scan(scan.inventory(self.root), None, 1)

    def test_write_failure_is_reported(self):
        self.put('a.py', 'pass')
        with patch.object(scan.os, 'replace', side_effect=PermissionError('no write')), self.assertRaises(PermissionError):
            scan.scan(scan.inventory(self.root), None, 10)


def package_available(name):
    try:
        scan.importlib.metadata.version(name)
        return True
    except scan.importlib.metadata.PackageNotFoundError:
        return False


class ParserTests(unittest.TestCase):
    @unittest.skipUnless(package_available('libclang'), 'requires declared C dependency')
    def test_control_paths_fixture_preserves_macro_return_and_branch_evidence(self):
        root = scan.SKILL / 'tests/fixtures/firmware'
        data = scan.parse_c(root, 'control_paths.c', ['-std=c11'])
        self.assertEqual(data['status'], 'ok', data['diagnostics'])
        definitions = {s['name']: s['id'] for s in data['symbols'] if s['kind'] == 'function'}
        self.assertEqual(set(definitions), {'initialize_interrupts', 'startup', 'apply_mode', 'dispatch'})
        startup = [e for e in data['edges'] if e['owner'] == definitions['startup']]
        self.assertTrue(any(e['kind'] == 'while_stmt' for e in startup))
        self.assertTrue(any(e['target'] == 'initialize_interrupts' and e['kind'] == 'direct-call' for e in startup))
        apply = [e for e in data['edges'] if e['owner'] == definitions['apply_mode']]
        self.assertTrue(any(e['kind'] == 'return_stmt' for e in apply))
        self.assertTrue(any(e['target'] == 'configure_channel' for e in apply))
        self.assertTrue(any(e['kind'] == 'macro_instantiation' and e['target'] == 'RETURN_IF_ERROR' for e in data['edges']))

    @unittest.skipUnless(package_available('libclang'), 'requires declared C dependency')
    def test_real_c_scan_without_config_and_with_uniform_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.c').write_text('int entry(void){return 1;}\n', encoding='utf-8')
            with patch.object(scan, 'cache_path', return_value=root / '.cache/index.json'):
                result, _ = scan.scan(scan.inventory(root), None, 10, mode='configured')
                self.assertEqual(result['status'], 'ok')
                self.assertIsNone(result['config'])
                self.assertIn('C uses parser defaults', scan.query(result, '', '', 0, 1000))
                payload = {'schema_version': 1, 'status': 'ready',
                           'context': 'selected C11 by user', 'c': {'arguments': ['-std=c11']}}
                output = root / 'docs/architecture/analysis-config.json'
                scan.prepare_config(root, payload, output)
                self.assertEqual(list(output.parent.iterdir()), [output])
                result, cache = scan.scan(scan.inventory(root), output, 10, mode='configured')
                self.assertEqual(result['status'], 'ok')
                self.assertIn('SYMBOL entry', scan.query(scan.load_index(cache), '', 'entry', 0, 1500))

    @unittest.skipUnless(package_available('libclang'), 'requires declared C dependency')
    def test_c_index_reuses_config_after_process_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'docs' / 'architecture'
            work = output / '_work' / 'overview'
            work.mkdir(parents=True)
            flags = output / 'compile_flags.txt'
            flags.write_text('-std=c11\n', encoding='utf-8')
            source = root / 'app.c'
            source.write_text('int entry(void){return 1;}\n', encoding='utf-8')
            candidate = work / 'candidate.md'
            candidate.write_text('# temporary\n', encoding='utf-8')
            with patch.object(scan, 'cache_path', return_value=root / '.cache' / 'index.json'):
                data, cache = scan.scan(scan.inventory(root), flags, 10, mode='configured')
            self.assertEqual(data['status'], 'ok')
            self.assertEqual(data['inventory']['count'], 1)
            candidate.unlink()
            work.rmdir()
            work.parent.rmdir()
            self.assertTrue(flags.is_file())
            self.assertIn('SYMBOL entry', scan.query(scan.load_index(cache), '', 'entry', 0, 1500))
            flags.write_text('-std=c11\n-DVARIANT=1\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'STALE_INDEX'):
                scan.load_index(cache)

    @unittest.skipUnless(package_available('libclang'), 'run in declared parser environment for real C test')
    def test_c_direct_pointer_reference_and_inactive_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'api.c'
            path.write_text('int helper(int x){return x;}\nvoid (*hook)(void);\nint entry(void){\n#if 0\n absent();\n#endif\n hook(); return helper(1);}\nvoid (*table[])(void)={0};\n', encoding='utf-8')
            data = scan.parse_c(root, path.name, ['-std=c11'])
            self.assertEqual(data['status'], 'ok')
            self.assertTrue(any(e['kind']=='direct-call' and e['target']=='helper' for e in data['edges']))
            self.assertTrue(any(e['kind']=='indirect-call-unresolved' for e in data['edges']))
            self.assertFalse(any(e['target']=='absent' for e in data['edges']))
            self.assertFalse(any(e['kind']=='function-reference-not-call' and e['target']=='helper' for e in data['edges']))

    @unittest.skipUnless(package_available('libclang'), 'requires declared C dependency')
    def test_callback_reference_is_not_call_and_incoming_preserves_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'route.c'
            path.write_text('void hook(void){}\nvoid reg(void (*p)(void));\nvoid setup(void){reg(hook);}\n', encoding='utf-8')
            data = scan.parse_c(root, path.name, ['-std=c11'])
            self.assertTrue(any(e['kind']=='function-reference-not-call' and e['target']=='hook' for e in data['edges']))
            self.assertFalse(any(e['kind']=='direct-call' and e['target']=='hook' for e in data['edges']))
            index = {'mode': 'configured', 'status': 'ok', 'inventory': {'count': 1, 'bytes': path.stat().st_size}, 'elapsed_seconds': 0, 'files': {'route.c': data}}
            output = scan.query(index, '', 'hook', 0, 1000, incoming=True)
            self.assertIn('function-reference-not-call', output)

    @unittest.skipUnless(package_available('markdown-it-py'), 'requires declared Markdown dependency')
    def test_markdown_code_fence_is_not_link(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'SKILL.md'
            path.write_text('# Route\nIf C read [driver](driver.md).\n```md\n[fake](fake.md)\n```\n', encoding='utf-8')
            data = scan.parse_markdown(path)
            self.assertEqual([e['target'] for e in data['edges']], ['driver.md'])
            self.assertEqual(data['edges'][0]['kind'], 'markdown-link-not-execution')

    @unittest.skipUnless(package_available('markdown-it-py'), 'requires declared Markdown dependency')
    def test_wikilink_retains_ambiguity_but_ignores_inline_code(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.md'
            path.write_text('[[Notes#Topic|Alias]] and `[[fake]]`\n', encoding='utf-8')
            data = scan.parse_markdown(path)
            self.assertEqual([e['target'] for e in data['edges']], ['Notes#Topic|Alias'])
            self.assertEqual(data['edges'][0]['kind'], 'wikilink-unresolved-not-execution')

    @unittest.skipUnless(package_available('pyslang'), 'requires declared HDL dependency')
    def test_hdl_generate_not_reported_as_elaborated_hardware(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'top.sv'
            path.write_text('module top #(parameter X=1)(); if(X) begin: g leaf u_leaf(); end endmodule', encoding='utf-8')
            data = scan.parse_hdl(path)
            self.assertEqual(data['status'], 'ok')
            self.assertTrue(any(e['kind']=='generate-condition-not-evaluated' for e in data['edges']))
            self.assertTrue(any(e['kind']=='instance-declaration-not-elaborated' for e in data['edges']))


if __name__ == '__main__':
    unittest.main()
