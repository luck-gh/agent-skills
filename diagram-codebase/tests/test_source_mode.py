"""验证无需工程环境的源码扫描与配置感知扫描不会混淆.

临时工程覆盖缺失 SDK,条件分支,声明/调用线索,缓存隔离与失败保护.
真实 Tree-sitter 测试仅在已安装固定依赖时运行,不自动安装.
"""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'src'))
import offline_scan as scan
from source_c import parse

SPEC = importlib.util.spec_from_file_location('source_cli', SKILL / 'scripts/analyze.py')
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)
HAS_PARSER = importlib.util.find_spec('tree_sitter') is not None and importlib.util.find_spec('tree_sitter_c') is not None


class SourceModeContractTests(unittest.TestCase):
    def test_source_configuration_conflict_stops_before_inventory(self):
        for option in ['--config', '--flags', '--compdb']:
            with self.subTest(option=option), patch.object(cli.scanlib, 'inventory') as inventory, redirect_stderr(io.StringIO()) as err:
                code = cli.main(['scan', '--root', '.', option, 'absent', '--progress'])
                inventory.assert_not_called()
                self.assertEqual(code, 1)
                self.assertIn('--mode configured', err.getvalue())
                self.assertIn('event=preparation_end', err.getvalue())

    def test_mode_is_part_of_cache_identity(self):
        data = {'root': 'root', 'scopes': ['.'], 'excludes': []}
        self.assertNotEqual(scan.cache_path(data, 'source'), scan.cache_path(data, 'configured'))

    def test_missing_source_packages_do_not_start_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.h').write_text('void api(void);', encoding='utf-8')
            with patch.object(scan, 'require_package', side_effect=ValueError('missing source parser')) as require, patch.object(scan.subprocess, 'run') as worker:
                with self.assertRaisesRegex(ValueError, 'missing source parser'):
                    scan.scan(scan.inventory(root), None, 10)
                require.assert_called_once_with('c-source')
                worker.assert_not_called()


