"""只读检查架构速览的 XML 和 Markdown 关联,避免每次手写机械检查.

适用于本 Skill 生成的未压缩 draw.io,不渲染或分析源码,只依赖 Python 标准库.
用法: python -B scripts/check_diagram.py architecture.drawio --markdown architecture.md
"""

import argparse
from html.parser import HTMLParser
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


LIMIT = 4 * 1024 * 1024
MODULE_ID = re.compile(r"mod_[A-Za-z0-9_]+\Z")


def read_text(path):
    """有界读取 UTF-8 文件,不跟随文件里的引用或执行内容."""
    with Path(path).open("rb") as stream:
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("file exceeds 4 MiB")
    return data.decode("utf-8-sig")


def check_drawio(text):
    """检查普通图形结构;返回模块 ID 和诊断,不判断语义或布局质量."""
    issues = []
    modules = set()
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", text, re.I):
        return modules, ["xml: DTD/entity declarations are not accepted"]
    try:
        document = ET.fromstring(text)
    except ET.ParseError as exc:
        return modules, [f"xml: {exc}"]
    if document.tag == "mxGraphModel":
        pages = [("page-1", document)]
    elif document.tag == "mxfile":
        diagrams = document.findall("diagram")
        if not diagrams:
            issues.append("xml: mxfile has no diagram")
        pages = []
        page_ids = set()
        for number, diagram in enumerate(diagrams, 1):
            page_id = diagram.get("id", f"page-{number}")
            if page_id in page_ids:
                issues.append(f"xml: duplicate page id {page_id}")
            page_ids.add(page_id)
            models = diagram.findall("mxGraphModel")
            if len(models) != 1:
                issues.append(f"{page_id}: expected one uncompressed mxGraphModel")
            else:
                pages.append((page_id, models[0]))
    else:
        return modules, ["xml: expected mxfile or mxGraphModel"]
    for page_id, model in pages:
        roots = model.findall("root")
        if len(roots) != 1:
            issues.append(f"{page_id}: expected one root")
            continue
        cells = {}
        for element in roots[0]:
            cell = element if element.tag == "mxCell" else element.find("mxCell")
            if cell is None or element.tag not in {"mxCell", "object", "UserObject"}:
                issues.append(f"{page_id}: unsupported cell wrapper {element.tag}")
                continue
            ident = element.get("id") or cell.get("id")
            if not ident or ident in cells:
                issues.append(f"{page_id}: missing/duplicate cell id {ident!r}")
                continue
            if element is not cell and cell.get("id") not in (None, ident):
                issues.append(f"{page_id}/{ident}: wrapper and cell ids disagree")
            cells[ident] = cell
        if "0" not in cells or "1" not in cells or cells["1"].get("parent") != "0":
            issues.append(f"{page_id}: root cell 0 and layer 1 -> 0 are required")
        if "0" in cells and cells["0"].get("parent") is not None:
            issues.append(f"{page_id}: root cell 0 must not have a parent")
        checked_ancestry = set()
        for ident, cell in cells.items():
            at = f"{page_id}/{ident}"
            parent = cell.get("parent")
            if ident != "0" and (parent not in cells or parent == ident):
                issues.append(f"{at}: invalid parent {parent!r}")
            trail = set()
            cursor = ident
            while cursor in cells and cursor not in checked_ancestry:
                if cursor in trail:
                    issues.append(f"{at}: parent cycle")
                    break
                trail.add(cursor)
                cursor = cells[cursor].get("parent")
            checked_ancestry.update(trail)
            vertex, edge = cell.get("vertex") == "1", cell.get("edge") == "1"
            if vertex and edge:
                issues.append(f"{at}: cell cannot be both vertex and edge")
            if ident.startswith("mod_"):
                if not MODULE_ID.fullmatch(ident) or not vertex or edge:
                    issues.append(f"{at}: module must be a vertex with an ASCII mod_ id")
                else:
                    modules.add(ident)
            if not vertex and not edge:
                continue
            geometries = cell.findall("mxGeometry")
            if len(geometries) != 1 or geometries[0].get("as") != "geometry":
                issues.append(f"{at}: expected one mxGeometry as=geometry")
                continue
            geometry = geometries[0]
            if vertex:
                for field in ("x", "y", "width", "height"):
                    try:
                        value = float(geometry.get(field, "0"))
                        if not math.isfinite(value) or (field in {"width", "height"} and value <= 0):
                            raise ValueError()
                    except ValueError:
                        issues.append(f"{at}: invalid geometry {field}")
            if edge:
                if geometry.get("relative") != "1":
                    issues.append(f"{at}: edge geometry requires relative=1")
                for field in ("source", "target"):
                    target = cell.get(field)
                    if target not in cells or cells[target].get("vertex") != "1":
                        issues.append(f"{at}: {field} must reference a vertex, got {target!r}")
    return modules, issues


