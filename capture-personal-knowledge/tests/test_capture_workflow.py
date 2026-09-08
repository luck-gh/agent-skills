from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
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
            checked = collections.preflight_collection(
                collection, write_scope="notes/engineering")
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

    def test_excluded_target_uses_current_os_case_semantics(self) -> None:
        for directory in ("private", "PRIVATE", "private-other"):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "notes/private").mkdir(parents=True)
                (root / "notes" / directory).mkdir(exist_ok=True)
                request, response = self.request_and_response()
                request["scope"] = "notes"
                request["operations"][0]["target"] = f"notes/{directory}/pattern.md"
                request = capture_plan.seal_request(request, ("plain-v1",))
                response = valid_response(request)
                collection = collections.CollectionConfig(
                    "notes", str(root), ("notes",), ("notes/private",), "plain-v1")
                plan, plan_digest = capture_plan.construct_write_plan(
                    request=request, response=response,
                    local_context={"plan_id": "plan-case-001", "collection_id": "notes",
                        "operation_intents": [{"operation_id": "operation-001",
                            "operation": "create", "before_hash": None}]},
                    allowed_format_profiles=("plain-v1",))
                context = capture_transaction.ExecutionContext(
                    "notes", capture_transaction.root_fingerprint(str(root)), "notes",
                    collection.include, collection.exclude)
                result = capture_transaction.TransactionExecutor().execute(
                    plan=plan, write_plan_digest=plan_digest,
                    collection=collection, context=context)[0]
                blocked = os.path.normcase(directory) == os.path.normcase("private")
                expected = ("unknown", "operation-binding-invalid") if blocked else (
                    "published", "verified")
                self.assertEqual(expected, (result.status, result.code))
                self.assertEqual(not blocked, (root / "notes" / directory / "pattern.md").exists())
                self.assertFalse((root / "notes/private/pattern.md").exists())

    def test_write_preflight_limits_permissions_to_target_parent(self) -> None:
        for denied in ("unrelated-write", "target-write", "excluded-read", "root-traverse"):
            with self.subTest(denied=denied), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target_parent = root / "notes/engineering"
                target_parent.mkdir(parents=True)
                (root / "notes/reference").mkdir()
                excluded = root / "notes/private"
                excluded.mkdir()
                request, response = self.request_and_response()
                collection = collections.CollectionConfig(
                    "notes", str(root), ("notes/engineering", "notes/reference"),
                    ("notes/private",), "plain-v1")
                plan, plan_digest = capture_plan.construct_write_plan(
                    request=request, response=response,
                    local_context={"plan_id": "plan-access-001", "collection_id": "notes",
                        "operation_intents": [{"operation_id": "operation-001",
                            "operation": "create", "before_hash": None}]},
                    allowed_format_profiles=("plain-v1",))
                context = capture_transaction.ExecutionContext(
                    "notes", capture_transaction.root_fingerprint(str(root)), "notes/engineering",
                    collection.include, collection.exclude)
                original_access = os.access

                def access(path, mode, *args, **kwargs):
                    if denied == "unrelated-write" and mode & os.W_OK and Path(path) != target_parent:
                        return False
                    if denied == "target-write" and mode & os.W_OK and Path(path) == target_parent:
                        return False
                    if denied == "excluded-read" and mode & os.R_OK and Path(path) == excluded:
                        return False
                    if denied == "root-traverse" and mode & os.X_OK and Path(path) == root:
                        return False
                    return original_access(path, mode, *args, **kwargs)

                with patch.object(collections.os, "access", side_effect=access):
                    result = capture_transaction.TransactionExecutor().execute(
                        plan=plan, write_plan_digest=plan_digest,
                        collection=collection, context=context)[0]
                allowed = denied == "unrelated-write"
                expected = ("published", "verified") if allowed else (
                    "unknown", "collection-location-unavailable")
                self.assertEqual(expected, (result.status, result.code))
                self.assertEqual(allowed, (target_parent / "pattern.md").exists())

    @unittest.skipUnless(os.name == "nt", "Windows 8.3 path aliases require Windows")
    def test_windows_short_directory_alias_cannot_bypass_exclude(self) -> None:
        import ctypes

        short_path = ctypes.windll.kernel32.GetShortPathNameW
        short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        short_path.restype = ctypes.c_uint
        for excluded_name in ("long", "short", "sibling"):
            with self.subTest(excluded_name=excluded_name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = root / "notes/private-long-name"
                directory.mkdir(parents=True)
                (root / "notes/other").mkdir()
                buffer = ctypes.create_unicode_buffer(32768)
                size = short_path(str(directory), buffer, len(buffer))
                if not size or size >= len(buffer):
                    self.skipTest("GetShortPathNameW is unavailable for the isolated fixture")
                alias = Path(buffer.value).name
                if os.path.normcase(alias) == os.path.normcase(directory.name):
                    self.skipTest("The temporary volume does not generate 8.3 aliases")
                exclude = directory.name if excluded_name == "long" else (
                    alias if excluded_name == "short" else "other")
                target_directory = directory.name if excluded_name == "short" else alias
                request, response = self.request_and_response()
                request["scope"] = "notes"
                request["operations"][0]["target"] = f"notes/{target_directory}/pattern.md"
                request = capture_plan.seal_request(request, ("plain-v1",))
                response = valid_response(request)
                collection = collections.CollectionConfig(
                    "notes", str(root), ("notes",), (f"notes/{exclude}",), "plain-v1")
                plan, plan_digest = capture_plan.construct_write_plan(
                    request=request, response=response,
                    local_context={"plan_id": "plan-alias-001", "collection_id": "notes",
                        "operation_intents": [{"operation_id": "operation-001",
                            "operation": "create", "before_hash": None}]},
                    allowed_format_profiles=("plain-v1",))
                context = capture_transaction.ExecutionContext(
                    "notes", capture_transaction.root_fingerprint(str(root)), "notes",
                    collection.include, collection.exclude)
                result = capture_transaction.TransactionExecutor().execute(
                    plan=plan, write_plan_digest=plan_digest,
                    collection=collection, context=context)[0]
                allowed = excluded_name == "sibling"
                expected = ("published", "verified") if allowed else (
                    "unknown", "collection-location-unavailable")
                self.assertEqual(expected, (result.status, result.code))
                self.assertEqual(allowed, (directory / "pattern.md").exists())
                self.assertFalse(list(root.rglob(".capture-*.tmp")))

    def test_canonical_preflight_rejects_resolved_alias_into_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            excluded = root / "notes/private-long-name"
            alias = root / "notes/alias"
            excluded.mkdir(parents=True)
            alias.mkdir()
            collection = collections.CollectionConfig(
                "notes", str(root), ("notes",), ("notes/private-long-name",), "plain-v1")
            original_realpath = os.path.realpath

            def realpath(path, *args, **kwargs):
                resolved = Path(original_realpath(path, *args, **kwargs))
                if resolved.is_relative_to(alias):
                    return str(excluded / resolved.relative_to(alias))
                return str(resolved)

            with patch.object(collections.os.path, "realpath", side_effect=realpath):
                with self.assertRaises(collections.CollectionConfigurationError):
                    collections.preflight_collection(collection, write_scope="notes/alias")
            self.assertFalse(list(root.rglob("*.md")))

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