@unittest.skipUnless(HAS_PARSER, 'requires declared C source dependencies')
class SourceParserTests(unittest.TestCase):
    def test_sdk_absent_keeps_all_branches_and_does_not_fabricate_calls(self):
        raw = (SKILL / 'tests/fixtures/firmware/source_structure.c').read_bytes()
        value = parse(raw, 'src/中文 文件.c')
        self.assertEqual(value['status'], 'ok', value['diagnostics'])
        self.assertEqual(value['dependencies'], {})
        edges = value['edges']
        calls = {e['target']: e for e in edges if e['kind'] == 'call-expression-unresolved'}
        self.assertTrue({'configure_a', 'configure_b', 'configure_generic', 'register_handler', 'callback', 'RETURN_IF_ERROR', 'apply'} <= calls.keys())
        self.assertNotIn('fake_call', calls)
        self.assertNotIn('comment_call', calls)
        self.assertNotIn('handler', calls)  # Passing a callback is not invoking it.
        self.assertEqual(calls['register_handler']['arguments'], '(handler)')
        self.assertTrue(all(calls[n]['conditions'] for n in ['configure_a', 'configure_b', 'configure_generic']))
        self.assertIn('NOT', ' '.join(calls['configure_b']['conditions']))
        self.assertEqual(len(calls['configure_generic']['conditions']), 2)
        self.assertFalse(any(e['kind'] == 'direct-call' for e in edges))
        self.assertTrue(any(s['kind'] == 'macro-definition-not-expanded' for s in value['symbols']))

    def test_headers_nested_conditions_and_pointer_calls(self):
        raw = b'#ifndef API_H\n#define API_H\n#if EXTRA\nvoid api(int value);\n#else\nstatic inline void api(int x){ table->hook(x); }\n#endif\n#endif\n'
        value = parse(raw, 'api.h')
        self.assertEqual(value['status'], 'ok')
        self.assertTrue(any(s['name'] == 'api' and s['kind'] == 'source-declaration' for s in value['symbols']))
        call = next(e for e in value['edges'] if e['kind'] == 'indirect-call-expression')
        self.assertEqual(call['target'], 'table->hook')
        self.assertEqual(len(call['conditions']), 2)
        self.assertIn('#ifndef API_H', call['conditions'][0])

    def test_errors_and_encoding_are_not_hidden(self):
        value = parse(b'int broken( {', 'bad.c')
        self.assertEqual(value['status'], 'partial')
        self.assertTrue(any('Syntax' in d for d in value['diagnostics']))
        with self.assertRaises(UnicodeDecodeError):
            parse(b'\xff', 'bad.c')

    def test_parenthesized_interfaces_and_same_line_declarations(self):
        raw = b'\xef\xbb\xbftypedef void (*callback_t)(void);\nint (*factory(void))(int);\nstruct Foo {} Foo; void api(void); void api(void);\n'
        value = parse(raw, 'interfaces.h')
        self.assertEqual(value['status'], 'ok', value['diagnostics'])
        self.assertTrue({'callback_t', 'factory', 'Foo', 'api'} <= {s['name'] for s in value['symbols']})
        ids = [s['id'] for s in value['symbols']]
        self.assertEqual(len(ids), len(set(ids)))

    @unittest.skipUnless(importlib.util.find_spec('clang') is not None, 'requires declared configured C parser')
    def test_configured_build_selects_branch_source_mode_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = b'int a(void); int b(void);\nint entry(void){\n#if BOARD\nreturn a();\n#else\nreturn b();\n#endif\n}\n'
            (root / 'app.c').write_bytes(raw)
            source = parse(raw, 'app.c')
            configured = scan.parse_c(root, 'app.c', ['-DBOARD=1'])
            self.assertEqual(configured['status'], 'ok', configured['diagnostics'])
            self.assertEqual({e['target'] for e in source['edges'] if e['kind'] == 'call-expression-unresolved'}, {'a', 'b'})
            self.assertEqual({e['target'] for e in configured['edges'] if e['kind'] == 'direct-call'}, {'a'})
            self.assertTrue(all(e['conditions'] for e in source['edges'] if e['kind'] == 'call-expression-unresolved'))

    def test_source_cli_full_flow_never_reads_or_rebuilds_environment_config(self):
        with tempfile.TemporaryDirectory(prefix='diagram 中文 ') as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            (root / 'src/api.h').write_text('static inline void api(void){ leaf(); }', encoding='utf-8')
            (root / 'src/app.c').write_bytes((SKILL / 'tests/fixtures/firmware/source_structure.c').read_bytes())
            config = root / 'docs/architecture/analysis-config.json'
            config.parent.mkdir(parents=True)
            config.write_text('not a valid config', encoding='utf-8')
            index = root / '.cache/index.json'
            with patch.object(cli.scanlib, 'cache_path', return_value=index), patch.object(cli.scanlib, 'load_config', side_effect=AssertionError('configuration must not be read')), redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                code = cli.main(['scan', '--root', str(root), '--scope', 'src', '--progress'])
            self.assertEqual(code, 0, err.getvalue())
            self.assertIn('mode=source', out.getvalue())
            self.assertIn('file="src/api.h"', err.getvalue())
            value = cli.scanlib.load_index(index)
            self.assertEqual(value['mode'], 'source')
            self.assertIsNone(value['config'])
            self.assertEqual(value['flags'], {})
            self.assertEqual(value['dependencies'], {})
            self.assertEqual(value['files']['src/api.h']['status'], 'ok')
            for incoming in [True, False]:
                query = cli.scanlib.query(value, '', 'configure_b' if incoming else 'apply', 0, 8000, incoming)
                self.assertIn('conditions(not evaluated)', query)
                self.assertIn('NOT', query)
            config.write_text('changed but not used', encoding='utf-8')
            self.assertEqual(cli.scanlib.load_index(index)['mode'], 'source')
            before = index.read_bytes()
            (root / 'src/app.c').write_text('int broken( {', encoding='utf-8')
            with patch.object(cli.scanlib, 'cache_path', return_value=index), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(['scan', '--root', str(root), '--scope', 'src']), 1)
            self.assertEqual(index.read_bytes(), before)
            self.assertTrue(index.with_name('index.partial.json').exists())
            with self.assertRaisesRegex(ValueError, 'STALE_INDEX'):
                cli.scanlib.load_index(index)
            self.assertEqual(list(config.parent.iterdir()), [config])


if __name__ == '__main__':
    unittest.main()
