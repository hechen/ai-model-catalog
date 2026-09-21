"""Validate pinned offline-model releases without network or third-party packages."""

import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


INT64_MAX = 2**63 - 1
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
REPO_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z")
LICENSES = {"Apache 2.0", "MIT", "Llama Community", "Gemma ToU", "Qwen Research", "Other"}
QUALITIES = {"Fast", "Balanced", "Higher Quality", "Highest Quality"}
# Runtime 1's shipped MLXLLM 3.31.3 text registry. Metadata availability does
# not establish that a particular release loads or meets an app's quality bar.
MODEL_TYPES = {
    "mistral", "llama", "phi", "phi3", "phimoe", "gemma", "gemma2", "gemma3", "gemma3_text", "gemma3n",
    "gemma4", "gemma4_text", "qwen2", "qwen3", "qwen3_moe", "qwen3_next", "qwen3_5", "qwen3_5_moe",
    "qwen3_5_text", "minicpm", "starcoder2", "cohere", "openelm", "internlm2", "deepseek_v3", "granite",
    "granitemoehybrid", "mimo", "mimo_v2_flash", "minimax", "glm4", "glm4_moe", "glm4_moe_lite",
    "acereason", "falcon_h1", "bitnet", "smollm3", "ernie4_5", "lfm2", "baichuan_m1", "exaone4",
    "gpt_oss", "lille-130m", "olmoe", "olmo2", "olmo3", "bailing_moe", "lfm2_moe", "nanochat",
    "nemotron_h", "afmoe", "jamba_3b", "mistral3", "apertus",
}


