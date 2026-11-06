"""覆盖真实 C 工程触发的长行号崩溃,旧编码与显式不透明语法视图.

由 unittest discover 执行;测试不引用用户工程,不运行固件,不安装依赖.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'src'))
import offline_scan as scan
from source_c import decode_source, parse, syntax_view

HAS_PARSER = importlib.util.find_spec('tree_sitter') is not None and importlib.util.find_spec('tree_sitter_c') is not None


@unittest.skipUnless(HAS_PARSER, 'requires declared C source dependencies')
class SourceRepairTests(unittest.TestCase):
    def test_long_file_line_numbers_survive_native_point_access(self):
        # 子进程隔离原生崩溃;行号跨过 Python 小整数缓存,并在分配结果后复核全部行号.
        code = (
            'import sys,json\n'
            f'sys.path.insert(0, {str(SKILL / "src")!r})\n'
            'from source_c import parse\n'
            'raw="".join(f"void f{i}(void){{ leaf(); }}\\n" for i in range(700)).encode()\n'
            'v=parse(raw,"long.c")\n'
            'assert v["status"]=="ok",v["diagnostics"]\n'
            'assert [e["line"] for e in v["edges"] if e["target"]=="leaf"]==list(range(1,701))\n'
            'assert [s["end"] for s in v["symbols"] if s["kind"]=="function"]==list(range(1,701))\n'
            'print(json.dumps({"last_line":v["symbols"][-1]["line"]}))\n'
        )
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['last_line'], 700)

    def test_legacy_encoding_and_context_preserve_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'legacy.c'
            raw = '// 中文注释\nvoid entry(void){ leaf(); }\n'.encode('gb18030')
            file.write_bytes(raw)
            value = parse(raw, 'legacy.c')
            self.assertEqual(value['status'], 'ok', value['diagnostics'])
            self.assertEqual(value['source_encoding'], 'gb18030')
            index = {'inventory': {'root': str(root)}, 'files': {'legacy.c': value}, 'status': 'ok'}
            self.assertIn('中文注释', scan.context(index, 'legacy.c', 1, 2, 1000))
            self.assertEqual(file.read_bytes(), raw)
        with self.assertRaises(UnicodeDecodeError):
            decode_source(b'\xff')

    def test_opaque_annotations_keep_offsets_and_all_conditional_branches(self):
        raw = (b'__I unsigned int count;\n__align(4) unsigned char code[256];\n'
               b'#ifdef __cplusplus\nextern "C" {\n#endif\n'
               b'int entry(void){\n#if BOARD\nreturn a();\n#else\nreturn b();\n#endif\n}\n'
               b'#ifdef __cplusplus\n}\n#endif\n')
        view, annotations = syntax_view(raw)
        self.assertEqual(len(view), len(raw))
        self.assertEqual([i for i, b in enumerate(view) if b == 10],
                         [i for i, b in enumerate(raw) if b == 10])
        self.assertEqual(len(annotations), 4)
        value = parse(raw, 'api.h')
        self.assertEqual(value['status'], 'ok', value['diagnostics'])
        calls = [e for e in value['edges'] if e['kind'] == 'call-expression-unresolved']
        self.assertEqual({e['target'] for e in calls}, {'a', 'b'})
        self.assertTrue(all(e['conditions'] for e in calls))
        entry = next(s for s in value['symbols'] if s['name'] == 'entry')
        self.assertEqual(entry['line'], 6)

    def test_literals_unpaired_wrappers_and_syntax_errors_are_not_hidden(self):
        raw = b'/*\n__I\n__align(4)\n*/\nconst char *s="__align(4)";\n'
        self.assertEqual(syntax_view(raw), (raw, []))
        unpaired = b'#ifdef __cplusplus\nextern "C" {\n#endif\nvoid api(void);\n'
        self.assertEqual(syntax_view(unpaired), (unpaired, []))
        self.assertEqual(parse(unpaired, 'bad.h')['status'], 'partial')
        value = parse(b'int broken(void){ return 1 }', 'bad.c')
        self.assertEqual(value['status'], 'partial')
        self.assertTrue(any('Syntax missing' in d for d in value['diagnostics']))


if __name__ == '__main__':
    unittest.main()
