"""先离线扫描工程,再限量查询事实和源码片段,避免整仓进入模型上下文.

用法: python -I -B analyze.py inventory --root PROJECT
scan 将内部索引写入本 Skill 的 tools/local/scans;query/context 只读并检查过期.
"""

import argparse
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import offline_scan as scanlib


def bounded(minimum, maximum):
    def value(raw):
        number = int(raw)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f'must be {minimum}..{maximum}')
        return number
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('inventory', 'scan'):
        command = commands.add_parser(name)
        command.add_argument('--root', required=True)
        command.add_argument('--scope', action='append', default=[])
        command.add_argument('--exclude', action='append', default=[])
        if name == 'scan':
            command.add_argument('--mode', choices=['source', 'configured'], default='source',
                                 help='source: no build inputs; configured: existing configuration-aware parsing')
            config = command.add_mutually_exclusive_group()
            config.add_argument('--flags')
            config.add_argument('--compdb')
            config.add_argument('--config', help='optional reusable analysis-config.json')
            command.add_argument('--timeout', type=bounded(1, 120), default=30)
            command.add_argument('--progress', action='store_true', help='flush preparation, parser and cache events to stderr; no log files')
    check = commands.add_parser('config-check', help='read-only freshness/readiness check, no project search')
    check.add_argument('--root', required=True)
    check.add_argument('--config', required=True)
    prepare = commands.add_parser('config-prepare', help='receive reviewed JSON via stdin; persist only the final config')
    prepare.add_argument('--root', required=True)
    prepare.add_argument('--stdin', action='store_true', required=True, help='read UTF-8 JSON from stdin, not a draft file')
    prepare.add_argument('--output', required=True)
    prepare.add_argument('--replace-sha256')
    for name in ('query', 'context'):
        command = commands.add_parser(name)
        command.add_argument('--index', required=True)
        command.add_argument('--file', required=name == 'context', default='')
        command.add_argument('--max-chars', type=bounded(1000, 16000), default=8000)
        if name == 'query':
            command.add_argument('--symbol', default='')
            command.add_argument('--view', choices=['architecture', 'full'], default='architecture',
                                 help='architecture hides macro occurrences, not calls/control points; full shows all facts')
            command.add_argument('--incoming', action='store_true')
            command.add_argument('--offset', type=bounded(0, 1000000), default=0)
        else:
            command.add_argument('--line', type=bounded(1, 10000000), required=True)
            command.add_argument('--lines', type=bounded(1, 120), default=60)
    internal = commands.add_parser('_parse', help=argparse.SUPPRESS)
    internal.add_argument('--root', required=True)
    internal.add_argument('--file', required=True)
    internal.add_argument('--language', choices=['c', 'c-header', 'python', 'markdown', 'hdl'], required=True)
    internal.add_argument('--mode', choices=['source', 'configured'], required=True)
    internal.add_argument('--args-json', required=True)
    args = parser.parse_args(argv)
    preparing = args.command == 'scan'
    preparation_started = time.monotonic() if preparing else None
    if preparing:
        scanlib.report_progress(args.progress, 'preparation_start', status='running')
    try:
        if args.command == 'config-check':
            scanlib.analysis_config(args.root, args.config)
            print('config=ready unchanged declared inputs; no semantic completeness claim')
            return 0
        if args.command == 'config-prepare':
            raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError('analysis configuration too large')
            payload = json.loads(raw.decode('utf-8-sig'))
            value = scanlib.prepare_config(args.root, payload, args.output, args.replace_sha256)
            print(f"config={value['status']} path={args.output}")
            return 0 if value['status'] == 'ready' else 1
        if args.command == '_parse':
            print(json.dumps(scanlib.worker(args.root, args.file, args.language, json.loads(args.args_json), args.mode), ensure_ascii=False))
            return 0
        if args.command in {'inventory', 'scan'}:
            if args.command == 'scan' and args.mode == 'source' and (args.config or args.flags or args.compdb):
                raise ValueError('source mode does not consume build configuration; select --mode configured or omit config explicitly')
            if args.command == 'scan' and args.config:
                try:
                    value = scanlib.read_json_config(args.config)
                    scanlib.config_shape(value, scanlib.physical(args.root))
                except (OSError, ValueError, TypeError, KeyError):
                    if not args.scope:
                        raise  # No reliable range: never expand a broken config to the whole project.
                    # Explicit scope is known; scan can still report dependency and config errors together.
                else:
                    selection = value.get('scan', {})
                    args.scope = args.scope or selection.get('scopes', [])
                    args.exclude = args.exclude or selection.get('excludes', [])
            data = scanlib.inventory(args.root, args.scope, args.exclude)
            if args.command == 'inventory':
                print(scanlib.inventory_text(data))
                return 0
            preparing = False  # scan owns the preparation-end event from this point.
            result, path = scanlib.scan(data, args.config or args.flags or args.compdb, args.timeout,
                                       args.progress, preparation_started, args.mode)
            print(f"scan={result['status']} index={path}")
            print(scanlib.query(result, '', '', 0, 8000))
            return 0 if result['status'] == 'ok' else 1
        data = scanlib.load_index(args.index)
        if args.command == 'query':
            if args.incoming and not args.symbol:
                raise ValueError('--incoming requires --symbol')
            print(scanlib.query(data, args.file, args.symbol, args.offset, args.max_chars, args.incoming, args.view))
        else:
            print(scanlib.context(data, args.file, args.line, args.lines, args.max_chars))
        return 0
    except Exception as exc:
        if preparing:
            scanlib.report_progress(args.progress, 'preparation_end', preparation_started, status='blocked', issues=1)
        print(f'ERROR: {type(exc).__name__}: {exc}; no full-source fallback, no installation performed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
