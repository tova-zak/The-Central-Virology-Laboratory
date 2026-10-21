# Cloud deploy handoff: technical findings (read-only investigation)

Worktree: `.worktrees/deploy-handoff`, branch `docs/deploy-handoff`, HEAD `78ba786` = origin/main (merge of PR #2).
No application code changed. No commit/push/merge. No network calls to Supabase, Gemini or Render. No `.env` / `frontend/.env.local` values read (only `.env.example` and `render.yaml`).

## Readiness matrix

| # | Area | Status | One-line reason |
|---|------|--------|-----------------|
| 1 | render.yaml + validator | READY | Both services on `main`, free, autoDeploy off, all secrets `sync:false`; validator exit 0 |
| 2 | Dockerfile + frontend build | PARTIAL | Backend verified statically only (Docker daemon not running); frontend build executed OK; deps unpinned, Node version unpinned |
| 3 | staging-real semantics | PARTIAL | Real Gemini / auth / CORS / limits all enforced and executed against dummy env; gaps: key validity unverifiable, `LOCAL_QUOTA_*` defaults (5/min, 20/day) not set in render.yaml, CORS must be JSON array |
| 4 | Supabase schema/storage | PARTIAL | Only table `batches` + one private bucket are used; no SQL file in repo (schema only in a docstring); live schema/RLS not verifiable offline. No public-URL usage, so NO blocker |
| 5 | local_spool / ephemeral FS | PARTIAL | Accepted staging limitation, not a blocker: originals + batch JSON are in Supabase; spool is a cache; in-flight jobs are lost on restart (documented recovery = re-upload) |
| 6 | Local blockers | PARTIAL | No hard blocker found; list of hygiene/risk items in section 6 |

READY=1 PARTIAL=5 BLOCKER=0

---

## 1. render.yaml (evidence: `render.yaml`)

| Check | Backend `virology-lab-staging-backend` | Frontend `virology-lab-staging-frontend` |
|---|---|---|
| runtime | `docker` (L7) | `static` (L63) |
| rootDir | `backend` (L8) | `frontend` (L65) |
| Dockerfile | `./Dockerfile`, context `.` (L9-10) | n/a |
| branch | `main` (L11) | `main` (L64) |
| plan | `free` (L12) | no `plan` key (static sites have none; not an issue) |
| region | `frankfurt` (L13) | n/a |
| healthCheckPath | `/ready` (L14) | n/a |
| autoDeployTrigger | `"off"` (L15) | `"off"` (L68) |
| build | Dockerfile | `npm ci && npm run build` (L66), publish `./dist` (L67) |
| SPA rewrite | n/a | `/*` -> `/index.html` (L87-90) |
| Security headers | n/a | nosniff, no-referrer, HSTS, X-Frame-Options DENY (L74-86) |

Env vars, backend:
- Fixed values: `DEPLOYMENT_MODE=staging-real` (L17-18), `DEMO_MODE=false` (L19-20), `HYBRID_*` all false (L25-34), `MAX_FILE_SIZE_MB=10`, `MAX_FILES_PER_BATCH=3`, `MAX_PAGES_PER_DOCUMENT=10`, `MAX_REQUEST_SIZE_MB=32`, `MAX_IMAGE_PIXELS=12000000`, `CONCURRENT_PROCESSING_BATCHES=1`, `UPLOAD_REQUESTS_PER_MINUTE=6` (L35-48).
- `sync:false` (entered in the dashboard): `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET_NAME`, `API_USERNAME`, `API_PASSWORD`, `CORS_ORIGINS`.
- Frontend: `VITE_DEPLOYMENT_MODE=staging` (fixed), `VITE_API_URL` (`sync:false`).
- No secret value is committed in render.yaml. There is no `LOCAL_QUOTA_*` entry (see 3).

Commands run (worktree root):
- `python scripts\validate_render_preparation.py` -> exit code 0. Output:
  - `Python AST parsing passed: 52 application files (not imported/executed).`
  - `YAML parsing/duplicate-key, paths, public-env and staging structural checks passed.`
  - `Production template has deliberate region/branch placeholders and a nonfunctional worker stub.`
  - `NOT checked: Render API/schema, images, dependencies, startup, requests, auth, jobs or Supabase.`
- The validator asserts `autoDeployTrigger == "off"` (script L73), the `sync:false` key set (L80) and `/ready` + `plan == free` (L84). It does NOT verify that `branch == main`; I confirmed that by reading the file.

## 2. Dockerfile and frontend build

`backend/Dockerfile` (static review; `docker info` failed because the Docker daemon is not running, so `docker build` was NOT run):
- L5 `python:3.13-slim`; L6 `TEMP_STORAGE_PATH=/app/temp_storage`.
- L9-20 apt: gcc, g++, tesseract-ocr (+heb, eng), libtesseract-dev, `libmagic1`, libglib2.0-0, libgl1 (OpenCV), curl.
- L26-27 `pip install -r requirements.txt`. It covers PyMuPDF, Pillow, openpyxl, opencv-python, numpy, pytesseract, supabase==2.33.0, google-genai, truststore, python-multipart, pydantic(-settings), python-dotenv, uvicorn[standard]. I AST-scanned `backend/app` imports (PIL, cv2, dotenv, fastapi, fitz/pymupdf, google, httpx, numpy, openpyxl, pydantic, pydantic_settings, pytesseract, starlette, supabase, truststore). All are provided by requirements.txt (httpx is listed under "Testing" and is also a supabase dependency).
- L30 `COPY app ./app` only. `.dockerignore` excludes `.env`, `.env.*`, `*.json` at the root (not `app/data/sending_institutions.json`), `temp_storage/`. No secret is baked in. `test_6_pages.pdf` is outside `app/`, so it is not in the image.
- L33-36 non-root user uid/gid 10001; `/app/temp_storage` is owned by it.
- L46 `exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 ... --limit-concurrency 16`. It binds Render's `$PORT` and runs a single worker, which the in-memory job registry requires.
- L42-43 Docker HEALTHCHECK curls `/ready` (Render uses its own `healthCheckPath`).
- `/ready` exists: `backend/app/main.py` L81-94 (`@app.get("/health")` and `@app.get("/ready")` share one handler). It returns 503 if `storage.check_ready()` fails. `/live` is at L97.
- Python 3.13 and unpinned requirements (everything except supabase) can drift on a clean build. Whether PyMuPDF/opencv wheels resolve on 3.13 linux was NOT verified (no docker build, no resolver run). PARTIAL.
- `backend/docker-compose.yml` is local-only and not used by Render.

Commands run (all exit 0 unless noted):
- `python -m compileall -q backend\app` -> exit 0.
- `docker info` -> daemon unreachable (error). Backend image build skipped by design.
- Frontend (`frontend`, with `VITE_DEPLOYMENT_MODE=staging`, `VITE_API_URL=https://placeholder-backend.example.onrender.com` set in the process only):
  - `npm ci` -> exit 0 (npm audit warnings only).
  - `npm run build` (`tsc && vite build`) -> exit 0. 113 modules, `dist/assets/index-*.js` 250 kB. The only warning is a Vite dynamic/static import notice for `api.ts`.
  - Node v24.13.0, npm 10.8.2, Python 3.13.12 locally. Render's Node version is not pinned (no `.nvmrc`, `.node-version`, `engines` or `NODE_VERSION` env). Vite 5 needs Node 18+, so this is low risk, but it is unverified on Render.
- Bundle secret scan (`dist/assets/*.js` for `AIza|service_role|SUPABASE|GEMINI|eyJhbGci|API_PASSWORD|localhost:8000`): the only hits were the UI word "Gemini" ("Gemini quota exhausted") and my placeholder URL. No secrets. `localhost:8000` was not found because `VITE_API_URL` replaced it.

Frontend config handling:
- `frontend/package.json` build = `tsc && vite build`.
- `frontend/src/services/api.ts` L8: `API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'`. The same fallback is in `DocumentViewerModal.tsx` L12.
- `frontend/vite.config.ts` L6-27 is a build-time allowlist. Only `VITE_API_URL` and `VITE_DEPLOYMENT_MODE` are accepted, or the build fails. The mode must be local, staging or production. For a non-local mode, `VITE_API_URL` must be an exact HTTPS origin with path `/`, no credentials, no query. Any other `VITE_*` variable fails the build, so a secret cannot leak via `VITE_*`.
- Basic-auth credentials are held in memory only (`App.tsx` L26 sets `apiClient.defaults.auth`). `api.ts` L20-30 strips auth from errors. No credentials in bundle or localStorage. Only the batch id is kept in localStorage (`WorkflowScreen.tsx` L39).
- `frontend/.env.local` does not exist in this worktree (it exists only in the root, not read). Vite's `loadEnv` would read one if present at build time, but Render clones the repo, so it will not be there.

## 3. staging-real semantics (executed against dummy env, not just read)

Source: `backend/app/core/config.py`.
(a) Requires real Gemini:
- L56 `deployment_mode` literal includes `staging-real`; L87-88 `is_cloud` = mode != local.
- L98-100: `staging-real` + `demo_mode` -> `ValueError("staging-real requires DEMO_MODE=false; mock extraction is prohibited")`.
- L101-103: no `GEMINI_API_KEY` / `GEMINI_API_1..8` in `os.environ` -> `ValueError`. L104-105: blank `GEMINI_MODEL` -> `ValueError`.
- L106-107: other cloud modes (`staging`, `cloud`) REQUIRE `DEMO_MODE=true`, so staging-real is the only cloud mode that allows real extraction.
- L92-96: `production` always raises (blocked by design).
- `validate_deployment()` is called at import via `get_storage_backend()` (`storage_adapter.py` L204; `process.py` L22 `_storage = get_storage_backend()`) and again in `main.py` `lifespan` L22-26. A misconfigured service therefore fails to boot (Render deploy fails, old version not replaced).
- `main.py` L23: `if os.getenv("RENDER") and not settings.is_cloud: raise`. Render sets `RENDER=true`, so a Render deploy cannot run in `local` mode.
- Extractor selection: `background.py` L148-161. `demo_mode` -> `MockExtractor`, else `GeminiExtractor`. In staging-real `demo_mode` is forced false, so there is no mock fallback. `quota_manager.py` skips tracking only when `demo_mode`.
- Executed proof (temporary script, deleted after, dummy values only, no network; `PYTHONPATH=backend`):
  - A no Gemini key -> ValueError "requires Gemini credentials".
  - B key + JSON CORS -> OK.
  - E `DEMO_MODE=true` -> ValueError "mock extraction is prohibited".
  - I blank model -> ValueError "requires GEMINI_MODEL".
- Gap: the check only tests that a key is non-empty. A wrong or expired key passes startup and only fails on the first extraction. VERIFY AFTER DEPLOYMENT.
- Gap: the default `gemini_model` is `"gemini-3.8-flash"` (config.py L27), and `GEMINI_MODEL` is `sync:false`. Whether the model name is valid and available to the key cannot be checked offline. VERIFY AFTER DEPLOYMENT.

(b) Authentication:
- `core/access.py` `require_access` (L11-19): HTTP Basic, `secrets.compare_digest` on `API_USERNAME` / `API_PASSWORD`. Local-mode bypass only if `deployment_mode == "local"` AND no `supabase_url` AND no `api_password`. In staging-real the bypass is impossible.
- `main.py` L72-74 applies `Depends(require_access)` to the `upload`, `process` and `documents` routers; `/api/session` (L77) also requires it. So upload, process, status, field edit/verify/reject, export-check, export, retry-failed and document download all require auth.
- Unauthenticated routes: `/health`, `/ready`, `/live`, `/` (main.py L81-107). `/health` and `/ready` expose `environment`, `extractor` class name, `version` and `demo_mode`. No secrets or PHI. Low severity.
- `config.py` L110-111: `API_USERNAME` required and `API_PASSWORD` must be at least 16 characters (executed: password "short" -> ValueError).
- Docs and OpenAPI are disabled when `is_cloud` (main.py L33-35).
- CORS: `main.py` L67-69 `allow_origins=settings.cors_origins`, `allow_credentials=True`, methods GET/POST/PATCH, headers Content-Type + Authorization. `config.py` L117-124 requires exact `https://host` origins: no wildcard, path, credentials, query, and no trailing slash (executed: `["*"]`, `https://f.example.com/` and the default `http://localhost:5173` all fail).
- IMPORTANT FORMAT GAP: `cors_origins` is `list[str]`, so pydantic-settings needs a JSON array: `["https://<frontend-host>"]`. Executed: a plain string `https://f.example.com` -> `SettingsError` (startup crash). A comma-separated value is also invalid. This matches `DEPLOYMENT.md` L178 and L208. Note that `.env.example` still shows "comma-separated"; that comment is wrong. Use JSON.
- 401 is returned with `WWW-Authenticate: Basic`; the frontend dispatches `api-auth-required` (api.ts L20-24) and shows a sign-in prompt (App.tsx).

(c) Limits (all env-driven, set in render.yaml L35-48):
- `MAX_FILES_PER_BATCH` -> `upload.py` L75-81 (400). `MAX_FILE_SIZE_MB` -> bounded read, `upload.py` L96-104 (413). `MAX_PAGES_PER_DOCUMENT` + encrypted PDF rejection -> `upload.py` L133-136. `MAX_IMAGE_PIXELS` -> `upload.py` L139-141 (+ `wrap_image_as_pdf`). MIME + magic bytes + declared-vs-detected match -> `upload.py` L106-122.
- `MAX_REQUEST_SIZE_MB` -> `core/request_limits.py` L22-30, L50-55 (Content-Length and streamed body, 413). `UPLOAD_REQUESTS_PER_MINUTE` -> L32-44 (per client IP, in-memory, 429).
- `CONCURRENT_PROCESSING_BATCHES` -> `process.py` (429 "Processing capacity reached") and `background.py` L271-273. Config range ge=1, le=4.
- Config bounds: MAX_FILE_SIZE_MB 1-100, pages 1-100, files 1-20, request size 1-512 (config.py L40-42, L59).
- Rate limiting uses `scope["client"]` (not X-Forwarded-For) and Render's proxy hides the client, so the upload limit is effectively global for all users. Acceptable for a one-team staging.

Functional gap (important): `LOCAL_QUOTA_REQUESTS_PER_MINUTE` defaults to 5 and `LOCAL_QUOTA_REQUESTS_PER_DAY` to 20 (config.py L82-83). They are enforced in `gemini_adapter.py` L527-535 via `quota_manager.track_request()` (every Gemini attempt counts) and they are NOT in render.yaml. A full batch (3 files x 10 pages) needs up to 30 calls, so it can exhaust the 20/day safety budget even though the provider limit may be higher. Counters are in memory, so they reset on restart and at UTC midnight. Fix without code: add `LOCAL_QUOTA_REQUESTS_PER_MINUTE` and `LOCAL_QUOTA_REQUESTS_PER_DAY` in the Render dashboard, set to the staging key's real limits, never above them. Optional: add them to render.yaml with `sync:false`. This needs approval, and `validate_render_preparation.py` L80 asserts the exact `sync:false` set, so the validator would need a matching update.

## 4. Supabase: schema-vs-code truth

Greps: `git grep -il supabase` over the whole worktree, plus `get_public_url|create_signed_url|.rpc(|.auth.|create_bucket|list_buckets`. There is no `supabase/` directory, no `*.sql` file and no migrations in the repo. The only schema definition is the docstring in `backend/app/services/storage/storage_adapter.py` L72-82. `DEPLOYMENT.md` L67-80 describes the same contract in prose.

What the backend actually uses (`storage_adapter.py`, `SupabaseStorageAdapter`):
- supabase-py `create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)` (L97): service-role key only, server side. No anon key, no Supabase Auth, no RPC, no realtime, no signed or public URLs.
- PostgREST, ONE table `public.batches`:
  - `insert({batch_id, batch_data, updated_at})` (L125)
  - `update(row).eq(batch_id).eq(updated_at, version)` (L127, optimistic lock: no row matched -> `StorageConflict` -> HTTP 409)
  - `select("batch_data,updated_at").eq(batch_id)` (L134)
  - `select("batch_id").eq(...)` (L143)
  - `select("batch_id")` (list, L147)
  - `delete().eq(batch_id)` (L151)
  - readiness: `select("batch_id,batch_data,updated_at").limit(0)` (L188)
- `created_at` is never written or read by the code; it is only a default column.
- Storage (bucket from `settings.supabase_bucket_name`):
  - `upload(path=f"{batch_id}/{file_name}", file=bytes, content-type application/octet-stream)` (L170-178). No upsert, so a duplicate path errors.
  - `download(path)` (L188).
  - `get_bucket(name)` with a `public` check (L190-193).
  - Object names: `batch_<12 hex>/doc_<12 hex>.pdf|.png|.jpg`, validated by `validate_storage_name` (L29-31). Images are converted to a one-page PDF at upload (`upload.py` L145-151), so stored objects are in practice always `.pdf`.
  - The original image bytes are not kept; only hash/size metadata (`original_sha256`) go in the manifest.
- Bucket env var: `SUPABASE_BUCKET_NAME`, default `virology-lab-uploads` (config.py L54). In render.yaml it is `sync:false`, so it must be entered (no default is applied on Render if left blank in the dashboard; a blank Render value would be an empty string and then the default does not apply, so ALWAYS set it).
- Bucket MUST be private and this is ENFORCED: `check_ready()` raises "Configured Supabase bucket must be private" unless `bucket.public is False` (L190-193). `check_ready` runs in `lifespan` (main.py L27) and in every `/ready` and `/health` call. A public bucket = service refuses to start / readiness 503. No code path produces a public URL. Private-bucket access is server-side download only (`documents.py` L63-76 streams bytes after SHA-256 check). So there is NO public-URL usage and no BLOCKER.
- `batch_data` JSONB holds the whole batch: manifest `documents[]` (document_id, storage_name, size_bytes, page_count, sha256, ...), `commitment_records`, `test_records`, status, errors, `saved_at`. It contains PHI (patient names, ID numbers, sender) once real extraction runs, and the bucket holds original patient documents. Hence "synthetic or approved non-sensitive documents only" for staging (render.yaml L1-2). Logs carry only ids/sizes/sha256 (upload.py L168-170), and uvicorn access logs are disabled (`--no-access-log`).
- Required `batches` schema (from the docstring; tests in `backend/tests/test_storage_adapter.py` are "REAL" Supabase tests and were NOT run):
  - `batch_id TEXT PRIMARY KEY`
  - `batch_data JSONB NOT NULL`
  - `created_at TIMESTAMP DEFAULT NOW()`
  - `updated_at TIMESTAMP DEFAULT NOW()`
  - `INDEX idx_batches_created ON batches(created_at DESC)` (optional performance only; the code never orders by created_at)
- Subtlety: `updated_at` is set by the application (Python ISO-8601 with `+00:00`) and used as the optimistic-lock token via `.eq("updated_at", version)`. The docstring uses `TIMESTAMP` (no timezone) and that is the contract the owner's earlier persistence evidence was gathered against (`docs/PERSISTENCE_READINESS_AUDIT.md`). Recommendation: keep `TIMESTAMP` exactly as in the docstring for the new project; do not "improve" it to `timestamptz` without a live test, because the `.eq` round trip is the only guard against overwriting human review. Whether `timestamptz` also round-trips cleanly is unverified.
- RLS: nothing in the repo defines policies. The service-role key bypasses RLS. Recommended for a new project: enable RLS on `public.batches` with NO policies and revoke table privileges from `anon` and `authenticated`, so the exposed PostgREST endpoint cannot be read with the public anon key. `DEPLOYMENT.md` L76-80 says confirm anon access is denied and do not relax RLS; `check_ready` verifies only table access and bucket privacy, NOT policies.
- Drift flags: (1) no SQL file in the repo (schema only in a docstring + prose); (2) `docs/` and `.env.example` say Supabase is "optional", but staging-real requires it (config.py L108-109); (3) the docstring header says "Postgres JSONB + Storage"; there is no additional table (e.g. no audit/doc tables). Neither the live existing project's schema nor its RLS could be inspected (no Supabase access by design). PARTIAL.
- DRAFT script for a NEW staging project (to be reviewed by the author step; not executed; idempotent and non-destructive, no data deletion):
```sql
create table if not exists public.batches (
  batch_id   text primary key,
  batch_data jsonb not null,
  created_at timestamp default now(),
  updated_at timestamp default now()
);
create index if not exists idx_batches_created on public.batches (created_at desc);
alter table public.batches enable row level security;          -- no policies: only service_role (bypasses RLS) can access
revoke all on table public.batches from anon, authenticated;
-- private bucket (name must equal SUPABASE_BUCKET_NAME; placeholder shown)
insert into storage.buckets (id, name, public)
values ('virology-lab-uploads', 'virology-lab-uploads', false)
on conflict (id) do nothing;
```
  Operator must then confirm in the dashboard that the bucket shows "Private" (if it already existed and was public, that is a manual fix; the `on conflict do nothing` will NOT flip it). Service-role key goes only into Render backend env, never into the frontend.

## 5. local_spool and Render's ephemeral filesystem

What lives on Render's ephemeral disk (`/app/temp_storage`, `/tmp`):
- `LocalSpool` (`services/storage/local_spool.py` L89-91): `/app/temp_storage/_verified_spool/<batch>/<doc>`. A write-through cache of the stored bytes. `upload.py` L156-161 writes it only when `settings.supabase_url` is set, and failures are swallowed (best effort). Remote Supabase is authoritative (docstring L5-6, L16-17).
  - Reads (`fetch_original`, L121-139) check the spool and verify SHA-256; on a miss they fall back to `storage.download_file`. A missing copy is explicitly "NOT an error". If both fail -> `OriginalUnavailable` (documents.py -> 502; background.py records a per-document integrity error).
  - TTL cleanup (24h by default, `TEMP_STORAGE_TTL_HOURS`) runs on each spool save (L77-81).
  - Effect of losing it: only a performance/network-robustness cache. The header says it was added because remote retrieval "was observed to fail or return different bytes on this network" (a local-network issue). On Render, whether Supabase download works is unverified (see test plan).
- Excel export (`process.py` L742-762): generated on demand from the persisted `commitment_records` and written to `/app/temp_storage/<batch>/<batch>_export.xlsx`, then streamed. `mkdir(exist_ok=True)` (no `parents=True`) works because `/app/temp_storage` exists (Dockerfile L34-35). The file is a throwaway; export is not persisted, but it can be regenerated any time after a restart. Survives restart: YES in the sense that it is reproducible.
- Processing workspace: `background.py` L249 `TemporaryDirectory("virology-processing-")` in `/tmp`; originals are re-downloaded from Supabase for each run (L274-296). Lost on restart, harmless.
- In-memory state (lost on restart, redeploy or free-plan spin-down): `BackgroundProcessor._jobs` (`background.py` L141, L288), plus the Gemini `QuotaManager` counters and exhausted flags (`quota_manager.py` L59-65), plus the per-IP upload-rate windows (`request_limits.py` L16). The Gemini key manager state is in memory too.
- Durable state in Supabase: uploaded originals (bucket, `upload.py` L152-154) and everything in `batches.batch_data` (manifest, status, extraction results, reviewer edits). Every field edit / verify / candidate reject calls `_storage.save_batch` (`process.py` PATCH/verify/reject handlers). A successful upload response means originals AND batch metadata are persisted (`upload.py` comment before `save_batch`). I did not verify whether extraction results are saved incrementally page by page or only at the end of a batch; check `background.py` after L366 before promising partial-result recovery.

Which flows survive a restart / spin-down:

| Flow | Survives? | Evidence |
|---|---|---|
| Uploaded originals | YES | Supabase bucket; `documents.py` fetches remote when the spool is missing |
| Uploaded batch not yet processed (`status=uploaded`) | YES, can be processed after restart | `process.py` loads it from Supabase; originals re-downloaded |
| Completed extraction results + review edits | YES | `batch_data` in Postgres; every edit saved; `GET /api/batches/{id}` falls back to storage (`process.py` ~L196-205) |
| Batch lookup after restart (frontend reload) | YES | batch id in localStorage + URL; `GET` loads from storage |
| Excel export after restart | YES (regenerated) | built from persisted records |
| Document preview after restart | YES | remote download + SHA-256 check |
| Batch IN PROCESSING when the service restarts | NO | job registry is in memory. Persisted status stays `processing`/`queued`; `POST .../process` returns 409 "Previous processing was interrupted; manual recovery required" (process.py L60-64); `retry-failed` returns 409 because the stored status is not failed/completed_with_errors/quota_exhausted (L106-107). `_report_interrupted_if_stale` (L123-146) makes GET report `failed` / `processing_interrupted`, but only after `EXTRACTION_BATCH_DEADLINE_SECONDS + 120` = 1920 s (about 32 min) since the last save, and it does not persist that. Recovery = upload again (new batch). |
| Gemini quota counters | NO (reset) | in memory |

Free plan behavior (Render docs, not re-verified in this step): free web services spin down after about 15 minutes with no inbound HTTP traffic and cold start (about 1 min) on the next request. While the frontend polls `GET /api/batches/{id}` every few seconds the service stays awake, so a normal run should not be spun down mid-processing; closing the browser tab during a long run can allow spin-down and kill the job. Also a redeploy or an environment change restarts the service. The first request after sleep can be slow, and the frontend axios timeout is 5 minutes (api.ts L13).

Single-worker / concurrency assumptions: `--workers 1` (Dockerfile L46) is required because `_jobs`, the quota counters and the rate windows are per process. `CONCURRENT_PROCESSING_BATCHES=1` (render.yaml L45-46) plus `process.py` returning 429 beyond capacity means a second batch must wait. Never scale to more than 1 instance or add workers.

Decision: NOT a blocker for a functional staging MVP. Documents and review state are durable (the local-spool risk the user asked about is mitigated by design because it is only a cache); only in-flight processing is lost, which is a known, surfaced and documented limitation (`DEPLOYMENT.md` mentions the durable-processing gap as a production P0). Must be written into the handoff as "do not restart/redeploy while a batch is processing; if it happens, re-upload".

Smallest optional local fixes (DESCRIBE ONLY; none applied, all need approval):
1. In `_report_interrupted_if_stale` (`process.py` L123-146), treat a persisted `queued`/`processing` batch with `saved_at` earlier than process start time as interrupted immediately (module-level `PROCESS_STARTED_AT`), instead of waiting 32 minutes. About 4 lines; makes the UI stop polling right after a restart. It is valid because the service is single-worker and the registry is empty at boot.
2. Not recommended for the MVP: persisting job state or a recovery endpoint (this is the production "durable processing" work).
3. Zero-code mitigation: keep the Render service from sleeping during a test session, and avoid redeploys while a batch is running.

## 6. Remaining locally-solvable items / risks (no hard blocker found)

| # | Item | Severity | Proposed minimal fix |
|---|------|----------|----------------------|
| L1 | `LOCAL_QUOTA_*` defaults (5/min, 20/day) are not in render.yaml (see 3) | Medium, functional | Set the two vars in the Render dashboard to the real limits of the staging Gemini key (or add `sync:false` entries to render.yaml and update the validator) |
| L2 | `CORS_ORIGINS` must be a JSON array, no trailing slash; `.env.example` wrongly says comma-separated | Medium, startup crash | Document the exact format in the handoff checklist; optionally fix the `.env.example` comment |
| L3 | No SQL file for the schema in the repo | Medium | Add the reviewed SQL to `docs/` or `supabase/` (docs only) |
| L4 | `backend/test_6_pages.pdf` is tracked (added in commit 488c12d "WIP: Pre-workflow snapshot"). I checked metadata and text only: 6 pages, no embedded images, 76 text characters per page, no 9+ digit run (no ID-like number), contains a generic marker such as "test"/"page N". It looks synthetic, but the author MUST confirm | Low | Owner confirms it is synthetic; otherwise remove it from git history/tracking. It is not copied into the Docker image |
| L5 | `.gitignore` ignores `.env`, but not `frontend/.env.local` (`git check-ignore` returned no match), `backend/temp_storage/` or `.agents/` | Low | Add `.env.local`, `.env.*.local`, `temp_storage/` entries (hygiene; this stays out of the worktree changes until approved) |
| L6 | Requirements are unpinned except supabase; Python 3.13; backend image never built here (Docker daemon off) | Medium, unverified | First Render build is the real test. If the owner has Docker Desktop, run `docker build -t vl-backend ./backend` (it bakes no secrets) before handing off. Optionally pin versions after a successful build |
| L7 | Render Node version not pinned | Low | Optionally set `NODE_VERSION` env on the static service (needs approval to edit render.yaml/validator) |
| L8 | Free plan RAM (512 MB): PDF render at 300 DPI / 3000 px with PyMuPDF + OpenCV + Tesseract imports; hybrid flags are off in render.yaml, which helps | Medium, unverified | Test a 10-page PDF in staging and watch for OOM restarts in Render logs |
| L9 | URL chicken-and-egg: `VITE_API_URL` needs the backend URL; `CORS_ORIGINS` needs the frontend URL | Process | Handoff order: create backend with a temporary valid HTTPS CORS value -> note backend URL -> set `VITE_API_URL` on the frontend and deploy -> note frontend URL -> set `CORS_ORIGINS` JSON on the backend and restart. Changing `VITE_API_URL` requires a frontend REBUILD (build-time variable) |
| L10 | `/health` and `/ready` are unauthenticated and expose version/extractor/environment | Low | Accept for staging |
| L11 | 1920 s stale-processing detection delay (section 5) | Low | Optional fix 1 in section 5 |
| L12 | Basic auth is a single shared credential in browser memory; no per-user identity | Accepted | Staging only; production is explicitly blocked in code |
| L13 | Supabase region should match Frankfurt (`eu-central-1`) for latency; also the data-residency approval noted in `DEPLOYMENT.md` L82-83 | Low | Operator choice when creating the project |
| L14 | `docs/` and the `*_REPORT.md` files in the root are noisy, with stale statements (e.g. "Supabase optional") | Low | Do not rely on them; `DEPLOYMENT.md` + code are the sources |

Confirmed OK: `/ready` exists; requirements cover all app imports; `compileall` passes; frontend build passes; no secrets in the bundle; the root `.env` and `frontend/.env.local` were not opened; no Render/Supabase/Gemini calls were made.

## What cannot be verified before deployment (post-deploy checks)
- Backend image builds on Render (Python 3.13 wheels, apt packages); service boots and `/ready` returns 200 (needs a correct Supabase URL/key, a private bucket and the `batches` table).
- Gemini key validity, model availability and quota; a real extraction of a synthetic PDF, PNG and JPEG.
- Supabase round trip: upload, download, optimistic lock `updated_at` equality on the real column type, RLS denies the anon key.
- Memory on the Free plan; behavior after spin-down; CORS preflight with Authorization from the real frontend origin; HSTS/headers on the real hosts.

## Line-number corrections (authoritative; some inline numbers above are approximate, within a few lines)
- `main.py`: lifespan L21-26 (RENDER guard L22-23), docs_url L30-32, CORS L62-64, router auth L67-68, `/api/session` L71, `/health`+`/ready` handler L76-91 (def at L78), `/live` L95-97.
- `process.py`: `_storage = get_storage_backend()` L24; manifest-missing 409 L55; capacity 429 L73; "interrupted; manual recovery required" 409 L75; retry-failed status 409 L108; capacity 429 L114; `_report_interrupted_if_stale` L123.
- `upload.py`: too many files L87; too large L106; type/magic mismatch L120; image pixels L139-141; invalid/encrypted PDF L143; spool copy L155-161.
- `storage_adapter.py`: `create_client` L103; insert L124; optimistic update L126; bucket upload L165; download L181; `check_ready` L186-192; `get_storage_backend` L195-203.
- `background.py`: `_jobs` L141; capacity ValueError L283; `TemporaryDirectory` L320.

## Commands run (exact)
- `git status --short`; `git log --oneline -2`
- `python scripts\validate_render_preparation.py` -> exit 0
- `python -m compileall -q backend\app` -> exit 0
- `docker --version` -> 25.0.3; `docker info` -> daemon not running
- `npm ci` and `npm run build` in `frontend` with placeholder `VITE_*` env -> both exit 0; `dist` and `node_modules` created by me were deleted afterwards (both are gitignored)
- A temporary Python script (in this folder, since deleted) reloaded `app.core.config` with dummy env to test `validate_deployment()` for 9 scenarios (no network, no Supabase client created, no Gemini). An AST import scan was also temporary and deleted.
- A PyMuPDF metadata/text-statistics check on `backend/test_6_pages.pdf` (counts and boolean regex only; text content not printed)
- Cleanup: removed `frontend/node_modules`, `frontend/dist`, `backend/**/__pycache__`. `git status --short` is clean apart from this `.agents/` folder.

READY=1 PARTIAL=5 BLOCKER=0
