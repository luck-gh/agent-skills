from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
SKILL_ROOT = Path(__file__).resolve().parents[1]
def load_script(module_name: str, relative_path: str):
    path = SKILL_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
contract = load_script("candidate_contract_v1", "src/candidate_contract_v1.py")
collections = load_script("validate_collections", "src/validate_collections.py")
capture_plan = load_script("validation_capture_plan", "src/validate_note_plan.py")
capture_transaction = load_script("validation_capture_transaction", "src/transaction_executor.py")
PROFILES = ("plain-v1", "yaml-frontmatter-v1", "plain-halfwidth-zh-v1")
def seal_request(request: dict) -> dict:
    sealed = copy.deepcopy(request)
    sealed["request_digest"] = "0" * 64
    sealed["request_digest"] = contract.request_digest(sealed)
    return sealed
def valid_request() -> dict:
    return seal_request(
        {
            "schema": "capture-note-plan",
            "version": 1,
            "direction": "capture-to-markdown",
            "max_hops": 1,
            "request_id": "req-001",
            "scope": "notes/engineering",
            "items": [
                {
                    "item_id": "item-001",
                    "content": {
                        "title": "Validated pattern",
                        "body": "# Validated pattern\n\n完整内容。\n",
                        "frontmatter": [{"name": "title", "value": "Validated pattern"}],
                        "taxonomy": {"tags": ["testing"], "categories": ["engineering"]},
                        "resource_refs": [],
                    },
                    "evidence": [
                        {
                            "evidence_id": "evidence-001",
                            "kind": "tested-result",
                            "summary": "Sanitized verification summary.",
                        }
                    ],
                }
            ],
            "operations": [
                {
                    "operation_id": "operation-001",
                    "item_ids": ["item-001"],
                    "target": "notes/engineering/pattern.md",
                    "transform": ["body"],
                    "format_profile": "plain-halfwidth-zh-v1",
                }
            ],
            "request_digest": "0" * 64,
        }
    )
def valid_response(request: dict) -> dict:
    response = {
        "schema": "markdown-note-candidate",
        "version": 1,
        "direction": "markdown-to-capture",
        "max_hops": 1,
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "candidates": [
            {
                "operation_id": "operation-001",
                "item_ids": ["item-001"],
                "filename": "pattern.md",
                "frontmatter": [],
                "taxonomy": {"tags": [], "categories": []},
                "body": "# Validated pattern\n\n完整内容.\n",
                "resource_refs": [],
            }
        ],
        "candidate_digest": "0" * 64,
    }
    response["candidate_digest"] = contract.candidate_digest(response)
    return response
