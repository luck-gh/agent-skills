from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path
SKILL_ROOT = Path(__file__).resolve().parents[1]
def load_script(module_name: str, relative_path: str):
    path = SKILL_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
install_roots = load_script("validation_install_roots", "src/check_install_roots.py")
class WindowsInstallRootTests(unittest.TestCase):
    def test_root_preflight_accepts_only_one_verified_d_drive_root(self) -> None:
        def probe(path):
            return {"canonical_path": path, "drive_type": "fixed", "is_local": True,
                "is_subst": False, "online": True, "filesystem": "NTFS", "exists": True,
                "is_directory": True, "ancestor_reparse": False, "forbidden_classes": []}
        for roots in ({"install_x64": r"D:\Programs\x64"}, {"install_x86": r"D:\Programs\x86"}):
            with self.subTest(roots=roots):
                self.assertEqual("ok", install_roots._check_with_probe(roots, probe)["status"])
        for bad in ({}, {"install_x64": r"D:\Programs\x64", "install_x86": r"D:\Programs\x86"},
                    {"install_x64": r"C:\Programs\x64"}):
            with self.subTest(bad=bad), self.assertRaises(install_roots.PreflightError):
                install_roots._check_with_probe(bad, probe)
        roots = {"install_x64": r"D:\Programs\x64"}
        with self.assertRaises(install_roots.PreflightError):
            install_roots._check_with_probe(roots, lambda path: {**probe(path), "is_subst": True})

if __name__ == "__main__":
    unittest.main()
