#!/usr/bin/env python3
"""验证一个或多个 physical skill dir 的通用分发契约.

存在理由: `new-skills` 需要确定性检查 Skill 结构与独立分发边界.
应用场景: 创建或修改 Skill 后检查入口,metadata,声明资源,settings 和 Python 源码.
用法: python -X utf8 -B scripts/validate_skill.py --json <skill-dir> [...]
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml


SCHEMA_VERSION = 1
MAX_TEXT_BYTES = 1_048_576
REPARSE_POINT = 0x0400
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCE_OPEN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
RESOURCE_DIRECTORIES = ("agents", "references", "scripts", "src", "assets")
DEV_SEGMENT = "_dev"
PARENT_SEGMENT = ".."


class ValidationInputError(RuntimeError):
    """表示调用输入无法作为 physical skill dir 检查."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValidationInputError(f"usage_error: {message}")


def _is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        int(getattr(info, "st_file_attributes", 0)) & REPARSE_POINT
    )


def _physical_directory(raw: str) -> Path:
    path = Path(os.path.abspath(raw))
    try:
        info = os.lstat(path)
    except OSError:
        raise ValidationInputError(f"skill directory is unavailable: {path}") from None
    if _is_link(info) or not stat.S_ISDIR(info.st_mode):
        raise ValidationInputError(f"skill directory must be physical: {path}")
    if SKILL_NAME.fullmatch(path.name) is None or len(path.name) > 64:
        raise ValidationInputError(f"skill directory name is invalid: {path.name}")
    return path


def _read_text(path: Path) -> str:
    try:
        info = os.lstat(path)
    except OSError as error:
        raise ValueError(f"unavailable file: {error}") from None
    if _is_link(info) or not stat.S_ISREG(info.st_mode):
        raise ValueError("must be a physical regular file")
    if info.st_size > MAX_TEXT_BYTES:
        raise ValueError("file is oversized")
    try:
        return path.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ValueError("file must be strict UTF-8") from None
    except OSError as error:
        raise ValueError(f"unreadable file: {error}") from None


def _issue(
    issues: list[dict[str, str]],
    skill: str,
    path: str,
    code: str,
    message: str,
) -> None:
    issues.append({"skill": skill, "path": path, "code": code, "message": message})


def _physical_files(
    skill_dir: Path,
    folder_name: str,
    issues: list[dict[str, str]],
) -> list[Path]:
    folder = skill_dir / folder_name
    if not os.path.lexists(folder):
        return []
    try:
        info = os.lstat(folder)
    except OSError as error:
        _issue(issues, skill_dir.name, folder_name, "invalid-resource", str(error))
        return []
    if _is_link(info) or not stat.S_ISDIR(info.st_mode):
        _issue(
            issues,
            skill_dir.name,
            folder_name,
            "non-physical-resource",
            "runtime resource directory must be physical",
        )
        return []

    files: list[Path] = []
    for current, directory_names, file_names in os.walk(folder, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current_path = Path(current)
        for name in list(directory_names):
            child = current_path / name
            child_info = os.lstat(child)
            if _is_link(child_info) or not stat.S_ISDIR(child_info.st_mode):
                directory_names.remove(name)
                _issue(
                    issues,
                    skill_dir.name,
                    child.relative_to(skill_dir).as_posix(),
                    "non-physical-resource",
                    "runtime resource directory must be physical",
                )
        for name in file_names:
            path = current_path / name
            relative = path.relative_to(skill_dir).as_posix()
            try:
                file_info = os.lstat(path)
            except OSError as error:
                _issue(issues, skill_dir.name, relative, "invalid-resource", str(error))
                continue
            if _is_link(file_info) or not stat.S_ISREG(file_info.st_mode):
                _issue(
                    issues,
                    skill_dir.name,
                    relative,
                    "non-physical-resource",
                    "runtime resource must be a physical regular file",
                )
                continue
            files.append(path)
    return files


def _load_yaml(
    path: Path,
    skill: str,
    relative: str,
    issues: list[dict[str, str]],
) -> object | None:
    try:
        return yaml.safe_load(_read_text(path))
    except (ValueError, yaml.YAMLError) as error:
        _issue(issues, skill, relative, "invalid-yaml", str(error))
        return None


def _frontmatter(skill_dir: Path, issues: list[dict[str, str]]) -> str | None:
    skill = skill_dir.name
    path = skill_dir / "SKILL.md"
    try:
        text = _read_text(path)
    except ValueError as error:
        _issue(issues, skill, "SKILL.md", "invalid-skill-file", str(error))
        return None
    match = FRONTMATTER.match(text)
    if match is None:
        _issue(
            issues,
            skill,
            "SKILL.md",
            "invalid-frontmatter",
            "frontmatter is missing or malformed",
        )
        return text
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        _issue(issues, skill, "SKILL.md", "invalid-frontmatter", str(error))
        return text
    if type(metadata) is not dict:
        _issue(
            issues,
            skill,
            "SKILL.md",
            "invalid-frontmatter",
            "frontmatter must be an object",
        )
        return text
    if metadata.get("name") != skill:
        _issue(
            issues,
            skill,
            "SKILL.md",
            "skill-name-mismatch",
            "frontmatter name must equal the directory name",
        )
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        _issue(
            issues,
            skill,
            "SKILL.md",
            "invalid-description",
            "description must be a non-empty string",
        )
    elif len(description) > 1024 or "<" in description or ">" in description:
        _issue(
            issues,
            skill,
            "SKILL.md",
            "invalid-description",
            "description violates platform limits",
        )
    return text


def _link_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1:value.index(">")]
    else:
        value = value.split(maxsplit=1)[0] if value else ""
    return unquote(value).split("#", 1)[0].split("?", 1)[0]


