# Render deployment runbook

Updated 2026-10-20. **Restricted real-extraction staging; clinical production is blocked.**
No cloud deployment, schema migration, RLS change, paid provisioning, GitHub push or
Gemini request was performed. Earlier application/Supabase testing was performed by
the owner. This revision uses focused offline configuration/contract checks only.
Staging accepts synthetic or institutionally approved non-sensitive documents only;
an API key does not authorize clinical-data processing.

## 1. Checkpoint and release boundaries

Persistence implementation checkpoint:
`0f71767d62320d49b3869ca60dc7fde63b73139c`

Commit message: `feat: integrate Supabase persistence and prepare secure deployment`.
Exactly the 20 files listed in docs/PERSISTENCE_READINESS_AUDIT.md were committed.
This is an implementation checkpoint, not production runtime validation. The previous
57 passing tests/build relate to baseline `71c56ee`, not the persistence or deployment edits.
The separate 22-file deployment-preparation milestone is recorded by
`6ef3843c8db6c43a29bfcd9c541b82685b305625` (`chore: prepare Render staging and production
security gates`). Local Gemini integration is checkpointed at
`16dd6599d45c6b375c73ff6b0583ffa275dd7ea6`. This restricted staging-real revision builds
on those implementation milestones. None constitutes runtime release validation.

Use the existing worktree and branch; never reset or clean to hide artifacts:

```powershell
Set-Location -LiteralPath 'D:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration'
git branch --show-current
git status --short
git show --stat 0f71767d62320d49b3869ca60dc7fde63b73139c
git diff --check
```

Review the committed deployment milestone before release. Never
stage environment files, PDFs, Excel files, batch dumps, .agents or the two unrelated
pre-existing test modifications. Do not use a blanket add command.

Only after explicit GitHub-push approval, execute this from the worktree:

```powershell
git push origin integration/final-mvp
```

Do not merge to main. An institution-approved production release branch is still
unresolved; do not invent it or fill the production placeholder automatically.
Push approval and deployment/resource approval are separate decisions.

## 2. Choose the environment

| Environment | Configuration | Status |
|---|---|---|
| Local | existing source/Docker Compose; local storage allowed | synthetic development |
| Staging real extraction | render.yaml; DEPLOYMENT_MODE=staging-real, DEMO_MODE=false | restricted real Gemini; synthetic or institutionally approved non-sensitive documents only |
| Staging mock demo | explicit DEPLOYMENT_MODE=staging (or cloud), DEMO_MODE=true override | MockExtractor; never used as a fallback for real extraction failures |
| Production | render.production.yaml.template | NON-DEPLOYABLE template; paid resources and unresolved region/branch; code fails closed |

Use distinct Supabase projects/buckets/credentials, Render services and identity
applications. Do not connect staging to a clinical project. The legacy cloud mode is
a mock-staging compatibility alias. Real extraction requires the separate explicit
staging-real mode, which rejects DEMO_MODE=true. The production template is not a deployable release:
its API is blocked and its worker only prints a blocker and exits without I/O.

## 3. Staging prerequisites

The operator needs authorized GitHub repository access, a Render workspace and a
staging Supabase project with the existing batches contract/private bucket. Retain
the owner's prior persistence evidence; do not assume it validates these new changes.

Existing table contract: public.batches has batch_id, batch_data JSONB, created_at
and updated_at. This task changes no table structure. A conditional updated_at write
rejects a stale review update instead of overwriting it. Originals use generated
batch/document names in the private Storage bucket; their manifest is in batch_data.
Batch/page fields and reviewed values remain inside the existing record JSONB.

Confirm the existing RLS and grants with the project owner: anonymous/public database
reads/writes and public Storage downloads must be denied. Service-role privileges
remain backend-only and bypass RLS, so production tenant authorization requires a
separate reviewed implementation. Do not run migrations or relax RLS to make a build
pass. The startup check verifies schema access and bucket privacy, not all policies.

