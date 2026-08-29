"""实现 Capture write plan 的 fail-closed 文件事务.

The module never logs paths or content. Update publication requires a supplied
atomic compare-and-swap backend; the default user-space backend refuses.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from validate_collections import (
    CollectionConfig,
    CollectionConfigurationError,
    FORMAT_PROFILES,
    preflight_collection,
)

HEX = set("0123456789abcdef")
MAX_CONTENT_BYTES = 512 * 1024
MAX_OPERATIONS = 128
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 20000
MAX_CONTAINER_ITEMS = 512
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
}

CasStatus = Literal["published", "conflict", "unknown"]
AtomicCasBackend = Callable[[Path, Path, str, str], CasStatus]


@dataclass(frozen=True)
class ExecutionContext:
    collection_id: str
    root_fingerprint: str
    scope: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionResult:
    status: Literal["published", "conflict", "unsupported", "unknown"]
    code: str
    after_hash: str | None = None


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def root_fingerprint(root: str) -> str:
    return hashlib.sha256(os.fsencode(os.path.normcase(os.path.abspath(root)))).hexdigest()


def _valid_hash(value: Any, *, nullable: bool = False) -> bool:
    return value is None and nullable or (
        isinstance(value, str) and len(value) == 64 and set(value) <= HEX
    )


def _bounded_plan(value: Any) -> bool:
    stack: list[tuple[Any, int]] = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            return False
        if isinstance(item, str):
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError:
                return False
            if size > MAX_CONTENT_BYTES:
                return False
        elif isinstance(item, dict):
            if len(item) > 64:
                return False
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > MAX_CONTAINER_ITEMS:
                return False
            stack.extend((child, depth + 1) for child in item)
    return True


def _safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 1024:
        return False
    if "\\" in value or value.startswith("/") or (len(value) >= 2 and value[1] == ":"):
        return False
    parts = value.split("/")
    return all(
        part not in {"", ".", ".."}
        and not any(ord(char) < 32 or char in '<>:"|?*' for char in part)
        and not part.endswith((" ", "."))
        and part.split(".", 1)[0].casefold() not in WINDOWS_RESERVED
        for part in parts
    )


def _inside(path: str, scope: str) -> bool:
    return path == scope or path.startswith(scope + "/")


def _collection_allows(path: str, collection: CollectionConfig) -> bool:
    return any(_inside(path, scope) for scope in collection.include) and not any(
        _inside(path, scope) for scope in collection.exclude
    )


def _is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise RuntimeError("metadata-unknown") from error


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _metadata_preflight(root_value: str, relative_path: str, operation: str) -> tuple[Path, Path]:
    root = Path(root_value).absolute()
    root_metadata = _lstat(root)
    if root_metadata is None or _is_reparse(root_metadata) or not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError("root-type-unknown")
    try:
        canonical_root = Path(os.path.realpath(root))
    except OSError as error:
        raise RuntimeError("canonical-root-unknown") from error
    if not _same_path(root, canonical_root):
        raise RuntimeError("root-canonical-mismatch")

    target = root.joinpath(*relative_path.split("/"))
    try:
        if os.path.commonpath((str(root), str(target))) != str(root):
            raise RuntimeError("outside-root")
    except (OSError, ValueError) as error:
        raise RuntimeError("containment-unknown") from error

    current = root
    for component in relative_path.split("/")[:-1]:
        current = current / component
        metadata = _lstat(current)
        if metadata is None:
            raise RuntimeError("ancestor-missing")
        if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError("ancestor-type-unknown")
        try:
            canonical = Path(os.path.realpath(current))
            if os.path.commonpath((str(canonical_root), str(canonical))) != str(canonical_root):
                raise RuntimeError("ancestor-outside-root")
        except (OSError, ValueError) as error:
            raise RuntimeError("ancestor-canonical-unknown") from error

    parent = target.parent
    if not os.access(parent, os.W_OK):
        raise RuntimeError("permission-unknown")
    target_metadata = _lstat(target)
    if operation == "create":
        if target_metadata is not None:
            raise FileExistsError
    elif operation == "update":
        if (
            target_metadata is None
            or _is_reparse(target_metadata)
            or not stat.S_ISREG(target_metadata.st_mode)
            or not os.access(target, os.R_OK | os.W_OK)
        ):
            raise RuntimeError("target-type-or-permission-unknown")
    else:
        raise RuntimeError("operation-unsupported")
    return root, target


def _read_hash(path: Path) -> str:
    metadata = _lstat(path)
    if metadata is None or _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("postread-type-unknown")
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError as error:
        raise RuntimeError("postread-unknown") from error
    return hasher.hexdigest()


def _validate_plan(plan: Any) -> bool:
    if not _bounded_plan(plan) or not isinstance(plan, dict) or set(plan) != {
        "schema",
        "version",
        "plan_id",
        "request_digest",
        "candidate_digest",
        "collection_id",
        "scope",
        "format_profile",
        "operations",
    }:
        return False
    if (
        plan.get("schema") != "capture-write-plan"
        or plan.get("version") != 1
        or isinstance(plan.get("version"), bool)
    ):
        return False
    operations = plan.get("operations")
    return isinstance(operations, list) and 0 < len(operations) <= MAX_OPERATIONS


class TransactionExecutor:
    def __init__(
        self,
        *,
        atomic_update_cas: AtomicCasBackend | None = None,
    ) -> None:
        self._atomic_update_cas = atomic_update_cas
        self._frozen = False

    @property
    def frozen(self) -> bool:
        return self._frozen

    def _unknown(self, code: str) -> ExecutionResult:
        self._frozen = True
        return ExecutionResult("unknown", code)

    def execute(
        self,
        *,
        plan: dict[str, Any],
        write_plan_digest: str,
        collection: CollectionConfig,
        context: ExecutionContext,
    ) -> tuple[ExecutionResult, ...]:
        if self._frozen:
            return (ExecutionResult("unknown", "executor-frozen"),)
        if not _validate_plan(plan):
            return (self._unknown("write-plan-invalid"),)
        collection_scopes = collection.include + collection.exclude
        if (
            not os.path.isabs(collection.root)
            or not collection.include
            or collection.format_profile not in FORMAT_PROFILES
            or any(not _safe_relative(scope) for scope in collection_scopes)
            or len({scope.casefold() for scope in collection.include}) != len(collection.include)
            or len({scope.casefold() for scope in collection.exclude}) != len(collection.exclude)
            or set(scope.casefold() for scope in collection.include)
            & set(scope.casefold() for scope in collection.exclude)
        ):
            return (self._unknown("collection-invalid"),)
        try:
            plan_digest = digest(plan)
        except (TypeError, ValueError, UnicodeError):
            return (self._unknown("write-plan-invalid"),)
        if plan_digest != write_plan_digest:
            return (self._unknown("write-plan-digest-mismatch"),)
        if (
            plan["collection_id"] != collection.id
            or plan["format_profile"] != collection.format_profile
            or context.collection_id != collection.id
            or context.root_fingerprint != root_fingerprint(collection.root)
            or context.scope != plan["scope"]
            or context.include != collection.include
            or context.exclude != collection.exclude
        ):
            return (self._unknown("execution-context-mismatch"),)
        if not _safe_relative(plan["scope"]) or not _collection_allows(plan["scope"], collection):
            return (self._unknown("scope-not-allowed"),)

        operations = plan["operations"]
        operation_ids = tuple(
            operation.get("operation_id") for operation in operations if isinstance(operation, dict)
        )
        if (
            len(operation_ids) != len(operations)
            or not all(
                isinstance(operation_id, str) and operation_id
                for operation_id in operation_ids
            )
            or len(set(operation_ids)) != len(operation_ids)
        ):
            return (self._unknown("operation-binding-invalid"),)

        results: list[ExecutionResult] = []
        for operation in operations:
            try:
                preflight_collection(collection, require_write=True)
            except CollectionConfigurationError:
                results.append(self._unknown("collection-location-unavailable"))
                break
            result = self._execute_one(collection, plan["scope"], operation)
            results.append(result)
            if result.status != "published":
                break
        return tuple(results)

    def _execute_one(
        self,
        collection: CollectionConfig,
        plan_scope: str,
        operation: Any,
    ) -> ExecutionResult:
        required = {
            "operation_id",
            "item_ids",
            "operation",
            "scope",
            "filename",
            "target",
            "format_profile",
            "transform",
            "body",
            "frontmatter",
            "taxonomy",
            "links",
            "resource_refs",
            "before_hash",
            "after_hash",
        }
        if not isinstance(operation, dict) or set(operation) != required:
            return self._unknown("operation-invalid")
        relative_path = operation["target"]
        op = operation["operation"]
        content = operation["body"]
        if (
            operation["scope"] != plan_scope
            or operation["format_profile"] != collection.format_profile
            or not _safe_relative(relative_path)
            or not _inside(relative_path, plan_scope)
            or not _collection_allows(relative_path, collection)
            or op not in {"create", "update"}
            or not isinstance(content, str)
            or operation["filename"] != relative_path.rsplit("/", 1)[-1]
            or not isinstance(operation["item_ids"], list)
            or not operation["item_ids"]
            or not all(isinstance(item_id, str) and item_id for item_id in operation["item_ids"])
        ):
            return self._unknown("operation-binding-invalid")
        try:
            content_bytes = content.encode("utf-8")
        except UnicodeError:
            return self._unknown("content-encoding-invalid")
        if not content_bytes or len(content_bytes) > MAX_CONTENT_BYTES:
            return self._unknown("content-limit")
        expected_after = hashlib.sha256(content_bytes).hexdigest()
        if operation["after_hash"] != expected_after:
            return self._unknown("after-hash-invalid")
        if not _valid_hash(operation["before_hash"], nullable=op == "create"):
            return self._unknown("before-hash-invalid")
        if op == "create" and operation["before_hash"] is not None:
            return self._unknown("create-before-hash-invalid")
        if op == "update" and operation["before_hash"] is None:
            return self._unknown("update-before-hash-invalid")

        try:
            _, target = _metadata_preflight(collection.root, relative_path, op)
        except FileExistsError:
            return ExecutionResult("conflict", "target-exists")
        except RuntimeError as error:
            return self._unknown(str(error))

        if op == "update":
            try:
                if _read_hash(target) != operation["before_hash"]:
                    return ExecutionResult("conflict", "before-hash-mismatch")
            except RuntimeError as error:
                return self._unknown(str(error))
            if self._atomic_update_cas is None:
                return ExecutionResult("unsupported", "update-unsupported")

        temporary: Path | None = None

        def discard_temporary() -> bool:
            nonlocal temporary
            if temporary is None:
                return True
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                return False
            temporary = None
            return True

        try:
            descriptor, name = tempfile.mkstemp(prefix=".capture-", suffix=".tmp", dir=target.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            if _read_hash(temporary) != expected_after:
                if not discard_temporary():
                    return self._unknown("temporary-cleanup-unknown")
                return self._unknown("temporary-hash-mismatch")

            if op == "create":
                try:
                    os.link(temporary, target, follow_symlinks=False)
                except FileExistsError:
                    if not discard_temporary():
                        return self._unknown("temporary-cleanup-unknown")
                    return ExecutionResult("conflict", "target-exists")
                except (NotImplementedError, OSError):
                    if not discard_temporary():
                        return self._unknown("temporary-cleanup-unknown")
                    return self._unknown("atomic-create-unavailable")
            else:
                status = self._atomic_update_cas(
                    temporary,
                    target,
                    operation["before_hash"],
                    expected_after,
                )
                if status == "conflict":
                    if not discard_temporary():
                        return self._unknown("temporary-cleanup-unknown")
                    return ExecutionResult("conflict", "before-hash-conflict")
                if status != "published":
                    if not discard_temporary():
                        return self._unknown("temporary-cleanup-unknown")
                    return self._unknown("atomic-update-unknown")

            if not discard_temporary():
                return self._unknown("temporary-cleanup-unknown")
            try:
                postread_hash = _read_hash(target)
            except RuntimeError as error:
                return self._unknown(str(error))
            if postread_hash != expected_after:
                return self._unknown("postread-hash-mismatch")
            return ExecutionResult("published", "verified", expected_after)
        except Exception:
            if not discard_temporary():
                return self._unknown("temporary-cleanup-unknown")
            return self._unknown("publication-unknown")