def _relative_target(
    skill_dir: Path,
    source: Path,
    raw: str,
    *,
    base: Path | None = None,
) -> tuple[Path, str] | None:
    target = _link_target(raw)
    if not target or "://" in target or target.startswith(("mailto:", "data:")):
        return None
    resolved = ((source.parent if base is None else base) / target).resolve(strict=False)
    try:
        relative = resolved.relative_to(skill_dir.resolve(strict=True)).as_posix()
    except ValueError:
        return resolved, ""
    return resolved, relative


def _markdown_without_code(text: str) -> str:
    visible: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines():
        if fence is not None:
            character, minimum = fence
            if re.fullmatch(
                rf"[ \t]{{0,3}}{re.escape(character)}{{{minimum},}}[ \t]*",
                line,
            ):
                fence = None
            visible.append("")
            continue
        opening = FENCE_OPEN.match(line)
        if opening:
            marker = opening.group(1)
            fence = (marker[0], len(marker))
            visible.append("")
            continue
        visible.append(re.sub(r"`+[^`\r\n]*`+", "", line))
    return "\n".join(visible)


def _resource_targets(text: str) -> list[str]:
    return [
        match.group(1)
        for match in MARKDOWN_LINK.finditer(_markdown_without_code(text))
    ]


def _check_local_target(
    skill_dir: Path,
    source: Path,
    raw: str,
    issues: list[dict[str, str]],
    *,
    base: Path | None = None,
) -> str | None:
    if any(character in raw for character in "*?[]"):
        return None
    parsed = _relative_target(skill_dir, source, raw, base=base)
    if parsed is None:
        return None
    resolved, relative = parsed
    source_relative = source.relative_to(skill_dir).as_posix()
    if not relative:
        _issue(
            issues,
            skill_dir.name,
            source_relative,
            "resource-escape",
            f"resource escapes skill: {raw}",
        )
    elif not resolved.exists():
        _issue(
            issues,
            skill_dir.name,
            source_relative,
            "missing-resource",
            f"missing resource: {relative}",
        )
    return relative or None


def _check_resources(
    skill_dir: Path,
    skill_text: str | None,
    files: dict[str, list[Path]],
    issues: list[dict[str, str]],
) -> None:
    declared: set[str] = set()
    markdown_files = [skill_dir / "SKILL.md"] + [
        path for path in files["references"] if path.suffix.lower() == ".md"
    ]
    for source in markdown_files:
        relative_source = source.relative_to(skill_dir).as_posix()
        try:
            text = skill_text if source == skill_dir / "SKILL.md" else _read_text(source)
        except ValueError as error:
            _issue(issues, skill_dir.name, relative_source, "invalid-resource", str(error))
            continue
        if text is None:
            continue
        for raw in _resource_targets(text):
            relative = _check_local_target(skill_dir, source, raw, issues)
            if source == skill_dir / "SKILL.md" and relative:
                declared.add(relative)

    required_declarations = [
        path
        for path in files["references"]
        if path.suffix.lower() == ".md"
    ] + [
        path
        for path in files["scripts"]
        if path.suffix.lower() == ".py"
    ]
    for path in required_declarations:
        relative = path.relative_to(skill_dir).as_posix()
        if relative not in declared:
            _issue(
                issues,
                skill_dir.name,
                relative,
                "undeclared-resource",
                "resource must use a direct Markdown link in SKILL.md",
            )