Supabase traffic uses its HTTPS APIs and private Storage objects. This does not claim
private-network peering between Render and Supabase; approve network/data-residency
arrangements independently. Keep secrets in Render's backend Environment settings.

## 4. Create the staging services after approval

Creating/applying a Blueprint can provision and deploy immediately, even when later
automatic deployments are disabled. Obtain approval BEFORE clicking Create/Apply.

1. In Render Dashboard choose **New > Blueprint**, connect
   https://github.com/tova-zak/The-Central-Virology-Laboratory, select
   integration/final-mvp and the root render.yaml. Review the exact revision.
2. Confirm the proposed services are virology-lab-staging-backend and
   virology-lab-staging-frontend. Do not silently replace/delete services owned by an
   existing Blueprint. If those names conflict, stop and reconcile ownership first.
3. Review the resource plan and region. Staging's existing Frankfurt selection is for
   synthetic or specifically approved non-sensitive data only, not clinical residency approval. No worker or
   Key Value service is created by the staging Blueprint.
4. Fill backend secrets/public settings when prompted, then review the entire plan.
   New secrets on existing services must be added manually under **Environment**;
   sync:false is not a secret-value update mechanism for an existing service.
   Set GEMINI_API_KEY and GEMINI_MODEL on the BACKEND only. Never import/upload a
   local .env file, create a Gemini secret file or add keys to frontend variables.
   Set DEPLOYMENT_MODE=staging-real and DEMO_MODE=false as defined in render.yaml.
   Keep the frontend VITE_DEPLOYMENT_MODE=staging; it does not select the extractor.
5. Apply only after the release/deployment authorization. Keep **Auto-Deploy > Off**.

If the backend/frontend URLs are not known until creation, the operator must plan
this approved setup window: fail-closed startup is expected until exact CORS/API
origins are entered. Never use wildcard CORS or guessed hostnames to bypass it.

### Backend Docker Web Service

In **Settings > Build & Deploy**, confirm:

- Runtime Docker; Root Directory backend.
- Dockerfile ./Dockerfile; Docker Context . (both relative to backend).
- No Python build command; Docker installs requirements from its context.
- Use the Docker CMD; host-provided PORT is respected.
- Single API worker/instance while processing remains in-process.
- Health Check Path /ready; /live is liveness only; /health is the readiness alias.
- Auto-Deploy disabled. No automatic pre-deploy migration/seed command.

The image runs as a non-root user, omits temporary artifacts and uses bounded Uvicorn
concurrency/keepalive/graceful shutdown. Disposable scratch files are permitted;
originals, patient fields and review decisions must reside in Supabase. A readiness
success does not prove write permissions, clinical controls, backup coverage or a
successful new deployment smoke test.

### React Static Site

