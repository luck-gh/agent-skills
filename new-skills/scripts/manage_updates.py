"""检查并在明确授权后升级 `new-skills` 管理的 Skill 安装.

公开入口:
  check --json
  check --automatic --json
  check --force --json
  preference --mode ask|check-only --authorized --json
  apply --expected-update-id <id> --authorized --json
  retire --old-skill <old> --replacement-skill <new> --expected-update-id <id> --authorized --json

脚本使用 Python 标准库.它在 Git 真源模式中只允许 fast-forward 更新,在公共
安装模式中按公开 manifest 仅更新已安装且发生变化的 Skill,并提供本地修改保护,
settings 保留,失败回滚和自更新提示.显式 retire 只收尾已完成改名的安装记录,
不推断改名关系,不安装或删除 Skill,也不修改发现入口.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen


SCHEMA_VERSION = 1
PUBLIC_REPOSITORY = "luck-gh/agent-skills"
MANIFEST_URL = "https://raw.githubusercontent.com/luck-gh/agent-skills/main/skills-manifest.json"
INSTALLER_VERSION = "1.5.21"
TTL = timedelta(hours=24)
IGNORED_NAMES = {"settings.json", "__pycache__", ".pytest_cache", ".git", "test-output"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
PRIVATE_RELATIVE_DIRECTORIES = {("tools", "local")}
PRESERVED_LOCAL_DIRECTORIES = (Path("tools/local"), Path("test-output"))


class UpdateError(RuntimeError):
    """表示检查,来源或升级安全契约不成立."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def state_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise UpdateError("LOCALAPPDATA is required for update state")
        return Path(base) / "new-skills" / "update-state.json"
    base = os.environ.get("XDG_STATE_HOME")
    return (Path(base) if base else Path.home() / ".local" / "state") / "new-skills" / "update-state.json"


def _empty_state() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "last_check_at": None,
        "public_snapshot_id": None,
        "installation_baselines": {},
        "failure_summary": None,
        "installation_root": None,
        "cache_context": None,
        "check_result": None,
        "update_preference": "ask",
    }


