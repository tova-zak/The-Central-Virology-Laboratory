# Local real Gemini extraction

Prepared 2026-10-20 on integration/final-mvp. No live Gemini request was made.
Use synthetic documents until the institution explicitly authorizes medical-data
processing by this provider. API-key possession does not authorize sending patient data.

## Findings and minimum fix

Configuration alone was insufficient:
- Settings defaulted to the final-integration worktree-root .env, which is absent.
- The credential file found is the MAIN repository .env, not backend/.env.
- Pydantic's .env parsing does not export numbered keys to os.environ; the key manager
  previously read only os.environ and therefore missed file-loaded keys.
- The response_schema model used extra=allow and untyped dictionaries, emitting
  additionalProperties at the root and nested objects. Typed commitment entries and
  extra=ignore now omit the keyword for the existing SDK response_schema converter.
  This is a compatibility fix, not a claim that every newer JSON-schema endpoint
  forbids additionalProperties.

APP_ENV_FILE now explicitly selects a credential/config file. Without it the default
is still the current worktree-root .env. There is no implicit fallback to another
worktree, no credential copying, and no environment-file modification. Process
variables override file values. Restart the backend after changing keys or mode.

Supported application key names: GEMINI_API_KEY and GEMINI_API_1 through GEMINI_API_8.
These are deduplicated in memory; key values/prefixes are never logged or included in
key-object repr. Do not put keys in commands, screenshots, test fixtures or Git.

The configured GEMINI_MODEL is gemini-3.8-flash. Google's current model documentation
lists it as stable with image/PDF inputs and structured outputs. Account/project
access, actual quota, billing and live service availability remain unverified.
Custom temperature was removed because current Gemini 3.6+ guidance deprecates it.
See the official references below. No model listing or generation API was called.

## Local startup (does not itself send documents)

Run the backend in one PowerShell window. This explicitly uses the existing main
repository credential file, selects real extraction locally, and disables optional
hybrid features for this direct extraction path. It leaves Render settings unchanged.