Confirm Root Directory frontend, Build Command `npm ci && npm run build`, Publish
Directory ./dist, automatic deployments disabled and the /* rewrite to /index.html.
These paths are relative to the configured root. Do not create a frontend web server
or run the Vite development server in Render.

Under **Environment**, set the public API origin and staging frontend mode. The
build rejects unknown VITE-prefixed variables and non-HTTPS hosted API origins.
Only public API/environment identifiers belong in the bundle. URLs are entered from
actual Render service/custom-domain settings; no assumed onrender.com URLs are used.

### Exact URLs, HTTPS and CORS

Open each service's **Settings > Custom Domains** or use its actual assigned HTTPS
origin. Configure the browser API base origin without a path, query or credentials.
Set backend CORS to a JSON array of exact frontend origins, with no trailing slash,
path, wildcard or comma-separated format. This command formats a public origin you
enter; it does not read or print secrets:

```powershell
$frontendOrigin = Read-Host 'Actual HTTPS frontend origin'
ConvertTo-Json -Compress -InputObject @($frontendOrigin)
```

Copy that JSON into the backend CORS setting. Enter the actual HTTPS backend origin
into the frontend API setting and rebuild the static site whenever it changes.
Use Render-managed TLS or approved institutional custom domains; confirm HTTP-to-
HTTPS behavior during the approved release check. Shared demo credentials must only
be sent over HTTPS. Do not disable TLS validation or weaken browser CORS.

## 5. Environment variable names and descriptions

Values/credentials are intentionally omitted. Names with a future designation are
not implemented runtime controls and must not be treated as unlocking production.

| Name | Scope | Description |
|---|---|---|
| DEPLOYMENT_MODE | backend | staging-real for restricted real extraction; staging/cloud retain mock-only enforcement; production is blocked |
| DEMO_MODE | backend | false required for staging-real; true required for staging/cloud mock mode |
| GEMINI_API_KEY | backend secret only | configure through Render Environment; required by the Blueprint; never in Git, frontend or a secret file |
| GEMINI_MODEL | backend | supported project model ID; enter gemini-3.8-flash if available to the project; no model-access API check has been performed |
| SUPABASE_URL | backend only | project API endpoint; dedicated project per environment |
| SUPABASE_SERVICE_KEY | backend secret | privileged database/Storage credential; never a Vite variable |
| SUPABASE_BUCKET_NAME | backend | existing private original-document bucket |
| API_USERNAME | staging backend | shared restricted-demo login identifier; not clinical identity |
| API_PASSWORD | staging backend secret | strong shared demo password, minimum 16 characters |
| CORS_ORIGINS | backend | JSON array of exact HTTPS frontend origins |
| PORT | hosting runtime | host-assigned web-service listening port |
| TEMP_STORAGE_PATH | backend | disposable scratch/export directory, not durable storage |
| MAX_FILE_SIZE_MB | backend | per-file byte budget |
| MAX_FILES_PER_BATCH | backend | maximum files in one upload |
| MAX_PAGES_PER_DOCUMENT | backend | accepted PDF page budget |
| MAX_REQUEST_SIZE_MB | backend | total streamed request cap including multipart overhead |
| MAX_IMAGE_PIXELS | backend | accepted image pixel budget |
| UPLOAD_REQUESTS_PER_MINUTE | backend | modest per-process demo upload throttle |
| CONCURRENT_PROCESSING_BATCHES | backend | active in-process demo batch cap |
| HYBRID_ENGINE_ENABLED | backend | optional hybrid pipeline master setting |
| HYBRID_ENABLE_PREPROCESSING | backend | optional image preprocessing |
| HYBRID_ENABLE_OCR | backend | optional OCR verification |
| HYBRID_ENABLE_HYBRID_VERIFICATION | backend | optional cross-verification |
| HYBRID_ENABLE_FOCUSED_RETRY | backend | optional focused extraction retry |
| VITE_API_URL | frontend build, public | actual HTTPS backend origin |
| VITE_DEPLOYMENT_MODE | frontend build, public | validates hosted-versus-local API configuration |
| REDIS_URL | future API/worker secret | proposed internal queue connection; no consumer implemented |

### Exact restricted staging settings

Manually configure these eight backend names in Render **Environment** (sync:false
prompts apply to newly created Blueprint services; add them manually on existing ones):

- GEMINI_API_KEY: the staging Gemini Developer API credential; keep its value secret.
- GEMINI_MODEL: the intended project-supported model ID (currently gemini-3.8-flash).
- SUPABASE_URL: the dedicated staging project's exact HTTPS API origin.
- SUPABASE_SERVICE_KEY: its backend-only privileged credential; keep its value secret.
- SUPABASE_BUCKET_NAME: the existing private staging bucket.
- API_USERNAME and API_PASSWORD: the restricted staging login; password at least 16 characters.
- CORS_ORIGINS: a JSON array containing the actual frontend HTTPS origin, without trailing slash.

The Blueprint supplies these non-secret backend settings; retain them:

```text
DEPLOYMENT_MODE=staging-real
DEMO_MODE=false
HYBRID_ENGINE_ENABLED=false
HYBRID_ENABLE_PREPROCESSING=false
HYBRID_ENABLE_OCR=false
HYBRID_ENABLE_HYBRID_VERIFICATION=false
HYBRID_ENABLE_FOCUSED_RETRY=false
MAX_FILE_SIZE_MB=10
MAX_FILES_PER_BATCH=3
MAX_PAGES_PER_DOCUMENT=10
MAX_REQUEST_SIZE_MB=32
MAX_IMAGE_PIXELS=12000000
CONCURRENT_PROCESSING_BATCHES=1
UPLOAD_REQUESTS_PER_MINUTE=6
```

On the frontend configure VITE_API_URL as the actual backend HTTPS origin (no path).
Retain the Blueprint's VITE_DEPLOYMENT_MODE=staging. These are the only two allowed
public build variables. Never add VITE_GEMINI_API_KEY or any backend credential.
Render supplies PORT; the Docker image supplies TEMP_STORAGE_PATH. Leave APP_ENV_FILE
unset in Render. Hosted key loading ignores dotenv files and accepts only backend
process variables. GEMINI_API_1 through GEMINI_API_8 are supported backend-only
alternatives, but one GEMINI_API_KEY is sufficient; key rotation does not add quota.

Missing environment keys, DEMO_MODE=true in staging-real, missing Supabase/login,
invalid HTTPS endpoints/CORS or production mode prevent startup. A private-bucket
readiness failure also prevents healthy deployment. Invalid credentials, unavailable
models, schema rejection, provider/network failure and quota exhaustion are detected
when processing, not by making a startup Gemini request. They return sanitized batch
errors without switching to MockExtractor.

Future institutional JWT issuer/audience/JWKS identifiers, SSO applications, tenant
policy configuration, audit settings and monitoring destinations will be named only
after provider/organization requirements are confirmed. There are no dummy secret
values, institutional URLs or fake production-control switches in this runbook.

## 6. Worker and production resource preparation

Read docs/PRODUCTION_ARCHITECTURE.md before considering the production template.
The proposed topology is a separate Docker API, separate Docker worker, a private
paid Render Key Value transport and dedicated Supabase PostgreSQL/Storage. Supabase
remains the system of record; no additional record database is introduced.

The queue is appropriate only with a transactional PostgreSQL job/outbox, leases,
idempotent page checkpoints, bounded retries, fencing and a reconciler. A queue
connection string alone does not implement recovery. No schema/RPC work or consumer
was added. The template worker command `python -m app.production_preflight` is a
nonfunctional blocker that exits with code 78, not a worker to deploy.

Do not apply render.production.yaml.template. It contains explicitly unresolved
release-branch/region markers and unapproved paid plans. After all P0 blockers and
institutional requirements are resolved, an engineer must replace the stub with a
real worker entry point, implement auth/tenant/audit controls, replace placeholders,
obtain paid-resource approval and review the finalized Blueprint. No environment
variable can enable the current production server.

Render Key Value production requirements: approved private internal connection,
external access denied, internal authentication reviewed, noeviction and journal-
snapshot persistence. A database outbox remains necessary because queue persistence
can lose recent writes. Get a current quote; do not rely on free queue durability.
No paid resources are provisioned by this work.

## 7. Manual release steps after approval

1. Approve and commit the exact release revision; satisfy the focused validation
   checklist below. Get separate push/deployment/resource approvals as applicable.
2. Push only the authorized branch with the command in section 1.
3. Review Blueprint sync changes before applying them; no automatic migrations.
4. For a configured service, use **Manual Deploy > Deploy a specific commit**, choose
   the approved revision, and confirm. If the dashboard labels differ, use its manual
   deploy control that explicitly selects the approved commit; never assume latest.
5. Inspect **Events/Logs** for build/startup, then confirm /ready through the approved
   runtime check. Configure the frontend origin/API origin and deploy the frontend
   from the same release revision. Verify its SPA refresh and authentication flow.
6. Permit synthetic or institutionally approved non-sensitive documents only. Clinical data remains prohibited until
   the institution signs off every clinical release gate.

## 8. Static evidence and focused release validation

Earlier deployment-preparation static checks: Python AST parsing of 47 application files,
YAML duplicate-key/structure/path checks, application TypeScript no-emit checking,
Vite configuration TypeScript no-emit checking and Git whitespace checks. The first
Vite type-check exposed config target/type issues; those were fixed and the check
passed. These checks import no application modules and contact no cloud services.

To repeat only those static checks (PyYAML must already be available for the Python
validator; no new dependency installation was performed here):

```powershell
Set-Location -LiteralPath 'D:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration'
python scripts/validate_render_preparation.py
git diff --check
Set-Location -LiteralPath 'D:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration\frontend'
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
node node_modules/typescript/bin/tsc --noEmit --incremental false --composite false -p tsconfig.node.json
```

### Focused runtime validation required before release (NOT executed here)

These are a bounded future validation checklist, not another broad E2E campaign:

- Python dependency installation/container build on Linux, non-root startup and
  PORT binding; frontend production build using its real staging origin.
- Startup rejects production mode, mismatched staging mode/DEMO_MODE, missing/partial credentials,
  public bucket, wildcard/non-HTTPS CORS and invalid configuration.
- /live versus /ready behavior on unavailable storage; valid JSON and no secret errors.
- An unauthenticated API/document request is denied; authenticated source retrieval
  and expired/invalid sign-in behavior work with exact-origin CORS.
- In staging-real, /ready reports environment=staging-real, demo_mode=false and
  extractor=GeminiExtractor; logs show EXTRACTOR_TYPE: GeminiExtractor. The UI displays
  the restricted real-extraction notice. Storage readiness does not prove Gemini access.
- Only after explicit live-call/deployment approval, process one new synthetic page.
  Compare the source values, require exactly one commitment, verify unreviewed export
  is blocked, save a correction and approve required fields, then confirm one Excel
  data row with that correction. No existing batch is reprocessed.
- If an API failure occurs, review shows the sanitized error_code/message and available
  retry delay, including quota-stopped batches. Do not treat HTTP 202 as extraction
  success or enable mock mode to make the real-extraction check pass.
- Oversized declared/streamed requests/files, bad MIME, invalid/encrypted/over-page
  PDFs, large images, upload-rate and processing-capacity limits return clear failures.
- On synthetic data only, a targeted saved correction/version-conflict/restart/export
  check for the newly connected persistence path, if the owner authorizes it. Existing
  owner evidence is not claimed as runtime proof of the new code.
- For future production only: JWT/MFA/roles/tenant-denial, audit atomicity, worker kill/
  retry/duplicate delivery and DB/object restore tests after approved implementation.

This staging-real revision adds focused offline checks for hosted configuration,
environment-only key loading, actual GeminiExtractor/Supabase selection, authentication
and terminal quota error visibility. Verification passed: 39 focused offline tests,
then one additional Blueprint-to-Settings parsing test; both application/Vite TypeScript
no-emit checks; offline Blueprint/AST structural validation; Git whitespace checks.
The included earlier 21 offline Gemini tests cover SDK schema compatibility, safe
failures and one commitment per page. There is one existing Pydantic deprecation warning.
No live Supabase
test, runtime server, Docker build, frontend production build or Gemini call is run
in this task. Offline checks do not prove live credentials, quota, availability or
extraction accuracy. The owner's earlier Supabase tests remain separate evidence.

## 9. Troubleshooting

| Symptom | First checks | Safe response |
|---|---|---|
| Docker build fails | context/Dockerfile relative to backend, dependency markers, system libs | fix source; do not broaden context to include artifacts |
| Static build fails | lockfile, public env allowlist, exact HTTPS API origin, TypeScript diagnostics | correct config; never put backend secrets into Vite |
| Startup fails closed | deployment mode, staging credentials, DEMO setting, exact CORS, private bucket/schema access | fix approved configuration; do not bypass production block |
| Readiness fails | Supabase reachability/permissions/private bucket and safe logs | resolve owner-approved connectivity; never fallback to local disk |
| 401 | demo credentials/session and cross-origin Authorization | sign in again; do not expose credentials in URLs |
| 409 on save | stale batch version or blocked reprocessing | reload and reconcile; do not overwrite reviewed data |
| 413/429 | configured request/file/processing/rate caps | retry within limits; do not disable all controls |
| queued/processing after restart | current in-process staging worker was interrupted | authorized manual recovery; preserve original/partial review; no blind reset |
| missing legacy source | older record lacks a durable manifest/original | approved recovery/import; do not fabricate a source or empty success |

## 10. Rollback, monitoring and costs

Rollback is a code/config release action requiring approval. Preserve current data
and capture the failed revision/config inventory. In each service use Render's
previous known-good deploy/rollback control or manually deploy a compatible known-
good commit. Restore frontend/API/worker versions together where their contracts
require it. Do not reset Git, wipe storage, delete clinical records or reverse a
migration blindly. Baseline 71c56ee lacks hosted persistence and must NOT be used
as a cloud rollback target over Supabase data. Checkpoint 0f71767 is an implementation
checkpoint, not automatically an operationally validated rollback target.

Database/schema changes need a separately reviewed expand/contract and backup plan.
No such migration is included. For a destructive incident, follow the approved
institutional DB AND Storage restore plan with explicit RPO/RTO and authorized operators.

Use Render **Metrics**, **Events**, **Logs** and an institution-approved monitoring
system. Watch memory/CPU, readiness failures, failed saves/conflicts, authentication
failures and (future) queue/outbox age/stale leases/dead letters. Assign on-call owners,
thresholds and alert destinations. No sensitive values in log/alert payloads; no
Authorization headers, source URLs or patient names. Current access logs are disabled.

Free staging resources are suitable only for a constrained demonstration, not a
clinical availability/SLA claim. Production template resource estimates, queue
persistence, Supabase backup/storage and monitoring costs require current vendor
quotes and explicit budget approval. Region selection is an institutional privacy
and data-residency decision, not a default inferred from staging.

## 11. Production blockers and approval checklist

P0: individual identity/SSO, MFA policy, server-enforced RBAC and organization access;
durable job/outbox/worker/recovery; protected transactional access/change/export audit;
confirmed RLS/service-role scope; institutional privacy/security/legal/data-residency
sign-offs; and focused runtime evidence for the new release. Production remains disabled.

P1: distributed abuse controls, malware/quarantine design, retention/deletion/legal
holds, verified database/object backup/restore, operational alerts and dependency/
image locking plus vulnerability review. P2: localization/accessibility, CSP refinement
and operator recovery usability. Full acceptance criteria are in the architecture guide.

Approval is required for pushes, deployment/Blueprint Apply, paid resources, schema/
RPC migrations, RLS changes, destructive data operations, live Gemini calls or clinical
data. The staging-real implementation is authorized; no live call/deployment is
authorized by this checkpoint. No compliance certification or clinical release is implied.

## Reference documentation

- [Render monorepo paths](https://render.com/docs/monorepo-support)
- [Render Blueprint fields and manual autodeploy controls](https://render.com/docs/blueprint-spec)
- [Background workers](https://render.com/docs/background-workers)
- [Key Value persistence](https://render.com/docs/key-value#data-persistence)
- [Supabase JWT validation](https://supabase.com/docs/guides/auth/jwts)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