def load_state(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty_state()
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdateError(f"update state cannot be read: {path}") from error
    if type(payload) is not dict or payload.get("schema_version") != SCHEMA_VERSION:
        raise UpdateError("update state must use schema_version 1")
    baselines = payload.get("installation_baselines")
    if type(baselines) is not dict or any(
        not isinstance(name, str) or not isinstance(digest, str)
        for name, digest in baselines.items()
    ):
        raise UpdateError("update state has invalid installation baselines")
    clean = _empty_state()
    clean.update(payload)
    if clean["update_preference"] not in ("ask", "check-only"):
        raise UpdateError("update state has an invalid update preference")
    for key in ("cache_context", "check_result"):
        if clean[key] is not None and type(clean[key]) is not dict:
            raise UpdateError(f"update state has an invalid {key}")
    if clean["last_check_at"] is not None and _parse_time(clean["last_check_at"]) is None:
        raise UpdateError("update state has an invalid last_check_at")
    if clean["installation_root"] is not None and not isinstance(clean["installation_root"], str):
        raise UpdateError("update state has an invalid installation_root")
    if clean["check_result"] is not None and clean["check_result"].get("status") not in (
        "up_to_date", "update_available", "attention", "ahead", "diverged"
    ):
        raise UpdateError("update state has an invalid cached check status")
    context = clean["cache_context"]
    if context is not None and (
        context.get("mode") not in ("git", "public")
        or any(not isinstance(context.get(key), str) for key in ("physical_root", "usage_root"))
    ):
        raise UpdateError("update state has an invalid cache context")
    result = clean["check_result"]
    if result is not None:
        if context is None or result.get("mode") != context["mode"] or not isinstance(result.get("update_id"), str):
            raise UpdateError("cached check result does not match its context")
        if result["mode"] == "public" and (
            any(type(result.get(key)) is not list for key in ("updates", "available", "retired", "unmanaged"))
            or type(result.get("blocked")) is not dict
        ):
            raise UpdateError("cached public check is missing its change lists")
        if result["mode"] == "git" and (type(result.get("dirty")) is not bool or type(result.get("changed_paths")) is not list):
            raise UpdateError("cached Git check is missing its worktree result")
    clean["installation_baselines"] = dict(baselines)
    return clean


def save_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix="update-state-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _read_metadata(path: Path) -> dict[str, object]:
    """严格读取待修改的元数据,保留未知字段并拒绝损坏或链接文件."""

    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink() or _is_reparse(path):
            raise UpdateError(f"metadata must be a regular file: {path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdateError(f"metadata cannot be read: {path.name}") from error
    if type(payload) is not dict:
        raise UpdateError(f"metadata must be a JSON object: {path.name}")
    return payload


def _require_absent(path: Path) -> None:
    """仅接受 lstat 明确的缺失,不把断链或权限错误当成已清理."""

    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise UpdateError(f"old skill path absence is unknown: {path}") from error
    raise UpdateError(f"old skill path still exists: {path}")


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def load_settings(skill_root: Path) -> tuple[Path, Path]:
    path = skill_root / "settings.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise UpdateError("new-skills/settings.json is required before update checks") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdateError(f"invalid new-skills/settings.json: {error}") from error
    if type(payload) is not dict or set(payload) != {"physical_root", "usage_root"}:
        raise UpdateError("new-skills/settings.json must contain only physical_root and usage_root")
    roots: list[Path] = []
    for field in ("physical_root", "usage_root"):
        value = payload[field]
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_dir():
            raise UpdateError(f"{field} must be an existing absolute directory")
        roots.append(Path(value).resolve(strict=True))
    return roots[0], roots[1]


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _git_root(physical_root: Path) -> Path | None:
    result = _run(["git", "-C", str(physical_root), "rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        return None
    try:
        root = Path(result.stdout.strip()).resolve(strict=True)
        physical_root.relative_to(root)
    except (OSError, ValueError):
        return None
    return root


def _git_value(root: Path, *arguments: str) -> str:
    result = _run(["git", "-C", str(root), *arguments])
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise UpdateError(detail[:500])
    return result.stdout.strip()


def git_check(root: Path) -> dict[str, object]:
    branch = _git_value(root, "branch", "--show-current")
    if not branch:
        raise UpdateError("detached HEAD is not supported for managed updates")
    upstream = _git_value(root, "rev-parse", "--abbrev-ref", "@{upstream}")
    fetch = _run(["git", "-C", str(root), "fetch", "--quiet"])
    if fetch.returncode != 0:
        raise UpdateError((fetch.stderr.strip() or "git fetch failed")[:500])
    local = _git_value(root, "rev-parse", "HEAD")
    remote = _git_value(root, "rev-parse", upstream)
    if local == remote:
        relation = "up_to_date"
    elif _run(["git", "-C", str(root), "merge-base", "--is-ancestor", local, remote]).returncode == 0:
        relation = "behind"
    elif _run(["git", "-C", str(root), "merge-base", "--is-ancestor", remote, local]).returncode == 0:
        relation = "ahead"
    else:
        relation = "diverged"
    changed = []
    if relation == "behind":
        changed = [line for line in _git_value(root, "diff", "--name-only", f"{local}..{remote}").splitlines() if line]
    dirty = bool(_git_value(root, "status", "--porcelain=v1"))
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "git",
        "status": "update_available" if relation == "behind" else relation,
        "update_id": remote,
        "branch": branch,
        "upstream": upstream,
        "dirty": dirty,
        "changed_paths": changed,
    }


def _is_reparse(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def content_hash(skill_dir: Path) -> str:
    if not skill_dir.is_dir() or skill_dir.is_symlink() or _is_reparse(skill_dir):
        raise UpdateError(f"skill is not a physical directory: {skill_dir.name}")
    files: list[Path] = []
    stack = [skill_dir]
    while stack:
        directory = stack.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            path = Path(entry.path)
            relative = path.relative_to(skill_dir)
            if entry.name in IGNORED_NAMES or path.suffix.lower() in IGNORED_SUFFIXES:
                continue
            if entry.is_dir(follow_symlinks=False) and relative.parts in PRIVATE_RELATIVE_DIRECTORIES:
                continue
            if entry.is_symlink() or _is_reparse(path):
                raise UpdateError(f"linked skill resource is unsupported: {path}")
            if entry.is_dir(follow_symlinks=False):
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.append(path)
            else:
                raise UpdateError(f"non-regular skill resource is unsupported: {path}")
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(skill_dir).as_posix()
        file_digest = hashlib.sha256(path.read_bytes()).digest()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest)
    return digest.hexdigest()


def _remove_tree_object(path: Path) -> None:
    if not os.path.lexists(path):
        return
    if path.is_symlink():
        path.unlink()
    elif _is_reparse(path):
        os.rmdir(path)
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def fetch_manifest(opener: Callable[..., object] = urlopen) -> dict[str, object]:
    request = Request(MANIFEST_URL, headers={"User-Agent": "new-skills-update/1"})
    try:
        with opener(request, timeout=15) as response:
            data = response.read()
        payload = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, URLError) as error:
        raise UpdateError(f"public manifest fetch failed: {error}") from error
    if type(payload) is not dict or payload.get("schema_version") != SCHEMA_VERSION:
        raise UpdateError("public manifest must use schema_version 1")
    if payload.get("repository") != PUBLIC_REPOSITORY:
        raise UpdateError("public manifest repository identity mismatch")
    if not isinstance(payload.get("snapshot_id"), str) or type(payload.get("skills")) is not dict:
        raise UpdateError("public manifest is missing snapshot_id or skills")
    for name, item in payload["skills"].items():
        if not isinstance(name, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None or type(item) is not dict or item.get("path") != name:
            raise UpdateError("public manifest contains an invalid skill entry")
        digest = item.get("content_sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise UpdateError("public manifest contains an invalid content hash")
    return payload


def _lock_entries() -> dict[str, object]:
    path = Path.home() / ".agents" / ".skill-lock.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdateError("installer lock cannot be read") from error
    if type(payload) is not dict or payload.get("version") != 3 or type(payload.get("skills")) is not dict:
        raise UpdateError("installer lock must use version 3 with skills records")
    return payload["skills"]


def _source_is_public(entry: object, name: str) -> bool:
    if type(entry) is not dict or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None:
        return False
    path = entry.get("skillPath")
    return (
        entry.get("sourceType") == "github"
        and str(entry.get("source", "")).lower() == PUBLIC_REPOSITORY.lower()
        and path == f"{name}/SKILL.md"
    )


def public_check(
    physical_root: Path,
    manifest: dict[str, object],
    state: dict[str, object],
    *,
    lock_entries: dict[str, object] | None = None,
) -> dict[str, object]:
    entries = _lock_entries() if lock_entries is None else lock_entries
    baselines = state["installation_baselines"]
    skills = manifest["skills"]
    updates: list[str] = []
    available: list[str] = []
    retired = sorted(name for name in baselines if name not in skills)
    blocked: dict[str, str] = {}
    unmanaged: list[str] = []
    current_hashes: dict[str, str] = {}
    for name in sorted(skills):
        target = physical_root / name
        if not target.is_dir():
            available.append(name)
            continue
        if not _source_is_public(entries.get(name), name):
            unmanaged.append(name)
            continue
        current = content_hash(target)
        latest = skills[name]["content_sha256"]
        current_hashes[name] = current
        baseline = baselines.get(name)
        if current == latest:
            baselines[name] = latest
        elif baseline is None:
            blocked[name] = "installation baseline is missing"
        elif current != baseline:
            blocked[name] = "local content differs from the installation baseline"
        else:
            updates.append(name)
    status = "update_available" if updates else "attention" if blocked or retired or unmanaged else "up_to_date"
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "public",
        "status": status,
        "update_id": manifest["snapshot_id"],
        "updates": updates,
        "available": available,
        "retired": retired,
        "blocked": blocked,
        "unmanaged": unmanaged,
        "current_hashes": current_hashes,
    }


class UpdateManager:
    def __init__(
        self,
        skill_root: Path,
        *,
        state_file: Path | None = None,
        now: Callable[[], datetime] = utc_now,
        manifest_opener: Callable[..., object] = urlopen,
        lock_entries: dict[str, object] | None = None,
    ) -> None:
        self.skill_root = skill_root.resolve(strict=True)
        self.state_file = state_file or state_path()
        self.now = now
        self.manifest_opener = manifest_opener
        self.lock_entries = lock_entries

    def _context(self, physical_root: Path, usage_root: Path, root: Path | None) -> dict[str, object]:
        """读取本地安装身份,使路径,来源或本地内容变化立即使网络缓存失效."""

        context = {"physical_root": str(physical_root), "usage_root": str(usage_root)}
        if root is not None:
            context.update({
                "mode": "git", "git_root": str(root),
                "head": _git_value(root, "rev-parse", "HEAD"),
                "branch": _git_value(root, "branch", "--show-current"),
                "upstream": _git_value(root, "rev-parse", "--abbrev-ref", "@{upstream}"),
                "remotes_sha256": hashlib.sha256(_git_value(root, "remote", "-v").encode("utf-8")).hexdigest(),
                "worktree": _git_value(root, "status", "--porcelain=v1"),
            })
        else:
            canonical = (Path.home() / ".agents" / "skills").resolve(strict=False)
            if physical_root != canonical:
                raise UpdateError(f"public updates require canonical physical_root {canonical}")
            entries = _lock_entries() if self.lock_entries is None else self.lock_entries
            encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
            context.update({
                "mode": "public", "lock_sha256": hashlib.sha256(encoded).hexdigest(),
                "local_hashes": {
                    name: content_hash(physical_root / name)
                    for name, entry in sorted(entries.items())
                    if _source_is_public(entry, name) and (physical_root / name).is_dir()
                },
            })
        return context

    @staticmethod
    def _bind_installation(state: dict[str, object], physical_root: Path, mode: str) -> None:
        """基线属于同一个实体根,不能随 settings 切换到另一份安装."""

        previous = state["installation_root"]
        context = state["cache_context"]
        if previous != str(physical_root) or (context is not None and context["mode"] != mode):
            state["installation_baselines"] = {}
            state["public_snapshot_id"] = None
        state["installation_root"] = str(physical_root)

    @staticmethod
    def _check_output(state: dict[str, object], *, cached: bool, automatic: bool = False) -> dict[str, object]:
        result = state["check_result"]
        attention = result["status"] in {"attention", "ahead", "diverged"} or result.get("dirty", False)
        attention = attention or bool(result.get("blocked") or result.get("unmanaged") or result.get("retired"))
        notification = "none"
        if not cached:
            if attention:
                notification = "report"
            elif result["status"] == "update_available":
                notification = "ask" if state["update_preference"] == "ask" else "report"
        output = {
            **result, "cached": cached, "checked_at": state["last_check_at"],
            "update_preference": state["update_preference"], "notification": notification,
        }
        if automatic:
            output["next_check_at"] = (_parse_time(state["last_check_at"]) + TTL).isoformat().replace("+00:00", "Z")
            if cached:
                return {key: output[key] for key in (
                    "schema_version", "status", "cached", "checked_at", "next_check_at", "notification"
                )}
            if result["mode"] == "public":
                del output["current_hashes"]
        return output

    def check(self, *, force: bool = False, automatic: bool = False) -> dict[str, object]:
        state = load_state(self.state_file)
        current_time = self.now().astimezone(timezone.utc)
        try:
            physical_root, usage_root = load_settings(self.skill_root)
            checked_at = _parse_time(state["last_check_at"])
            cache_in_time = checked_at is not None and timedelta(0) <= current_time - checked_at < TTL
            if (
                automatic and not force and state["check_result"] is not None and cache_in_time
                and state["installation_root"] == str(physical_root)
                and state["cache_context"]["physical_root"] == str(physical_root)
                and state["cache_context"]["usage_root"] == str(usage_root)
            ):
                # 自动调用只复用带时间的快照;不启动 Git,扫描内容或重新读取安装器记录.
                return self._check_output(state, cached=True, automatic=True)
            root = _git_root(physical_root)
            context = self._context(physical_root, usage_root, root)
            if (
                not force and state["check_result"] is not None and context == state["cache_context"]
                and state["installation_root"] == str(physical_root)
                and cache_in_time
            ):
                return self._check_output(state, cached=True, automatic=automatic)
            self._bind_installation(state, physical_root, context["mode"])
            if root is not None:
                result = git_check(root)
            else:
                manifest = fetch_manifest(self.manifest_opener)
                result = public_check(
                    physical_root,
                    manifest,
                    state,
                    lock_entries=self.lock_entries,
                )
                state["public_snapshot_id"] = manifest["snapshot_id"]
        except (UpdateError, OSError) as error:
            state["failure_summary"] = str(error)[:500]
            state["check_result"] = None
            save_state(self.state_file, state)
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "error",
                "error": str(error),
                "non_blocking": True, "cached": False, "notification": "report",
                "checked_at": state["last_check_at"], "update_preference": state["update_preference"],
            }
        state["last_check_at"] = current_time.isoformat().replace("+00:00", "Z")
        state["cache_context"] = context
        state["check_result"] = result
        state["failure_summary"] = None
        save_state(self.state_file, state)
        return self._check_output(state, cached=False, automatic=automatic)

    def preference(self, mode: str, *, authorized: bool) -> dict[str, object]:
        """保存用户明确的询问偏好,不执行网络检查或安装."""

        if not authorized:
            raise UpdateError("preference requires --authorized")
        if mode not in {"ask", "check-only"}:
            raise UpdateError("preference mode must be ask or check-only")
        state = load_state(self.state_file)
        state["update_preference"] = mode
        save_state(self.state_file, state)
        return {"schema_version": SCHEMA_VERSION, "status": "preference_saved", "update_preference": mode}

    def apply(self, expected_update_id: str, *, authorized: bool) -> dict[str, object]:
        if not authorized:
            raise UpdateError("apply requires --authorized")
        physical_root, _ = load_settings(self.skill_root)
        root = _git_root(physical_root)
        if root is not None:
            state = load_state(self.state_file)
            result = self._apply_git(root, expected_update_id)
            if result["status"] == "updated":
                state["check_result"] = None
                save_state(self.state_file, state)
            return result
        return self._apply_public(physical_root, expected_update_id)

    def retire(
        self,
        old_skill: str,
        replacement_skill: str,
        expected_update_id: str,
        *,
        authorized: bool,
    ) -> dict[str, object]:
        """在改名已完成后收尾公开安装记录,不触碰 Skill 内容或链接."""

        if not authorized:
            raise UpdateError("retire requires --authorized")
        for name in (old_skill, replacement_skill):
            if not isinstance(name, str) or len(name) > 64 or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None:
                raise UpdateError("retire requires valid lowercase hyphen-case skill names")
        if old_skill == replacement_skill:
            raise UpdateError("old and replacement skill names must differ")
        physical_root, usage_root = load_settings(self.skill_root)
        canonical = (Path.home() / ".agents" / "skills").resolve(strict=False)
        if physical_root != canonical:
            raise UpdateError(f"public retirement requires canonical physical_root {canonical}")
        for root in dict.fromkeys((physical_root, usage_root)):
            _require_absent(root / old_skill)
        manifest = fetch_manifest(self.manifest_opener)
        if manifest["snapshot_id"] != expected_update_id:
            raise UpdateError("public snapshot changed after check; run check again")
        skills = manifest["skills"]
        if old_skill in skills or replacement_skill not in skills:
            raise UpdateError("public snapshot must retire the old name and contain the replacement")
        state = _read_metadata(self.state_file)
        baselines = state.get("installation_baselines")
        if state.get("installation_root") != str(physical_root):
            raise UpdateError("retirement requires installation baselines bound to the physical root")
        if state.get("schema_version") != SCHEMA_VERSION or type(baselines) is not dict or any(
            not isinstance(name, str) or not isinstance(digest, str) for name, digest in baselines.items()
        ):
            raise UpdateError("retirement requires valid persisted installation baselines")
        lock_path = Path.home() / ".agents" / ".skill-lock.json"
        lock = _read_metadata(lock_path)
        entries = lock.get("skills")
        if lock.get("version") != 3 or type(entries) is not dict:
            raise UpdateError("retirement requires a valid version 3 installer lock")
        if not _source_is_public(entries.get(replacement_skill), replacement_skill):
            raise UpdateError("replacement skill is not managed by the public repository")
        if old_skill in entries and not _source_is_public(entries[old_skill], old_skill):
            raise UpdateError("old skill installer source does not match the public repository")
        try:
            actual = content_hash(physical_root / replacement_skill)
        except OSError as error:
            raise UpdateError("replacement skill content cannot be verified") from error
        if actual != skills[replacement_skill]["content_sha256"] or actual != baselines.get(replacement_skill):
            raise UpdateError("replacement content, public hash and persisted baseline must match")
        result = {
            "schema_version": SCHEMA_VERSION,
            "mode": "public",
            "update_id": manifest["snapshot_id"],
            "old_skill": old_skill,
            "replacement_skill": replacement_skill,
        }
        if old_skill not in baselines:
            if old_skill in entries:
                raise UpdateError("old skill baseline is missing but its installer record remains")
            return {**result, "status": "no_changes"}
        new_state = {
            **state, "check_result": None,
            "installation_baselines": {name: digest for name, digest in baselines.items() if name != old_skill},
        }
        new_lock = {**lock, "skills": {name: entry for name, entry in entries.items() if name != old_skill}}
        changes = []
        if old_skill in entries:
            changes.append((lock_path, lock, new_lock))
        changes.append((self.state_file, state, new_state))
        try:
            for path, original, updated in changes:
                save_state(path, updated)
                if _read_metadata(path) != updated:
                    raise UpdateError("retirement metadata verification failed")
        except Exception as error:
            restored = True
            for path, original, updated in reversed(changes):
                try:
                    current = _read_metadata(path)
                    if current != original:
                        if current != updated:
                            raise UpdateError("retirement metadata has an unexpected value")
                        save_state(path, original)
                    if _read_metadata(path) != original:
                        raise UpdateError("retirement metadata restoration failed")
                except Exception:
                    restored = False
            if not restored:
                raise UpdateError("retirement_metadata_state_unknown; inspect installer lock and update state") from error
            raise UpdateError("retirement metadata update failed; original records restored") from error
        return {**result, "status": "retired"}

    def _apply_git(self, root: Path, expected: str) -> dict[str, object]:
        status = git_check(root)
        if status["update_id"] != expected:
            raise UpdateError("upstream changed after check; run check again")
        if status["dirty"]:
            raise UpdateError("git worktree is dirty")
        if status["status"] == "up_to_date":
            return {**status, "status": "no_changes"}
        if status["status"] != "update_available":
            raise UpdateError(f"git branch is not fast-forwardable: {status['status']}")
        result = _run(["git", "-C", str(root), "pull", "--ff-only"])
        if result.returncode != 0:
            raise UpdateError((result.stderr.strip() or "git pull --ff-only failed")[:500])
        return {**status, "status": "updated", "changed_paths": status["changed_paths"]}

    def _apply_public(self, physical_root: Path, expected: str) -> dict[str, object]:
        canonical = (Path.home() / ".agents" / "skills").resolve(strict=False)
        if physical_root != canonical:
            raise UpdateError(f"public updates require canonical physical_root {canonical}")
        state = load_state(self.state_file)
        self._bind_installation(state, physical_root, "public")
        manifest = fetch_manifest(self.manifest_opener)
        if manifest["snapshot_id"] != expected:
            raise UpdateError("public snapshot changed after check; run check again")
        status = public_check(
            physical_root,
            manifest,
            state,
            lock_entries=self.lock_entries,
        )
        updates = status["updates"]
        if not updates:
            return {**status, "status": "attention" if status["status"] == "attention" else "no_changes"}
        lock_path = Path.home() / ".agents" / ".skill-lock.json"
        npx = "npx.cmd" if os.name == "nt" else "npx"
        with tempfile.TemporaryDirectory(prefix="new-skills-update-") as temporary:
            backup_root = Path(temporary)
            settings: dict[str, bytes] = {}
            settings_absent: set[str] = set()
            for name in updates:
                target = physical_root / name
                # 本机环境也在备份范围内,拒绝链接以免复制到安装根之外.
                pending = [target]
                while pending:
                    directory = pending.pop()
                    for entry in os.scandir(directory):
                        path = Path(entry.path)
                        if entry.is_symlink() or _is_reparse(path):
                            raise UpdateError(f"linked local installation cannot be backed up: {path}")
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(path)
                        elif not entry.is_file(follow_symlinks=False):
                            raise UpdateError(f"non-regular local installation resource: {path}")
                for relative in PRESERVED_LOCAL_DIRECTORIES:
                    local_directory = target / relative
                    if local_directory.exists() and not local_directory.is_dir():
                        raise UpdateError(f"local runtime path must be a directory: {local_directory}")
                shutil.copytree(target, backup_root / name)
                local_settings = target / "settings.json"
                if local_settings.is_file():
                    settings[name] = local_settings.read_bytes()
                else:
                    settings_absent.add(name)
            had_lock = lock_path.is_file()
            if had_lock:
                shutil.copy2(lock_path, backup_root / ".skill-lock.json")
            command = [npx, f"skills@{INSTALLER_VERSION}", "add", PUBLIC_REPOSITORY, "-g", "-y", "--agent", "universal"]
            for name in updates:
                command.extend(["--skill", name])
            result = _run(command)
            try:
                if result.returncode != 0:
                    raise UpdateError((result.stderr.strip() or "skills installer failed")[:500])
                for name in updates:
                    # 先确认新实体与父目录没有链接,再恢复本机文件.
                    if content_hash(physical_root / name) != manifest["skills"][name]["content_sha256"]:
                        raise UpdateError(f"updated content hash mismatch: {name}")
                    local_settings = physical_root / name / "settings.json"
                    if os.path.lexists(local_settings) and (local_settings.is_symlink() or _is_reparse(local_settings)):
                        raise UpdateError(f"updated settings must not be a link: {name}")
                for name, data in settings.items():
                    (physical_root / name / "settings.json").write_bytes(data)
                for name in settings_absent:
                    local_settings = physical_root / name / "settings.json"
                    if local_settings.is_file():
                        local_settings.unlink()
                for name in updates:
                    for relative in PRESERVED_LOCAL_DIRECTORIES:
                        saved = backup_root / name / relative
                        if not saved.is_dir():
                            continue
                        destination = physical_root / name / relative
                        if os.path.lexists(destination):
                            raise UpdateError(f"updated package conflicts with local runtime directory: {name}/{relative.as_posix()}")
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(saved, destination)
                validator = physical_root / "new-skills" / "scripts" / "validate_skill.py"
                validation = _run(
                    [sys.executable, "-X", "utf8", "-B", str(validator), "--json", *[str(physical_root / name) for name in updates]]
                )
                if validation.returncode != 0:
                    raise UpdateError("updated skills failed validation")
                for name in updates:
                    actual = content_hash(physical_root / name)
                    expected_hash = manifest["skills"][name]["content_sha256"]
                    if actual != expected_hash:
                        raise UpdateError(f"updated content hash mismatch: {name}")
                    state["installation_baselines"][name] = actual
            except Exception:
                for name in updates:
                    target = physical_root / name
                    _remove_tree_object(target)
                    shutil.copytree(backup_root / name, target)
                lock_backup = backup_root / ".skill-lock.json"
                if lock_backup.is_file():
                    lock_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(lock_backup, lock_path)
                elif not had_lock and lock_path.is_file():
                    lock_path.unlink()
                raise
        state["public_snapshot_id"] = manifest["snapshot_id"]
        state["failure_summary"] = None
        state["check_result"] = None
        save_state(self.state_file, state)
        return {
            **status,
            "status": "updated",
            "updated": updates,
            "restart_required": "new-skills" in updates,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("--force", action="store_true")
    check.add_argument("--automatic", action="store_true")
    check.add_argument("--json", action="store_true", required=True)
    preference = commands.add_parser("preference")
    preference.add_argument("--mode", choices=("ask", "check-only"), required=True)
    preference.add_argument("--authorized", action="store_true", required=True)
    preference.add_argument("--json", action="store_true", required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("--expected-update-id", required=True)
    apply.add_argument("--authorized", action="store_true", required=True)
    apply.add_argument("--json", action="store_true", required=True)
    retire = commands.add_parser("retire")
    retire.add_argument("--old-skill", required=True)
    retire.add_argument("--replacement-skill", required=True)
    retire.add_argument("--expected-update-id", required=True)
    retire.add_argument("--authorized", action="store_true", required=True)
    retire.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manager = UpdateManager(Path(__file__).resolve().parents[1])
    try:
        if args.command == "check":
            payload = manager.check(force=args.force, automatic=args.automatic)
        elif args.command == "apply":
            payload = manager.apply(args.expected_update_id, authorized=args.authorized)
        elif args.command == "preference":
            payload = manager.preference(args.mode, authorized=args.authorized)
        else:
            payload = manager.retire(args.old_skill, args.replacement_skill, args.expected_update_id, authorized=args.authorized)
    except UpdateError as error:
        payload = {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(error)}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 1 if payload["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