```powershell
Set-Location -LiteralPath 'D:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration\backend'
$env:APP_ENV_FILE = 'D:\אקתון\The-Central-Virology-Laboratory\.env'
$env:DEPLOYMENT_MODE = 'local'
$env:DEMO_MODE = 'false'
$env:GEMINI_MODEL = 'gemini-3.8-flash'
$env:EXTRACTION_TIMEOUT_SECONDS = '300'
$env:CORS_ORIGINS = '["http://localhost:5173"]'
$env:HYBRID_ENGINE_ENABLED = 'false'
$env:HYBRID_ENABLE_PREPROCESSING = 'false'
$env:HYBRID_ENABLE_OCR = 'false'
$env:HYBRID_ENABLE_HYBRID_VERIFICATION = 'false'
$env:HYBRID_ENABLE_FOCUSED_RETRY = 'false'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second PowerShell window:

```powershell
Set-Location -LiteralPath 'D:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration\frontend'
$env:VITE_DEPLOYMENT_MODE = 'local'
$env:VITE_API_URL = 'http://localhost:8000'
npm run dev -- --host localhost --port 5173 --strictPort
```

Open http://localhost:5173. Starting these services alone makes no Gemini generation
request. Clicking Process on an uploaded document invokes the real provider. Do not
perform that action through an assistant without explicit live-call approval, and
use synthetic documents only until separate medical-data authorization is confirmed.
No UI opt-in or API key is treated as institutional privacy approval.

Storage selection remains unchanged: if the selected file configures Supabase,
the backend continues using it and requires the existing login settings. Otherwise
local JSON is used for local development. No Supabase connectivity test was repeated
in this task. Do not clear/change storage credentials merely to bypass an error.

To return to MockExtractor: stop the backend, change only DEMO_MODE to true in the
same PowerShell window, and restart the same uvicorn command. No key edits are needed.
The frontend mode label comes from backend health metadata.

## Failure behavior and preserved contracts

The existing Extractor/ExtractionResult contract remains the provider boundary for
future enterprise integration. There is no implicit switch to Vertex/enterprise;
the current adapter explicitly selects Gemini Developer API. A replacement provider
can implement the same abstraction without rewriting review/export/storage.

Provider failures become controlled ExtractionError metadata: invalid_credentials,
model_incompatible, schema_incompatible, daily_quota, rate_limit, request_rejected,
provider_timeout, provider_unavailable, invalid_response or extraction_failed. Raw
SDK exception bodies, responses and credentials are not returned as error text.
Persisted batch errors contain sanitized messages/codes and retry information.
Fatal credential/model/schema failures stop remaining calls for the batch. Quota
exhaustion and rate cooldowns do not trigger quota-bypass key rotation. Bounded
transient retries honor provider cooldowns; long delays return control for manual
retry. An outer worker timeout does not start an overlapping thread request.

The existing 5-per-minute and 20-per-day counters are local safety budgets, NOT
verified provider limits. Provider quotas are project-wide and model/tier-specific.
Generic 429/RESOURCE_EXHAUSTED is no longer classified as daily exhaustion without
an explicit daily indicator. Provider RetryInfo is preferred; a daily failure without
it receives a conservative local cooldown, not a claimed UTC-midnight reset time.
These in-memory guards are not a production distributed quota/accounting system.

### Safe network diagnostics

The subsequent transport-diagnostics revision replaces the custom direct IPv4
transport with HTTPX standard proxy/IP routing, retaining truststore certificate
and hostname verification. Standard process HTTPS_PROXY/HTTP_PROXY/ALL_PROXY and
NO_PROXY settings are honored; proxy values/credentials are never logged. Do not
assume the inspection shell and an already-running backend have the same environment.
The HTTPX connect/read/write/pool timeouts remain 60 seconds and the SDK timeout remains
60000 milliseconds. The background outer wait now defaults to 300 seconds, configurable
through EXTRACTION_TIMEOUT_SECONDS (30-600 seconds). These are different limits;
60 seconds is not a total processing deadline. The SDK AFC-enabled
message precedes the remote request and does not establish HTTP or extraction success.

Failures now retain safe diagnostics in the backend log and persisted batch errors:
exception class chain, HTTP status when available, numeric OS/certificate error codes,
and timeout phase. Raw exception text, request URLs, headers, response bodies and
medical contents remain withheld. Codes distinguish dns_error, tls_certificate_error,
tls_error, proxy_error, network_access_denied, connection_refused,
network_connection_failed, network_transport_error and provider_timeout. HTTP 5xx
uses provider_unavailable with the exact available status, rather than conflating it
with transport failures. Unknown causes remain unknown; classification does not prove
network filtering, proxy necessity or which IP family failed.

For batch_fd554e03ad41 the earlier provider_unavailable mapping discarded the original
cause and status. No matching local log/batch artifact or accessible terminal history
was available during inspection. Its exact historical network/API cause cannot be
reconstructed from the sanitized error and AFC/client-created lines. No new Gemini
call was made. A future explicitly approved synthetic request is needed to verify
connectivity and capture the new diagnostics; existing reviewed batches are not reprocessed.

### Confirmed premature worker timeout: batch_c9c1ed480a99

The owner's timestamped logs show extraction starting at 19:47:28.195 on 2026-10-20,
the SDK call starting at 19:47:29.285, the worker expiring at 19:48:58.202, and HTTP 200
at 19:51:00.153. The adapter reported 210873.5ms for the API call and successful JSON
parsing. A read-only lookup of this batch's status/error metadata confirmed the stored
worker-timeout message with empty diagnostics. The old 90-second worker guard cancelled
the waiting future, not its synchronous HTTP thread, so the later response had no
consumer. It could not replace the already-persisted missing-field record.

Only the worker deadline is increased to a bounded default of 300 seconds, covering
the observed approximately 212-second extraction. HTTPX/SDK limits, retry counts,
TLS/proxy routing, model, Supabase, approval/export controls and reviewed values are
unchanged. Worker timeout errors now retain timeout_layer=worker, limit, elapsed time
and attempt; HTTPX timeout errors identify their own layer and phase. Genuinely late
responses are still not written over completed batches or human review. The previous
HTTP 503 in the supplied logs belongs to a different batch; it is not the outcome of
this batch. Proxy/filtering/model latency is not diagnosed from these timestamps.

Focused offline regressions reproduce the earlier rejection and successful delivery
within the new bound using a validated in-memory SDK response, check deadline bounds,
and ensure worker versus HTTPX metadata stays distinct. No new Gemini call was made.
Restart the backend with the setting above; do not reprocess an existing reviewed
batch. A fresh synthetic extraction still needs explicit live-call approval before
an assistant runs it. HTTP 200 and parsing do not prove source-field accuracy.

A failed page produces a missing/manual-review commitment rather than fabricated
patient values. Accepted source pages remain represented once each. Existing raw,
normalized and reviewed patient fields, manual corrections, persistence and Excel
mapping are preserved. Required missing/unreviewed fields still block export.
Reprocessing existing records remains prohibited to protect human-reviewed values.

The subsequent restricted-staging revision introduces DEPLOYMENT_MODE=staging-real
with DEMO_MODE=false; see DEPLOYMENT.md for Render instructions. Staging/cloud mock
mode still requires DEMO_MODE=true. Hosted Gemini keys come exclusively from backend
environment variables, never APP_ENV_FILE. Clinical production remains blocked;
production security gates, RLS and database schema are unchanged.

## Verification

21 focused offline tests passed using the installed google-genai SDK, an in-memory
HTTP MockTransport and blocked outbound socket/real HTTP transport access. Only
Windows asyncio internal loopback socketpair construction is permitted by the guard. They cover actual
SDK schema serialization, patient field contracts, malformed responses, auth/model/
schema/quota/service failures, timeout sanitization, key-file/process precedence,
secret-safe logging/repr, bounded background retries, one commitment per page,
and hosted security guards. No live connectivity/credential
validity or extraction-quality claim is made. No broad/E2E campaign was run.

A separate no-network configuration inspection explicitly selected the actual main
repository .env and initialized GeminiExtractor with DEMO_MODE disabled. It loaded
nine distinct credentials in memory without constructing an API client or exposing
any values. This proves configuration selection only, not that those keys are valid.

This change set contains six backend source files, one focused offline test module
and this guide. Existing unrelated edits/artifacts remain untouched. No push, merge,
deployment, live Supabase change or Gemini API call occurred.

## Official references

- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/troubleshooting
- https://ai.google.dev/gemini-api/docs/rate-limits

## GEMINI_FORCE_IPV4 (IPv6 black-holed networks)

Diagnosed 2026-10-21: DNS returns 8 IPv6 then 8 IPv4 addresses for generativelanguage.googleapis.com; all IPv6 connects timed out
(3 s each) while IPv4 connected in ~7 ms. httpx tries addresses in order with a full timeout each, so requests stalled in the TCP connect
phase. A text-only request over IPv4 returned HTTP 200 (TCP 0.09 s, TLS 0.10 s).

Set `GEMINI_FORCE_IPV4=true` (default `false`) to bind the Gemini client to IPv4 (`local_address=0.0.0.0`). TLS verification still
uses the truststore context and timeouts/retries are unchanged. Limitation: a custom httpx transport bypasses automatic proxy
discovery (HTTP_PROXY/HTTPS_PROXY/system proxy); leave it `false` behind a proxy. Windows network settings are not modified.