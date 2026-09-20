# AI model catalog

The public cloud-model catalog used by CHSharedKit apps. This repository is the
authoritative source for model IDs, display names, estimated prices, recommended
models, and retirement fallbacks. It contains no SDK source or credentials.

## Endpoint

`https://raw.githubusercontent.com/hechen/ai-model-catalog/main/cloud-model-catalog.json`

## Update models

1. Edit `cloud-model-catalog.json` using the provider's current API documentation.
2. Increase `revision` using the sortable `YYYY-MM-DD.NN` format. Preserve the
   existing schema and supported model selections unless retiring a model.
3. Run `python3 validate.py` and push the change to `main`.

Routine model, pricing, and retirement updates do not require an SDK tag or app
release. A model that needs a new endpoint or request format still requires code
support before it is offered. The recommended model and migration fallback must
both be in the provider's model list.

CHSharedKit retains a bundled copy for offline startup. Refresh that resource
from this repository when preparing an SDK release; do not edit it as the live
catalog's source of truth.

## Compatibility with shipped apps

Older apps use `https://hechen.github.io/apps/closet/cloud-model-catalog.json`.
That URL remains available as a generated compatibility copy. The blog's Pages
workflow fetches this repository during builds and checks hourly for catalog
changes, deploying only when needed. The JSON is no longer maintained in the
blog repository. GitHub schedules can be delayed or disabled after 60 days of
repository inactivity. For immediate propagation or after such inactivity, run:

```sh
gh workflow run hugo.yml --repo hechen/hechen.github.io --ref master
```

Verify both URLs after deployment. No new cross-repository credential is needed.

## Format

`schemaVersion: 1` matches `CHAICloudModelCatalogManifest` in CHSharedKit. Prices
are USD per million tokens and are estimates for standard processing; the schema
does not express every cache, long-context, batch, or service-tier adjustment.

Clients validate downloaded data, retain the last valid cache, and fall back to
the SDK's bundled resource offline. Model availability remains account-specific.
