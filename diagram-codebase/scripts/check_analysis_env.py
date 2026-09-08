"""检查可选离线解析环境,避免把包已安装误报为分析能力可用.

用法: python -I -B check_analysis_env.py --profile c
只解析内置小样例,不扫描用户工程,不联网,不安装,不启动子程序或写文件.
依赖版本来自随包 lock 文件;只检查明确选中的分支.
"""

import argparse
import ast
import importlib.metadata
from pathlib import Path
import platform
import struct
import sys


PROFILES = ("python", "markdown", "c-source", "c", "hdl")
LOCK_ROOT = Path(__file__).resolve().parents[1] / "tools" / "bundled"


def expected_packages(profile):
    """读取本包固定格式的锁文件,不是通用 requirements 解析器."""
    if profile == "python":
        return []
    path = LOCK_ROOT / f"{profile}-win-cp312.txt"
    packages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split()[0].split("==")
            packages.append((name, version))
    if not packages:
        raise ValueError(f"empty dependency lock: {path.name}")
    return packages


def check_python():
    tree = ast.parse("def entry(x):\n    return helper(x)\n")
    function = tree.body[0]
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    if function.name != "entry" or function.lineno != 1 or len(calls) != 1:
        raise RuntimeError("Python AST sample mismatch")
    return "function=entry; call-expression=helper; line=1"


def check_markdown():
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(
        "# Entry\n\nFor firmware, read [driver](driver.md).\n"
    )
    links = [child.attrGet("href") for token in tokens
             for child in token.children or [] if child.type == "link_open"]
    if links != ["driver.md"] or tokens[0].map != [0, 1]:
        raise RuntimeError("Markdown link / source position sample mismatch")
    return "link=driver.md; heading-lines=1; condition-semantics=not-evaluated"


def check_c():
    from clang import cindex

    source = "int helper(int x) { return x; }\nint entry(void) { return helper(1); }\n"
    unit = cindex.Index.create().parse(
        "diagram_probe.c", args=["-xc", "-std=c11"],
        unsaved_files=[("diagram_probe.c", source)],
    )
    errors = [str(d) for d in unit.diagnostics if d.severity >= cindex.Diagnostic.Error]
    if errors:
        raise RuntimeError("; ".join(errors))
    functions = [n for n in unit.cursor.get_children()
                 if n.kind == cindex.CursorKind.FUNCTION_DECL]
    calls = [n for n in unit.cursor.walk_preorder()
             if n.kind == cindex.CursorKind.CALL_EXPR]
    if [n.spelling for n in functions] != ["helper", "entry"]:
        raise RuntimeError("C function sample mismatch")
    if len(calls) != 1 or calls[0].referenced.spelling != "helper" or calls[0].location.line != 2:
        raise RuntimeError("C direct call / source position sample mismatch")
    return "functions=helper,entry; direct-call=helper; line=2; SDK=not-tested"


def check_hdl():
    from pyslang.syntax import SyntaxTree
    from pyslang.ast import Compilation

    tree = SyntaxTree.fromText(
        "module leaf(input logic a, output logic y); assign y=a; endmodule\n"
        "module top(input logic a, output logic y); leaf u_leaf(.a(a),.y(y)); endmodule\n"
    )
    compilation = Compilation()
    compilation.addSyntaxTree(tree)
    root = compilation.getRoot()
    if any(d.isError() for d in compilation.getAllDiagnostics()):
        raise RuntimeError("HDL sample has compilation errors")
    tops = list(root.topInstances)
    if len(tops) != 1 or tops[0].name != "top":
        raise RuntimeError("HDL top instance sample mismatch")
    members = list(tops[0].body)
    if not any(m.name == "u_leaf" for m in members):
        raise RuntimeError("HDL child instance sample mismatch")
    return "top=top; child=u_leaf; simulation=not-run; Verilog-A=not-supported"


def check_c_source():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from source_c import parse
    result = parse(b'#include "absent_sdk.h"\n#if BOARD\nvoid entry(void){ a(); }\n#else\nvoid entry(void){ b(); }\n#endif\n', 'probe.c')
    calls = [e for e in result['edges'] if e['kind'] == 'call-expression-unresolved']
    if result['status'] != 'ok' or [e['target'] for e in calls] != ['a', 'b'] or not all(e['conditions'] for e in calls):
        raise RuntimeError('C source syntax / conditional branches sample mismatch')
    return 'calls=a,b; conditions=not-evaluated; SDK=not-required; symbol-resolution=not-performed'


CHECKS = {"python": check_python, "markdown": check_markdown, "c-source": check_c_source, "c": check_c, "hdl": check_hdl}


def check_profile(profile):
    """区分平台,缺包,版本偏离和真实加载/解析失败;不尝试自动修复."""
    if profile != "python" and not (
        sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12)
        and sys.platform == "win32" and struct.calcsize("P") == 8
        and platform.machine().lower() in ("amd64", "x86_64")
    ):
        return False, "UNVERIFIED_PLATFORM: locks target CPython 3.12 / Windows x86-64"
    try:
        for name, expected in expected_packages(profile):
            actual = importlib.metadata.version(name)
            if actual != expected:
                return False, f"VERSION_MISMATCH: {name} expected={expected} actual={actual}; no upgrade performed"
        return True, CHECKS[profile]()
    except importlib.metadata.PackageNotFoundError as exc:
        return False, f"MISSING_DEPENDENCY: {exc.name}; no installation performed"
    except Exception as exc:
        return False, f"PROBE_FAILED: {type(exc).__name__}: {exc}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, action="append", required=True)
    args = parser.parse_args(argv)
    print(f"Python {platform.python_version()}; {sys.platform}; {platform.machine()}")
    failed = False
    for profile in dict.fromkeys(args.profile):
        passed, detail = check_profile(profile)
        failed |= not passed
        print(f"{'PASS' if passed else 'FAIL'} [{profile}] {detail}")
    print("Parser readiness only; project scanning, semantic mapping and visual validation are not certified.")
    return int(failed)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
