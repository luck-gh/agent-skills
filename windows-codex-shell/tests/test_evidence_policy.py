"""验证 Windows Codex shell 证据分类,授权门禁和完成条件.

测试仅使用虚构路径与结构化布尔事实,不读取真实日志,不修改系统 ACL,
不启动 UAC,也不调用真实 sandbox helper.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "evaluate_windows_shell_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("windows_shell_evidence", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable_to_load_evidence_evaluator")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
evaluate_evidence = MODULE.evaluate_evidence


class EvidencePolicyTests(unittest.TestCase):
    def repair_ready(self) -> dict[str, object]:
        return {
            "write_ace_grant_failed": True,
            "set_named_security_info_error": 5,
            "exact_failure_object_recorded": True,
            "pre_owner_recorded": True,
            "pre_dacl_recorded": True,
            "write_dac_distinguished": True,
            "repair_target": "X:\\ExampleWorkspace\\Project",
            "repair_target_scope": "workspace_root",
            "repair_target_is_resolved": True,
            "host_action_allowed": True,
            "rollback_basis_recorded": True,
            "post_state_verification_defined": True,
        }

    def completed_validation(self) -> dict[str, object]:
        return {
            "sandbox_start_results": [True, True, True],
            "latest_setup_errors": [],
            "runner_success": True,
            "target_command_success": True,
            "workspace_file_read_success": True,
            "git_status_success": True,
            "controlled_write_success": True,
            "write_content_verified": True,
            "git_post_status_verified": True,
            "setup_error_state": "updated",
            "post_acl_verified": True,
        }

    def test_generic_helper_error_without_suberror_is_unresolved(self) -> None:
        result = evaluate_evidence({"helper_unknown_error": True})
        self.assertIn("unresolved_helper_failure", result["categories"])
        self.assertFalse(result["repair_plan_allowed"])

    def test_write_ace_grant_failed_classifies_workspace_dacl(self) -> None:
        result = evaluate_evidence({"write_ace_grant_failed": True})
        self.assertIn("workspace_dacl_failure", result["categories"])
        self.assertIn("set_named_security_info_error_5", result["missing_evidence"])

    def test_set_named_security_info_access_denied_classifies_dacl(self) -> None:
        result = evaluate_evidence({"set_named_security_info_error": 5})
        self.assertIn("workspace_dacl_failure", result["categories"])
        self.assertIn("write_ace_grant_failed_signature", result["missing_evidence"])

    def test_marker_access_denied_is_separate_failure(self) -> None:
        result = evaluate_evidence({"marker_exists": True, "marker_readable": False})
        self.assertEqual(result["categories"], ["marker_acl_failure"])

    def test_empty_setup_errors_then_runner_failure(self) -> None:
        result = evaluate_evidence({"setup_errors": [], "runner_failed": True})
        self.assertIn("command_runner_failure", result["categories"])
        self.assertNotIn("workspace_dacl_failure", result["categories"])

    def test_windowsapps_bundled_rg_denial_is_tool_start_failure(self) -> None:
        result = evaluate_evidence(
            {
                "bundled_tool_access_denied": True,
                "bundled_tool_location": "windowsapps",
            }
        )
        self.assertEqual(result["categories"], ["tool_start_failure"])

    def test_setup_and_bundled_tool_failures_remain_independent(self) -> None:
        result = evaluate_evidence(
            {
                "write_ace_grant_failed": True,
                "set_named_security_info_error": 5,
                "bundled_tool_access_denied": True,
                "bundled_tool_location": "windowsapps",
            }
        )
        self.assertIn("workspace_dacl_failure", result["categories"])
        self.assertIn("tool_start_failure", result["categories"])

    def test_write_unknown_outcome_requires_post_state(self) -> None:
        result = evaluate_evidence(
            {"write_operation": True, "helper_error": True, "post_state": "unknown"}
        )
        self.assertIn("unknown_outcome", result["categories"])
        self.assertEqual(result["next_action"], "check_post_state_without_replay")

    def test_acl_repair_processing_zero_objects_is_not_applied(self) -> None:
        evidence = {**self.completed_validation(), "repair_processed_count": 0}
        result = evaluate_evidence(evidence)
        self.assertIn("repair_not_applied", result["categories"])
        self.assertFalse(result["repair_complete"])

    def test_external_success_and_sandbox_failure_is_path_specific(self) -> None:
        result = evaluate_evidence(
            {"external_execution_success": True, "sandbox_execution_failure": True}
        )
        self.assertIn("sandbox_path_specific_failure", result["categories"])
        self.assertNotIn("workspace_dacl_failure", result["categories"])

    def test_second_of_three_sandbox_starts_failing_blocks_completion(self) -> None:
        evidence = {
            **self.completed_validation(),
            "sandbox_start_results": [True, False, True],
        }
        result = evaluate_evidence(evidence)
        self.assertFalse(result["repair_complete"])
        self.assertIn("three_consecutive_sandbox_starts", result["failed_validations"])

    def test_no_repair_authorization_limits_output(self) -> None:
        evidence = {**self.repair_ready(), "authorization_level": "diagnose_only"}
        result = evaluate_evidence(evidence)
        self.assertFalse(result["repair_plan_allowed"])
        self.assertEqual(result["allowed_output"], "diagnosis_and_nonexecuting_handoff")

    def test_authorized_but_imprecise_target_refuses_modification(self) -> None:
        evidence = {
            **self.repair_ready(),
            "authorization_level": "repair_execution",
            "repair_target": ".\\Project",
            "repair_target_is_resolved": False,
        }
        result = evaluate_evidence(evidence)
        self.assertFalse(result["repair_execution_handoff_allowed"])
        self.assertIn("target_not_absolute", result["safety_blocks"])

    def test_broad_acl_targets_are_rejected(self) -> None:
        cases = (
            ("X:\\", "workspace_root", "target_is_volume_root"),
            ("C:\\Users\\ExampleUser", "workspace_root", "target_is_user_home"),
            (
                "C:\\Program Files\\WindowsApps\\Example.App",
                "workspace_root",
                "target_is_windowsapps",
            ),
        )
        for path, scope, expected in cases:
            with self.subTest(path=path):
                evidence = {
                    **self.repair_ready(),
                    "authorization_level": "repair_execution",
                    "repair_target": path,
                    "repair_target_scope": scope,
                }
                result = evaluate_evidence(evidence)
                self.assertFalse(result["repair_execution_handoff_allowed"])
                self.assertIn(expected, result["safety_blocks"])

    def test_truncated_or_oversized_logs_never_count_as_complete(self) -> None:
        for field in ("logs_truncated", "logs_too_large_for_bounded_read"):
            with self.subTest(field=field):
                evidence = {
                    **self.repair_ready(),
                    "authorization_level": "repair_execution",
                    field: True,
                }
                result = evaluate_evidence(evidence)
                self.assertIn("evidence_incomplete", result["categories"])
                self.assertFalse(result["repair_execution_handoff_allowed"])

    def test_rg_failure_allows_only_one_narrow_powershell_fallback(self) -> None:
        first = evaluate_evidence(
            {"rg_start_failed": True, "narrow_powershell_fallback_attempts": 0}
        )
        second = evaluate_evidence(
            {"rg_start_failed": True, "narrow_powershell_fallback_attempts": 1}
        )
        self.assertTrue(first["powershell_fallback_allowed"])
        self.assertFalse(second["powershell_fallback_allowed"])

    def test_helper_write_failure_must_not_be_replayed(self) -> None:
        result = evaluate_evidence(
            {
                "helper_unknown_error": True,
                "helper_error": True,
                "write_operation": True,
            }
        )
        self.assertEqual(result["next_action"], "check_post_state_without_replay")
        self.assertIn("unknown_outcome", result["categories"])

    def test_require_escalated_without_acl_change_is_not_completion(self) -> None:
        evidence = {
            **self.completed_validation(),
            "require_escalated_succeeded": True,
            "post_acl_verified": False,
        }
        result = evaluate_evidence(evidence)
        self.assertFalse(result["repair_complete"])
        self.assertIn(
            "leaving_sandbox_did_not_prove_windows_admin_or_acl_change",
            result["notes"],
        )

    def test_real_uac_need_requires_visible_confirmation(self) -> None:
        evidence = {
            **self.repair_ready(),
            "authorization_level": "repair_execution",
            "windows_admin_token_required": True,
            "visible_uac_confirmed": False,
        }
        result = evaluate_evidence(evidence)
        self.assertTrue(result["uac_step_required"])
        self.assertFalse(result["repair_execution_handoff_allowed"])
        self.assertEqual(result["allowed_output"], "repair_plan_waiting_for_visible_uac")
        self.assertTrue(result["uac_authorization_step"]["must_be_user_visible"])
        self.assertEqual(
            result["uac_authorization_step"]["exact_target"],
            "X:\\ExampleWorkspace\\Project",
        )

    def test_all_repair_gates_allow_specialized_executor_handoff(self) -> None:
        evidence = {
            **self.repair_ready(),
            "authorization_level": "repair_execution",
        }
        result = evaluate_evidence(evidence)
        self.assertTrue(result["repair_plan_allowed"])
        self.assertTrue(result["repair_execution_handoff_allowed"])
        self.assertEqual(
            result["next_action"], "handoff_to_host_allowed_specialized_executor"
        )

    def test_all_post_repair_validations_allow_completion(self) -> None:
        result = evaluate_evidence(self.completed_validation())
        self.assertTrue(result["repair_complete"])
        self.assertEqual(result["failed_validations"], [])

    def test_file_write_without_write_dac_is_dacl_capability_gap(self) -> None:
        result = evaluate_evidence(
            {"ordinary_file_write_success": True, "write_dac_available": False}
        )
        self.assertIn("workspace_dacl_failure", result["categories"])

    def test_removable_workspace_without_disk_error_is_not_hardware_fault(self) -> None:
        result = evaluate_evidence(
            {"workspace_on_removable_drive": True, "disk_or_filesystem_error": False}
        )
        self.assertFalse(result["hardware_fault_attribution_allowed"])
        self.assertIn(
            "removable_location_is_not_hardware_fault_evidence", result["notes"]
        )


if __name__ == "__main__":
    unittest.main()
