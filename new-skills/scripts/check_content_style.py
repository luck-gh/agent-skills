#!/usr/bin/env python3
"""检查 skill 中文正文中的受控全角标点.

存在理由: `new-skills` 需要确定性检查受控中文正文风格.
应用场景: 修改 skill 后扫描调用方明确传入的 physical skill dir.
用法: python -X utf8 -B scripts/check_content_style.py --json <skill-dir> [...]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path


SCHEMA_VERSION = 1
MAX_BYTES = 1_048_576
REPARSE_POINT = 0x0400
RULES = {
    "，": "zh-punct-fullwidth-comma",
    "。": "zh-punct-ideographic-period",
    "；": "zh-punct-fullwidth-semicolon",
    "：": "zh-punct-fullwidth-colon",
    "！": "zh-punct-fullwidth-exclamation",
    "？": "zh-punct-fullwidth-question",
    "（": "zh-punct-fullwidth-left-parenthesis",
    "）": "zh-punct-fullwidth-right-parenthesis",
    "【": "zh-punct-fullwidth-left-bracket",
    "】": "zh-punct-fullwidth-right-bracket",
    "、": "zh-punct-ideographic-comma",
}
FENCE_OPEN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
BLOCKQUOTE = re.compile(r"^[ \t]{0,3}>")
COMMAND = re.compile(
    r"^[ \t]*(?:[-*+]\s+)?(?:\$\s+|PS\s+[^>]*>\s*|"
    r"python(?:3)?\s+|pip(?:3)?\s+|git\s+|pwsh\s+|powershell\s+|"
    r"cmd\s+|bash\s+|sh\s+|node\s+|npm\s+|npx\s+|uv\s+|"
    r"cargo\s+|go\s+|java\s+|dotnet\s+)",
)
MASK_PATTERNS = (
    re.compile(r"(?i)\b(?:https?|ftp)://[^\s<>\"']+"),
    re.compile(r"(?<!\w)(?:[A-Za-z]:[\\/]|\\\\)[^\s<>\"']+"),
    re.compile(
        r"(?<!\S)(?!(?i:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)/)"
        r"(?:\.{0,2}[\\/]|[A-Za-z0-9_.<>-]+[\\/])[^\s<>\"']+"
    ),
    re.compile(r"(?<!\w)/(?:\\.|[^/\s])+/[A-Za-z]*"),
)


class StyleError(RuntimeError):
    """Report a deterministic input or read failure."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise StyleError(f"usage_error: {message}")


def _is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        int(getattr(info, "st_file_attributes", 0)) & REPARSE_POINT
    )


def _physical_directory(raw: str) -> Path:
    path = Path(os.path.abspath(raw))
    try:
        info = os.lstat(path)
    except OSError:
        raise StyleError(f"skill directory is unavailable: {path}") from None
    if _is_link(info) or not stat.S_ISDIR(info.st_mode):
        raise StyleError(f"skill directory must be a physical directory: {path}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", path.name):
        raise StyleError(f"skill directory name is invalid: {path.name}")
    return path


def _regular_text(path: Path, label: str) -> str:
    try:
        before = os.lstat(path)
    except OSError:
        raise StyleError(f"{label} is unavailable") from None
    if _is_link(before) or not stat.S_ISREG(before.st_mode):
        raise StyleError(f"{label} must be a regular file")
    if before.st_size > MAX_BYTES:
        raise StyleError(f"{label} is oversized")
    try:
        raw = path.read_bytes()
    except OSError:
        raise StyleError(f"{label} is unreadable") from None
    try:
        after = os.lstat(path)
    except OSError:
        raise StyleError(f"{label} changed while being read") from None
    identity_before = (before.st_dev, before.st_ino, before.st_size)
    identity_after = (after.st_dev, after.st_ino, after.st_size)
    if _is_link(after) or identity_before != identity_after:
        raise StyleError(f"{label} changed while being read")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise StyleError(f"{label} must be strict UTF-8") from None


