"""`new-skills` 更新检查,覆盖保护和回滚行为回归测试."""

from __future__ import annotations

import importlib.util
import json
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
                "skillPath": name,
            }
            for name in names
        }

    def test_ttl_skips_and_force_bypasses(self) -> None:
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            base = Path(temporary)
            state_path = base / "state.json"
            state = self.updater._empty_state()
            state["last_check_at"] = (now - timedelta(hours=1)).isoformat()
            state["public_snapshot_id"] = "cached"
            self.updater.save_state(state_path, state)
            manager = self.updater.UpdateManager(
                SKILL_ROOT,
                state_file=state_path,
                now=lambda: now,
                manifest_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
            )
            skipped = manager.check()
            self.assertEqual("ttl_skipped", skipped["status"])
            with mock.patch.object(self.updater, "load_settings", side_effect=self.updater.UpdateError("forced")):
                forced = manager.check(force=True)
            self.assertEqual("error", forced["status"])
            self.assertTrue(forced["non_blocking"])

    def test_network_failure_is_recorded_and_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="update-test-") as temporary:
            base = Path(temporary)
            physical = base / "skills"
            physical.mkdir()
            manager = self.updater.UpdateManager(
                SKILL_ROOT,
                state_file=base / "state.json",
                manifest_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
            )
            with mock.patch.object(self.updater, "load_settings", return_value=(physical, physical)), mock.patch.object(
                self.updater, "_git_root", return_value=None
            ):
                payload = manager.check(force=True)
            self.assertEqual("error", payload["status"])
            self.assertTrue(payload["non_blocking"])
            saved = self.updater.load_state(base / "state.json")
            self.assertIn("offline", saved["failure_summary"])

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


if __name__ == "__main__":
    unittest.main()
