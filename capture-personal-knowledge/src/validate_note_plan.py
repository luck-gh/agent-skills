"""绑定 Capture 写入状态与规范 Markdown 候选契约;供 write plan 构造前校验使用."""

from __future__ import annotations

import argparse
import copy
import hashlib
import re
import sys
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

import candidate_contract_v1 as _adapter


LOCAL_CONTEXT_KEYS = frozenset({"plan_id", "collection_id", "operation_intents"})
LOCAL_INTENT_KEYS = frozenset({"operation_id", "operation", "before_hash"})
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# Public adapter functions are aliases, not a second schema implementation.
ContractError = _adapter.ContractError
ERROR_CODE = _adapter.ERROR_CODE
LIMITS = _adapter.LIMITS
candidate_digest = _adapter.candidate_digest
canonical_json_bytes = _adapter.canonical_json_bytes
fixed_error_response = _adapter.fixed_error_response
parse_request = _adapter.parse_request
parse_response = _adapter.parse_response
request_digest = _adapter.request_digest
validate_error_response = _adapter.validate_error_response
validate_request = _adapter.validate_request
validate_response = _adapter.validate_response


def _fail() -> None:
    raise ContractError()


def _opaque_id(value: Any) -> str:
    if type(value) is not str or not _OPAQUE_ID.fullmatch(value):
        _fail()
    return value


def _local_hash(value: Any, *, nullable: bool) -> str | None:
    if value is None and nullable:
        return None
    if type(value) is not str or not _HEX64.fullmatch(value):
        _fail()
    return value


def seal_request(
    value: Mapping[str, Any],
    allowed_format_profiles: Collection[str],
) -> dict[str, Any]:
    """Seal and validate a request with Capture's explicit profile allowlist."""

    if type(value) is not dict:
        _fail()
    result = copy.deepcopy(value)
    result["request_digest"] = "0" * 64
    result["request_digest"] = request_digest(result)
    return validate_request(result, allowed_format_profiles)


def build_request(
    *,
    request_id: str,
    scope: str,
    items: list[dict[str, Any]],
    operations: list[dict[str, Any]],
    allowed_format_profiles: Collection[str],
) -> dict[str, Any]:
    """Build the canonical formatter request without Capture-local write state."""

    return seal_request(
        {
            "schema": _adapter.REQUEST_SCHEMA,
            "version": _adapter.VERSION,
            "direction": _adapter.REQUEST_DIRECTION,
            "max_hops": _adapter.MAX_HOPS,
            "request_id": request_id,
            "scope": scope,
            "items": copy.deepcopy(items),
            "operations": copy.deepcopy(operations),
            "request_digest": "0" * 64,
        },
        allowed_format_profiles,
    )


def construct_write_plan(
    *,
    request: Any,
    response: Any,
    local_context: Any,
    allowed_format_profiles: Collection[str],
) -> tuple[dict[str, Any], str]:
    """Bind one validated candidate per operation to Capture-only write state."""

    validated_request = validate_request(request, allowed_format_profiles)
    validated_response = validate_response(
        response, validated_request, allowed_format_profiles
    )
    if type(local_context) is not dict or set(local_context) != LOCAL_CONTEXT_KEYS:
        _fail()
    plan_id = _opaque_id(local_context["plan_id"])
    collection_id = _opaque_id(local_context["collection_id"])
    raw_intents = local_context["operation_intents"]
    if type(raw_intents) is not list or not raw_intents:
        _fail()

    intents: dict[str, dict[str, Any]] = {}
    for raw_intent in raw_intents:
        if type(raw_intent) is not dict or set(raw_intent) != LOCAL_INTENT_KEYS:
            _fail()
        operation_id = _opaque_id(raw_intent["operation_id"])
        operation = raw_intent["operation"]
        if operation_id in intents or operation not in {"create", "update"}:
            _fail()
        before_hash = _local_hash(
            raw_intent["before_hash"], nullable=operation == "create"
        )
        if operation == "create" and before_hash is not None:
            _fail()
        if operation == "update" and before_hash is None:
            _fail()
        intents[operation_id] = {
            "operation_id": operation_id,
            "operation": operation,
            "before_hash": before_hash,
        }

    request_operations = validated_request["operations"]
    request_operation_ids = {
        operation["operation_id"] for operation in request_operations
    }
    if set(intents) != request_operation_ids:
        _fail()
    profiles = {operation["format_profile"] for operation in request_operations}
    if len(profiles) != 1:
        _fail()
    candidates = {
        candidate["operation_id"]: candidate
        for candidate in validated_response["candidates"]
    }

    operations: list[dict[str, Any]] = []
    for request_operation in request_operations:
        operation_id = request_operation["operation_id"]
        candidate = candidates[operation_id]
        intent = intents[operation_id]
        parent = request_operation["target"].rsplit("/", 1)[0]
        final_target = parent + "/" + candidate["filename"]
        body = candidate["body"]
        operations.append(
            {
                "operation_id": operation_id,
                "item_ids": copy.deepcopy(candidate["item_ids"]),
                "operation": intent["operation"],
                "scope": validated_request["scope"],
                "filename": candidate["filename"],
                "target": final_target,
                "format_profile": request_operation["format_profile"],
                "transform": copy.deepcopy(request_operation["transform"]),
                "body": body,
                "frontmatter": copy.deepcopy(candidate["frontmatter"]),
                "taxonomy": copy.deepcopy(candidate["taxonomy"]),
                "links": [],
                "resource_refs": copy.deepcopy(candidate["resource_refs"]),
                "before_hash": intent["before_hash"],
                "after_hash": hashlib.sha256(body.encode("utf-8", "strict")).hexdigest(),
            }
        )

    plan = {
        "schema": "capture-write-plan",
        "version": 1,
        "plan_id": plan_id,
        "request_digest": validated_request["request_digest"],
        "candidate_digest": validated_response["candidate_digest"],
        "collection_id": collection_id,
        "scope": validated_request["scope"],
        "format_profile": next(iter(profiles)),
        "operations": operations,
    }
    write_plan_digest = hashlib.sha256(canonical_json_bytes(plan)).hexdigest()
    return plan, write_plan_digest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format-profile",
        action="append",
        required=True,
        dest="format_profiles",
        help="Capture-selected logical profile allowlist; repeat as needed.",
    )
    return parser


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(payload))


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        request = parse_request(
            sys.stdin.buffer.read(LIMITS["bytes"] + 1), args.format_profiles
        )
    except (ContractError, SystemExit):
        _emit({"status": "invalid", "error": ERROR_CODE})
        return 2
    except Exception:
        _emit({"status": "invalid", "error": ERROR_CODE})
        return 2
    _emit({"status": "valid", "request_digest": request["request_digest"]})
    return 0


__all__ = [
    "ADAPTER_PATH",
    "ContractError",
    "ERROR_CODE",
    "LIMITS",
    "build_request",
    "candidate_digest",
    "canonical_json_bytes",
    "construct_write_plan",
    "fixed_error_response",
    "parse_request",
    "parse_response",
    "request_digest",
    "seal_request",
    "validate_error_response",
    "validate_request",
    "validate_response",
]


if __name__ == "__main__":
    raise SystemExit(main())
