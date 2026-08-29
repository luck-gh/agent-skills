#!/usr/bin/env python3
"""校验 Capture collection 配置及当前根目录可用性;供 note 路由预检使用."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_INPUT_BYTES = 1_048_576
MAX_DEPTH = 8
MAX_NODES = 10_000
MAX_STRING_CHARS = 4_096
MAX_OBJECT_MEMBERS = 128
MAX_ARRAY_ITEMS = 128
MAX_COLLECTIONS = 64
MAX_SCOPES = 128
NAMESPACE_VERSION = 1
OPAQUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
FORMAT_PROFILES = frozenset({"plain-v1", "yaml-frontmatter-v1"})
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
}

EXIT_CONFIGURATION_REQUIRED = 10
EXIT_INVALID_CONFIGURATION = 11
EXIT_USAGE_ERROR = 14


class CollectionConfigurationError(ValueError):
    def __init__(self, code: int, payload: dict[str, Any]) -> None:
        super().__init__(payload["error"])
        self.code = code
        self.payload = payload


@dataclass(frozen=True)
class CollectionConfig:
    id: str
    root: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    format_profile: str


@dataclass(frozen=True)
class ScopePreflight:
    root: Path
    include: tuple[Path, ...]
    exclude: tuple[Path, ...]


def _invalid() -> CollectionConfigurationError:
    return CollectionConfigurationError(
        EXIT_INVALID_CONFIGURATION,
        {
            "status": "invalid_configuration",
            "error": "invalid_collections",
            "variable": "collections",
        },
    )


def _unavailable() -> CollectionConfigurationError:
    return CollectionConfigurationError(
        EXIT_CONFIGURATION_REQUIRED,
        {
            "status": "configuration_required",
            "error": "configuration_required",
            "reason": "configured_location_unavailable",
            "variable": "collections",
        },
    )


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _invalid()
        result[key] = value
    return result


def _constant(value: str) -> None:
    del value
    raise _invalid()


def _control(value: str) -> bool:
    return any(
        ord(character) < 0x20 or ord(character) == 0x7F or 0xD800 <= ord(character) <= 0xDFFF
        for character in value
    )


def _bounded(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise _invalid()
        if item is None:
            raise _invalid()
        if isinstance(item, bool) or isinstance(item, int):
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise _invalid()
            continue
        if isinstance(item, str):
            if len(item) > MAX_STRING_CHARS or _control(item):
                raise _invalid()
            continue
        if isinstance(item, list):
            if len(item) > MAX_ARRAY_ITEMS:
                raise _invalid()
            stack.extend((child, depth + 1) for child in item)
            continue
        if isinstance(item, dict):
            if len(item) > MAX_OBJECT_MEMBERS:
                raise _invalid()
            for key, child in item.items():
                if not isinstance(key, str) or not key or _control(key):
                    raise _invalid()
                stack.append((child, depth + 1))
            continue
        raise _invalid()


def parse_json(raw: bytes) -> Any:
    if not raw or len(raw) > MAX_INPUT_BYTES or raw.startswith(b"\xef\xbb\xbf"):
        raise _invalid()
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except CollectionConfigurationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, OverflowError, ValueError):
        raise _invalid() from None
    _bounded(value)
    return value


def _safe_scope(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 1_024 or _control(value):
        raise _invalid()
    if "\\" in value or value.startswith("/") or re.match(r"[A-Za-z]:", value):
        raise _invalid()
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise _invalid()
    if any(
        any(character in '<>:"|?*' for character in part)
        or part.endswith((" ", "."))
        or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED
        for part in parts
    ):
        raise _invalid()
    return value


def _is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _available_root(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_STRING_CHARS or _control(value):
        raise _invalid()
    candidate = Path(value)
    if not candidate.is_absolute() or any(part in {".", ".."} for part in candidate.parts):
        raise _invalid()
    try:
        metadata = candidate.lstat()
        canonical = Path(os.path.realpath(candidate))
    except OSError:
        raise _unavailable() from None
    if (
        _is_reparse(metadata)
        or not stat.S_ISDIR(metadata.st_mode)
        or not _same_path(candidate, canonical)
        or not os.access(candidate, os.R_OK)
    ):
        raise _unavailable()
    return str(candidate)


def _scope_directory(root: Path, relative: str, *, require_write: bool) -> Path:
    try:
        canonical_root = Path(os.path.realpath(root))
    except OSError:
        raise _unavailable() from None
    current = root
    for component in relative.split("/"):
        current = current / component
        try:
            metadata = current.lstat()
            canonical = Path(os.path.realpath(current))
            contained = os.path.commonpath((str(canonical_root), str(canonical))) == str(canonical_root)
        except (OSError, ValueError):
            raise _unavailable() from None
        access = os.R_OK | os.X_OK | (os.W_OK if require_write else 0)
        if (
            _is_reparse(metadata)
            or not stat.S_ISDIR(metadata.st_mode)
            or not contained
            or not os.access(current, access)
        ):
            raise _unavailable()
    return current


def preflight_collection(
    collection: CollectionConfig,
    *,
    require_write: bool = False,
) -> ScopePreflight:
    root_value = _available_root(collection.root)
    root = Path(root_value)
    root_access = os.R_OK | os.X_OK | (os.W_OK if require_write else 0)
    if not os.access(root, root_access):
        raise _unavailable()
    include = tuple(
        _scope_directory(root, relative, require_write=require_write)
        for relative in collection.include
    )
    exclude = tuple(
        _scope_directory(root, relative, require_write=require_write)
        for relative in collection.exclude
    )
    return ScopePreflight(root=root, include=include, exclude=exclude)


def validate_variables(value: Any, *, check_locations: bool = True) -> tuple[CollectionConfig, ...]:
    _bounded(value)
    if not isinstance(value, dict) or set(value) != {"collections"}:
        raise _invalid()
    raw_collections = value["collections"]
    if not isinstance(raw_collections, list) or not 1 <= len(raw_collections) <= MAX_COLLECTIONS:
        raise _invalid()

    identifiers: set[str] = set()
    roots: set[str] = set()
    checked: list[CollectionConfig] = []
    for raw_collection in raw_collections:
        if not isinstance(raw_collection, dict) or set(raw_collection) != {
            "id", "root", "scope", "format_profile"
        }:
            raise _invalid()
        identifier = raw_collection["id"]
        if not isinstance(identifier, str) or not OPAQUE.fullmatch(identifier):
            raise _invalid()
        identifier_key = identifier.casefold()
        if identifier_key in identifiers:
            raise _invalid()
        identifiers.add(identifier_key)

        root_value = raw_collection["root"]
        if check_locations:
            root = _available_root(root_value)
        else:
            if not isinstance(root_value, str) or not Path(root_value).is_absolute() or _control(root_value):
                raise _invalid()
            root = root_value
        root_key = os.path.normcase(os.path.abspath(root))
        if root_key in roots:
            raise _invalid()
        roots.add(root_key)

        scope = raw_collection["scope"]
        if not isinstance(scope, dict) or set(scope) != {"include", "exclude"}:
            raise _invalid()
        include = scope["include"]
        exclude = scope["exclude"]
        if not isinstance(include, list) or not 1 <= len(include) <= MAX_SCOPES:
            raise _invalid()
        if not isinstance(exclude, list) or len(exclude) > MAX_SCOPES:
            raise _invalid()
        checked_scopes: dict[str, tuple[str, ...]] = {}
        folded_scopes: dict[str, set[str]] = {}
        for label, paths in (("include", include), ("exclude", exclude)):
            normalized = tuple(_safe_scope(path) for path in paths)
            folded = {path.casefold() for path in normalized}
            if len(folded) != len(normalized):
                raise _invalid()
            checked_scopes[label] = normalized
            folded_scopes[label] = folded
        if folded_scopes["include"] & folded_scopes["exclude"]:
            raise _invalid()

        format_profile = raw_collection["format_profile"]
        if not isinstance(format_profile, str) or format_profile not in FORMAT_PROFILES:
            raise _invalid()
        checked.append(
            CollectionConfig(
                id=identifier,
                root=root,
                include=checked_scopes["include"],
                exclude=checked_scopes["exclude"],
                format_profile=format_profile,
            )
        )
    result = tuple(checked)
    if check_locations:
        for collection in result:
            preflight_collection(collection)
    return result


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CollectionConfigurationError(
            EXIT_USAGE_ERROR,
            {"status": "usage_error", "error": "usage_error"},
        )


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(description=__doc__)
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False))


def main(argv: list[str] | None = None) -> int:
    try:
        _parser().parse_args(sys.argv[1:] if argv is None else argv)
        variables = parse_json(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        collections = validate_variables(variables)
    except CollectionConfigurationError as error:
        _emit(error.payload)
        return error.code
    except Exception:
        error = _invalid()
        _emit(error.payload)
        return error.code
    _emit({"status": "ok", "namespace_version": NAMESPACE_VERSION, "collection_count": len(collections)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
