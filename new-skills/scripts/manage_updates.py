"""检查并在明确授权后升级 `new-skills` 管理的 Skill 安装.

公开入口:
  check --json
  check --force --json
  apply --expected-update-id <id> --authorized --json

脚本使用 Python 标准库.它在 Git 真源模式中只允许 fast-forward 更新,在公共
安装模式中按公开 manifest 仅更新已安装且发生变化的 Skill,并提供本地修改保护,
settings 保留,失败回滚和自更新提示.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
IGNORED_NAMES = {"settings.json", "__pycache__", ".pytest_cache", ".git"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


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
    }


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return _empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _empty_state()
    if type(payload) is not dict or payload.get("schema_version") != SCHEMA_VERSION:
        return _empty_state()
    baselines = payload.get("installation_baselines")
    if type(baselines) is not dict or any(
        not isinstance(name, str) or not isinstance(digest, str)
        for name, digest in baselines.items()
    ):
        return _empty_state()
    clean = _empty_state()
    clean.update({key: payload.get(key) for key in clean if key != "schema_version"})
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
            if entry.name in IGNORED_NAMES or path.suffix.lower() in IGNORED_SUFFIXES:
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
        if not isinstance(name, str) or type(item) is not dict or item.get("path") != name:
            raise UpdateError("public manifest contains an invalid skill entry")
        digest = item.get("content_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise UpdateError("public manifest contains an invalid content hash")
    return payload


def _lock_entries() -> dict[str, object]:
    path = Path.home() / ".agents" / ".skill-lock.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if type(payload) is not dict or payload.get("version") != 3 or type(payload.get("skills")) is not dict:
        return {}
    return payload["skills"]


def _source_is_public(entry: object, name: str) -> bool:
    if type(entry) is not dict:
        return False
    path = entry.get("skillPath")
    return (
        entry.get("sourceType") == "github"
        and str(entry.get("source", "")).lower() == PUBLIC_REPOSITORY.lower()
        and isinstance(path, str)
        and path.strip("/").split("/")[-1] == name
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

    def check(self, *, force: bool = False) -> dict[str, object]:
        state = load_state(self.state_file)
        checked_at = _parse_time(state.get("last_check_at"))
        current_time = self.now().astimezone(timezone.utc)
        if not force and checked_at is not None and current_time - checked_at < TTL:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "ttl_skipped",
                "checked_at": state["last_check_at"],
                "update_id": state.get("public_snapshot_id"),
                "failure_summary": state.get("failure_summary"),
            }
        state["last_check_at"] = current_time.isoformat().replace("+00:00", "Z")
        try:
            physical_root, _ = load_settings(self.skill_root)
            root = _git_root(physical_root)
            if root is not None:
                result = git_check(root)
                state["failure_summary"] = None
            else:
                manifest = fetch_manifest(self.manifest_opener)
                result = public_check(
                    physical_root,
                    manifest,
                    state,
                    lock_entries=self.lock_entries,
                )
                state["public_snapshot_id"] = manifest["snapshot_id"]
                state["failure_summary"] = None
        except UpdateError as error:
            state["failure_summary"] = str(error)[:500]
            save_state(self.state_file, state)
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "error",
                "error": str(error),
                "non_blocking": True,
            }
        save_state(self.state_file, state)
        return result

    def apply(self, expected_update_id: str, *, authorized: bool) -> dict[str, object]:
        if not authorized:
            raise UpdateError("apply requires --authorized")
        physical_root, _ = load_settings(self.skill_root)
        root = _git_root(physical_root)
        if root is not None:
            return self._apply_git(root, expected_update_id)
        return self._apply_public(physical_root, expected_update_id)

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
            return {**status, "status": "no_changes"}
        lock_path = Path.home() / ".agents" / ".skill-lock.json"
        npx = "npx.cmd" if os.name == "nt" else "npx"
        with tempfile.TemporaryDirectory(prefix="new-skills-update-") as temporary:
            backup_root = Path(temporary)
            settings: dict[str, bytes] = {}
            settings_absent: set[str] = set()
            for name in updates:
                target = physical_root / name
                shutil.copytree(target, backup_root / name)
                local_settings = target / "settings.json"
                if local_settings.is_file():
                    settings[name] = local_settings.read_bytes()
                else:
                    settings_absent.add(name)
            had_lock = lock_path.is_file()
            if had_lock:
                shutil.copy2(lock_path, backup_root / ".skill-lock.json")
            command = [npx, f"skills@{INSTALLER_VERSION}", "add", PUBLIC_REPOSITORY, "-g", "-y"]
            for name in updates:
                command.extend(["--skill", name])
            result = _run(command)
            try:
                if result.returncode != 0:
                    raise UpdateError((result.stderr.strip() or "skills installer failed")[:500])
                for name, data in settings.items():
                    (physical_root / name / "settings.json").write_bytes(data)
                for name in settings_absent:
                    local_settings = physical_root / name / "settings.json"
                    if local_settings.is_file():
                        local_settings.unlink()
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
    check.add_argument("--json", action="store_true", required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("--expected-update-id", required=True)
    apply.add_argument("--authorized", action="store_true", required=True)
    apply.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manager = UpdateManager(Path(__file__).resolve().parents[1])
    try:
        if args.command == "check":
            payload = manager.check(force=args.force)
        else:
            payload = manager.apply(args.expected_update_id, authorized=args.authorized)
    except UpdateError as error:
        payload = {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(error)}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 1 if payload["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