def _check_agents(
    skill_dir: Path,
    agent_files: list[Path],
    issues: list[dict[str, str]],
) -> None:
    payloads: dict[str, object | None] = {}
    for path in agent_files:
        if path.suffix.lower() not in {".yaml", ".yml"}:
            continue
        relative = path.relative_to(skill_dir).as_posix()
        payloads[relative] = _load_yaml(path, skill_dir.name, relative, issues)

    relative = "agents/openai.yaml"
    if relative not in payloads:
        return
    payload = payloads[relative]
    if type(payload) is not dict or type(payload.get("interface")) is not dict:
        _issue(
            issues,
            skill_dir.name,
            relative,
            "invalid-openai-metadata",
            "interface object is required",
        )
        return
    interface = payload["interface"]
    for field in ("display_name", "short_description", "default_prompt"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            _issue(
                issues,
                skill_dir.name,
                relative,
                "invalid-openai-metadata",
                f"{field} must be a non-empty string",
            )
    short_description = interface.get("short_description")
    if isinstance(short_description, str) and not 25 <= len(short_description) <= 64:
        _issue(
            issues,
            skill_dir.name,
            relative,
            "invalid-openai-metadata",
            "short_description must contain 25 to 64 characters",
        )
    prompt = interface.get("default_prompt")
    if isinstance(prompt, str) and f"${skill_dir.name}" not in prompt:
        _issue(
            issues,
            skill_dir.name,
            relative,
            "invalid-openai-prompt",
            f"default_prompt must mention ${skill_dir.name}",
        )
    brand_color = interface.get("brand_color")
    if brand_color is not None and (
        not isinstance(brand_color, str)
        or re.fullmatch(r"#[0-9A-Fa-f]{6}", brand_color) is None
    ):
        _issue(
            issues,
            skill_dir.name,
            relative,
            "invalid-openai-metadata",
            "brand_color must be a six-digit hexadecimal color",
        )
    source = skill_dir / relative
    for field in ("icon_small", "icon_large"):
        value = interface.get(field)
        if isinstance(value, str):
            _check_local_target(skill_dir, source, value, issues, base=skill_dir)


def _normalized_json(path: Path) -> tuple[dict[str, object] | None, str | None]:
    try:
        text = _read_text(path)
        value = json.loads(text)
    except (ValueError, json.JSONDecodeError) as error:
        return None, str(error)
    if type(value) is not dict or not value:
        return None, "settings JSON must be a non-empty object"
    expected = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    normalized_text = text.replace("\r\n", "\n")
    if "\r" in normalized_text or normalized_text != expected:
        return value, "settings JSON must use UTF-8, 2-space indentation, and one trailing newline"
    return value, None


def _check_settings(skill_dir: Path, issues: list[dict[str, str]]) -> None:
    skill = skill_dir.name
    example_path = skill_dir / "settings.example.json"
    settings_path = skill_dir / "settings.json"
    ignore_path = skill_dir / ".gitignore"
    has_example = os.path.lexists(example_path)
    has_settings = os.path.lexists(settings_path)
    if not has_example and not has_settings:
        return

    example: dict[str, object] | None = None
    if not has_example:
        _issue(
            issues,
            skill,
            "settings.json",
            "missing-settings-example",
            "settings.example.json is required",
        )
    else:
        example, error = _normalized_json(example_path)
        if error:
            _issue(issues, skill, "settings.example.json", "invalid-settings-json", error)

    try:
        ignore_lines = [
            line.strip()
            for line in _read_text(ignore_path).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except ValueError:
        ignore_lines = []
    if "/settings.json" not in ignore_lines:
        _issue(
            issues,
            skill,
            ".gitignore",
            "settings-not-ignored",
            "add the exact /settings.json rule",
        )
    if "/settings.example.json" in ignore_lines:
        _issue(
            issues,
            skill,
            ".gitignore",
            "settings-example-ignored",
            "settings.example.json must remain distributable",
        )

    if not has_settings:
        return
    settings, error = _normalized_json(settings_path)
    if error:
        _issue(issues, skill, "settings.json", "invalid-settings-json", error)
    elif example is not None and settings is not None:
        unknown = set(settings) - set(example)
        if unknown:
            _issue(
                issues,
                skill,
                "settings.json",
                "unknown-settings-field",
                f"unknown fields: {', '.join(sorted(unknown))}",
            )


def _hidden_path(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        if re.search(r"(['\"])_dev\1", source):
            return DEV_SEGMENT
        prefixes = tuple(
            quote + PARENT_SEGMENT + separator
            for quote in ('"', "'")
            for separator in ("/", "\\")
        )
        if any(prefix in source for prefix in prefixes):
            return PARENT_SEGMENT
        return None
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        normalized = node.value.replace("\\", "/")
        segments = [segment for segment in normalized.split("/") if segment]
        if "/" in normalized and PARENT_SEGMENT in segments:
            return PARENT_SEGMENT
        if DEV_SEGMENT not in segments:
            continue
        if "/" in normalized:
            return DEV_SEGMENT
        parent = parents.get(node)
        if isinstance(parent, ast.BinOp):
            return DEV_SEGMENT
        if isinstance(parent, ast.Call):
            function = parent.func
            call_name = (
                function.id
                if isinstance(function, ast.Name)
                else function.attr
                if isinstance(function, ast.Attribute)
                else ""
            )
            if call_name.lower() in {"path", "open", "join", "insert", "append"}:
                return DEV_SEGMENT
        if isinstance(parent, (ast.Assign, ast.AnnAssign)):
            targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
            names = [target.id.lower() for target in targets if isinstance(target, ast.Name)]
            if any(
                marker in name
                for name in names
                for marker in ("path", "dir", "root", "target", "entry")
            ):
                return DEV_SEGMENT
    return None


def _check_python(
    skill_dir: Path,
    files: dict[str, list[Path]],
    issues: list[dict[str, str]],
) -> None:
    for folder_name in ("scripts", "src"):
        for path in files[folder_name]:
            if path.suffix.lower() != ".py":
                continue
            relative = path.relative_to(skill_dir).as_posix()
            try:
                source = _read_text(path)
            except ValueError as error:
                _issue(
                    issues,
                    skill_dir.name,
                    relative,
                    "invalid-python-resource",
                    str(error),
                )
                continue
            hidden = _hidden_path(source)
            if hidden:
                _issue(
                    issues,
                    skill_dir.name,
                    relative,
                    "external-runtime-dependency",
                    f"runtime source contains a {hidden} path segment",
                )
            try:
                compile(source, str(path), "exec")
            except SyntaxError as error:
                _issue(
                    issues,
                    skill_dir.name,
                    relative,
                    "python-syntax-error",
                    f"line {error.lineno}: {error.msg}",
                )


def validate_skill(skill_dir: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    files = {
        folder_name: _physical_files(skill_dir, folder_name, issues)
        for folder_name in RESOURCE_DIRECTORIES
    }
    skill_text = _frontmatter(skill_dir, issues)
    _check_resources(skill_dir, skill_text, files, issues)
    _check_agents(skill_dir, files["agents"], issues)
    _check_settings(skill_dir, issues)
    _check_python(skill_dir, files, issues)
    issues.sort(key=lambda item: (item["skill"], item["path"], item["code"], item["message"]))
    return issues


def validate_skills(raw_directories: list[str]) -> dict[str, object]:
    if not raw_directories:
        raise ValidationInputError("usage_error: at least one skill directory is required")
    directories = [_physical_directory(raw) for raw in raw_directories]
    normalized = [os.path.normcase(os.path.normpath(str(path))) for path in directories]
    if len(normalized) != len(set(normalized)):
        raise ValidationInputError("duplicate skill directory")
    if len({path.name for path in directories}) != len(directories):
        raise ValidationInputError("duplicate physical skill name")
    ordered = sorted(directories, key=lambda item: (item.name, os.path.normcase(str(item))))
    issues: list[dict[str, str]] = []
    for skill_dir in ordered:
        issues.extend(validate_skill(skill_dir))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "invalid" if issues else "ok",
        "checked_skills": [path.name for path in ordered],
        "issues": issues,
    }


def _parser() -> Parser:
    parser = Parser(description=__doc__)
    parser.add_argument("--json", action="store_true", required=True)
    parser.add_argument("skill_dirs", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        payload = validate_skills(args.skill_dirs)
        code = 1 if payload["issues"] else 0
    except ValidationInputError as error:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "checked_skills": [],
            "issues": [],
            "error": str(error),
        }
        code = 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
