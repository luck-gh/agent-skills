"""`new-skills` 更新检查,覆盖保护和回滚行为回归测试."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.error import URLError


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_updater():
    path = SKILL_ROOT / "scripts" / "manage_updates.py"
    spec = importlib.util.spec_from_file_location("manage_updates_tested", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.data


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.updater = load_updater()

    def _skill(self, root: Path, name: str, text: str, *, settings: bytes | None = None) -> Path:
        skill = root / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(text, encoding="utf-8")
        if settings is not None:
            (skill / "settings.json").write_bytes(settings)
        return skill

    def _manifest(self, root: Path, names: list[str], snapshot: str = "snapshot-2") -> dict[str, object]:
        return {
            "schema_version": 1,
            "repository": "luck-gh/agent-skills",
            "snapshot_id": snapshot,
            "skills": {
                name: {
                    "path": name,
                    "content_sha256": self.updater.content_hash(root / name),
                    "files": [],
                }
                for name in names
            },
        }

    @staticmethod
    def _locks(*names: str) -> dict[str, object]:
        return {
            name: {
                "sourceType": "github",
                "source": "luck-gh/agent-skills",
                "skillPath": f"{name}/SKILL.md",
            }
            for name in names
        }

    def _public_fixture(self, base: Path):
        physical = base / ".agents" / "skills"
        physical.mkdir(parents=True)
        self._skill(physical, "alpha", "installed")
        manifest = self._manifest(physical, ["alpha"])
        opener = mock.Mock(side_effect=lambda *_args, **_kwargs: Response(manifest))
        manager = self.updater.UpdateManager(
            SKILL_ROOT, state_file=base / "state.json", manifest_opener=opener, lock_entries=self._locks("alpha"),
        )
        return manager, physical, manifest, opener

    def _check(self, manager, physical, *, usage=None, force=False, automatic=False):
        with mock.patch.object(self.updater.Path, "home", return_value=physical.parent.parent), mock.patch.object(
            self.updater, "load_settings", return_value=(physical, usage or physical)
        ), mock.patch.object(self.updater, "_git_root", return_value=None):
            return manager.check(force=force, automatic=automatic)

    def test_ttl_preserves_result_and_refreshes_at_exactly_24_hours(self) -> None:
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, opener = self._public_fixture(Path(temporary))
            manager.now = lambda: now
            initial = self._check(manager, physical)
            self.assertFalse(initial["cached"])
            manifest["skills"]["alpha"]["content_sha256"] = "a" * 64
            manager.now = lambda: now + timedelta(hours=24) - timedelta(microseconds=1)
            cached = self._check(manager, physical)
            self.assertTrue(cached["cached"])
            self.assertEqual(initial["checked_at"], cached["checked_at"])
            self.assertEqual(initial["updates"], cached["updates"])
            self.assertEqual(1, opener.call_count)
            manager.now = lambda: now + timedelta(hours=24)
            fresh = self._check(manager, physical)
            self.assertFalse(fresh["cached"])
            self.assertEqual(["alpha"], fresh["updates"])
            self.assertEqual("ask", fresh["notification"])
            again = self._check(manager, physical)
            self.assertTrue(again["cached"])
            self.assertEqual(["alpha"], again["updates"])
            self.assertEqual("none", again["notification"])
            self.assertFalse(self._check(manager, physical, force=True)["cached"])
            self.assertEqual(3, opener.call_count)

    def test_content_hash_ignores_local_runtime_directories(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            skill = self._skill(Path(temporary), "alpha", "stable")
            baseline = self.updater.content_hash(skill)
            local = skill / "tools" / "local"
            local.mkdir(parents=True)
            (local / "state.json").write_text("local\n", encoding="utf-8")
            output = skill / "test-output"
            output.mkdir()
            (output / "result.json").write_text("generated\n", encoding="utf-8")
            self.assertEqual(baseline, self.updater.content_hash(skill))

    def test_automatic_cache_does_not_run_git_hash_lock_network_or_write_state(self) -> None:
        for mode in ("public", "git"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
                manager, physical, _manifest, opener = self._public_fixture(Path(temporary))
                now = datetime(2026, 11, 6, tzinfo=timezone.utc)
                manager.now = lambda: now
                first = self._check(manager, physical)
                if mode == "git":
                    state = self.updater.load_state(manager.state_file)
                    state["cache_context"]["mode"] = "git"
                    state["check_result"] = {
                        "schema_version": 1, "mode": "git", "status": "update_available",
                        "update_id": "remote", "dirty": False, "changed_paths": ["alpha/SKILL.md"],
                    }
                    self.updater.save_state(manager.state_file, state)
                before = manager.state_file.read_bytes()
                opener.reset_mock()
                opener.side_effect = AssertionError("cached checks must not use the network")
                with mock.patch.object(self.updater, "load_settings", return_value=(physical, physical)), \
                    mock.patch.object(self.updater, "_git_root", side_effect=AssertionError("no Git discovery")), \
                    mock.patch.object(manager, "_context", side_effect=AssertionError("no content context")), \
                    mock.patch.object(self.updater, "_lock_entries", side_effect=AssertionError("no installer lock")), \
                    mock.patch.object(self.updater, "content_hash", side_effect=AssertionError("no content hash")), \
                    mock.patch.object(self.updater, "save_state", side_effect=AssertionError("no state write")):
                    cached = manager.check(automatic=True)
                self.assertEqual({"schema_version", "status", "cached", "checked_at", "next_check_at", "notification"}, set(cached))
                self.assertTrue(cached["cached"])
                self.assertEqual("none", cached["notification"])
                self.assertEqual(first["checked_at"], cached["checked_at"])
                self.assertEqual("2026-11-07T00:00:00Z", cached["next_check_at"])
                self.assertEqual(before, manager.state_file.read_bytes())
                opener.assert_not_called()

    def test_automatic_expiry_and_force_refresh_and_return_decision_without_hashes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, opener = self._public_fixture(Path(temporary))
            now = datetime(2026, 11, 6, tzinfo=timezone.utc)
            manager.now = lambda: now
            first = self._check(manager, physical, automatic=True)
            self.assertFalse(first["cached"])
            self.assertNotIn("current_hashes", first)
            self.assertEqual("2026-11-07T00:00:00Z", first["next_check_at"])
            manifest["skills"]["alpha"]["content_sha256"] = "a" * 64
            manager.now = lambda: now + timedelta(hours=24)
            fresh = self._check(manager, physical, automatic=True)
            self.assertFalse(fresh["cached"])
            self.assertEqual(["alpha"], fresh["updates"])
            self.assertEqual("ask", fresh["notification"])
            self.assertEqual("2026-11-08T00:00:00Z", fresh["next_check_at"])
            self.assertNotIn("current_hashes", fresh)
            self.assertIn("current_hashes", self.updater.load_state(manager.state_file)["check_result"])
            self.assertFalse(self._check(manager, physical, force=True, automatic=True)["cached"])
            self.assertEqual(3, opener.call_count)

    def test_automatic_settings_root_changes_invalidate_cache(self) -> None:
        for changed in ("physical", "usage"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
                base = Path(temporary)
                manager, physical, _manifest, opener = self._public_fixture(base / "first")
                self._check(manager, physical, automatic=True)
                if changed == "physical":
                    physical = base / "second" / ".agents" / "skills"
                    self._skill(physical, "alpha", "installed")
                    usage = physical
                else:
                    usage = base / "usage"
                    usage.mkdir()
                result = self._check(manager, physical, usage=usage, automatic=True)
                self.assertFalse(result["cached"])
                self.assertEqual(2, opener.call_count)
                state = self.updater.load_state(manager.state_file)
                self.assertEqual(str(physical), state["installation_root"])
                self.assertEqual(str(usage), state["cache_context"]["usage_root"])

    def test_automatic_missing_future_or_invalid_check_time_never_uses_cache(self) -> None:
        for checked_at in (None, "2026-11-07T00:00:00Z", "invalid"):
            with self.subTest(checked_at=checked_at), tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
                manager, physical, _manifest, opener = self._public_fixture(Path(temporary))
                manager.now = lambda: datetime(2026, 11, 6, tzinfo=timezone.utc)
                self._check(manager, physical)
                state = self.updater.load_state(manager.state_file)
                state["last_check_at"] = checked_at
                self.updater.save_state(manager.state_file, state)
                if checked_at == "invalid":
                    with self.assertRaisesRegex(self.updater.UpdateError, "last_check_at"):
                        self._check(manager, physical, automatic=True)
                    self.assertEqual(1, opener.call_count)
                else:
                    self.assertFalse(self._check(manager, physical, automatic=True)["cached"])
                    self.assertEqual(2, opener.call_count)

    def test_automatic_cached_snapshot_does_not_bypass_apply_content_protection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, _opener = self._public_fixture(Path(temporary))
            self._check(manager, physical, automatic=True)
            (physical / "alpha" / "SKILL.md").write_text("local edit", encoding="utf-8")
            cached = self._check(manager, physical, automatic=True)
            self.assertTrue(cached["cached"])
            with mock.patch.object(self.updater.Path, "home", return_value=physical.parent.parent), mock.patch.object(
                self.updater, "_run", side_effect=AssertionError("local changes must not install")
            ):
                result = manager._apply_public(physical, manifest["snapshot_id"])
            self.assertEqual("attention", result["status"])
            self.assertEqual("local content differs from the installation baseline", result["blocked"]["alpha"])

    def test_automatic_cli_dispatch_and_network_error_have_no_cache_deadline(self) -> None:
        with mock.patch.object(self.updater.UpdateManager, "check", return_value={"status": "up_to_date"}) as check, \
            mock.patch("builtins.print"):
            self.assertEqual(0, self.updater.main(["check", "--automatic", "--json"]))
        check.assert_called_once_with(force=False, automatic=True)
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, _manifest, opener = self._public_fixture(Path(temporary))
            opener.side_effect = URLError("offline")
            result = self._check(manager, physical, automatic=True)
            self.assertEqual("error", result["status"])
            self.assertNotIn("next_check_at", result)
            self.assertFalse(result["cached"])

    def test_network_failure_is_recorded_and_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, opener = self._public_fixture(Path(temporary))
            opener.side_effect = URLError("offline")
            payload = self._check(manager, physical)
            self.assertEqual("error", payload["status"])
            self.assertTrue(payload["non_blocking"])
            saved = self.updater.load_state(manager.state_file)
            self.assertIn("offline", saved["failure_summary"])
            self.assertIsNone(saved["last_check_at"])
            opener.side_effect = lambda *_args, **_kwargs: Response(manifest)
            recovered = self._check(manager, physical)
            self.assertEqual("up_to_date", recovered["status"])
            self.assertFalse(recovered["cached"])
            self.assertEqual(2, opener.call_count)

    def test_failed_forced_check_does_not_extend_previous_success_or_hide_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, opener = self._public_fixture(Path(temporary))
            first = self._check(manager, physical)
            opener.side_effect = URLError("offline")
            self.assertEqual("error", self._check(manager, physical, force=True)["status"])
            state = self.updater.load_state(manager.state_file)
            self.assertEqual(first["checked_at"], state["last_check_at"])
            self.assertIsNone(state["check_result"])
            opener.side_effect = lambda *_args, **_kwargs: Response(manifest)
            self.assertFalse(self._check(manager, physical)["cached"])
            self.assertEqual(3, opener.call_count)

    def test_real_cli_source_path_only(self) -> None:
        entry = self._locks("alpha")["alpha"]
        self.assertTrue(self.updater._source_is_public(entry, "alpha"))
        for path in ("alpha", "other/alpha/SKILL.md", "alpha/SKILL.md/", "../alpha/SKILL.md"):
            self.assertFalse(self.updater._source_is_public({**entry, "skillPath": path}, "alpha"))
        self.assertFalse(self.updater._source_is_public({**entry, "source": "other/repo"}, "alpha"))

    def test_declining_update_keeps_checks_and_never_runs_installer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, opener = self._public_fixture(Path(temporary))
            first = self._check(manager, physical)
            manifest["skills"]["alpha"]["content_sha256"] = "a" * 64
            with mock.patch.object(self.updater, "_run", side_effect=AssertionError("must not install")):
                preference = manager.preference("check-only", authorized=True)
                manager.now = lambda: self.updater._parse_time(first["checked_at"]) + timedelta(hours=24)
                result = self._check(manager, physical)
            self.assertEqual("check-only", preference["update_preference"])
            self.assertEqual("update_available", result["status"])
            self.assertEqual("report", result["notification"])
            self.assertEqual(2, opener.call_count)
            self.assertEqual("installed", (physical / "alpha" / "SKILL.md").read_text(encoding="utf-8"))
            manager.preference("ask", authorized=True)
            self.assertEqual("ask", self._check(manager, physical, force=True)["notification"])

    def test_preference_requires_authorization_and_cli_dispatches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, _physical, _manifest, _opener = self._public_fixture(Path(temporary))
            with self.assertRaisesRegex(self.updater.UpdateError, "authorized"):
                manager.preference("check-only", authorized=False)
            self.assertFalse(manager.state_file.exists())
            with self.assertRaisesRegex(self.updater.UpdateError, "mode"):
                manager.preference("later", authorized=True)
        with mock.patch.object(self.updater.UpdateManager, "preference", return_value={"status": "preference_saved"}) as preference, mock.patch("builtins.print"):
            self.assertEqual(0, self.updater.main(["preference", "--mode", "check-only", "--authorized", "--json"]))
        preference.assert_called_once_with("check-only", authorized=True)

    def test_installation_changes_invalidate_cache_and_keep_valid_same_root_baselines(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, _manifest, opener = self._public_fixture(Path(temporary))
            self._check(manager, physical)
            baseline = self.updater.load_state(manager.state_file)["installation_baselines"]["alpha"]
            manager.lock_entries["other"] = self._locks("other")["other"]
            self.assertFalse(self._check(manager, physical)["cached"])
            usage = Path(temporary) / "usage"
            usage.mkdir()
            self.assertFalse(self._check(manager, physical, usage=usage)["cached"])
            (physical / "alpha" / "SKILL.md").write_text("locally changed", encoding="utf-8")
            changed = self._check(manager, physical, usage=usage)
            self.assertFalse(changed["cached"])
            self.assertEqual("attention", changed["status"])
            self.assertEqual("report", changed["notification"])
            self.assertEqual(baseline, self.updater.load_state(manager.state_file)["installation_baselines"]["alpha"])
            self.assertEqual(4, opener.call_count)

    def test_noncanonical_install_is_rejected_before_network(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, _manifest, opener = self._public_fixture(Path(temporary))
            custom = Path(temporary) / "custom"
            custom.mkdir()
            with mock.patch.object(self.updater, "load_settings", return_value=(custom, custom)), mock.patch.object(
                self.updater, "_git_root", return_value=None
            ), mock.patch.object(self.updater.Path, "home", return_value=physical.parent.parent):
                result = manager.check()
            self.assertEqual("error", result["status"])
            self.assertIn("canonical", result["error"])
            opener.assert_not_called()

    def test_damaged_state_is_reported_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, _manifest, _opener = self._public_fixture(Path(temporary))
            manager.state_file.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(self.updater.UpdateError, "cannot be read"):
                self._check(manager, physical)
            self.assertEqual("{", manager.state_file.read_text(encoding="utf-8"))
            with mock.patch.object(self.updater, "state_path", return_value=manager.state_file), mock.patch("builtins.print") as output:
                self.assertEqual(1, self.updater.main(["check", "--json"]))
            self.assertEqual("error", json.loads(output.call_args.args[0])["status"])

    def test_cached_result_shape_and_installer_lock_fail_explicitly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, _manifest, _opener = self._public_fixture(Path(temporary))
            self._check(manager, physical)
            state = self.updater.load_state(manager.state_file)
            del state["check_result"]["updates"]
            self.updater.save_state(manager.state_file, state)
            with self.assertRaisesRegex(self.updater.UpdateError, "change lists"):
                self.updater.load_state(manager.state_file)
            lock_path = physical.parent / ".skill-lock.json"
            lock_path.write_text("{", encoding="utf-8")
            with mock.patch.object(self.updater.Path, "home", return_value=physical.parent.parent):
                with self.assertRaisesRegex(self.updater.UpdateError, "installer lock"):
                    self.updater._lock_entries()

    def test_distinct_installation_does_not_reuse_other_roots_baseline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            base = Path(temporary)
            manager, physical, manifest, _opener = self._public_fixture(base / "first")
            self._check(manager, physical)
            second = base / "second" / ".agents" / "skills"
            self._skill(second, "alpha", "installed")
            manifest["skills"]["alpha"]["content_sha256"] = "a" * 64
            manager.preference("check-only", authorized=True)
            result = self._check(manager, second)
            self.assertEqual("installation baseline is missing", result["blocked"]["alpha"])
            self.assertEqual("check-only", result["update_preference"])
            self.assertFalse(result["cached"])

    def test_unbound_baseline_requires_current_content_reverification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, _opener = self._public_fixture(Path(temporary))
            state = self.updater._empty_state()
            state["installation_baselines"]["alpha"] = self.updater.content_hash(physical / "alpha")
            self.updater.save_state(manager.state_file, state)
            original = manifest["skills"]["alpha"]["content_sha256"]
            manifest["skills"]["alpha"]["content_sha256"] = "a" * 64
            result = self._check(manager, physical)
            self.assertEqual("installation baseline is missing", result["blocked"]["alpha"])
            self.assertEqual({}, self.updater.load_state(manager.state_file)["installation_baselines"])
            manifest["skills"]["alpha"]["content_sha256"] = original
            self.assertEqual("up_to_date", self._check(manager, physical, force=True)["status"])
            self.assertEqual(original, self.updater.load_state(manager.state_file)["installation_baselines"]["alpha"])

    def test_git_cache_tracks_local_identity_and_never_prompts_for_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            root = Path(temporary)
            manager = self.updater.UpdateManager(SKILL_ROOT, state_file=root / "state.json")
            values = {
                ("rev-parse", "HEAD"): "local", ("branch", "--show-current"): "main",
                ("rev-parse", "--abbrev-ref", "@{upstream}"): "origin/main",
                ("remote", "-v"): "origin https://example.com/repo.git",
                ("status", "--porcelain=v1"): "",
            }
            result = {"schema_version": 1, "mode": "git", "status": "update_available", "update_id": "remote", "dirty": False, "changed_paths": ["alpha/SKILL.md"]}
            with mock.patch.object(self.updater, "load_settings", return_value=(root, root)), mock.patch.object(
                self.updater, "_git_root", return_value=root
            ), mock.patch.object(self.updater, "_git_value", side_effect=lambda _root, *args: values[args]), mock.patch.object(
                self.updater, "git_check", side_effect=lambda _root: dict(result)
            ) as check:
                self.assertEqual("ask", manager.check()["notification"])
                self.assertTrue(manager.check()["cached"])
                for arguments, value in (
                    (("rev-parse", "HEAD"), "new-head"),
                    (("remote", "-v"), "origin https://example.com/other.git"),
                    (("branch", "--show-current"), "other-branch"),
                    (("rev-parse", "--abbrev-ref", "@{upstream}"), "origin/other-branch"),
                ):
                    values[arguments] = value
                    self.assertFalse(manager.check()["cached"])
                values[("status", "--porcelain=v1")] = " M alpha/SKILL.md"
                result["dirty"] = True
                dirty = manager.check()
                self.assertEqual("report", dirty["notification"])
                self.assertEqual(6, check.call_count)
            self.assertNotIn("https://example.com", manager.state_file.read_text(encoding="utf-8"))

    def test_blocked_apply_returns_attention_without_invoking_installer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, manifest, _opener = self._public_fixture(Path(temporary))
            manifest["skills"]["alpha"]["content_sha256"] = "a" * 64
            with mock.patch.object(self.updater.Path, "home", return_value=physical.parent.parent), mock.patch.object(
                self.updater, "_run", side_effect=AssertionError("blocked update must not install")
            ):
                result = manager._apply_public(physical, manifest["snapshot_id"])
            self.assertEqual("attention", result["status"])
            self.assertIn("alpha", result["blocked"])

    def test_fresh_install_then_new_release_then_explicit_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            base = Path(temporary)
            manager, physical, manifest, opener = self._public_fixture(base)
            initial = self._check(manager, physical)
            latest = self._skill(base / "latest", "alpha", "new-release")
            manifest["snapshot_id"] = "snapshot-3"
            manifest["skills"]["alpha"]["content_sha256"] = self.updater.content_hash(latest)
            manager.now = lambda: self.updater._parse_time(initial["checked_at"]) + timedelta(hours=24)
            pending = self._check(manager, physical)
            self.assertEqual("ask", pending["notification"])
            manager.preference("check-only", authorized=True)
            commands = []
            def install(command, **_kwargs):
                commands.append(command)
                if command[0] in {"npx", "npx.cmd"}:
                    (physical / "alpha" / "SKILL.md").write_text("new-release", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")
            with mock.patch.object(self.updater.Path, "home", return_value=physical.parent.parent), mock.patch.object(
                self.updater, "load_settings", return_value=(physical, physical)
            ), mock.patch.object(self.updater, "_git_root", return_value=None), mock.patch.object(self.updater, "_run", side_effect=install):
                with self.assertRaisesRegex(self.updater.UpdateError, "authorized"):
                    manager.apply(pending["update_id"], authorized=False)
                self.assertEqual([], commands)
                updated = manager.apply(pending["update_id"], authorized=True)
            self.assertEqual("updated", updated["status"])
            installer = commands[0]
            self.assertEqual("universal", installer[installer.index("--agent") + 1])
            self.assertEqual(1, installer.count("--agent"))
            self.assertIsNone(self.updater.load_state(manager.state_file)["check_result"])
            after = self._check(manager, physical)
            self.assertEqual("up_to_date", after["status"])
            self.assertFalse(after["cached"])
            self.assertEqual("check-only", after["update_preference"])
            self.assertEqual(4, opener.call_count)

    def test_successful_git_apply_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            manager, physical, _manifest, _opener = self._public_fixture(Path(temporary))
            self._check(manager, physical)
            with mock.patch.object(self.updater, "load_settings", return_value=(physical, physical)), mock.patch.object(
                self.updater, "_git_root", return_value=physical
            ), mock.patch.object(manager, "_apply_git", return_value={"status": "updated"}):
                self.assertEqual("updated", manager.apply("remote", authorized=True)["status"])
            self.assertIsNone(self.updater.load_state(manager.state_file)["check_result"])

    def test_public_check_updates_only_clean_managed_installs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            base = Path(temporary)
            installed = base / "installed"
            latest = base / "latest"
            installed.mkdir()
            latest.mkdir()
            alpha = self._skill(installed, "alpha", "old")
            beta = self._skill(installed, "beta", "locally changed")
            self._skill(installed, "unmanaged", "old")
            self._skill(latest, "alpha", "new")
            self._skill(latest, "beta", "remote")
            self._skill(latest, "new-skill", "new")
            self._skill(latest, "unmanaged", "remote")
            state = self.updater._empty_state()
            state["installation_baselines"] = {
                "alpha": self.updater.content_hash(alpha),
                "beta": "0" * 64,
                "retired": "1" * 64,
            }
            result = self.updater.public_check(
                installed,
                self._manifest(latest, ["alpha", "beta", "new-skill", "unmanaged"]),
                state,
                lock_entries=self._locks("alpha", "beta"),
            )
            self.assertEqual(["alpha"], result["updates"])
            self.assertEqual(["new-skill"], result["available"])
            self.assertEqual(["retired"], result["retired"])
            self.assertEqual("local content differs from the installation baseline", result["blocked"]["beta"])
            self.assertEqual(["unmanaged"], result["unmanaged"])

    def test_missing_baseline_blocks_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            base = Path(temporary)
            installed = base / "installed"
            latest = base / "latest"
            installed.mkdir()
            latest.mkdir()
            self._skill(installed, "alpha", "old")
            self._skill(latest, "alpha", "new")
            result = self.updater.public_check(
                installed,
                self._manifest(latest, ["alpha"]),
                self.updater._empty_state(),
                lock_entries=self._locks("alpha"),
            )
            self.assertEqual([], result["updates"])
            self.assertEqual("installation baseline is missing", result["blocked"]["alpha"])

    def test_public_apply_restores_settings_and_marks_self_update(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            fake_home = Path(temporary)
            physical = fake_home / ".agents" / "skills"
            latest = fake_home / "latest"
            physical.mkdir(parents=True)
            latest.mkdir()
            original_settings = b'{\n  "physical_root": "x",\n  "usage_root": "y"\n}\n'
            old = self._skill(physical, "new-skills", "old", settings=original_settings)
            self._skill(latest, "new-skills", "new")
            manifest = self._manifest(latest, ["new-skills"])
            state_file = fake_home / "state.json"
            state = self.updater._empty_state()
            state["installation_baselines"] = {"new-skills": self.updater.content_hash(old)}
            state["installation_root"] = str(physical)
            state["update_preference"] = "check-only"
            self.updater.save_state(state_file, state)
            manager = self.updater.UpdateManager(
                SKILL_ROOT,
                state_file=state_file,
                manifest_opener=lambda *_args, **_kwargs: Response(manifest),
                lock_entries=self._locks("new-skills"),
            )

            def fake_run(command, **_kwargs):
                if command[0] in {"npx", "npx.cmd"}:
                    (physical / "new-skills" / "SKILL.md").write_text("new", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(self.updater.Path, "home", return_value=fake_home), mock.patch.object(
                self.updater, "_run", side_effect=fake_run
            ):
                result = manager._apply_public(physical, "snapshot-2")
            self.assertEqual("updated", result["status"])
            self.assertTrue(result["restart_required"])
            self.assertEqual(original_settings, (physical / "new-skills" / "settings.json").read_bytes())
            saved = self.updater.load_state(state_file)
            self.assertEqual(manifest["skills"]["new-skills"]["content_sha256"], saved["installation_baselines"]["new-skills"])
            self.assertEqual("check-only", saved["update_preference"])
            self.assertIsNone(saved["check_result"])

    def test_public_apply_failure_restores_original_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            fake_home = Path(temporary)
            physical = fake_home / ".agents" / "skills"
            latest = fake_home / "latest"
            physical.mkdir(parents=True)
            latest.mkdir()
            old = self._skill(physical, "alpha", "old")
            self._skill(latest, "alpha", "new")
            manifest = self._manifest(latest, ["alpha"])
            state_file = fake_home / "state.json"
            state = self.updater._empty_state()
            state["installation_baselines"] = {"alpha": self.updater.content_hash(old)}
            state["installation_root"] = str(physical)
            self.updater.save_state(state_file, state)
            manager = self.updater.UpdateManager(
                SKILL_ROOT,
                state_file=state_file,
                manifest_opener=lambda *_args, **_kwargs: Response(manifest),
                lock_entries=self._locks("alpha"),
            )

            def fail_after_mutation(command, **_kwargs):
                if command[0] in {"npx", "npx.cmd"}:
                    (physical / "alpha" / "SKILL.md").write_text("partial", encoding="utf-8")
                    return subprocess.CompletedProcess(command, 1, "", "failed")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(self.updater.Path, "home", return_value=fake_home), mock.patch.object(
                self.updater, "_run", side_effect=fail_after_mutation
            ):
                with self.assertRaises(self.updater.UpdateError):
                    manager._apply_public(physical, "snapshot-2")
            self.assertEqual("old", (physical / "alpha" / "SKILL.md").read_text(encoding="utf-8"))

    def test_public_apply_preserves_local_runtime_directories_and_rolls_back_conflicts(self) -> None:
        for conflict in (False, True):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
                base = Path(temporary)
                manager, physical, manifest, _opener = self._public_fixture(base)
                local_files = {
                    Path("tools/local/environment.json"): b'{"runtime":"retained"}',
                    Path("test-output/result.json"): b'{"result":"retained"}',
                }
                for relative, data in local_files.items():
                    path = physical / "alpha" / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                self._check(manager, physical)
                before_state = manager.state_file.read_bytes()
                latest = self._skill(base / "latest", "alpha", "new")
                manifest["skills"]["alpha"]["content_sha256"] = self.updater.content_hash(latest)
                def install(command, **_kwargs):
                    if command[0] in {"npx", "npx.cmd"}:
                        target = physical / "alpha"
                        shutil.rmtree(target)
                        shutil.copytree(latest, target)
                        if conflict:
                            destination = target / "tools" / "local"
                            destination.mkdir(parents=True)
                            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, "", "")
                with mock.patch.object(self.updater.Path, "home", return_value=base), mock.patch.object(
                    self.updater, "_run", side_effect=install
                ):
                    if conflict:
                        with self.assertRaisesRegex(self.updater.UpdateError, "conflicts with local runtime"):
                            manager._apply_public(physical, manifest["snapshot_id"])
                    else:
                        self.assertEqual("updated", manager._apply_public(physical, manifest["snapshot_id"])["status"])
                for relative, data in local_files.items():
                    self.assertEqual(data, (physical / "alpha" / relative).read_bytes())
                self.assertEqual("installed" if conflict else "new", (physical / "alpha" / "SKILL.md").read_text(encoding="utf-8"))
                if conflict:
                    self.assertEqual(before_state, manager.state_file.read_bytes())
                    self.assertFalse((physical / "alpha" / "tools" / "local" / "unexpected.json").exists())

    def test_public_apply_rejects_local_reparse_point_before_installing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            base = Path(temporary)
            manager, physical, manifest, _opener = self._public_fixture(base)
            local = physical / "alpha" / "tools" / "local"
            local.mkdir(parents=True)
            self._check(manager, physical)
            manifest["skills"]["alpha"]["content_sha256"] = "a" * 64
            with mock.patch.object(self.updater.Path, "home", return_value=base), mock.patch.object(
                self.updater, "_is_reparse", side_effect=lambda path: path == local
            ), mock.patch.object(self.updater, "_run", side_effect=AssertionError("must not install")):
                with self.assertRaisesRegex(self.updater.UpdateError, "linked local installation"):
                    manager._apply_public(physical, manifest["snapshot_id"])

    def test_git_check_relations_and_dirty_state(self) -> None:
        root = Path("C:/repo")

        def values(_root, *arguments):
            mapping = {
                ("branch", "--show-current"): "master",
                ("rev-parse", "--abbrev-ref", "@{upstream}"): "origin/master",
                ("rev-parse", "HEAD"): "local",
                ("rev-parse", "origin/master"): "remote",
                ("diff", "--name-only", "local..remote"): "new-skills/SKILL.md",
                ("status", "--porcelain=v1"): " M local.txt",
            }
            return mapping[arguments]

        def runs(command, **_kwargs):
            if "fetch" in command:
                return subprocess.CompletedProcess(command, 0, "", "")
            if "merge-base" in command and command[-2:] == ["local", "remote"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 1, "", "")

        with mock.patch.object(self.updater, "_git_value", side_effect=values), mock.patch.object(
            self.updater, "_run", side_effect=runs
        ):
            result = self.updater.git_check(root)
        self.assertEqual("update_available", result["status"])
        self.assertTrue(result["dirty"])
        self.assertEqual(["new-skills/SKILL.md"], result["changed_paths"])

    def test_git_apply_rejects_dirty_or_diverged(self) -> None:
        manager = object.__new__(self.updater.UpdateManager)
        for status in ("diverged", "ahead"):
            with mock.patch.object(
                self.updater,
                "git_check",
                return_value={"update_id": "id", "dirty": False, "status": status},
            ):
                with self.assertRaises(self.updater.UpdateError):
                    manager._apply_git(Path("C:/repo"), "id")
        with mock.patch.object(
            self.updater,
            "git_check",
            return_value={"update_id": "id", "dirty": True, "status": "update_available"},
        ):
            with self.assertRaises(self.updater.UpdateError):
                manager._apply_git(Path("C:/repo"), "id")

    def _retire_fixture(self, base: Path):
        physical = base / ".agents" / "skills"
        physical.mkdir(parents=True)
        replacement = self._skill(physical, "replacement-skill", "replacement", settings=b'{"local":true}\n')
        state_file = base / "state.json"
        state = self.updater._empty_state()
        state.update({"last_check_at": "2026-10-05T00:00:00Z", "extension": {"keep": [1, 2]}})
        state["installation_root"] = str(physical)
        state["installation_baselines"] = {
            "retired-skill": "a" * 64,
            "replacement-skill": self.updater.content_hash(replacement),
            "other": "b" * 64,
        }
        self.updater.save_state(state_file, state)
        lock_path = base / ".agents" / ".skill-lock.json"
        lock = {"version": 3, "skills": self._locks("retired-skill", "replacement-skill"), "lastSelectedAgents": ["codex"], "extension": {"keep": True}}
        lock["skills"]["other"] = {"source": "another/repository", "custom": [3]}
        self.updater.save_state(lock_path, lock)
        manifest = self._manifest(physical, ["replacement-skill"])
        manager = self.updater.UpdateManager(SKILL_ROOT, state_file=state_file, manifest_opener=lambda *_args, **_kwargs: Response(manifest))
        return manager, physical, state_file, lock_path, manifest

    def _retire(self, manager, physical, **kwargs):
        arguments = {"old_skill": "retired-skill", "replacement_skill": "replacement-skill", "expected_update_id": "snapshot-2", "authorized": True}
        arguments.update(kwargs)
        with mock.patch.object(self.updater.Path, "home", return_value=physical.parent.parent), mock.patch.object(
            self.updater, "load_settings", return_value=(physical, physical)
        ), mock.patch.object(self.updater, "_run", side_effect=AssertionError("retire must not run Git or an installer")):
            return manager.retire(**arguments)

    def test_retire_preserves_unrelated_metadata_and_content_then_repeats_without_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
            original_state = json.loads(state_file.read_text(encoding="utf-8"))
            original_lock = json.loads(lock_path.read_text(encoding="utf-8"))
            replacement_before = {path.name: path.read_bytes() for path in (physical / "replacement-skill").iterdir()}
            result = self._retire(manager, physical)
            self.assertEqual("retired", result["status"])
            del original_state["installation_baselines"]["retired-skill"]
            del original_lock["skills"]["retired-skill"]
            self.assertEqual(original_state, json.loads(state_file.read_text(encoding="utf-8")))
            self.assertEqual(original_lock, json.loads(lock_path.read_text(encoding="utf-8")))
            self.assertEqual(replacement_before, {path.name: path.read_bytes() for path in (physical / "replacement-skill").iterdir()})
            before = (state_file.read_bytes(), lock_path.read_bytes())
            with mock.patch.object(self.updater, "save_state", side_effect=AssertionError("repeat must not write")):
                self.assertEqual("no_changes", self._retire(manager, physical)["status"])
            self.assertEqual(before, (state_file.read_bytes(), lock_path.read_bytes()))

    def test_retire_requires_authorization_and_explicit_distinct_valid_names(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, _state_file, _lock_path, _manifest = self._retire_fixture(Path(temporary))
            with mock.patch.object(self.updater, "fetch_manifest", side_effect=AssertionError("invalid request must not fetch")):
                for arguments in (
                    {"authorized": False}, {"old_skill": "../retired-skill"},
                    {"replacement_skill": "Replacement"}, {"old_skill": ""},
                    {"old_skill": "replacement-skill"}, {"replacement_skill": "a" * 65},
                ):
                    with self.subTest(arguments=arguments), self.assertRaises(self.updater.UpdateError):
                        self._retire(manager, physical, **arguments)

    def test_retire_invalidates_the_cached_check_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, state_file, _lock_path, manifest = self._retire_fixture(Path(temporary))
            state = self.updater.load_state(state_file)
            state["cache_context"] = {"mode": "public", "physical_root": str(physical), "usage_root": str(physical)}
            state["check_result"] = self.updater.public_check(
                physical, manifest, state, lock_entries=self._locks("replacement-skill")
            )
            self.updater.save_state(state_file, state)
            self.assertEqual("retired", self._retire(manager, physical)["status"])
            self.assertIsNone(self.updater.load_state(state_file)["check_result"])

    def test_retire_rejects_existing_old_directory_broken_link_and_unknown_absence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
            before = (state_file.read_bytes(), lock_path.read_bytes())
            old = physical / "retired-skill"
            old.mkdir()
            with self.assertRaisesRegex(self.updater.UpdateError, "still exists"):
                self._retire(manager, physical)
            old.rmdir()
            real_lstat = self.updater.Path.lstat
            for failure in (PermissionError("denied"), None):
                def lstat(path, *, _failure=failure):
                    if path == old:
                        if _failure is not None:
                            raise _failure
                        # A broken link has lstat metadata even though is_dir/exists are false.
                        return mock.Mock(st_mode=0o120777)
                    return real_lstat(path)
                with self.subTest(failure=failure), mock.patch.object(self.updater.Path, "lstat", lstat):
                    with self.assertRaises(self.updater.UpdateError):
                        self._retire(manager, physical)
            self.assertEqual(before, (state_file.read_bytes(), lock_path.read_bytes()))

    def test_retire_rejects_an_old_usage_entry_and_noncanonical_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            base = Path(temporary)
            manager, physical, _state_file, _lock_path, _manifest = self._retire_fixture(base)
            usage = base / "usage"
            usage.mkdir()
            (usage / "retired-skill").write_text("conflicting entry", encoding="utf-8")
            with mock.patch.object(self.updater.Path, "home", return_value=base), mock.patch.object(
                self.updater, "load_settings", return_value=(physical, usage)
            ):
                with self.assertRaisesRegex(self.updater.UpdateError, "still exists"):
                    manager.retire("retired-skill", "replacement-skill", "snapshot-2", authorized=True)
            with mock.patch.object(self.updater.Path, "home", return_value=base), mock.patch.object(
                self.updater, "load_settings", return_value=(usage, usage)
            ):
                with self.assertRaisesRegex(self.updater.UpdateError, "canonical"):
                    manager.retire("retired-skill", "replacement-skill", "snapshot-2", authorized=True)

    def test_retire_rejects_changed_snapshot_membership_sources_or_baselines(self) -> None:
        mutations = ("snapshot", "old_present", "new_missing", "new_source", "old_source", "new_baseline", "old_baseline", "unbound_state", "local_change", "new_link")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
                manager, physical, state_file, lock_path, manifest = self._retire_fixture(Path(temporary))
                state = json.loads(state_file.read_text(encoding="utf-8"))
                lock = json.loads(lock_path.read_text(encoding="utf-8"))
                if mutation == "snapshot":
                    manifest["snapshot_id"] = "snapshot-3"
                elif mutation == "old_present":
                    manifest["skills"]["retired-skill"] = {"path": "retired-skill", "content_sha256": "a" * 64}
                elif mutation == "new_missing":
                    manifest["skills"].clear()
                elif mutation in {"new_source", "old_source"}:
                    name = "replacement-skill" if mutation == "new_source" else "retired-skill"
                    lock["skills"][name]["source"] = "another/repository"
                    self.updater.save_state(lock_path, lock)
                elif mutation in {"new_baseline", "old_baseline"}:
                    name = "replacement-skill" if mutation == "new_baseline" else "retired-skill"
                    del state["installation_baselines"][name]
                    self.updater.save_state(state_file, state)
                elif mutation == "unbound_state":
                    del state["installation_root"]
                    self.updater.save_state(state_file, state)
                elif mutation == "local_change":
                    (physical / "replacement-skill" / "SKILL.md").write_text("local edits", encoding="utf-8")
                before = (state_file.read_bytes(), lock_path.read_bytes())
                with mock.patch.object(self.updater, "_is_reparse", wraps=self.updater._is_reparse) as reparse:
                    if mutation == "new_link":
                        reparse.side_effect = lambda path: path == physical / "replacement-skill"
                    with self.assertRaises(self.updater.UpdateError):
                        self._retire(manager, physical)
                self.assertEqual(before, (state_file.read_bytes(), lock_path.read_bytes()))

    def test_retire_rejects_unreadable_or_invalid_metadata_instead_of_using_empty_records(self) -> None:
        for target, payload in (("lock", b"{"), ("lock", b'{"version":2,"skills":{}}'), ("state", b"{"), ("state", b'{"schema_version":1,"installation_baselines":[]}')):
            with self.subTest(target=target, payload=payload), tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
                manager, physical, state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
                (lock_path if target == "lock" else state_file).write_bytes(payload)
                with mock.patch.object(self.updater, "save_state", side_effect=AssertionError("invalid metadata must not write")):
                    with self.assertRaises(self.updater.UpdateError):
                        self._retire(manager, physical)
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, _state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
            real_read = self.updater.Path.read_text
            def read(path, *args, **kwargs):
                if path == lock_path:
                    raise PermissionError("denied")
                return real_read(path, *args, **kwargs)
            with mock.patch.object(self.updater.Path, "read_text", read):
                with self.assertRaisesRegex(self.updater.UpdateError, "cannot be read"):
                    self._retire(manager, physical)

    def test_retire_with_already_removed_old_lock_only_updates_the_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, _state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            del lock["skills"]["retired-skill"]
            self.updater.save_state(lock_path, lock)
            before = lock_path.read_bytes()
            self.assertEqual("retired", self._retire(manager, physical)["status"])
            self.assertEqual(before, lock_path.read_bytes())

    def test_retire_repeat_still_verifies_the_replacement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
            self._retire(manager, physical)
            before = (state_file.read_bytes(), lock_path.read_bytes())
            (physical / "replacement-skill" / "SKILL.md").write_text("local edits after retirement", encoding="utf-8")
            with self.assertRaisesRegex(self.updater.UpdateError, "must match"):
                self._retire(manager, physical)
            self.assertEqual(before, (state_file.read_bytes(), lock_path.read_bytes()))

    def test_retire_restores_lock_and_state_when_state_write_fails_before_or_after_replace(self) -> None:
        for after_replace in (False, True):
            with self.subTest(after_replace=after_replace), tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
                manager, physical, state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
                before = (json.loads(state_file.read_text(encoding="utf-8")), json.loads(lock_path.read_text(encoding="utf-8")))
                real_save = self.updater.save_state
                failed = False
                def save(path, payload):
                    nonlocal failed
                    if path == state_file and not failed:
                        failed = True
                        if after_replace:
                            real_save(path, payload)
                        raise OSError("write failed")
                    real_save(path, payload)
                with mock.patch.object(self.updater, "save_state", side_effect=save):
                    with self.assertRaisesRegex(self.updater.UpdateError, "original records restored"):
                        self._retire(manager, physical)
                self.assertEqual(before, (json.loads(state_file.read_text(encoding="utf-8")), json.loads(lock_path.read_text(encoding="utf-8"))))

    def test_retire_reports_unknown_when_lock_restoration_cannot_be_verified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
            real_save = self.updater.save_state
            def save(path, payload):
                if path == state_file or (path == lock_path and "retired-skill" in payload["skills"]):
                    raise OSError("write denied")
                real_save(path, payload)
            with mock.patch.object(self.updater, "save_state", side_effect=save):
                with self.assertRaisesRegex(self.updater.UpdateError, "retirement_metadata_state_unknown"):
                    self._retire(manager, physical)

    def test_retire_does_not_overwrite_unexpected_metadata_during_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retire-test-") as temporary:
            manager, physical, state_file, lock_path, _manifest = self._retire_fixture(Path(temporary))
            state_before = state_file.read_bytes()
            real_save = self.updater.save_state
            unexpected = None
            def save(path, payload):
                nonlocal unexpected
                unexpected = {**payload, "unexpected_writer": True}
                real_save(path, unexpected)
                raise OSError("write outcome uncertain")
            with mock.patch.object(self.updater, "save_state", side_effect=save) as writer:
                with self.assertRaisesRegex(self.updater.UpdateError, "retirement_metadata_state_unknown"):
                    self._retire(manager, physical)
            self.assertEqual(1, writer.call_count)
            self.assertEqual(unexpected, json.loads(lock_path.read_text(encoding="utf-8")))
            self.assertEqual(state_before, state_file.read_bytes())

    def test_retire_cli_requires_explicit_names_snapshot_and_authorization(self) -> None:
        parser = self.updater._parser()
        args = parser.parse_args(["retire", "--old-skill", "retired-skill", "--replacement-skill", "replacement-skill", "--expected-update-id", "snapshot-2", "--authorized", "--json"])
        self.assertEqual("retire", args.command)
        self.assertTrue(args.authorized)
        with mock.patch.object(self.updater.UpdateManager, "retire", return_value={"status": "retired"}) as retire, mock.patch("builtins.print"):
            self.assertEqual(0, self.updater.main(["retire", "--old-skill", "retired-skill", "--replacement-skill", "replacement-skill", "--expected-update-id", "snapshot-2", "--authorized", "--json"]))
        retire.assert_called_once_with("retired-skill", "replacement-skill", "snapshot-2", authorized=True)


if __name__ == "__main__":
    unittest.main()
