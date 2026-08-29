"""`new-skills` 通用 skill 验证与自有工具回归测试."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_skill(root: Path, name: str = "sample-skill") -> Path:
    skill = root / name
    (skill / "agents").mkdir(parents=True)
    (skill / "references").mkdir()
    (skill / "scripts").mkdir()
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill.\n---\n\n"
        "# Test\n\n[Rules](references/rules.md), [check](scripts/check.py), "
        "and example `[Text](target)`.\n",
        encoding="utf-8",
    )
    (skill / "references" / "rules.md").write_text("# Rules\n", encoding="utf-8")
    (skill / "scripts" / "check.py").write_text("VALUE = 1\n", encoding="utf-8")
    (skill / "agents" / "openai.yaml").write_text(
        "interface:\n"
        '  display_name: "Sample"\n'
        '  short_description: "Validate a standalone sample skill"\n'
        f'  default_prompt: "Use ${name} for this sample."\n',
        encoding="utf-8",
    )
    return skill


class SkillValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load(SKILL_ROOT / "scripts" / "validate_skill.py", "local_validator")

    def test_valid_skill_and_optional_settings_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            skill = write_skill(Path(temporary))
            (skill / "settings.example.json").write_text(
                '{\n  "root": "D:/example"\n}\n', encoding="utf-8"
            )
            (skill / ".gitignore").write_text("/settings.json\n", encoding="utf-8")
            payload = self.validator.validate_skills([str(skill)])
        self.assertEqual("ok", payload["status"], payload["issues"])
        self.assertEqual([], payload["issues"])

    def test_frontmatter_links_and_openai_metadata_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            skill = write_skill(Path(temporary))
            (skill / "SKILL.md").write_text(
                "---\nname: wrong-name\ndescription: Test skill.\n---\n\n"
                "[Missing](references/missing.md)\n",
                encoding="utf-8",
            )
            (skill / "agents" / "openai.yaml").write_text(
                "interface:\n  display_name: Sample\n  short_description: Sample\n"
                "  default_prompt: Missing invocation.\n",
                encoding="utf-8",
            )
            codes = {
                item["code"] for item in self.validator.validate_skill(skill)
            }
        self.assertTrue(
            {
                "skill-name-mismatch",
                "missing-resource",
                "invalid-openai-prompt",
            }.issubset(codes)
        )

    def test_all_agent_yaml_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            skill = write_skill(Path(temporary))
            (skill / "agents" / "runtime.yml").write_text(
                "runtime: [\n", encoding="utf-8"
            )
            issues = self.validator.validate_skill(skill)
        self.assertIn(
            ("agents/runtime.yml", "invalid-yaml"),
            {(item["path"], item["code"]) for item in issues},
        )

    def test_openai_icons_are_resolved_from_skill_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            skill = write_skill(Path(temporary))
            (skill / "assets").mkdir()
            (skill / "assets" / "small.svg").write_text("<svg/>\n", encoding="utf-8")
            (skill / "assets" / "large.svg").write_text("<svg/>\n", encoding="utf-8")
            metadata = (
                "interface:\n"
                '  display_name: "Sample"\n'
                '  short_description: "Validate a standalone sample skill"\n'
                '  default_prompt: "Use $sample-skill for this sample."\n'
                '  icon_small: "./assets/small.svg"\n'
                '  icon_large: "./assets/large.svg"\n'
            )
            (skill / "agents" / "openai.yaml").write_text(metadata, encoding="utf-8")
            valid_issues = self.validator.validate_skill(skill)
            (skill / "assets" / "large.svg").unlink()
            missing_issues = self.validator.validate_skill(skill)
        self.assertEqual([], valid_issues)
        self.assertIn(
            ("agents/openai.yaml", "missing-resource", "missing resource: assets/large.svg"),
            {
                (item["path"], item["code"], item["message"])
                for item in missing_issues
            },
        )

    def test_references_and_public_scripts_require_direct_markdown_links(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            root = Path(temporary)
            skill = write_skill(root)
            (skill / "references" / "extra.md").write_text(
                "# Extra\n", encoding="utf-8"
            )
            (skill / "scripts" / "extra.py").write_text(
                "VALUE = 2\n", encoding="utf-8"
            )
            issues = self.validator.validate_skill(skill)
            commands_only = write_skill(root, "commands-only")
            (commands_only / "SKILL.md").write_text(
                "---\nname: commands-only\ndescription: Test skill.\n---\n\n"
                "# Test\n\n[Rules](references/rules.md).\n\n"
                "`python -X utf8 -B scripts/check.py --json target`\n\n"
                "```text\npython scripts/check.py --json target\n```\n",
                encoding="utf-8",
            )
            command_issues = self.validator.validate_skill(commands_only)
            linked = write_skill(root, "linked-script")
            (linked / "SKILL.md").write_text(
                "---\nname: linked-script\ndescription: Test skill.\n---\n\n"
                "# Test\n\n[Rules](references/rules.md).\n\n"
                "Run [the validator](scripts/check.py) with the required arguments.\n\n"
                "```text\npython scripts/check.py --json target\n```\n",
                encoding="utf-8",
            )
            linked_issues = self.validator.validate_skill(linked)
        undeclared = {
            item["path"]
            for item in issues
            if item["code"] == "undeclared-resource"
        }
        self.assertEqual(
            {"references/extra.md", "scripts/extra.py"},
            undeclared,
        )
        self.assertIn(
            ("scripts/check.py", "undeclared-resource"),
            {(item["path"], item["code"]) for item in command_issues},
        )
        self.assertEqual([], linked_issues)

    def test_duplicate_skill_names_from_distinct_directories_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            root = Path(temporary)
            first = write_skill(root / "first", "same-skill")
            second = write_skill(root / "second", "same-skill")
            with self.assertRaisesRegex(
                self.validator.ValidationInputError,
                "duplicate physical skill name",
            ):
                self.validator.validate_skills([str(first), str(second)])

    def test_settings_are_pretty_ignored_and_schema_bounded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            skill = write_skill(Path(temporary))
            (skill / "settings.example.json").write_text(
                '{"root":"D:/example"}', encoding="utf-8"
            )
            (skill / "settings.json").write_text(
                '{\n  "other": "D:/local"\n}\n', encoding="utf-8"
            )
            codes = {
                item["code"] for item in self.validator.validate_skill(skill)
            }
        self.assertEqual(
            {"invalid-settings-json", "settings-not-ignored", "unknown-settings-field"},
            codes,
        )

    def test_runtime_python_is_compiled_without_execution_or_dev_dependency(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            skill = write_skill(Path(temporary))
            (skill / "scripts" / "check.py").write_text(
                'TARGET = "_dev"\nif True print("never")\n', encoding="utf-8"
            )
            codes = {
                item["code"] for item in self.validator.validate_skill(skill)
            }
        self.assertEqual({"external-runtime-dependency", "python-syntax-error"}, codes)

    def test_parent_path_literal_is_a_hidden_runtime_dependency(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-validator-") as temporary:
            root = Path(temporary)
            skill = write_skill(root)
            (skill / "scripts" / "check.py").write_text(
                'raise RuntimeError("must not execute")\nTARGET = "../sibling/tool.py"\n',
                encoding="utf-8",
            )
            codes = {
                item["code"] for item in self.validator.validate_skill(skill)
            }
            safe = write_skill(root, "path-validator")
            (safe / "scripts" / "check.py").write_text(
                'FORBIDDEN_SEGMENTS = {"_dev", ".."}\n',
                encoding="utf-8",
            )
            safe_codes = {
                item["code"] for item in self.validator.validate_skill(safe)
            }
        self.assertEqual({"external-runtime-dependency"}, codes)
        self.assertEqual(set(), safe_codes)

    def test_new_skills_validates_after_isolated_copy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="new-skills-isolated-") as temporary:
            isolated = Path(temporary) / "new-skills"
            shutil.copytree(
                SKILL_ROOT,
                isolated,
                ignore=shutil.ignore_patterns("settings.json", "__pycache__", "*.pyc"),
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    str(isolated / "scripts" / "validate_skill.py"),
                    "--json",
                    str(isolated),
                ],
                cwd=temporary,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            payload = json.loads(result.stdout)
            dependency = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    "-c",
                    "import importlib.metadata as m; print(m.version('PyYAML'))",
                ],
                cwd=temporary,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertTrue((isolated / "settings.example.json").is_file())
            self.assertTrue((isolated / ".gitignore").is_file())
            self.assertFalse((isolated / "settings.json").exists())
            self.assertFalse(any(isolated.rglob("*.pyc")))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual((0, "6.0.2"), (dependency.returncode, dependency.stdout.strip()))
        self.assertEqual(("ok", []), (payload["status"], payload["issues"]), payload)


class NewSkillsToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entry = load(SKILL_ROOT / "scripts" / "ensure_skill_entry.py", "local_entry")
        cls.style = load(SKILL_ROOT / "scripts" / "check_content_style.py", "local_style")

    def test_entry_inspection_is_read_only_and_creation_is_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory(prefix="entry-tool-") as temporary:
            root = Path(temporary)
            physical = root / "entry-skill"
            entries = root / "entries"
            physical.mkdir()
            entries.mkdir()
            entry = entries / "entry-skill"
            self.assertEqual("absent", self.entry.probe_entry(physical, entry).kind)
            entry.mkdir()
            (entry / "sentinel").write_text("external", encoding="utf-8")
            with self.assertRaisesRegex(self.entry.CheckError, "entry conflict"):
                self.entry.inspect(physical, entry)
            self.assertEqual("external", (entry / "sentinel").read_text(encoding="utf-8"))
        with mock.patch.object(self.entry.os, "symlink") as symlink:
            physical, entry = Path("/physical"), Path("/entries/skill")
            self.entry.create_and_publish_posix_entry(physical, entry)
        symlink.assert_called_once_with(str(physical), str(entry), target_is_directory=True)

    def test_discovery_rejects_symlink_physical_dir_before_resolve_or_create(self) -> None:
        fake_info = mock.Mock(st_mode=stat.S_IFLNK, st_file_attributes=0)
        self._assert_linked_physical_dir_fails_closed(fake_info)

    def test_discovery_rejects_reparse_physical_dir_before_resolve_or_create(self) -> None:
        fake_info = mock.Mock(st_mode=stat.S_IFDIR, st_file_attributes=self.entry.REPARSE_POINT)
        self._assert_linked_physical_dir_fails_closed(fake_info)

    def _assert_linked_physical_dir_fails_closed(self, fake_info) -> None:
        physical = Path("entry-skill")
        entry = Path("entries") / "entry-skill"
        for action, authorized in (("inspect", False), ("ensure", True)):
            arguments = [
                action,
                "--physical-dir",
                str(physical),
                "--entry-dir",
                str(entry),
            ]
            if authorized:
                arguments.append("--authorized")
            with mock.patch.object(self.entry.os, "lstat", return_value=fake_info), mock.patch.object(
                self.entry.Path,
                "resolve",
                side_effect=AssertionError("resolve must not run"),
            ), mock.patch.object(
                self.entry,
                "create_entry",
                side_effect=AssertionError("entry must not be created"),
            ), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(2, self.entry.main(arguments))
            self.assertFalse(entry.exists())

    def test_content_style_reports_locations_and_respects_exclusions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="style-") as temporary:
            root = Path(temporary)
            failing = write_skill(root, "failing-skill")
            (failing / "SKILL.md").write_text(
                "---\nname: failing-skill\ndescription: Test skill.\n---\n\n# Test\n中文，正文.\n",
                encoding="utf-8",
            )
            payload = self.style.check_skills([str(failing)])
            self.assertEqual("，", payload["violations"][0]["offending_character"])
            passing = write_skill(root, "passing-skill")
            (passing / "SKILL.md").write_text(
                "---\nname: passing-skill\ndescription: Test skill.\n---\n\n# Test\n"
                "中文,正文.\n`inline，code`\n> 外部引用，原文\n"
                "```text\n代码，示例\n```\n",
                encoding="utf-8",
            )
            payload = self.style.check_skills([str(passing)])
            self.assertEqual([], payload["violations"])

    def test_content_style_scans_agent_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="style-agent-") as temporary:
            skill = write_skill(Path(temporary), "metadata-skill")
            (skill / "agents" / "runtime.yml").write_text(
                'interface:\n  display_name: "界面，文本"\n', encoding="utf-8"
            )
            payload = self.style.check_skills([str(skill)])
        self.assertEqual("agents/runtime.yml", payload["violations"][0]["relative_path"])


if __name__ == "__main__":
    unittest.main()
