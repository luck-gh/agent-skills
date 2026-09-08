"""轻量检查的真实文件和错误回归,保证纯标准库,只读和检查边界.

用法: python -B -m unittest discover -s tests -p "test*.py"
"""

import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_diagram.py"
SPEC = importlib.util.spec_from_file_location("checker", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)
XML = (ROOT / "assets" / "overview.drawio").read_text(encoding="utf-8")
MD = (ROOT / "assets" / "architecture.md").read_text(encoding="utf-8")


def altered(ident, **attrs):
    tree = ET.fromstring(XML)
    tree.find(f".//mxCell[@id='{ident}']").attrib.update(attrs)
    return ET.tostring(tree, encoding="unicode")


class DiagramChecks(unittest.TestCase):
    def assert_bad(self, text, fragment):
        self.assertTrue(any(fragment in i for i in checker.check_drawio(text)[1]))

    def test_bundled_pair(self):
        modules, issues = checker.check_drawio(XML)
        self.assertEqual(issues, [])
        self.assertEqual(modules, {"mod_entry", "mod_processor", "mod_store"})
        self.assertEqual(checker.check_markdown(MD, modules), [])

    def test_bare_model(self):
        model = ET.fromstring(XML).find("diagram/mxGraphModel")
        self.assertEqual(checker.check_drawio(ET.tostring(model, encoding="unicode"))[1], [])

    def test_invalid_xml(self):
        self.assert_bad("<mxfile>", "xml:")

    def test_dtd_and_entities(self):
        self.assert_bad('<!DOCTYPE mxfile [<!ENTITY x "hello">]>' + XML, "DTD/entity")

    def test_unrecognized_root_and_empty_file(self):
        self.assert_bad("<svg/>", "expected mxfile")
        self.assert_bad("<mxfile/>", "no diagram")

    def test_compressed_not_silently_accepted(self):
        self.assert_bad('<mxfile><diagram id="x">someBase64</diagram></mxfile>', "uncompressed")

    def test_duplicate_cell(self):
        self.assert_bad(altered("mod_entry", id="mod_store"), "duplicate cell")

    def test_bad_parent(self):
        self.assert_bad(altered("mod_entry", parent="missing"), "invalid parent")

    def test_parent_cycle(self):
        text = altered("mod_entry", parent="mod_processor")
        tree = ET.fromstring(text)
        tree.find(".//mxCell[@id='mod_processor']").set("parent", "mod_entry")
        self.assert_bad(ET.tostring(tree, encoding="unicode"), "parent cycle")

    def test_reserved_layer(self):
        self.assert_bad(altered("1", parent="missing"), "layer 1")
        self.assert_bad(altered("0", parent="1"), "root cell 0")

    def test_endpoint_must_be_vertex(self):
        self.assert_bad(altered("edge_process", target="missing"), "target must reference")
        self.assert_bad(altered("edge_process", target="1"), "target must reference")

    def test_both_vertex_edge(self):
        self.assert_bad(altered("mod_entry", edge="1"), "both vertex and edge")

    def test_geometry(self):
        for value in ["0", "-1", "nan", "inf", "bad"]:
            with self.subTest(value=value):
                tree = ET.fromstring(XML)
                tree.find(".//mxCell[@id='mod_entry']/mxGeometry").set("width", value)
                self.assert_bad(ET.tostring(tree, encoding="unicode"), "invalid geometry width")

    def test_edge_relative(self):
        self.assert_bad(XML.replace('relative="1"', 'relative="0"'), "relative=1")

    def test_object_wrapper(self):
        tree = ET.fromstring(XML)
        root = tree.find("diagram/mxGraphModel/root")
        cell = root.find("mxCell[@id='mod_entry']")
        root.remove(cell)
        wrapper = ET.SubElement(root, "object", id=cell.attrib.pop("id"), label=cell.attrib.pop("value"))
        wrapper.append(cell)
        self.assertEqual(checker.check_drawio(ET.tostring(tree, encoding="unicode"))[1], [])

    def test_multiple_pages_share_module_ids(self):
        tree = ET.fromstring(XML)
        second = ET.fromstring(XML).find("diagram")
        second.set("id", "details")
        tree.append(second)
        self.assertEqual(checker.check_drawio(ET.tostring(tree, encoding="unicode"))[1], [])
        second.set("id", "overview")
        self.assert_bad(ET.tostring(tree, encoding="unicode"), "duplicate page")

    def test_missing_and_duplicate_anchors(self):
        self.assertTrue(any("missing module" in i for i in checker.check_markdown(MD.replace('<a id="mod_entry"></a>', ''), {"mod_entry"})))
        self.assertTrue(any("duplicate" in i for i in checker.check_markdown(MD + '\n<a id="mod_entry"></a>')))

    def test_examples_not_anchors(self):
        for sample in ['```html\n<a id="mod_entry"></a>\n```', '`<a id="mod_entry"></a>`', '<!-- <a id="mod_entry"></a> -->']:
            with self.subTest(sample=sample):
                self.assertTrue(any("missing module" in i for i in checker.check_markdown(sample, {"mod_entry"})))

    def test_code_fences(self):
        self.assertTrue(any("unclosed" in i for i in checker.check_markdown("```mermaid\nflowchart LR\nA-->B")))
        self.assertTrue(any("empty" in i for i in checker.check_markdown("~~~mermaid\n~~~")))
        self.assertEqual(checker.check_markdown("````text\n```\n````"), [])

    def test_pair_needs_overview_and_identified_modules(self):
        self.assertTrue(any("structure overview" in i for i in checker.check_markdown('<a id="mod_a"></a>', {"mod_a"})))
        self.assertTrue(any("no mod_" in i for i in checker.check_markdown(MD, set())))

    def test_not_a_mermaid_parser(self):
        # 检查不声称通用 Mermaid 语法通过,未知渲染错误留给实际阅读器.
        self.assertEqual(checker.check_markdown("```mermaid\nflowchart LR\nnot valid [\n```"), [])


class CliChecks(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", "-S", "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def test_standard_library_only_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            script, graph, markdown = folder / "check.py", folder / "diagram.drawio", folder / "diagram.md"
            shutil.copyfile(SCRIPT, script)
            graph.write_text(XML, encoding="utf-8")
            markdown.write_text(MD, encoding="utf-8")
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
            result = subprocess.run([sys.executable, "-I", "-S", "-B", str(script), str(graph), "--markdown", str(markdown)], cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Not checked:", result.stdout)
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()})

    def test_bad_candidate_does_not_change_successful_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            old, candidate = folder / "old.drawio", folder / "candidate.drawio"
            old.write_text(XML, encoding="utf-8")
            candidate.write_text("<broken>", encoding="utf-8")
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            self.assertEqual(self.run_cli(candidate).returncode, 1)
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})

    def test_missing_input_and_arguments(self):
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli("--not-an-option").returncode, 2)
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(self.run_cli(Path(temp) / "absent.drawio").returncode, 1)

    def test_markdown_only(self):
        self.assertEqual(self.run_cli("--markdown", ROOT / "assets" / "architecture.md").returncode, 0)

    def test_encoding_size_and_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bad.drawio"
            for data in [b"\xff\xfe\x00", b"a" * (checker.LIMIT + 1)]:
                target.write_bytes(data)
                self.assertEqual(self.run_cli(target).returncode, 1)
            self.assertEqual(self.run_cli(temp).returncode, 1)


if __name__ == "__main__":
    unittest.main()
