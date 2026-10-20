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
