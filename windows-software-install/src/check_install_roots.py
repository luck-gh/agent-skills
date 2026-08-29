#!/usr/bin/env python3
"""对单一架构的 Windows 安装根执行实时安全预检;供安装路径选择门禁使用."""

from __future__ import annotations

import ctypes
import json
import ntpath
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Mapping


MAX_INPUT_BYTES = 16_384
ROOT_KEYS = {"install_x64", "install_x86"}
EVIDENCE_KEYS = {
    "canonical_path",
    "drive_type",
    "is_local",
    "is_subst",
    "online",
    "filesystem",
    "exists",
    "is_directory",
    "ancestor_reparse",
    "forbidden_classes",
}
FORBIDDEN_CLASSES = {
    "cloud_sync",
    "drive_root",
    "profile_tree",
    "skill_tree",
    "source_tree",
    "system_tree",
}


class PreflightError(RuntimeError):
    """Fixed-code failure that never embeds a candidate path."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PreflightError("invalid_input")
        result[key] = value
    return result


def _load_request(raw: bytes) -> dict[str, str]:
    if not raw or len(raw) > MAX_INPUT_BYTES or raw.startswith(b"\xef\xbb\xbf"):
        raise PreflightError("invalid_input")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, PreflightError):
        raise PreflightError("invalid_input") from None
    if not isinstance(value, dict) or len(value) != 1 or not set(value) <= ROOT_KEYS:
        raise PreflightError("invalid_input")
    if any(not isinstance(item, str) for item in value.values()):
        raise PreflightError("invalid_input")
    return value


def _windows_path(value: str) -> str:
    if not value or value.startswith(("\\\\", "//")) or not value.startswith("D:\\"):
        raise PreflightError("unsafe_or_unavailable_path")
    if "/" in value or "\\\\" in value[3:]:
        raise PreflightError("unsafe_or_unavailable_path")
    drive, tail = ntpath.splitdrive(value)
    parts = tail.split("\\")[1:]
    if drive != "D:" or not parts or any(
        not part or part in {".", ".."} or part.endswith((".", " ")) or ":" in part
        for part in parts
    ):
        raise PreflightError("unsafe_or_unavailable_path")
    if ntpath.normpath(value) != value or value == "D:\\":
        raise PreflightError("unsafe_or_unavailable_path")
    return value


def _contains(parent: str, child: str) -> bool:
    parent_key = ntpath.normcase(ntpath.normpath(parent)).rstrip("\\/")
    child_key = ntpath.normcase(ntpath.normpath(child)).rstrip("\\/")
    try:
        return ntpath.commonpath([parent_key, child_key]) == parent_key
    except ValueError:
        return False


def _is_subst_device(value: str) -> bool:
    return bool(re.match(r"^\\\?\?\\[A-Za-z]:\\", value))


def _validate_evidence(requested: str, evidence: Mapping[str, Any]) -> str:
    if not isinstance(evidence, Mapping) or set(evidence) != EVIDENCE_KEYS:
        raise PreflightError("probe_failed")
    canonical = _windows_path(evidence["canonical_path"])
    boolean_keys = ("is_local", "is_subst", "online", "exists", "is_directory", "ancestor_reparse")
    if any(type(evidence[key]) is not bool for key in boolean_keys):
        raise PreflightError("probe_failed")
    classes = evidence["forbidden_classes"]
    if not isinstance(classes, list) or any(item not in FORBIDDEN_CLASSES for item in classes):
        raise PreflightError("probe_failed")
    if (
        canonical != requested
        or evidence["drive_type"] != "fixed"
        or not evidence["is_local"]
        or evidence["is_subst"]
        or not evidence["online"]
        or not isinstance(evidence["filesystem"], str)
        or evidence["filesystem"].upper() != "NTFS"
        or not evidence["exists"]
        or not evidence["is_directory"]
        or evidence["ancestor_reparse"]
        or classes
    ):
        raise PreflightError("unsafe_or_unavailable_path")
    return canonical


def _check_with_probe(
    roots: Mapping[str, Any],
    probe: Callable[[str], Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(roots, Mapping) or len(roots) != 1 or not set(roots) <= ROOT_KEYS:
        raise PreflightError("invalid_input")
    for key in roots:
        if not isinstance(roots[key], str):
            raise PreflightError("invalid_input")
        requested = _windows_path(roots[key])
        try:
            evidence = probe(requested)
        except PreflightError:
            raise
        except Exception:
            raise PreflightError("probe_failed") from None
        _validate_evidence(requested, evidence)
    return {
        "status": "ok",
        "checks": [
            "canonical_d_drive",
            "directory_exists",
            "fixed_local_online_ntfs",
            "no_reparse_ancestor",
            "not_subst",
        ],
        "remaining_requirements": [
            "acl_for_install_context",
            "capacity_for_operation",
            "exact_target_authorization",
        ],
    }


def _classify_path(canonical: str) -> list[str]:
    lowered = {part.casefold() for part in Path(canonical).parts}
    classes: list[str] = []
    if ntpath.normcase(canonical).rstrip("\\") == "d:":
        classes.append("drive_root")
    if lowered & {"onedrive", "dropbox", "baidusyncdisk", "google drive", "icloud drive"}:
        classes.append("cloud_sync")
    skill_root = str(Path(__file__).resolve().parents[1])
    source_root = os.getcwd()
    profile_root = str(Path.home())
    if _contains(skill_root, canonical) or _contains(canonical, skill_root):
        classes.append("skill_tree")
    if _contains(source_root, canonical) or _contains(canonical, source_root):
        classes.append("source_tree")
    if _contains(profile_root, canonical) or _contains(canonical, profile_root):
        classes.append("profile_tree")
    if _contains(r"C:\Windows", canonical) or _contains(canonical, r"C:\Windows"):
        classes.append("system_tree")
    return sorted(set(classes))


def probe_windows_root(path: str) -> Mapping[str, Any]:
    """Probe current Windows volume and directory state without changing it."""

    requested = _windows_path(path)
    if os.name != "nt":
        raise PreflightError("unsupported_environment")
    canonical = os.path.realpath(requested)
    exists = os.path.exists(canonical)
    is_directory = os.path.isdir(canonical)
    ancestor_reparse = False
    if exists:
        for candidate in (Path(canonical), *Path(canonical).parents):
            try:
                info = candidate.lstat()
            except OSError:
                raise PreflightError("probe_failed") from None
            attributes = getattr(info, "st_file_attributes", 0)
            if candidate.is_symlink() or attributes & 0x400:
                ancestor_reparse = True
                break

    drive_root = ntpath.splitdrive(canonical)[0] + "\\"
    drive_type_code = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
    drive_types = {2: "removable", 3: "fixed", 4: "remote", 5: "optical", 6: "ramdisk"}
    filesystem = ""
    fs_buffer = ctypes.create_unicode_buffer(32)
    if ctypes.windll.kernel32.GetVolumeInformationW(
        drive_root, None, 0, None, None, None, fs_buffer, len(fs_buffer)
    ):
        filesystem = fs_buffer.value
    device = ctypes.create_unicode_buffer(1024)
    is_subst = False
    drive = ntpath.splitdrive(canonical)[0]
    if ctypes.windll.kernel32.QueryDosDeviceW(drive, device, len(device)):
        is_subst = _is_subst_device(device.value)
    return {
        "canonical_path": canonical,
        "drive_type": drive_types.get(drive_type_code, "unknown"),
        "is_local": drive_type_code == 3,
        "is_subst": is_subst,
        "online": exists,
        "filesystem": filesystem,
        "exists": exists,
        "is_directory": is_directory,
        "ancestor_reparse": ancestor_reparse,
        "forbidden_classes": _classify_path(canonical),
    }


def _bind(real_probe: Callable[[str], Mapping[str, Any]]) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    def production_check(roots: Mapping[str, Any]) -> dict[str, Any]:
        return _check_with_probe(roots, real_probe)

    production_check.__name__ = "check_install_roots"
    return production_check


check_install_roots = _bind(probe_windows_root)


def _emit(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False))


def main(argv: list[str] | None = None) -> int:
    if (sys.argv[1:] if argv is None else argv):
        _emit({"status": "invalid_preflight_input"})
        return 14
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        result = check_install_roots(_load_request(raw))
    except PreflightError as exc:
        status = "invalid_preflight_input" if str(exc) == "invalid_input" else "preflight_failed"
        _emit({"status": status, "reason": str(exc)})
        return 11 if status == "invalid_preflight_input" else 12
    except Exception:
        _emit({"status": "preflight_failed", "reason": "probe_failed"})
        return 12
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