class AnchorReader(HTMLParser):
    """只提取实际 HTML 锚点,忽略注释中的示例."""

    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            value = dict(attrs).get("id", "")
            if value.startswith("mod_"):
                self.ids.append(value)


def check_markdown(text, modules=None):
    """检查顶层围栏和模块锚点,不实现另一套 Markdown/Mermaid 解析器."""
    issues, prose, diagrams = [], [], []
    opened = None
    body = []
    for number, line in enumerate(text.splitlines(), 1):
        if opened:
            char, count, language, start = opened
            if re.fullmatch(r" {0,3}" + re.escape(char) + "{" + str(count) + r",}\s*", line):
                if language == "mermaid":
                    content = "\n".join(body).strip()
                    if not content:
                        issues.append(f"markdown:{start}: empty Mermaid block")
                    diagrams.append(content)
                opened = None
            else:
                body.append(line)
        else:
            fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
            if fence:
                marker, info = fence.groups()
                opened = (marker[0], len(marker), info.strip(), number)
                body = []
            else:
                prose.append(line)
    if opened:
        issues.append(f"markdown:{opened[3]}: unclosed code fence")
    parser = AnchorReader()
    # 去掉常见的单行 inline code 示例,不把模板里的锚点当实际模块.
    parser.feed(re.sub(r"(`+)([^`\n]*?)\1", "", "\n".join(prose)))
    seen = set()
    for ident in parser.ids:
        if ident in seen:
            issues.append(f"markdown: duplicate module anchor {ident}")
        if not MODULE_ID.fullmatch(ident):
            issues.append(f"markdown: invalid module anchor {ident}")
        seen.add(ident)
    for ident in sorted(modules or set()):
        if ident not in seen:
            issues.append(f"markdown: missing module anchor {ident}")
    if modules is not None:
        if not modules:
            issues.append("pair: no mod_ module vertices available for correspondence check")
        if not any(re.match(r"(?:flowchart|graph)\s+(?:TB|TD|BT|LR|RL)\b", d) for d in diagrams):
            issues.append("markdown: pair requires a Mermaid structure overview")
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only draw.io/Markdown structural check; no rendering")
    parser.add_argument("drawio", nargs="?")
    parser.add_argument("--markdown")
    args = parser.parse_args(argv)
    if not args.drawio and not args.markdown:
        parser.error("provide a drawio file and/or --markdown")
    issues = []
    modules = None
    try:
        if args.drawio:
            modules, found = check_drawio(read_text(args.drawio))
            issues.extend(found)
        if args.markdown:
            issues.extend(check_markdown(read_text(args.markdown), modules))
    except (OSError, UnicodeError, ValueError) as exc:
        issues.append(f"input: {exc}")
    print("FAIL: structure" if issues else "PASS: requested structural checks only")
    for issue in issues:
        print(f"- {issue}")
    print("Not checked: source semantics, full Mermaid syntax, rendering, visual layout.")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
