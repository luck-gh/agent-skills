"""验证模型路由数据的边界、引用完整性和单一真源约束.

运行方式:python -X utf8 -B -m unittest discover -s tests -p "test_*.py" -v
"""

from __future__ import annotations

import json
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
    "unmapped_implicit",
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


def read_catalog() -> tuple[str, dict[str, object]]:
    raw = CATALOG_PATH.read_text(encoding="utf-8")
    return raw, json.loads(raw)


class ModelRoutingTests(unittest.TestCase):
    def test_catalog_is_canonical_and_schema_bounded(self) -> None:
        raw, catalog = read_catalog()

        self.assertEqual(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", raw)
        self.assertEqual(1, catalog["schema_version"])
        self.assertEqual(TOP_LEVEL_FIELDS, set(catalog))
        self.assertEqual(POLICY_FIELDS, set(catalog["selection_policy"]))
        for model in catalog["models"]:
            self.assertEqual(MODEL_FIELDS, set(model))
        for source in catalog["sources"]:
            self.assertEqual(SOURCE_FIELDS, set(source))

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
            self.assertNotIn(model["model_id"], other_text)
            self.assertNotIn(model["display_name"], other_text)


if __name__ == "__main__":
    unittest.main()