class ValidationError(ValueError):
    """A manifest does not satisfy the supported offline catalog contract."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def object_value(value, label):
    require(isinstance(value, dict), f"{label}: expected object")
    return value


def string(value, label):
    require(isinstance(value, str) and value.strip(), f"{label}: expected nonempty string")
    return value


def choice(value, choices, label):
    require(isinstance(value, str) and value in choices, f"{label}: unsupported value")


def integer(value, label, minimum=1):
    # bool is an int subclass; accepting true for sizes/revisions breaks Codable.
    require(type(value) is int and minimum <= value <= INT64_MAX,
            f"{label}: expected integer in {minimum}...{INT64_MAX}")
    return value


def string_list(value, label):
    require(isinstance(value, list), f"{label}: expected array")
    for item in value:
        string(item, label)
    require(len(set(value)) == len(value), f"{label}: duplicate value")


def safe_path(value, label):
    path = string(value, label)
    # Canonical relative URL/file paths only: reject traversal, encoded variants,
    # URL syntax, Windows separators/drives, empty components and control chars.
    require(len(path.encode("utf-8")) <= 512
            and all(part not in {"", ".", ".."} and re.fullmatch(r"[A-Za-z0-9._-]+", part)
                    for part in path.split("/")),
            f"{label}: unsafe relative path")
    return path


def validate(catalog):
    object_value(catalog, "catalog")
    require(type(catalog.get("schemaVersion")) is int and catalog["schemaVersion"] == 1,
            "schemaVersion: unsupported schema")
    integer(catalog.get("revision"), "revision")
    models = catalog.get("models")
    require(isinstance(models, list) and 1 <= len(models) <= 256, "models: expected 1...256 models")
    model_ids = set()
    for model in models:
        object_value(model, "model")
        model_id = string(model.get("id"), "model.id")
        require(IDENTIFIER.fullmatch(model_id), f"{model_id}: invalid model ID")
        require(model_id not in model_ids, f"{model_id}: duplicate model ID")
        model_ids.add(model_id)
        for key in ("displayName", "description", "quantization"):
            string(model.get(key), f"{model_id}.{key}")
        size = integer(model.get("sizeBytes"), f"{model_id}.sizeBytes")
        integer(model.get("minRAM_GB"), f"{model_id}.minRAM_GB")
        choice(model.get("license"), LICENSES, f"{model_id}.license")
        choice(model.get("quality"), QUALITIES, f"{model_id}.quality")
        require(type(model.get("requiresAcknowledgment")) is bool,
                f"{model_id}: requiresAcknowledgment must be boolean")
        if model["license"] in {"Llama Community", "Gemma ToU", "Qwen Research", "Other"}:
            require(model["requiresAcknowledgment"], f"{model_id}: license acknowledgement required")
        choice(model.get("chatTemplate"), {"chatML", "llama3", "gemma"}, f"{model_id}.chatTemplate")
        for key in ("languages", "strengths"):
            string_list(model.get(key), f"{model_id}.{key}")
        require(model.get("isCustom") is False, f"{model_id}: catalog model cannot be custom")
        if model.get("sha256") is not None:
            require(isinstance(model["sha256"], str) and HEX64.fullmatch(model["sha256"]),
                    f"{model_id}: invalid legacy sha256")

        release = object_value(model.get("release"), f"{model_id}.release")
        if "licenseName" in release or model["license"] == "Other":
            string(release.get("licenseName"), f"{model_id}.licenseName")
        if "licenseURL" in release or model["license"] == "Other":
            license_url = urlsplit(string(release.get("licenseURL"), f"{model_id}.licenseURL"))
            require(license_url.scheme == "https" and license_url.hostname
                    and not (license_url.username or license_url.password or license_url.query or license_url.fragment),
                    f"{model_id}: licenseURL must be HTTPS without credentials, query, or fragment")
        repo = string(release.get("repoID"), f"{model_id}.repoID")
        require(REPO_ID.fullmatch(repo), f"{model_id}: invalid repository ID")
        url = urlsplit(string(model.get("downloadURL"), f"{model_id}.downloadURL"))
        require(url.scheme == "https" and url.netloc == "huggingface.co"
                and url.path == f"/{repo}" and not url.query and not url.fragment,
                f"{model_id}: downloadURL must be the exact HTTPS Hugging Face repo homepage")
        revision = release.get("revision")
        require(isinstance(revision, str) and HEX40.fullmatch(revision),
                f"{model_id}: release must pin a full lowercase 40-hex commit")
        require(release.get("runtime") == "mlx-text", f"{model_id}: unsupported runtime")
        choice(release.get("modelType"), MODEL_TYPES, f"{model_id}.modelType")
        integer(release.get("minimumRuntimeVersion"), f"{model_id}.minimumRuntimeVersion")
        choice(release.get("status"), {"active", "retired"}, f"{model_id}.status")
        if model["license"] == "Qwen Research":
            require(release["status"] == "retired",
                    f"{model_id}: Qwen Research is retained only as retired installation metadata")

        files = release.get("files")
        require(isinstance(files, list) and 1 <= len(files) <= 512, f"{model_id}: expected 1...512 files")
        paths = set()
        total = 0
        for file in files:
            object_value(file, f"{model_id}.file")
            path = safe_path(file.get("path"), f"{model_id}.file.path")
            require(path not in paths, f"{model_id}: duplicate file path {path}")
            paths.add(path)
            total += integer(file.get("sizeBytes"), f"{model_id}.{path}.sizeBytes")
            digest = file.get("sha256")
            require(isinstance(digest, str) and HEX64.fullmatch(digest),
                    f"{model_id}.{path}: expected lowercase SHA-256, not a Git SHA-1")
        require(total == size, f"{model_id}: sizeBytes must equal the exact file-size sum")
        require("config.json" in paths, f"{model_id}: missing config.json")
        require("tokenizer_config.json" in paths, f"{model_id}: missing tokenizer_config.json")
        require({"tokenizer.json", "tokenizer.model"} & paths, f"{model_id}: missing tokenizer")
        require(any(path.endswith(".safetensors") for path in paths), f"{model_id}: missing weights")

        recommendations = object_value(release.get("recommendations"), f"{model_id}.recommendations")
        require("liftcoach" in recommendations, f"{model_id}: missing LiftCoach assessment")
        for app, recommendation in recommendations.items():
            require(isinstance(app, str) and IDENTIFIER.fullmatch(app), f"{model_id}: invalid app ID")
            object_value(recommendation, f"{model_id}.{app}")
            score = integer(recommendation.get("score"), f"{model_id}.{app}.score", minimum=0)
            require(score <= 100, f"{model_id}.{app}: recommendation score must be 0...100")
            string(recommendation.get("reason"), f"{model_id}.{app}.reason")
            verification = recommendation.get("verification")
            choice(verification, {"unverified", "passed", "failed"}, f"{model_id}.{app}.verification")
            if "evidence" in recommendation:
                string(recommendation["evidence"], f"{model_id}.{app}.evidence")
            if verification == "passed":
                string(recommendation.get("evidence"), f"{model_id}.{app}: passed requires evidence")
            if release["status"] == "retired":
                require(score == 0, f"{model_id}.{app}: retired release cannot retain a recommendation score")


def load(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    data = Path(path).read_bytes()
    require(len(data) <= 2_000_000, "Catalog exceeds runtime's 2 MB limit")
    return json.loads(data, object_pairs_hook=unique_keys)


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "offline-model-catalog.json")
    try:
        catalog = load(path)
        validate(catalog)
    except (OSError, ValueError, TypeError) as error:
        print(f"Invalid offline catalog: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"Valid offline catalog: revision {catalog['revision']}, {len(catalog['models'])} models")
