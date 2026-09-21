import copy
import json
from pathlib import Path
import tempfile
import unittest

from validate_offline import INT64_MAX, ValidationError, load, validate


ROOT = Path(__file__).resolve().parents[1]


class OfflineCatalogTests(unittest.TestCase):
    def setUp(self):
        # Contract fixture is independent of the published inventory so legitimate
        # JSON-only additions, retirements and evidence updates do not need edits
        # to Python tests merely to change model counts or verification status.
        self.catalog = {
            "schemaVersion": 1,
            "revision": 1,
            "models": [{
                "id": "test-model", "displayName": "Test model", "description": "Test candidate",
                "sizeBytes": 4, "quantization": "MLX-4bit",
                "downloadURL": "https://huggingface.co/example/test-model", "minRAM_GB": 4,
                "license": "MIT", "quality": "Balanced", "requiresAcknowledgment": False,
                "chatTemplate": "chatML", "languages": ["English"], "strengths": ["Text candidate"],
                "isCustom": False,
                "release": {
                    "repoID": "example/test-model", "revision": "a" * 40, "runtime": "mlx-text",
                    "modelType": "qwen2", "minimumRuntimeVersion": 1, "status": "active",
                    "files": [{"path": path, "sizeBytes": 1, "sha256": "b" * 64}
                              for path in ["config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors"]],
                    "recommendations": {"liftcoach": {
                        "score": 5, "reason": "Unverified candidate", "verification": "unverified"
                    }}
                }
            }]
        }
        self.model = self.catalog["models"][0]
        self.release = self.model["release"]

    def invalid(self):
        with self.assertRaises(ValidationError):
            validate(self.catalog)

    def test_pinned_catalog_validates(self):
        published = load(ROOT / "offline-model-catalog.json")
        validate(published)
        for model in published["models"]:
            self.assertEqual(model["sizeBytes"], sum(f["sizeBytes"] for f in model["release"]["files"]))

    def test_schema_and_revision_require_real_integers(self):
        for key, values in {"schemaVersion": [True, "1", 2, None], "revision": [True, "1", 0, -1, 1.5, INT64_MAX + 1]}.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    candidate = copy.deepcopy(self.catalog)
                    candidate[key] = value
                    with self.assertRaises(ValidationError):
                        validate(candidate)

    def test_revision_and_runtime_floor_can_advance(self):
        self.catalog["revision"] = 2
        self.release["minimumRuntimeVersion"] = 2
        validate(self.catalog)

    def test_all_required_model_fields(self):
        for key in self.model:
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.catalog)
                del candidate["models"][0][key]
                with self.assertRaises(ValidationError):
                    validate(candidate)

    def test_all_required_release_fields(self):
        for key in self.release:
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.catalog)
                del candidate["models"][0]["release"][key]
                with self.assertRaises(ValidationError):
                    validate(candidate)

    def test_duplicate_ids_are_rejected(self):
        self.catalog["models"].append(copy.deepcopy(self.model))
        self.invalid()

    def test_same_repo_can_have_distinct_profiles(self):
        other = copy.deepcopy(self.model)
        other["id"] += "-profile"
        self.catalog["models"].append(other)
        validate(self.catalog)

    def test_noncanonical_urls_are_rejected(self):
        repo = self.release["repoID"]
        for url in [f"http://huggingface.co/{repo}", f"https://huggingface.co.evil.test/{repo}",
                    f"https://user@huggingface.co/{repo}", f"https://huggingface.co:443/{repo}",
                    f"https://huggingface.co/{repo}?download=1", f"https://huggingface.co/{repo}#main",
                    f"https://huggingface.co/{repo}/", "https://huggingface.co/other/model"]:
            with self.subTest(url=url):
                self.model["downloadURL"] = url
                self.invalid()

    def test_repository_ids_cannot_escape_paths(self):
        for repo in ["../model", "org/../model", "org/model/extra", "org/%2e%2e", "org\\model", "org/name?x=1"]:
            with self.subTest(repo=repo):
                self.release["repoID"] = repo
                self.model["downloadURL"] = "https://huggingface.co/" + repo
                self.invalid()

    def test_revision_must_pin_full_commit(self):
        for revision in ["main", "v1.0", "a" * 39, "A" * 40, "g" * 40, None, 1]:
            with self.subTest(revision=revision):
                self.release["revision"] = revision
                self.invalid()

    def test_each_file_requires_sha256_not_git_blob_sha1(self):
        for digest in ["a" * 40, "A" * 64, "z" * 64, "", None, True]:
            with self.subTest(digest=digest):
                self.release["files"][0]["sha256"] = digest
                self.invalid()

    def test_unsafe_file_paths_are_rejected(self):
        for path in ["../config.json", "/config.json", "a/../../config.json", "./config.json",
                     "a//config.json", "a/", "a\\config.json", "C:config.json",
                     "%2e%2e/config.json", "%252e%252e/config.json", "config.json?x=1",
                     "config.json#fragment", "bad\x00.json", "bad\n.json", "bad name.json",
                     "配置.json", "a" * 513]:
            with self.subTest(path=path):
                self.release["files"][0]["path"] = path
                self.invalid()

    def test_safe_nested_and_license_files_are_allowed(self):
        self.release["files"].append({"path": "legal/LICENSE", "sizeBytes": 10, "sha256": "f" * 64})
        self.model["sizeBytes"] += 10
        validate(self.catalog)

    def test_duplicate_file_paths_are_rejected(self):
        file = copy.deepcopy(self.release["files"][0])
        self.release["files"].append(file)
        self.model["sizeBytes"] += file["sizeBytes"]
        self.invalid()

    def test_sizes_must_be_positive_int64_and_sum_exactly(self):
        for size in [True, 0, -1, 1.5, "20", INT64_MAX + 1]:
            with self.subTest(size=size):
                self.release["files"][0]["sizeBytes"] = size
                self.invalid()
        self.setUp()
        self.model["sizeBytes"] += 1
        self.invalid()

    def test_integer_metadata_rejects_bool(self):
        for container, key in [(self.model, "minRAM_GB"), (self.release, "minimumRuntimeVersion")]:
            prior = container[key]
            container[key] = True
            self.invalid()
            container[key] = prior

    def test_runtime_dependencies_are_required(self):
        for predicate in [lambda p: p == "config.json", lambda p: p in {"tokenizer.json", "tokenizer.model"},
                          lambda p: p.endswith(".safetensors")]:
            with self.subTest(predicate=predicate):
                candidate = copy.deepcopy(self.catalog)
                model = candidate["models"][0]
                model["release"]["files"] = [f for f in model["release"]["files"] if not predicate(f["path"])]
                model["sizeBytes"] = sum(f["sizeBytes"] for f in model["release"]["files"])
                with self.assertRaises(ValidationError):
                    validate(candidate)

    def test_tokenizer_configuration_is_required_even_when_total_size_matches(self):
        self.release["files"] = [file for file in self.release["files"] if file["path"] != "tokenizer_config.json"]
        self.model["sizeBytes"] = sum(file["sizeBytes"] for file in self.release["files"])
        with self.assertRaisesRegex(ValidationError, "missing tokenizer_config.json"):
            validate(self.catalog)

    def test_shipped_text_architectures_can_be_added_without_validator_changes(self):
        for model_type in ["qwen3", "gemma3_text", "mistral", "phi"]:
            with self.subTest(model_type=model_type):
                self.release["modelType"] = model_type
                validate(self.catalog)

    def test_inventory_limits_match_runtime(self):
        for index in range(256):
            model = copy.deepcopy(self.model)
            model["id"] = f"test-model-{index}"
            self.catalog["models"].append(model)
        self.invalid()
        self.setUp()
        self.release["files"].extend({"path": f"asset-{i}.json", "sizeBytes": 1, "sha256": "c" * 64}
                                     for i in range(509))
        self.model["sizeBytes"] = len(self.release["files"])
        self.invalid()

    def test_recommendation_scores_match_runtime_bounds(self):
        self.release["recommendations"]["liftcoach"]["score"] = 101
        self.invalid()

    def test_oversized_manifest_is_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "too-large.json"
            path.write_text(" " * 2_000_001)
            with self.assertRaisesRegex(ValidationError, "2 MB limit"):
                load(path)

    def test_unknown_runtime_model_type_and_status_are_rejected(self):
        for key, value in [("runtime", "mlx-vision"), ("modelType", "qwen2_vl"), ("status", "disabled")]:
            with self.subTest(key=key):
                prior = self.release[key]
                self.release[key] = value
                self.invalid()
                self.release[key] = prior

    def test_qwen_research_is_retired_with_acknowledgement(self):
        self.model["license"] = "Qwen Research"
        self.model["requiresAcknowledgment"] = True
        self.release["status"] = "retired"
        self.release["recommendations"]["liftcoach"]["score"] = 0
        validate(self.catalog)
        self.release["status"] = "active"
        self.invalid()

    def test_restricted_licenses_need_acknowledgement(self):
        for license in ["Llama Community", "Gemma ToU"]:
            with self.subTest(license=license):
                self.model["license"] = license
                self.model["requiresAcknowledgment"] = False
                self.invalid()

    def test_other_license_supports_future_catalog_only_additions(self):
        self.model["license"] = "Other"
        self.model["requiresAcknowledgment"] = True
        self.invalid()
        self.release["licenseName"] = "Example Model License"
        self.invalid()
        self.release["licenseURL"] = "https://example.org/model/LICENSE"
        validate(self.catalog)
        self.model["requiresAcknowledgment"] = False
        self.invalid()

    def test_other_license_rejects_unsafe_links(self):
        self.model["license"] = "Other"
        self.model["requiresAcknowledgment"] = True
        self.release["licenseName"] = "Example Model License"
        for url in ["http://example.org/LICENSE", "file:///tmp/LICENSE", "https://user:secret@example.org/LICENSE",
                    "https://example.org/LICENSE?token=secret", "https://example.org/LICENSE#terms"]:
            with self.subTest(url=url):
                self.release["licenseURL"] = url
                self.invalid()

    def test_recommendation_pass_requires_nonempty_evidence(self):
        rec = self.release["recommendations"]["liftcoach"]
        rec["verification"] = "passed"
        self.invalid()
        rec["evidence"] = "  "
        self.invalid()
        rec["evidence"] = "reports/liftcoach/runtime1-device-matrix.json"
        validate(self.catalog)

    def test_verification_is_not_inferred_from_score(self):
        rec = self.release["recommendations"]["liftcoach"]
        rec["score"] = 100
        validate(self.catalog)
        self.assertEqual(rec["verification"], "unverified")
        rec["verification"] = "recommended"
        self.invalid()

    def test_retired_recommendation_score_must_be_zero(self):
        self.release["status"] = "retired"
        self.invalid()
        for rec in self.release["recommendations"].values():
            rec["score"] = 0
        validate(self.catalog)

    def test_bad_enum_types_are_validation_errors(self):
        for key in ["license", "quality", "chatTemplate"]:
            prior = self.model[key]
            self.model[key] = []
            self.invalid()
            self.model[key] = prior

    def test_duplicate_json_object_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schemaVersion":1,"schemaVersion":2}')
            with self.assertRaisesRegex(ValidationError, "Duplicate JSON key"):
                load(path)


if __name__ == "__main__":
    unittest.main()
