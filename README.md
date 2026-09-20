# AI model catalog

The public cloud-model catalog used by CHSharedKit apps. This repository is the
authoritative source for model IDs, display names, estimated prices, recommended
models, and retirement fallbacks. It contains no SDK source or credentials.

## Endpoint

`https://raw.githubusercontent.com/hechen/ai-model-catalog/main/cloud-model-catalog.json`

## Update models

1. Edit `cloud-model-catalog.json` using the provider's current API documentation.
2. Increase `revision` lexicographically (for example, `2026-09-20.2` to
   `2026-09-20.3`). Preserve the existing schema and supported model selections
   unless retiring a model. Do not use `.10` after `.9`: it sorts earlier.
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

## Catalog-defined providers (CHSharedKit 2.14.0+)

Apps adopt SDK 2.14.0 once. After that, adding providers using the supported
`openai-chat-completions` format needs only a catalog edit. The SDK registers
providers from its bundled/cached catalog at launch and reconciles them after
a successful refresh. Shared settings refresh once per process when opened;
hosts can also call `CHAICloudModelCatalog.shared.refreshIfNeeded()` at launch.
Users still choose the provider and enter their own key. App filters and
purchase/consent policies continue to apply.


### Compatibility and SDK updates

The catalog supports multiple providers, but runtime compatibility depends on
an implemented API adapter. CHSharedKit 2.14.0 supports these cases:

| Change | JSON only? | Requirement |
| --- | --- | --- |
| Add/update OpenAI or Claude models, prices, or retirement rules | Yes | The model must work with the existing built-in adapter. |
| Add a provider such as Grok using OpenAI-compatible Chat Completions | Yes | HTTPS, bearer API-key authentication, and the supported request/response format. |
| Add a provider using a native Anthropic Messages or another API format | No | Add a catalog runtime adapter to CHSharedKit first. Built-in Claude support does not make arbitrary Messages-compatible providers catalog-configurable. |
| Use OpenAI Responses, a different authentication scheme, or audio/tool-calling features | No | These are outside the current generic adapter and need SDK support. |

The generic adapter currently supports text, image input, and SSE text streaming;
each model must declare the capabilities it actually supports. An
“OpenAI-compatible” label alone is insufficient: the provider must support the
Chat Completions subset used by this adapter.

Each app must ship one update adopting SDK 2.14.0 and route requests through the
shared manager or an appropriate host bridge. After that, compatible additions
arrive on catalog refresh without another SDK or app release. Users still select
the provider and supply their own key. App capability filters, purchase gates,
and consent rules continue to apply; on-device-only apps do not expose cloud
providers.

When a new API adapter is implemented and shipped, later providers using that
supported format can also be added through JSON alone.

### Provider fields

Use the `xai` entry as a complete example. Provider fields:

- `id`: stable lowercase identifier; built-in IDs are reserved.
- `displayName`, `apiKeyURL`, `privacyPolicyURL`: settings copy and links.
- `api.format`: `openai-chat-completions`.
- `api.baseURL`: HTTPS API root, e.g. `https://api.x.ai/v1` (the SDK appends
  `/chat/completions`). No credentials, query, or fragment.
- `api.tokenLimitParameter`: `max_completion_tokens` or `max_tokens`, according
  to the API documentation. No temperature is sent.
- Each model's `capabilities`: `textInput`, optionally `visionInput` and
  `streaming`. Omitted capabilities default to text only. Unsupported
  capabilities are never advertised by the adapter.

The adapter uses bearer authentication, text/image Chat Completions, and SSE
text deltas. A different authentication scheme, native API format, or new
capability (tools, audio, etc.) requires SDK support first. Clients skip unknown
formats instead of attempting a request. Existing OpenAI/Claude adapters and
settings retain their behavior.

Keys are isolated by app, provider ID and API endpoint. Changing an endpoint
requires a new key entry; redirects are rejected. Withdrawn providers become
unavailable without silently selecting another cloud provider. Model selections
are per provider; missing/retired choices use the declared migration fallback.

The new fields are optional additions to schema 1. Older SDKs continue to read
OpenAI/Claude model updates but do not register new providers. Installed app
binaries need one release adopting 2.14.0 before this behavior is available.

Grok 4.6 was checked against the [official model documentation](https://docs.x.ai/developers/grok-4-6)
and [Chat Completions reference](https://docs.x.ai/developers/rest-api-reference/inference/chat-completions).
Prices express standard short-context rates; actual billing can differ.
