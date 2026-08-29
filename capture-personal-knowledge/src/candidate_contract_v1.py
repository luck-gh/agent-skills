"""实现 Capture 自有的 note-plan v1 与 Markdown 候选契约;供候选往返校验使用.

This module deliberately performs no file, environment, profile, process, or
network I/O.  Callers supply the complete JSON bytes and the complete set of
allowed logical format-profile identifiers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Collection, Mapping, Sequence
from typing import Any


REQUEST_SCHEMA = "capture-note-plan"
RESPONSE_SCHEMA = "markdown-note-candidate"
VERSION = 1
REQUEST_DIRECTION = "capture-to-markdown"
RESPONSE_DIRECTION = "markdown-to-capture"
MAX_HOPS = 1

LIMITS = {
    "bytes": 262_144,
    "depth": 16,
    "nodes": 4_096,
    "count": 128,
    "string_bytes": 32_768,
    "body_bytes": 131_072,
    "resources": 64,
}
MAX_ID_BYTES = 128
MAX_PATH_BYTES = 1_024
MAX_FILENAME_BYTES = 255
MAX_TEXT_BYTES = 8_192
MAX_LABEL_BYTES = 1_024
MAX_TAXONOMY_VALUES = 64
MAX_FRONTMATTER_FIELDS = 64
MAX_ITEMS = 64
MAX_OPERATIONS = 64
MAX_ITEM_IDS = 64
MAX_TRANSFORMS = 8
MAX_FORMAT_PROFILES = 64

REQUEST_KEYS = frozenset(
    {
        "schema",
        "version",
        "direction",
        "max_hops",
        "request_id",
        "scope",
        "items",
        "operations",
        "request_digest",
    }
)
ITEM_KEYS = frozenset({"item_id", "content", "evidence"})
CONTENT_KEYS = frozenset(
    {"title", "body", "frontmatter", "taxonomy", "resource_refs"}
)
EVIDENCE_KEYS = frozenset({"evidence_id", "kind", "summary"})
OPERATION_KEYS = frozenset(
    {"operation_id", "item_ids", "target", "transform", "format_profile"}
)
FRONTMATTER_ENTRY_KEYS = frozenset({"name", "value"})
TAXONOMY_KEYS = frozenset({"tags", "categories"})
RESOURCE_REF_KEYS = frozenset({"resource_id", "kind", "target", "label"})
RESPONSE_KEYS = frozenset(
    {
        "schema",
        "version",
        "direction",
        "max_hops",
        "request_id",
        "request_digest",
        "candidates",
        "candidate_digest",
    }
)
CANDIDATE_KEYS = frozenset(
    {
        "operation_id",
        "item_ids",
        "filename",
        "frontmatter",
        "taxonomy",
        "body",
        "resource_refs",
    }
)
ERROR_KEYS = frozenset(
    {"schema", "version", "direction", "max_hops", "error"}
)

TRANSFORMS = frozenset(
    {"filename", "frontmatter", "taxonomy", "body", "resource-refs"}
)
ERROR_CODE = "invalid-contract-input"
ERROR_RESPONSE = {
    "schema": RESPONSE_SCHEMA,
    "version": VERSION,
    "direction": RESPONSE_DIRECTION,
    "max_hops": MAX_HOPS,
    "error": ERROR_CODE,
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_LOGICAL_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_FRONTMATTER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_WINDOWS_DEVICE = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.IGNORECASE
)
_BANNED_JOINED_KEYS = frozenset(
    {
        "root",
        "rootconfirmed",
        "privacystatus",
        "confirmation",
        "needsconfirmation",
        "authorization",
        "authorize",
        "approval",
        "approve",
        "grant",
        "permission",
        "profile",
        "path",
        "template",
        "command",
        "default",
        "writestate",
        "writeplan",
        "callback",
        "execute",
        "commit",
        "push",
        "pair",
    }
)
_SECRET_KEY_MARKERS = (
    "secret",
    "password",
    "passwd",
    "credential",
    "privatekey",
    "apikey",
    "accesstoken",
    "refreshtoken",
    "authtoken",
)
_FORBIDDEN_PROFILE_PARTS = frozenset(
    {"default", "path", "template", "command", "shell", "exec", "execute"}
)


class ContractError(ValueError):
    """A deliberately non-reflective contract failure."""

    def __init__(self) -> None:
        super().__init__(ERROR_CODE)


def _fail() -> None:
    raise ContractError()


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole canonical JSON representation used by this contract."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", "strict")
    except (TypeError, ValueError, UnicodeError):
        _fail()
    return encoded


def digest_without(value: Mapping[str, Any], field: str) -> str:
    if type(value) is not dict or field not in value:
        _fail()
    payload = copy.deepcopy(value)
    del payload[field]
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def request_digest(request: Mapping[str, Any]) -> str:
    return digest_without(request, "request_digest")


def candidate_digest(response: Mapping[str, Any]) -> str:
    return digest_without(response, "candidate_digest")


def fixed_error_response() -> dict[str, Any]:
    """Return the fixed failure object; it never reflects caller input."""

    return copy.deepcopy(ERROR_RESPONSE)


def _reject_constant(_value: str) -> None:
    _fail()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def _decode(raw: bytes) -> Any:
    if type(raw) is not bytes or not raw or len(raw) > LIMITS["bytes"]:
        _fail()
    if raw.startswith(b"\xef\xbb\xbf"):
        _fail()
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except ContractError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail()
    _walk_limits(value)
    if canonical_json_bytes(value) != raw:
        _fail()
    return value


def _key_signature(key: str) -> str:
    expanded = _CAMEL_BOUNDARY.sub("_", key)
    return _NON_ALNUM.sub("", expanded.casefold())


def _reject_key(key: str) -> None:
    if type(key) is not str:
        _fail()
    joined = _key_signature(key)
    if joined in _BANNED_JOINED_KEYS:
        _fail()
    if any(marker in joined for marker in _SECRET_KEY_MARKERS):
        _fail()


def _walk_limits(value: Any, depth: int = 0, budget: list[int] | None = None, key: str = "") -> None:
    if budget is None:
        budget = [0]
    if depth > LIMITS["depth"]:
        _fail()
    budget[0] += 1
    if budget[0] > LIMITS["nodes"]:
        _fail()
    if value is None or type(value) is bool:
        _fail()
    if type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            _fail()
        return
    if type(value) is str:
        cap = LIMITS["body_bytes"] if key == "body" else LIMITS["string_bytes"]
        try:
            size = len(value.encode("utf-8", "strict"))
        except UnicodeError:
            _fail()
        if size > cap or "\x00" in value:
            _fail()
        return
    if type(value) is list:
        if len(value) > LIMITS["count"]:
            _fail()
        for item in value:
            _walk_limits(item, depth + 1, budget)
        return
    if type(value) is dict:
        if len(value) > LIMITS["count"]:
            _fail()
        for child_key, child in value.items():
            _reject_key(child_key)
            _walk_limits(child, depth + 1, budget, child_key)
        return
    _fail()


def _exact_keys(value: Any, keys: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _fail()
    return value


def _exact_list(value: Any, maximum: int) -> list[Any]:
    if type(value) is not list or not value or len(value) > maximum:
        _fail()
    return value


def _exact_int(value: Any, expected: int) -> None:
    if type(value) is not int or value != expected:
        _fail()


def _exact_string(value: Any, expected: str) -> None:
    if type(value) is not str or value != expected:
        _fail()


def _sized_text(value: Any, maximum: int, *, multiline: bool) -> str:
    if type(value) is not str:
        _fail()
    try:
        size = len(value.encode("utf-8", "strict"))
    except UnicodeError:
        _fail()
    if size > maximum or unicodedata.normalize("NFC", value) != value:
        _fail()
    for char in value:
        point = ord(char)
        if point == 0x7F or point < 0x20 and not (
            multiline and char in "\t\n\r"
        ):
            _fail()
    return value


def _opaque_id(value: Any) -> str:
    if type(value) is not str or not _OPAQUE_ID.fullmatch(value):
        _fail()
    if len(value.encode("utf-8")) > MAX_ID_BYTES:
        _fail()
    return value


def _logical_id(value: Any) -> str:
    if type(value) is not str or not _LOGICAL_ID.fullmatch(value):
        _fail()
    return value


def _format_profile(value: Any, allowlist: frozenset[str]) -> str:
    profile = _logical_id(value)
    if profile not in allowlist:
        _fail()
    if any(part in _FORBIDDEN_PROFILE_PARTS for part in profile.split("-")):
        _fail()
    return profile


def _profile_allowlist(values: Collection[str]) -> frozenset[str]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Collection):
        _fail()
    if not values or len(values) > MAX_FORMAT_PROFILES:
        _fail()
    result: set[str] = set()
    for value in values:
        profile = _logical_id(value)
        if any(part in _FORBIDDEN_PROFILE_PARTS for part in profile.split("-")):
            _fail()
        if profile in result:
            _fail()
        result.add(profile)
    return frozenset(result)


def _relative_path(value: Any, *, filename: bool = False) -> str:
    if type(value) is not str or not value:
        _fail()
    if unicodedata.normalize("NFC", value) != value:
        _fail()
    maximum = MAX_FILENAME_BYTES if filename else MAX_PATH_BYTES
    if len(value.encode("utf-8", "strict")) > maximum:
        _fail()
    if (
        value.startswith(("/", "\\"))
        or _DRIVE_PREFIX.match(value)
        or "\\" in value
        or "%" in value
        or "?" in value
        or "#" in value
        or ":" in value
    ):
        _fail()
    parts = value.split("/")
    if filename and len(parts) != 1:
        _fail()
    if any(
        not part
        or part in {".", ".."}
        or part.endswith((" ", "."))
        or _WINDOWS_DEVICE.match(part)
        for part in parts
    ):
        _fail()
    for part in parts:
        _sized_text(part, MAX_FILENAME_BYTES, multiline=False)
    return value


def _target_in_scope(target: Any, scope: str, *, markdown: bool) -> str:
    checked = _relative_path(target)
    if checked.casefold() == scope.casefold() or not checked.casefold().startswith(
        scope.casefold() + "/"
    ):
        _fail()
    if markdown and not checked.casefold().endswith(".md"):
        _fail()
    return checked


def _unique(values: Sequence[str]) -> None:
    if len(values) != len(set(values)):
        _fail()


def _frontmatter(value: Any) -> list[dict[str, str]]:
    if type(value) is not list or len(value) > MAX_FRONTMATTER_FIELDS:
        _fail()
    names: list[str] = []
    for entry in value:
        item = _exact_keys(entry, FRONTMATTER_ENTRY_KEYS)
        name = item["name"]
        if type(name) is not str or not _FRONTMATTER_NAME.fullmatch(name):
            _fail()
        _reject_key(name)
        names.append(name.casefold())
        _sized_text(item["value"], MAX_TEXT_BYTES, multiline=True)
    _unique(names)
    return value


def _taxonomy(value: Any) -> dict[str, list[str]]:
    result = _exact_keys(value, TAXONOMY_KEYS)
    for field in ("tags", "categories"):
        entries = result[field]
        if type(entries) is not list or len(entries) > MAX_TAXONOMY_VALUES:
            _fail()
        normalized: list[str] = []
        for entry in entries:
            text = _sized_text(entry, MAX_LABEL_BYTES, multiline=False)
            if not text:
                _fail()
            normalized.append(text.casefold())
        _unique(normalized)
    return result


def _resource_refs(value: Any, scope: str) -> list[dict[str, str]]:
    if type(value) is not list or len(value) > LIMITS["resources"]:
        _fail()
    ids: list[str] = []
    for entry in value:
        ref = _exact_keys(entry, RESOURCE_REF_KEYS)
        ids.append(_opaque_id(ref["resource_id"]))
        _logical_id(ref["kind"])
        _target_in_scope(ref["target"], scope, markdown=False)
        _sized_text(ref["label"], MAX_LABEL_BYTES, multiline=False)
    _unique(ids)
    return value


def _validate_content(value: Any, scope: str) -> None:
    content = _exact_keys(value, CONTENT_KEYS)
    _sized_text(content["title"], MAX_LABEL_BYTES, multiline=False)
    _sized_text(content["body"], LIMITS["body_bytes"], multiline=True)
    _frontmatter(content["frontmatter"])
    _taxonomy(content["taxonomy"])
    _resource_refs(content["resource_refs"], scope)


def validate_request(value: Any, allowed_format_profiles: Collection[str]) -> dict[str, Any]:
    """Validate a decoded request without consulting any ambient state."""

    allowlist = _profile_allowlist(allowed_format_profiles)
    _walk_limits(value)
    request = _exact_keys(value, REQUEST_KEYS)
    _exact_string(request["schema"], REQUEST_SCHEMA)
    _exact_int(request["version"], VERSION)
    _exact_string(request["direction"], REQUEST_DIRECTION)
    _exact_int(request["max_hops"], MAX_HOPS)
    _opaque_id(request["request_id"])
    scope = _relative_path(request["scope"])
    if not _HEX64.fullmatch(request["request_digest"]):
        _fail()

    items = _exact_list(request["items"], MAX_ITEMS)
    item_ids: list[str] = []
    for raw_item in items:
        item = _exact_keys(raw_item, ITEM_KEYS)
        item_ids.append(_opaque_id(item["item_id"]))
        _validate_content(item["content"], scope)
        evidence = item["evidence"]
        if type(evidence) is not list or len(evidence) > LIMITS["count"]:
            _fail()
        evidence_ids: list[str] = []
        for raw_evidence in evidence:
            entry = _exact_keys(raw_evidence, EVIDENCE_KEYS)
            evidence_ids.append(_opaque_id(entry["evidence_id"]))
            _logical_id(entry["kind"])
            _sized_text(entry["summary"], MAX_TEXT_BYTES, multiline=True)
        _unique(evidence_ids)
    _unique(item_ids)
    known_items = set(item_ids)

    operations = _exact_list(request["operations"], MAX_OPERATIONS)
    operation_ids: list[str] = []
    targets: list[str] = []
    for raw_operation in operations:
        operation = _exact_keys(raw_operation, OPERATION_KEYS)
        operation_ids.append(_opaque_id(operation["operation_id"]))
        bound_ids = _exact_list(operation["item_ids"], MAX_ITEM_IDS)
        checked_ids = [_opaque_id(item_id) for item_id in bound_ids]
        _unique(checked_ids)
        if any(item_id not in known_items for item_id in checked_ids):
            _fail()
        target = _target_in_scope(operation["target"], scope, markdown=True)
        targets.append(target.casefold())
        transforms = _exact_list(operation["transform"], MAX_TRANSFORMS)
        checked_transforms = [_logical_id(name) for name in transforms]
        _unique(checked_transforms)
        if "body" not in checked_transforms or any(
            name not in TRANSFORMS for name in checked_transforms
        ):
            _fail()
        _format_profile(operation["format_profile"], allowlist)
    _unique(operation_ids)
    _unique(targets)
    if request_digest(request) != request["request_digest"]:
        _fail()
    return request


def parse_request(raw: bytes, allowed_format_profiles: Collection[str]) -> dict[str, Any]:
    value = _decode(raw)
    return validate_request(value, allowed_format_profiles)


def _validate_candidate(candidate: Any, operation: dict[str, Any], scope: str) -> str:
    result = _exact_keys(candidate, CANDIDATE_KEYS)
    if result["operation_id"] != operation["operation_id"]:
        _fail()
    if result["item_ids"] != operation["item_ids"]:
        _fail()
    filename = _relative_path(result["filename"], filename=True)
    if not filename.casefold().endswith(".md"):
        _fail()
    request_filename = operation["target"].rsplit("/", 1)[-1]
    if "filename" not in operation["transform"] and filename != request_filename:
        _fail()
    _frontmatter(result["frontmatter"])
    _taxonomy(result["taxonomy"])
    _sized_text(result["body"], LIMITS["body_bytes"], multiline=True)
    _resource_refs(result["resource_refs"], scope)
    if "frontmatter" not in operation["transform"] and result["frontmatter"]:
        _fail()
    if "taxonomy" not in operation["transform"] and (
        result["taxonomy"]["tags"] or result["taxonomy"]["categories"]
    ):
        _fail()
    if "resource-refs" not in operation["transform"] and result["resource_refs"]:
        _fail()
    parent = operation["target"].rsplit("/", 1)[0]
    return (parent + "/" + filename).casefold()


def validate_response(
    value: Any,
    request: Any,
    allowed_format_profiles: Collection[str],
) -> dict[str, Any]:
    """Validate a candidate response and its complete binding to one request."""

    validated_request = validate_request(request, allowed_format_profiles)
    _walk_limits(value)
    response = _exact_keys(value, RESPONSE_KEYS)
    _exact_string(response["schema"], RESPONSE_SCHEMA)
    _exact_int(response["version"], VERSION)
    _exact_string(response["direction"], RESPONSE_DIRECTION)
    _exact_int(response["max_hops"], MAX_HOPS)
    if response["request_id"] != validated_request["request_id"]:
        _fail()
    if response["request_digest"] != validated_request["request_digest"]:
        _fail()
    if not _HEX64.fullmatch(response["candidate_digest"]):
        _fail()
    candidates = _exact_list(response["candidates"], MAX_OPERATIONS)
    operations = validated_request["operations"]
    if len(candidates) != len(operations):
        _fail()
    targets = [
        _validate_candidate(candidate, operation, validated_request["scope"])
        for candidate, operation in zip(candidates, operations)
    ]
    _unique(targets)
    if candidate_digest(response) != response["candidate_digest"]:
        _fail()
    return response


def parse_response(
    raw: bytes,
    request: Any,
    allowed_format_profiles: Collection[str],
) -> dict[str, Any]:
    value = _decode(raw)
    return validate_response(value, request, allowed_format_profiles)


def validate_error_response(value: Any) -> dict[str, Any]:
    """Accept only the fixed non-reflective failure response."""

    _walk_limits(value)
    error = _exact_keys(value, ERROR_KEYS)
    if error != ERROR_RESPONSE:
        _fail()
    return error


__all__ = [
    "ContractError",
    "ERROR_CODE",
    "LIMITS",
    "candidate_digest",
    "canonical_json_bytes",
    "fixed_error_response",
    "parse_request",
    "parse_response",
    "request_digest",
    "validate_error_response",
    "validate_request",
    "validate_response",
]
