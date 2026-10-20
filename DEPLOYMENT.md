# Deployment preparation: protected synthetic MVP

Status: prepared changes, not deployed or newly runtime-verified. The user reports
having performed Supabase persistence tests. This work does not repeat or certify those tests.

## Approval boundary

No cloud resources, schema, RLS policies, production data, branches or deployments
were changed. Do not push, merge or deploy without explicit approval.

## Existing storage contract

Use the existing `public.batches` table with `batch_id`, `batch_data` (JSONB),
`created_at`, and `updated_at`. No migration is introduced. Patient fields,
commitments, source-page identifiers, review state, and document manifests stay
inside `batch_data`. The existing `updated_at` column protects against stale saves:
a conflicting writer receives HTTP 409 and must reload instead of overwriting review.

Original documents are private objects under generated batch/document identifiers.
The backend downloads them with its service-role credential after API authentication.
The browser receives a streamed response, not a public Supabase URL or service key.
Enable RLS and deny public/anonymous access to the table and bucket in the existing
project; deployment requires owner confirmation of these policies. The application
checks bucket privacy and schema access at startup but cannot certify RLS policies.
Service-role credentials bypass RLS and must remain backend-only.

Cloud mode requires Supabase credentials, a private existing bucket, explicit HTTPS
frontend origins and shared demo login credentials. It refuses a local-storage
fallback and restricts this cloud MVP to synthetic DEMO_MODE extraction. Render
must use cloud mode. A failed read/save produces a failure response, never a fake
successful save. Health checks perform read-only schema/bucket checks, not writes.
A successful health check proves reachability and privacy, not database write permissions.

## Environment variable names only

Backend required for the protected cloud demo:
- `DEPLOYMENT_MODE`
- `DEMO_MODE`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_BUCKET_NAME`
- `API_USERNAME`
- `API_PASSWORD`
- `CORS_ORIGINS`

Optional backend processing/runtime configuration:
- `PORT`
- `TEMP_STORAGE_PATH`
- `HYBRID_ENGINE_ENABLED`
- `HYBRID_ENABLE_PREPROCESSING`
- `HYBRID_ENABLE_OCR`
- `HYBRID_ENABLE_HYBRID_VERIFICATION`
- `HYBRID_ENABLE_FOCUSED_RETRY`

Frontend build-time configuration:
- `VITE_API_URL`

Configure values in hosting secret settings, never source control. CORS uses a JSON
array of exact frontend origins, not a comma-separated string. Do not expose the
service role, demo password, or extraction credentials through Vite environment variables.
The frontend asks for demo credentials and keeps them in browser memory, not localStorage.
A refresh requires sign-in again; the existing batch URL/local batch identifier can
then reload the persisted record. No credentials are added to document URLs.

## Deployment steps after approval

1. Review the persistence changes and approve the exact commit for release. Keep
   all unrelated test edits, PDFs, XLSX files, dumps, environment files and .agents out.
2. Confirm the existing Supabase table contract and private bucket/RLS configuration
   using the owner's prior evidence. No destructive migrations or public policies.
3. In Render, select the approved revision of `integration/final-mvp`; use the root
   `render.yaml`. Automatic deployment remains disabled. Backend Docker context is
   `backend`; frontend root is `frontend`.
4. Configure the backend variables above. Select cloud mode and synthetic demo mode,
   use a long random demo password (at least 16 characters), and configure exact HTTPS
   frontend CORS origins as a JSON array. Keep optional hybrid features disabled for
   this mock extraction demo. Use a single backend worker.
5. Configure the frontend API URL for the approved HTTPS backend endpoint.
6. Only after explicit deployment approval, manually deploy backend and frontend.
   Docker installs requirements, uses the host-provided port and disables access logs;
   frontend uses `npm ci && npm run build` and publishes `dist` with SPA routing.
7. Runtime sign-off/build validation for these new changes remains outstanding under
   the user's instruction not to run further tests or verification workflows.

## Remaining limitations before real medical use

This is a protected single-team synthetic demo, not a clinical production service.
Shared Basic authentication over HTTPS does not provide per-user or per-batch ownership,
MFA, a review audit ledger, or a clinical authorization model. Rate limiting, upload
abuse controls, retention/deletion policy, backups, monitoring and dependency locking
still require production review. Do not use real patient data.

Completed batches and originals use Supabase. Rendering/downloads and generated Excel
responses use disposable local files and can be regenerated. In-process jobs are not
a durable queue. A backend restart during queued/processing work needs manual recovery;
it never automatically re-extracts over human corrections. Existing legacy cloud records
without a document manifest need an explicit original-document import/recovery plan.
There is no automatic migration of local JSON/PDF files. Partial failed uploads may leave
unreferenced private objects; automatic cloud deletion is intentionally not introduced.
