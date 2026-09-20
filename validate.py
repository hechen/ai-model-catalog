"""Validate the public catalog without third-party dependencies."""

import json
import math
import sys
from pathlib import Path


def validate(catalog):
    assert catalog["schemaVersion"] == 1, "Unsupported schema"
    assert isinstance(catalog["revision"], str) and catalog["revision"].strip(), "Missing revision"
    providers = catalog["providers"]
    assert {p["id"] for p in providers} >= {"openai", "claude"}, "Missing required provider"
    assert len({p["id"] for p in providers}) == len(providers), "Duplicate provider"
    for provider in providers:
        models = provider["models"]
        ids = [model["id"] for model in models]
        assert ids and len(set(ids)) == len(ids), "Empty or duplicate model list"
        assert provider["recommendedModelID"] in ids, "Missing recommended model"
        assert provider["migrationFallbackModelID"] in ids, "Missing fallback model"
        retired = provider["retiredModelIDs"]
        assert all(isinstance(value, str) and value for value in retired), "Invalid retired ID"
        assert not set(ids).intersection(retired), "Selectable model marked retired"
        for model in models:
            assert all(isinstance(model[key], str) and model[key].strip() for key in ("id", "name"))
            for key in ("inputPerMillion", "outputPerMillion", "imageInputPerMillion"):
                value = model[key]
                assert type(value) in (int, float) and math.isfinite(value) and value >= 0, "Invalid price"


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "cloud-model-catalog.json")
    catalog = json.loads(path.read_text())
    validate(catalog)
    print(f"Valid catalog: {catalog['revision']}")
