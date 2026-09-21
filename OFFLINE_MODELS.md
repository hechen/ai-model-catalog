# Offline model catalog

`offline-model-catalog.json` describes pinned MLX text-model releases for the
CHSharedKit offline catalog runtime. It is separate from the cloud API catalog.
Its endpoint after publication is:

`https://raw.githubusercontent.com/hechen/ai-model-catalog/main/offline-model-catalog.json`

An app needs one update adopting the offline catalog runtime before it can use
this manifest. Older binaries with a static local-model list do not gain remote
refresh merely because the file exists. Model metadata refresh must not download
weights, change the user's selected model, or replace an installed model.

## What can change through JSON

Compatible model releases, display metadata, download retirement, and per-app
evaluation metadata can change through this catalog. A new architecture, runtime,
tokenizer implementation, quantization implementation, input modality, or model
feature that the installed MLX runtime cannot execute needs an SDK/app update.
`minimumRuntimeVersion` states that boundary; it does not install runtime code.

The initial runtime is `mlx-text`, version 1. Revision 1 of this catalog uses
model types `qwen2`, `llama`, `phi3`, and `gemma2`; the shipped MLX text registry
supports additional architectures, mirrored by `MODEL_TYPES` in the validator.
A compatible release using an already-shipped text architecture can be added
through JSON after its assets, license, and runtime requirements are checked.
Architecture registration is not evidence of successful inference. Qwen2-VL
belongs in a separately supported vision pipeline and is not a text-model
download candidate.

Clients should validate fresh metadata, keep the last valid cached manifest,
and use their bundled resource when no valid cache is available. Cache refresh
failure must not erase the previous valid catalog. A newer manifest only changes
available metadata; model installation remains an explicit user action. A
retired entry preserves stable IDs and existing-installation metadata while
disabling new catalog downloads. It does not delete an existing installation.

## Schema 1

The top level contains `schemaVersion: 1`, a positive integer `revision`, and a
nonempty `models` array. Unlike the cloud catalog's revision string, this revision
is numeric. Increment it for every published change; never reuse a revision with
different bytes or roll it backward.

The runtime limits a manifest to 2,000,000 bytes and 256 models, each containing
at most 512 files. Relative file paths are at most 512 UTF-8 bytes and contain
only ASCII letters, digits, periods, underscores, and hyphens in each component.
Empty, `.` and `..` path components are rejected. Every release must list
`config.json`, `tokenizer_config.json`, a `tokenizer.json` or `tokenizer.model`,
and its safetensors weights. Recommendation scores are integers from 0 to 100.

Each model includes the Codable `LocalModelInfo` fields: `id`, `displayName`,
`description`, `sizeBytes`, `quantization`, `downloadURL`, `minRAM_GB`, `license`,
`quality`, `requiresAcknowledgment`, `chatTemplate`, `languages`, `strengths`,
`isCustom: false`, and `release`. The legacy model-level `sha256` is optional and
omitted for these multi-file releases; integrity comes from each file digest.

`release` contains:

| Field | Meaning |
| --- | --- |
| `repoID` | Exact Hugging Face `owner/repository`; `downloadURL` must be its HTTPS homepage. |
| `revision` | Full lowercase 40-hex Git commit, never `main`, a branch, or a tag. |
| `runtime` | `mlx-text`. |
| `modelType` | A model architecture supported by that runtime. |
| `minimumRuntimeVersion` | Positive integer compatibility floor. |
| `status` | `active` or `retired`; retired models have recommendation score zero. |
| `files` | Complete required file inventory: canonical relative `path`, positive Int64 `sizeBytes`, and lowercase 64-hex `sha256`. |
| `recommendations` | Per-app `score`, `reason`, `verification`, and optional `evidence`. |
| `licenseName`, `licenseURL` | Optional named terms and HTTPS link; both are required when the model uses license `Other`. |

`sizeBytes` is the exact sum of the listed download files, including tokenizer
and configuration files. It is not an inference-memory estimate. `minRAM_GB`
retains the prior catalog's screening hint; device loading and memory behavior
still need measurement. A device passing this hint is not a runtime test result.
Legacy quality tiers and ranking scores are also retained metadata, not proof
that a model is best for an app.

