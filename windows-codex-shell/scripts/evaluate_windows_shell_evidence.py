"""评估已脱敏的 Windows Codex shell 诊断事实.

本模块用于把人工提取的最小证据稳定映射为故障分类,ACL 修复门禁和
修复后验证结果.它不读取系统日志,不调用 sandbox helper,不修改 ACL,
也不启动 UAC.命令行用法:
`python -X utf8 -B scripts/evaluate_windows_shell_evidence.py --input evidence.json`.
"""

from __future__ import annotations

import argparse
import json
import ntpath
import re
import sys
from pathlib import Path
from typing import Any


_UNRESOLVED_VARIABLE = re.compile(r"%[^%]+%|\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*")


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def validate_repair_target(
    target_path: Any,
    *,
    target_scope: Any,
    target_is_resolved: Any,
) -> list[str]:
    """返回精确 ACL 修复目标的拒绝原因,空列表表示通过静态门禁."""

    reasons: list[str] = []
    if not isinstance(target_path, str) or not target_path.strip():
        return ["target_missing"]

    candidate = target_path.strip()
    if _UNRESOLVED_VARIABLE.search(candidate):
        reasons.append("target_has_unresolved_variable")
    if any(character in candidate for character in ("*", "?")):
        reasons.append("target_has_wildcard")
    if not ntpath.isabs(candidate):
        reasons.append("target_not_absolute")
    if target_is_resolved is not True:
        reasons.append("target_not_resolved")
    if target_scope != "workspace_root":
        reasons.append("target_not_exact_workspace_root")

    normalized = ntpath.normpath(candidate)
    drive, tail = ntpath.splitdrive(normalized)
    if not drive:
        reasons.append("target_missing_windows_identity")
    if drive and tail in ("", "\\", "/"):
        reasons.append("target_is_volume_root")

    lowered = normalized.casefold().replace("/", "\\")
    if "\\program files\\windowsapps" in lowered:
        reasons.append("target_is_windowsapps")

    _, without_drive = ntpath.splitdrive(lowered)
    parts = [part for part in without_drive.split("\\") if part]
    if len(parts) == 2 and parts[0] in ("users", "documents and settings"):
        reasons.append("target_is_user_home")

    return list(dict.fromkeys(reasons))


