#!/usr/bin/env python3
"""管理 skill 的可选 discovery entry.

存在理由: `new-skills` 需要确定性管理可选 discovery entry.
应用场景: 检查一个明确 entry,或在当前调用授权后创建 Junction/symlink.
用法: python -X utf8 -B scripts/ensure_skill_entry.py <inspect|ensure> --physical-dir <dir> --entry-dir <dir> [--validator <file>] [--authorized]
"""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPARSE_POINT = 0x0400


class CheckError(RuntimeError):
    """表示输入不满足 entry 契约或创建失败."""


@dataclass(frozen=True)
class EntryProbe:
    kind: str
    detail: str


def _absolute(raw: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(raw))))


def normalized(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def overlaps(first: Path, second: Path) -> bool:
    try:
        common = Path(os.path.commonpath((first, second)))
    except ValueError:
        return False
    return normalized(common) in {normalized(first), normalized(second)}


def _is_windows_platform() -> bool:
    return os.name == "nt"


def _is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        int(getattr(info, "st_file_attributes", 0)) & REPARSE_POINT
    )


def _physical_directory(raw: str | Path) -> Path:
    path = _absolute(raw)
    try:
        info = os.lstat(path)
    except OSError:
        raise CheckError(f"physical dir does not exist: {path}") from None
    if _is_link(info) or not stat.S_ISDIR(info.st_mode):
        raise CheckError(f"physical dir must be a physical directory: {path}")
    return path


def _is_link_entry(path: Path) -> bool:
    try:
        return _is_link(os.lstat(path))
    except OSError:
        return False


def run_validator(skill_dir: Path, validator: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(validator), str(skill_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise CheckError(f"platform validation failed: {detail}")


def probe_entry(physical: Path, entry: Path) -> EntryProbe:
    if not os.path.lexists(entry):
        return EntryProbe("absent", "entry does not exist")
    if not _is_link_entry(entry):
        return EntryProbe("non-link", "entry exists but is not a symlink or Junction")
    try:
        target = entry.resolve(strict=True)
    except OSError as error:
        return EntryProbe("broken-link", f"entry target is unavailable: {error}")
    if normalized(target) == normalized(physical):
        kind = "exact-junction" if _is_windows_platform() else "exact-symlink"
        return EntryProbe(kind, f"entry target is exactly {physical}")
    return EntryProbe("wrong-link", f"entry target is {target}; expected {physical}")


def inspect(physical: Path, entry: Path) -> str:
    probe = probe_entry(physical, entry)
    if probe.kind == "absent":
        return "entry is absent and may be created after explicit authorization"
    if probe.kind in {"exact-junction", "exact-symlink"}:
        return f"entry is an {probe.kind}; no change made"
    raise CheckError(f"entry conflict ({probe.kind}): {probe.detail}")


def create_and_publish_posix_entry(physical: Path, entry: Path) -> str:
    try:
        os.symlink(str(physical), str(entry), target_is_directory=True)
    except FileExistsError:
        status = inspect(physical, entry)
        return f"{status}; concurrent publisher won"
    return "directory symlink created without replacement"


def _create_windows_junction(physical: Path, entry: Path) -> str:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(entry), str(physical)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        probe = probe_entry(physical, entry)
        if probe.kind == "exact-junction":
            return "entry is an exact-junction; concurrent publisher won"
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise CheckError(f"Junction creation failed: {detail}")
    return "Junction created without replacement"


def create_entry(physical: Path, entry: Path) -> str:
    result = (
        _create_windows_junction(physical, entry)
        if _is_windows_platform()
        else create_and_publish_posix_entry(physical, entry)
    )
    probe = probe_entry(physical, entry)
    if probe.kind not in {"exact-junction", "exact-symlink"}:
        raise CheckError(f"created entry could not be verified ({probe.kind}): {probe.detail}")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "ensure"))
    parser.add_argument("--physical-dir", required=True)
    parser.add_argument("--entry-dir", required=True)
    parser.add_argument("--validator")
    parser.add_argument("--authorized", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        physical_input = _physical_directory(args.physical_dir)
        entry = _absolute(args.entry_dir)
        if not entry.parent.is_dir():
            raise CheckError(f"entry parent does not exist: {entry.parent}")
        if normalized(physical_input.name) != normalized(entry.name):
            raise CheckError("physical dir and entry dir must use the same skill name")
        physical = physical_input.resolve(strict=True)
        if overlaps(physical, entry):
            raise CheckError("physical dir and entry dir must not overlap")
        if args.action == "inspect" and args.authorized:
            raise CheckError("--authorized is only valid with ensure")

        if args.validator:
            validator = _absolute(args.validator)
            if not validator.is_file():
                raise CheckError(f"validator does not exist: {validator}")
            run_validator(physical_input, validator)
        status = inspect(physical, entry)
        if args.action == "ensure" and status.startswith("entry is absent"):
            if not args.authorized:
                raise CheckError("ensure requires --authorized")
            status = create_entry(physical, entry)

        print(f"OK: {status}")
        print(f"physical={physical}")
        print(f"entry={entry}")
        return 0
    except (CheckError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