class CaptureWorkflowTests(unittest.TestCase):
    @staticmethod
    def request_and_response() -> tuple[dict, dict]:
        request = valid_request()
        request["operations"][0]["format_profile"] = "plain-v1"
        request = capture_plan.seal_request(request, ("plain-v1",))
        response = valid_response(request)
        return request, response
    def test_collection_contract_and_capture_markdown_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "notes/engineering").mkdir(parents=True)
            (root / "notes/private").mkdir()
            variables = {"collections": [{"id": "notes", "root": str(root),
                "scope": {"include": ["notes/engineering"], "exclude": ["notes/private"]},
                "format_profile": "plain-v1"}]}
            collection = collections.validate_variables(variables)[0]
            checked = collections.preflight_collection(collection, require_write=True)
            self.assertEqual((root / "notes/engineering",), checked.include)
            with self.assertRaises(collections.CollectionConfigurationError):
                collections.validate_variables({"collections": [{**variables["collections"][0],
                    "scope": {"include": ["notes/../private"], "exclude": []}}]}, check_locations=False)
            request, response = self.request_and_response()
            self.assertEqual(response, contract.validate_response(response, request, ("plain-v1",)))
            self.assertEqual(response, capture_plan.validate_response(response, request, ("plain-v1",)))
            plan, plan_digest = capture_plan.construct_write_plan(
                request=request, response=response,
                local_context={"plan_id": "plan-001", "collection_id": "notes",
                    "operation_intents": [{"operation_id": "operation-001",
                        "operation": "create", "before_hash": None}]},
                allowed_format_profiles=("plain-v1",))
            self.assertEqual(capture_transaction.digest(plan), plan_digest)
            self.assertNotIn("root", json.dumps(request))
    def test_create_transaction_is_verified_and_no_clobber(self) -> None:
        request, response = self.request_and_response()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "notes/engineering").mkdir(parents=True)
            collection = collections.CollectionConfig(
                "notes", str(root), ("notes/engineering",), (), "plain-v1")
            plan, plan_digest = capture_plan.construct_write_plan(
                request=request, response=response,
                local_context={"plan_id": "plan-001", "collection_id": "notes",
                    "operation_intents": [{"operation_id": "operation-001",
                        "operation": "create", "before_hash": None}]},
                allowed_format_profiles=("plain-v1",))
            context = capture_transaction.ExecutionContext(
                "notes", capture_transaction.root_fingerprint(str(root)), "notes/engineering",
                collection.include, collection.exclude)
            executor = capture_transaction.TransactionExecutor()
            first = executor.execute(plan=plan, write_plan_digest=plan_digest,
                collection=collection, context=context)
            self.assertEqual(("published", "verified"), (first[0].status, first[0].code))
            target = root / "notes/engineering/pattern.md"
            before = target.read_bytes()
            second = executor.execute(plan=plan, write_plan_digest=plan_digest,
                collection=collection, context=context)
            self.assertEqual(("conflict", "target-exists"), (second[0].status, second[0].code))
            self.assertEqual(before, target.read_bytes())

    def test_batch_create_uses_one_execution_context_without_item_approvals(self) -> None:
        request, response = self.request_and_response()
        request["items"].append({
            "item_id": "item-002",
            "content": {
                "title": "Second pattern",
                "body": "# Second pattern\n\n第二条完整内容。\n",
                "frontmatter": [{"name": "title", "value": "Second pattern"}],
                "taxonomy": {"tags": ["testing"], "categories": ["engineering"]},
                "resource_refs": [],
            },
            "evidence": [{
                "evidence_id": "evidence-002",
                "kind": "tested-result",
                "summary": "Second sanitized verification summary.",
            }],
        })
        request["operations"].append({
            "operation_id": "operation-002",
            "item_ids": ["item-002"],
            "target": "notes/engineering/second.md",
            "transform": ["body"],
            "format_profile": "plain-v1",
        })
        request = capture_plan.seal_request(request, ("plain-v1",))
        response["request_digest"] = request["request_digest"]
        response["candidates"].append({
            "operation_id": "operation-002",
            "item_ids": ["item-002"],
            "filename": "second.md",
            "frontmatter": [],
            "taxonomy": {"tags": [], "categories": []},
            "body": "# Second pattern\n\n第二条完整内容.\n",
            "resource_refs": [],
        })
        response["candidate_digest"] = "0" * 64
        response["candidate_digest"] = contract.candidate_digest(response)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "notes/engineering").mkdir(parents=True)
            collection = collections.CollectionConfig(
                "notes", str(root), ("notes/engineering",), (), "plain-v1")
            plan, plan_digest = capture_plan.construct_write_plan(
                request=request,
                response=response,
                local_context={
                    "plan_id": "plan-batch-001",
                    "collection_id": "notes",
                    "operation_intents": [
                        {"operation_id": "operation-001", "operation": "create",
                         "before_hash": None},
                        {"operation_id": "operation-002", "operation": "create",
                         "before_hash": None},
                    ],
                },
                allowed_format_profiles=("plain-v1",),
            )
            context = capture_transaction.ExecutionContext(
                "notes", capture_transaction.root_fingerprint(str(root)), "notes/engineering",
                collection.include, collection.exclude)
            results = capture_transaction.TransactionExecutor().execute(
                plan=plan,
                write_plan_digest=plan_digest,
                collection=collection,
                context=context,
            )
            self.assertEqual(
                [("published", "verified"), ("published", "verified")],
                [(result.status, result.code) for result in results],
            )
            self.assertTrue((root / "notes/engineering/pattern.md").is_file())
            self.assertTrue((root / "notes/engineering/second.md").is_file())

    def test_transport_contract_rejects_escape_authorization_and_digest_drift(self) -> None:
        expected = {
            "schema": "markdown-note-candidate",
            "version": 1,
            "direction": "markdown-to-capture",
            "max_hops": 1,
            "error": "invalid-contract-input",
        }
        self.assertEqual(expected, contract.fixed_error_response())
        cases = []
        escaped = valid_request()
        escaped["operations"][0]["target"] = "notes/../private.md"
        cases.append(seal_request(escaped))
        unauthorized = valid_request()
        unauthorized["items"][0]["evidence"][0]["authorization"] = "must-not-echo"
        cases.append(seal_request(unauthorized))
        drifted = valid_request()
        drifted["scope"] = "notes/changed"
        cases.append(drifted)
        for request in cases:
            with self.subTest(target=request.get("scope")), self.assertRaisesRegex(
                contract.ContractError, r"^invalid-contract-input$"
            ):
                contract.validate_request(request, PROFILES)

    def test_update_without_atomic_backend_is_explicitly_unsupported(self) -> None:
        request, response = self.request_and_response()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "notes/engineering/pattern.md"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"existing content\n")
            before = target.read_bytes()
            before_hash = hashlib.sha256(before).hexdigest()
            collection = collections.CollectionConfig(
                "notes", str(root), ("notes/engineering",), (), "plain-v1"
            )
            plan, plan_digest = capture_plan.construct_write_plan(
                request=request,
                response=response,
                local_context={
                    "plan_id": "plan-update-001",
                    "collection_id": "notes",
                    "operation_intents": [{
                        "operation_id": "operation-001",
                        "operation": "update",
                        "before_hash": before_hash,
                    }],
                },
                allowed_format_profiles=("plain-v1",),
            )
            context = capture_transaction.ExecutionContext(
                "notes",
                capture_transaction.root_fingerprint(str(root)),
                "notes/engineering",
                collection.include,
                collection.exclude,
            )
            result = capture_transaction.TransactionExecutor().execute(
                plan=plan,
                write_plan_digest=plan_digest,
                collection=collection,
                context=context,
            )
            self.assertEqual(("unsupported", "update-unsupported"),
                             (result[0].status, result[0].code))
            self.assertEqual(before, target.read_bytes())
if __name__ == "__main__":
    unittest.main()