def evaluate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """根据结构化最小事实返回分类,授权门禁和完成状态."""

    categories: list[str] = []
    missing: list[str] = []
    safety_blocks: list[str] = []
    notes: list[str] = []

    dacl_signature = bool(evidence.get("write_ace_grant_failed")) or (
        evidence.get("set_named_security_info_error") == 5
    )
    write_dac_gap = (
        evidence.get("ordinary_file_write_success") is True
        and evidence.get("write_dac_available") is False
    )
    if dacl_signature or write_dac_gap:
        _append_once(categories, "workspace_dacl_failure")
    if evidence.get("write_ace_grant_failed") and evidence.get(
        "set_named_security_info_error"
    ) != 5:
        missing.append("set_named_security_info_error_5")
    if evidence.get("set_named_security_info_error") == 5 and not evidence.get(
        "write_ace_grant_failed"
    ):
        missing.append("write_ace_grant_failed_signature")

    if evidence.get("marker_exists") is True and evidence.get("marker_readable") is False:
        _append_once(categories, "marker_acl_failure")
    if evidence.get("setup_errors") == [] and evidence.get("runner_failed") is True:
        _append_once(categories, "command_runner_failure")
    if (
        evidence.get("bundled_tool_access_denied") is True
        and evidence.get("bundled_tool_location") == "windowsapps"
    ):
        _append_once(categories, "tool_start_failure")
    if evidence.get("write_operation") is True and evidence.get(
        "helper_error"
    ) is True and evidence.get("post_state") in (None, "unknown"):
        _append_once(categories, "unknown_outcome")
    if evidence.get("external_execution_success") is True and evidence.get(
        "sandbox_execution_failure"
    ) is True:
        _append_once(categories, "sandbox_path_specific_failure")
    if evidence.get("repair_processed_count") == 0:
        _append_once(categories, "repair_not_applied")

    has_specific_helper_evidence = any(
        category
        in {
            "workspace_dacl_failure",
            "marker_acl_failure",
            "command_runner_failure",
        }
        for category in categories
    )
    if evidence.get("helper_unknown_error") is True and not has_specific_helper_evidence:
        _append_once(categories, "unresolved_helper_failure")

    evidence_incomplete = any(
        (
            evidence.get("logs_complete") is False,
            evidence.get("logs_truncated") is True,
            evidence.get("logs_too_large_for_bounded_read") is True,
        )
    )
    if evidence_incomplete:
        _append_once(categories, "evidence_incomplete")
        safety_blocks.append("bounded_log_evidence_incomplete")

    rg_start_failed = evidence.get("rg_start_failed") is True
    fallback_attempts = evidence.get("narrow_powershell_fallback_attempts", 0)
    if not isinstance(fallback_attempts, int) or fallback_attempts < 0:
        fallback_attempts = 0
        safety_blocks.append("invalid_fallback_attempt_count")
    powershell_fallback_allowed = rg_start_failed and fallback_attempts == 0
    if rg_start_failed and fallback_attempts >= 1:
        notes.append("narrow_powershell_fallback_already_used")

    if evidence.get("workspace_on_removable_drive") is True:
        if evidence.get("disk_or_filesystem_error") is True:
            notes.append("storage_fault_requires_independent_evidence_review")
        else:
            notes.append("removable_location_is_not_hardware_fault_evidence")

    target_blocks = validate_repair_target(
        evidence.get("repair_target"),
        target_scope=evidence.get("repair_target_scope"),
        target_is_resolved=evidence.get("repair_target_is_resolved"),
    )
    safety_blocks.extend(target_blocks)

    repair_gate_requirements = {
        "exact_workspace_dacl_evidence": "workspace_dacl_failure" in categories
        and evidence.get("exact_failure_object_recorded") is True,
        "pre_owner_recorded": evidence.get("pre_owner_recorded") is True,
        "pre_dacl_recorded": evidence.get("pre_dacl_recorded") is True,
        "write_dac_distinguished": evidence.get("write_dac_distinguished") is True,
        "target_safe": not target_blocks,
        "host_action_allowed": evidence.get("host_action_allowed") is True,
        "rollback_basis_recorded": evidence.get("rollback_basis_recorded") is True,
        "post_state_verification_defined": evidence.get(
            "post_state_verification_defined"
        )
        is True,
    }
    failed_repair_gates = [
        name for name, satisfied in repair_gate_requirements.items() if not satisfied
    ]

    authorization = evidence.get("authorization_level", "diagnose_only")
    if authorization not in {"diagnose_only", "repair_plan", "repair_execution"}:
        authorization = "diagnose_only"
        safety_blocks.append("invalid_authorization_level")

    uac_required = evidence.get("windows_admin_token_required") is True
    uac_confirmed = evidence.get("visible_uac_confirmed") is True
    if uac_required and authorization == "repair_execution" and not uac_confirmed:
        safety_blocks.append("visible_uac_confirmation_required")

    uac_authorization_step: dict[str, Any] | None = None
    if uac_required:
        uac_authorization_step = {
            "must_be_user_visible": True,
            "exact_target": (
                evidence.get("repair_target") if not target_blocks else None
            ),
            "purpose": (
                "使当前用户能够修改精确工作区根目录的 DACL,从而允许 "
                "Codex sandbox setup helper 添加所需 ACE"
            ),
            "requires_user_confirmation": not uac_confirmed,
            "require_escalated_is_not_admin_proof": True,
        }

    base_repair_gate_passed = not failed_repair_gates and not evidence_incomplete
    repair_plan_allowed = authorization in {"repair_plan", "repair_execution"} and (
        base_repair_gate_passed
    )
    repair_execution_handoff_allowed = (
        authorization == "repair_execution"
        and base_repair_gate_passed
        and (not uac_required or uac_confirmed)
    )

    if authorization == "diagnose_only":
        allowed_output = "diagnosis_and_nonexecuting_handoff"
    elif not repair_plan_allowed:
        allowed_output = "diagnosis_and_blocked_repair_handoff"
    elif repair_execution_handoff_allowed:
        allowed_output = "repair_execution_handoff_allowed"
    elif uac_required:
        allowed_output = "repair_plan_waiting_for_visible_uac"
    else:
        allowed_output = "repair_plan_only"

    validation_requirements = {
        "three_consecutive_sandbox_starts": len(
            evidence.get("sandbox_start_results", [])
        )
        >= 3
        and all(evidence.get("sandbox_start_results", [])[-3:]),
        "latest_setup_errors_empty": evidence.get("latest_setup_errors") == [],
        "runner_success": evidence.get("runner_success") is True,
        "target_command_success": evidence.get("target_command_success") is True,
        "workspace_file_read_success": evidence.get("workspace_file_read_success")
        is True,
        "git_status_success": evidence.get("git_status_success") is True,
        "controlled_write_success": evidence.get("controlled_write_success") is True,
        "write_content_verified": evidence.get("write_content_verified") is True,
        "git_post_status_verified": evidence.get("git_post_status_verified") is True,
        "setup_error_state_current": evidence.get("setup_error_state")
        in {"absent", "updated", "not_current"},
        "post_acl_verified": evidence.get("post_acl_verified") is True,
    }
    failed_validations = [
        name for name, satisfied in validation_requirements.items() if not satisfied
    ]
    repair_complete = (
        not failed_validations
        and "repair_not_applied" not in categories
        and not evidence_incomplete
    )

    if evidence.get("require_escalated_succeeded") is True and evidence.get(
        "post_acl_verified"
    ) is not True:
        notes.append("leaving_sandbox_did_not_prove_windows_admin_or_acl_change")
        repair_complete = False

    if "unknown_outcome" in categories:
        next_action = "check_post_state_without_replay"
    elif "unresolved_helper_failure" in categories:
        next_action = "collect_bounded_direct_evidence"
    elif repair_execution_handoff_allowed:
        next_action = "handoff_to_host_allowed_specialized_executor"
    elif repair_plan_allowed:
        next_action = "present_precise_repair_plan_and_wait_for_authorization"
    else:
        next_action = "report_diagnosis_missing_gates_and_nonexecuting_handoff"

    return {
        "schema_version": 1,
        "categories": categories,
        "missing_evidence": list(dict.fromkeys(missing)),
        "safety_blocks": list(dict.fromkeys(safety_blocks)),
        "notes": list(dict.fromkeys(notes)),
        "powershell_fallback_allowed": powershell_fallback_allowed,
        "authorization_level": authorization,
        "repair_gate_requirements": repair_gate_requirements,
        "failed_repair_gates": failed_repair_gates,
        "repair_plan_allowed": repair_plan_allowed,
        "repair_execution_handoff_allowed": repair_execution_handoff_allowed,
        "uac_step_required": uac_required,
        "uac_authorization_step": uac_authorization_step,
        "allowed_output": allowed_output,
        "validation_requirements": validation_requirements,
        "failed_validations": failed_validations,
        "repair_complete": repair_complete,
        "hardware_fault_attribution_allowed": evidence.get("disk_or_filesystem_error")
        is True,
        "next_action": next_action,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="评估已脱敏的 Windows Codex shell 诊断事实,不执行系统修改."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="UTF-8 JSON 文件;内容应为人工整理的最小结构化事实,不是原始日志.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        return 2
    if not isinstance(payload, dict):
        print(
            json.dumps(
                {"status": "error", "error": "input_must_be_json_object"},
                ensure_ascii=False,
            )
        )
        return 2
    result = evaluate_evidence(payload)
    print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