def _files_under(skill_dir: Path, folder_name: str, suffixes: set[str]) -> list[Path]:
    folder = skill_dir / folder_name
    if not os.path.lexists(folder):
        return []
    info = os.lstat(folder)
    if _is_link(info) or not stat.S_ISDIR(info.st_mode):
        raise StyleError(f"{folder_name} must be a physical directory")
    files: list[Path] = []
    for current, directory_names, file_names in os.walk(folder, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current_path = Path(current)
        for name in list(directory_names):
            child = current_path / name
            child_info = os.lstat(child)
            if _is_link(child_info) or not stat.S_ISDIR(child_info.st_mode):
                raise StyleError(
                    f"{folder_name} contains a non-physical directory: "
                    f"{child.relative_to(skill_dir).as_posix()}"
                )
        for name in file_names:
            path = current_path / name
            if path.suffix.lower() in suffixes:
                files.append(path)
    return files


def _collect_files(skill_dir: Path) -> list[Path]:
    files = [skill_dir / "SKILL.md"]
    files.extend(_files_under(skill_dir, "references", {".md"}))
    files.extend(_files_under(skill_dir, "agents", {".yaml", ".yml"}))
    return sorted(files, key=lambda item: item.relative_to(skill_dir).as_posix())


def _mark(ignored: list[bool], start: int, end: int) -> None:
    for index in range(max(0, start), min(len(ignored), end)):
        ignored[index] = True


def _mask_inline_code(line: str, ignored: list[bool], delimiter: int | None) -> int | None:
    index = 0
    while index < len(line):
        if delimiter is not None:
            end = line.find("`" * delimiter, index)
            if end < 0:
                _mark(ignored, index, len(line))
                return delimiter
            _mark(ignored, index, end + delimiter)
            index = end + delimiter
            delimiter = None
            continue
        if line[index] != "`":
            index += 1
            continue
        end = index
        while end < len(line) and line[end] == "`":
            end += 1
        delimiter = end - index
        _mark(ignored, index, end)
        index = end
    return delimiter


def _mask_html_comments(line: str, ignored: list[bool], inside: bool) -> bool:
    index = 0
    while index < len(line):
        if inside:
            end = line.find("-->", index)
            if end < 0:
                _mark(ignored, index, len(line))
                return True
            _mark(ignored, index, end + 3)
            index = end + 3
            inside = False
            continue
        start = line.find("<!--", index)
        if start < 0:
            break
        end = line.find("-->", start + 4)
        if end < 0:
            _mark(ignored, start, len(line))
            return True
        _mark(ignored, start, end + 3)
        index = end + 3
    return inside


def _mask_yaml_comment(line: str, ignored: list[bool]) -> None:
    single = False
    double = False
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and double:
            escaped = True
            continue
        if character == "'" and not double:
            single = not single
            continue
        if character == '"' and not single:
            double = not double
            continue
        if character == "#" and not single and not double:
            _mark(ignored, index, len(line))
            return


def _scan_text(skill: str, relative_path: str, text: str, *, markdown: bool) -> list[dict]:
    violations: list[dict] = []
    fence: tuple[str, int] | None = None
    inline_delimiter: int | None = None
    html_comment = False
    lines = text.splitlines()
    frontmatter = bool(markdown and lines and lines[0].strip() == "---")
    for line_number, line in enumerate(lines, 1):
        if frontmatter:
            if line_number > 1 and line.strip() == "---":
                frontmatter = False
            continue
        if markdown and fence is not None:
            character, minimum = fence
            if re.fullmatch(rf"[ \t]{{0,3}}{re.escape(character)}{{{minimum},}}[ \t]*", line):
                fence = None
            continue
        if markdown:
            opening = FENCE_OPEN.match(line)
            if opening:
                run = opening.group(1)
                fence = (run[0], len(run))
                continue
            if BLOCKQUOTE.match(line) or COMMAND.match(line):
                continue
        ignored = [False] * len(line)
        html_comment = _mask_html_comments(line, ignored, html_comment)
        inline_delimiter = _mask_inline_code(line, ignored, inline_delimiter)
        if not markdown:
            _mask_yaml_comment(line, ignored)
        for pattern in MASK_PATTERNS:
            for match in pattern.finditer(line):
                _mark(ignored, match.start(), match.end())
        for column, character in enumerate(line, 1):
            if not ignored[column - 1] and character in RULES:
                violations.append({
                    "skill": skill,
                    "relative_path": relative_path,
                    "line": line_number,
                    "column": column,
                    "offending_character": character,
                    "rule_id": RULES[character],
                })
    return violations


def check_skills(raw_directories: list[str]) -> dict:
    if not raw_directories:
        raise StyleError("usage_error: at least one skill physical directory is required")
    directories = [_physical_directory(raw) for raw in raw_directories]
    normalized = [os.path.normcase(os.path.normpath(str(path))) for path in directories]
    if len(set(normalized)) != len(normalized):
        raise StyleError("duplicate skill physical directory")
    if len({path.name for path in directories}) != len(directories):
        raise StyleError("duplicate physical skill name")
    directories.sort(key=lambda item: (item.name, os.path.normcase(str(item))))
    checked_skills: list[str] = []
    checked_files = 0
    violations: list[dict] = []
    for skill_dir in directories:
        checked_skills.append(skill_dir.name)
        for path in _collect_files(skill_dir):
            relative = path.relative_to(skill_dir).as_posix()
            text = _regular_text(path, f"{skill_dir.name}/{relative}")
            checked_files += 1
            violations.extend(_scan_text(
                skill_dir.name,
                relative,
                text,
                markdown=path.suffix.lower() == ".md",
            ))
    violations.sort(key=lambda item: (
        item["skill"], item["relative_path"], item["line"], item["column"], item["rule_id"]
    ))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "violations" if violations else "ok",
        "checked_skills": checked_skills,
        "checked_files": checked_files,
        "violations": violations,
    }


def _parser() -> Parser:
    parser = Parser(description=__doc__)
    parser.add_argument("--json", action="store_true", required=True)
    parser.add_argument("skill_dirs", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        payload = check_skills(args.skill_dirs)
        code = 1 if payload["violations"] else 0
    except StyleError as error:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "checked_skills": [],
            "checked_files": 0,
            "violations": [],
            "error": str(error),
        }
        code = 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