The supported license labels are `Apache 2.0`, `MIT`, `Llama Community`,
`Gemma ToU`, `Qwen Research`, and `Other`. License-specific entries require the
existing acknowledgement flow. `Other` enables a legitimate new license to be
described with its name and terms link without extending a Swift enum, provided
the model otherwise works with the installed runtime. Do not use `Other` to hide
known restrictions or relabel Qwen Research as commercially unrestricted.

Verification is explicit:

- `unverified`: loading, inference, and app task quality are not established.
- `passed`: the app's required evaluation passed, with nonempty `evidence`
  identifying the report or its URL.
- `failed`: evaluated and did not meet the app's requirements.

A positive ranking score does not imply `passed`. The picker must not label an
unverified model as a verified recommendation. Record device, OS, SDK/runtime
version, model commit, test prompts, success/failure criteria, and relevant
quality/memory results in the evidence report before marking a release passed.

## Initial inventory and verification limits

Revision 1 was prepared on 2026-09-21 using the nine reachable text repositories
from the CHSharedKit 2.14.0 static catalog. Every file inventory is pinned to its
recorded commit. All app assessments are `unverified`; no weights were downloaded
and no model inference was run to prepare this manifest.

- Eight entries are active download candidates.
- Qwen 2.5 3B remains as retired metadata because its upstream
  [Qwen Research license](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE)
  requires separate commercial permission. It is not Apache 2.0. Its score is
  zero, its acknowledgement flag is on, and new catalog downloads are disabled.
- The inaccessible `mlx-community/SmolLM2-1.7B-Instruct-4bit` repository is omitted
  from new downloads. No replacement repository or license was guessed.
- Qwen2-VL is omitted because it requires a vision runtime.
- Gemma and Llama retain their specific license labels and require acknowledgement.

The 63 file records include all JSON and safetensors files at these pins plus
`tokenizer.model` when present. None of these revisions has a separate
`chat_template.jinja`; chat templates live in tokenizer configuration. A future
release that uses an external chat template must list it. No repository Python
implementation is downloaded or executed; the shipped MLX architecture registry
provides runtime code.

Hugging Face metadata was read through
`https://huggingface.co/api/models/{repoID}/revision/{commit}?blobs=true`.
Safetensors and other LFS objects use the API's SHA-256 and exact size. For ordinary
Git blobs, the bytes of small JSON files were fetched at the pinned commit,
checked against their Git blob SHA-1 and byte count, and hashed with SHA-256.
A Git blob SHA-1 is never placed in a SHA-256 field. There were 33 unique ordinary
blobs totaling 12,155,260 bytes; large tokenizer objects and weights were not
fetched. Runtime download verification must still compare the actual downloaded
file bytes to the manifest before marking a model installed.
Installation also performs a short runtime load/generation check, which is
separate from passing an app's task-quality evaluation. Model runtime cancellation
is cooperative; this catalog does not promise a hard inference deadline or
immediate cancellation of an uncooperative runtime operation.

## Updating a release

1. Confirm the exact upstream repository, its public accessibility, license,
   model type, and tokenizer/runtime requirements. Check upstream license terms;
   do not inherit an earlier catalog's label without checking it.
2. Resolve and pin a full commit. Enumerate every required runtime file and
   obtain SHA-256 and size using the procedure above. Include every shard named
   by `model.safetensors.index.json`, required tokenizer assets, and templates.
3. Preserve the stable model ID. Set the exact total size and runtime floor.
   Metadata refresh must not silently install the new commit over an existing
   user-selected release.
4. Mark new or changed app assessments `unverified` until evidence covers that
   exact model commit/runtime. Use `retired` and score zero to withdraw a catalog
   download while retaining existing-installation metadata.
5. Increase the manifest's integer revision. Validate both catalogs and tests:

   ```sh
   python3 validate.py
   python3 validate_offline.py
   python3 -m unittest discover -s tests -v
   ```

6. Review and publish the catalog change only when authorized. Verify the raw
   endpoint returns the intended revision after publication. Copy this
   authoritative manifest into the SDK's bundled resource when preparing an SDK
   release; keep this repository as the source of truth.

CI runs these checks without networking. Structural validation verifies schema,
safe paths/URLs, pins, digest shapes, totals, and evaluation metadata; it cannot
prove upstream availability, model output quality, license permission for a
particular use, or successful on-device inference.
