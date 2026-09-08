"""验证初始化探测的分支隔离和失败报告,不安装依赖或扫描用户工程.

运行: python -B -m unittest discover -s tests -p test_check_analysis_env.py
真实外部解析器检查仅在明确选定的验收环境里由 CLI 执行.
"""

import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
import zipfile


ENTRY = Path(__file__).resolve().parents[1] / "scripts" / "check_analysis_env.py"
SPEC = importlib.util.spec_from_file_location("analysis_env", ENTRY)
env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(env)


class BundledWheelTests(unittest.TestCase):
    def test_bundled_files_match_locked_artifacts(self):
        wheel_dir = env.LOCK_ROOT / "wheels"
        expected_files = set()
        for line in (env.LOCK_ROOT / "markdown-win-cp312.txt").read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            package, digest = line.split()
            name, version = package.split("==")
            filename = f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
            expected_files.add(filename)
            self.assertEqual(hashlib.sha256((wheel_dir / filename).read_bytes()).hexdigest(), digest.removeprefix("--hash=sha256:"))
        self.assertEqual({p.name for p in wheel_dir.iterdir()}, expected_files)

    def test_original_licenses_are_preserved_in_archives(self):
        required = {
            "markdown_it_py-4.0.0-py3-none-any.whl": (
                "markdown_it_py-4.0.0.dist-info/licenses/LICENSE",
                "markdown_it_py-4.0.0.dist-info/licenses/LICENSE.markdown-it",
            ),
            "mdurl-0.1.2-py3-none-any.whl": ("mdurl-0.1.2.dist-info/LICENSE",),
        }
        for filename, entries in required.items():
            with zipfile.ZipFile(env.LOCK_ROOT / "wheels" / filename) as archive:
                for entry in entries:
                    content = archive.read(entry).decode("utf-8")
                    self.assertIn("Copyright", content)
                    self.assertIn("Permission is hereby granted", content)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        for target, value in (("platform", "win32"), ("version_info", (3, 12, 4))):
            guard = patch.object(env.sys, target, value)
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(env.platform, "machine", return_value="AMD64")
        guard.start()
        self.addCleanup(guard.stop)

    def test_python_does_not_query_third_party_packages(self):
        with patch.object(env.importlib.metadata, "version", side_effect=AssertionError("package lookup")):
            passed, message = env.check_profile("python")
        self.assertTrue(passed, message)
        self.assertIn("entry", message)

    def test_missing_dependency_is_not_ready(self):
        with patch.object(env.importlib.metadata, "version", side_effect=importlib.metadata.PackageNotFoundError("libclang")):
            passed, message = env.check_profile("c")
        self.assertFalse(passed)
        self.assertIn("MISSING_DEPENDENCY", message)

    def test_version_mismatch_does_not_load_parser(self):
        with patch.object(env.importlib.metadata, "version", return_value="0.0"), patch.dict(env.CHECKS, c=lambda: self.fail("parser loaded")):
            passed, message = env.check_profile("c")
        self.assertFalse(passed)
        self.assertIn("VERSION_MISMATCH", message)

    def test_loader_failure_is_not_ready(self):
        def broken():
            raise OSError("DLL load failed")

        with patch.object(env.importlib.metadata, "version", return_value="18.1.1"), patch.dict(env.CHECKS, c=broken):
            passed, message = env.check_profile("c")
        self.assertFalse(passed)
        self.assertIn("DLL load failed", message)

    def test_wrong_platform_stops_before_package_lookup(self):
        with patch.object(env.sys, "platform", "linux"), patch.object(env.importlib.metadata, "version", side_effect=AssertionError("package lookup")):
            passed, message = env.check_profile("hdl")
        self.assertFalse(passed)
        self.assertIn("UNVERIFIED_PLATFORM", message)

    def test_python_profile_does_not_require_windows(self):
        with patch.object(env.sys, "platform", "linux"):
            passed, message = env.check_profile("python")
        self.assertTrue(passed, message)

    def test_markdown_checks_transitive_package(self):
        with patch.object(env.importlib.metadata, "version", side_effect=["4.0.0", "0.0"]):
            passed, message = env.check_profile("markdown")
        self.assertFalse(passed)
        self.assertIn("mdurl", message)

    def test_only_selected_profiles_are_checked_once(self):
        with patch.object(env, "check_profile", return_value=(True, "ready")) as check, contextlib.redirect_stdout(io.StringIO()):
            code = env.main(["--profile", "python", "--profile", "python"])
        self.assertEqual(code, 0)
        check.assert_called_once_with("python")

    def test_failure_exit_and_other_profile_results_preserved(self):
        output = io.StringIO()
        with patch.object(env, "check_profile", side_effect=[(False, "missing"), (True, "ready")]), contextlib.redirect_stdout(output):
            code = env.main(["--profile", "c", "--profile", "python"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL [c]", output.getvalue())
        self.assertIn("PASS [python]", output.getvalue())

    def test_no_install_or_network_for_python_probe(self):
        with patch.object(socket, "create_connection", side_effect=AssertionError("network")), patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess")), patch.object(Path, "write_text", side_effect=AssertionError("write")):
            passed, message = env.check_profile("python")
        self.assertTrue(passed, message)

    def test_unsupported_profile_is_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            env.main(["--profile", "verilog-a"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
