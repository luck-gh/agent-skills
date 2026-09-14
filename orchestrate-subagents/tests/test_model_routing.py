"""验证模型路由数据的边界、引用完整性和单一真源约束.

运行方式:python -X utf8 -B -m unittest discover -s tests -p "test_*.py" -v
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = SKILL_ROOT / "references" / "model-routing.json"

TOP_LEVEL_FIELDS = {"schema_version", "selection_policy", "models", "sources"}
POLICY_FIELDS = {
    "mapping_role",
    "availability_gate",
    "supported_explicit_unmapped",
    "unsupported_explicit",
    "unmapped_automatic",
}
MODEL_FIELDS = {
    "model_id",
    "display_name",
    "default_level_id",
    "task_profile_ids",
    "default_reasoning_profile_id",
    "availability",
    "source_ids",
}
SOURCE_FIELDS = {"source_id", "kind", "location"}
REASONING_PROFILES = {"light", "balanced", "deep", "exceptional"}
MODEL_ID_PATTERN = re.compile(
    r"(?<![a-z0-9])gpt-\d+(?:\.\d+)*(?:-[a-z][a-z0-9]*)*(?![a-z0-9-])",
    re.IGNORECASE,
)


def read_catalog() -> tuple[str, dict[str, object]]:
    raw = CATALOG_PATH.read_text(encoding="utf-8")
    return raw, json.loads(raw)


def find_model_ids(text: str) -> set[str]:
    """找出正文中符合当前模型 ID 形态的名称."""

    return {match.group(0).lower() for match in MODEL_ID_PATTERN.finditer(text)}


def find_unregistered_model_ids(text: str, registered_ids: set[str]) -> set[str]:
    """找出正文中符合模型 ID 形态但未在目录登记的名称."""

    return find_model_ids(text) - {model_id.lower() for model_id in registered_ids}


class ModelRoutingTests(unittest.TestCase):
    def test_catalog_is_canonical_and_schema_bounded(self) -> None:
        raw, catalog = read_catalog()

        self.assertEqual(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", raw)
        self.assertEqual(2, catalog["schema_version"])
        self.assertEqual(TOP_LEVEL_FIELDS, set(catalog))
        self.assertEqual(POLICY_FIELDS, set(catalog["selection_policy"]))
        for model in catalog["models"]:
            self.assertEqual(MODEL_FIELDS, set(model))
        for source in catalog["sources"]:
            self.assertEqual(SOURCE_FIELDS, set(source))

    def test_policy_keeps_runtime_gate_and_explicit_choice(self) -> None:
        _, catalog = read_catalog()
        self.assertEqual(
            {
                "mapping_role": "advisory_for_automatic_selection",
                "availability_gate": "current_tool_schema",
                "supported_explicit_unmapped": "allowed",
                "unsupported_explicit": "refused",
                "unmapped_automatic": "omitted",
            },
            catalog["selection_policy"],
        )

    def test_profiles_are_declared_and_have_candidates(self) -> None:
        _, catalog = read_catalog()
        guidance = (SKILL_ROOT / "references" / "model-selection.md").read_text(encoding="utf-8")
        declared = set(re.findall(r"^- `([a-z]+(?:-[a-z]+)+)`:", guidance, re.MULTILINE))
        mapped = {profile for model in catalog["models"] for profile in model["task_profile_ids"]}
        self.assertTrue(declared)
        self.assertEqual(declared, mapped)

    def test_focused_changes_do_not_depend_on_one_model(self) -> None:
        _, catalog = read_catalog()
        candidates = [
            model for model in catalog["models"]
            if model["default_level_id"] == "L2"
            and "targeted-code-change" in model["task_profile_ids"]
        ]
        self.assertGreaterEqual(len(candidates), 2)
        for unavailable in candidates:
            remaining = [model for model in candidates if model["model_id"] != unavailable["model_id"]]
            self.assertTrue(remaining)

    def test_mappings_cover_levels_and_reference_declared_sources(self) -> None:
        _, catalog = read_catalog()
        models = catalog["models"]
        sources = catalog["sources"]
        model_ids = [model["model_id"] for model in models]
        display_names = [model["display_name"] for model in models]
        source_ids = [source["source_id"] for source in sources]

        self.assertEqual(len(model_ids), len(set(model_ids)))
        self.assertEqual(len(display_names), len(set(display_names)))
        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertEqual({"L1", "L2", "L3", "L4"}, {model["default_level_id"] for model in models})
        for model in models:
            self.assertEqual("schema-gated", model["availability"])
            self.assertTrue(model["task_profile_ids"])
            self.assertTrue(model["source_ids"])
            self.assertTrue(set(model["source_ids"]).issubset(source_ids))
            self.assertIn(model["default_reasoning_profile_id"], REASONING_PROFILES)

    def test_concrete_model_names_exist_only_in_catalog(self) -> None:
        _, catalog = read_catalog()
        other_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in SKILL_ROOT.rglob("*")
            if path.is_file()
            and path != CATALOG_PATH
            and path.suffix.lower() in {".md", ".py", ".toml", ".yaml", ".yml"}
        )

        for model in catalog["models"]:
            self.assertNotIn(model["display_name"], other_text)

        registered_ids = {model["model_id"] for model in catalog["models"]}
        self.assertEqual(set(), find_model_ids(other_text))
        self.assertEqual(set(), find_unregistered_model_ids(other_text, registered_ids))

    def test_unregistered_model_id_shape_is_detected(self) -> None:
        _, catalog = read_catalog()
        registered_ids = {model["model_id"] for model in catalog["models"]}
        known_id = next(iter(registered_ids))
        unknown_id = "-".join(("gpt", "999.9", "unlisted"))

        self.assertEqual({known_id, unknown_id}, find_model_ids(f"{known_id} {unknown_id}"))
        self.assertEqual(
            {unknown_id},
            find_unregistered_model_ids(f"{known_id} {unknown_id}", registered_ids),
        )
        self.assertEqual(set(), find_unregistered_model_ids("generic model guidance", registered_ids))


if __name__ == "__main__":
    unittest.main()
