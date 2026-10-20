# Persistence audit and implementation handoff

Baseline: `71c56eec276c9189bc019f47b0b687683ba7377e` on `integration/final-mvp`,
inside the existing `final-integration` worktree. Existing unrelated modifications
and temporary artifacts were preserved.

## Evidence and limits

The user states that they already performed Supabase persistence tests. Those tests
were not repeated here and are not independently certified by this report. Initial
local configuration inspection found no configured Supabase URL/service credential.
No cloud calls, migrations, writes, deletions, Gemini calls or deployment occurred.
After the user's updated instruction, no additional tests, E2E workflows, backend
restart experiment, dependency installation or frontend build was run. The earlier
57 passing tests and successful frontend build apply only to the baseline commit,
not these new integration edits. Changes were reviewed as source/diff only.

## Initial actual backends

| Operation | Before | Implementation now prepared |
|---|---|---|
| Upload/original document | local disk only | selected adapter; private Storage objects in cloud |
| Batch creation | local directory only | persistent JSONB manifest after object uploads |
| Processing state | in-memory jobs, final JSON | persistent queued/processing/final state; in-memory worker |
| Commitment/patient fields | JSON files | existing batches JSONB via adapter |
| Corrections and review | JSON read/modify/write | same JSONB record, conditional updated_at writes |
| Export eligibility | local JSON | selected backend, same required-review policy |
| Source retrieval | local file search | persisted manifest and authenticated private download |
| Rendering and Excel | local files | disposable scratch/output, never persistence authority |

The Supabase adapter previously existed but had no application callers. Its upsert
could overwrite stale data, and the existing health endpoint tested only local disk
and constructed invalid JSON using Python dict formatting. Render configuration used
an incorrect backend build path and a non-JSON CORS setting; Docker copied the entire
backend context, risking accidental inclusion of untracked artifacts.

## Changes

- Connected upload, document retrieval, process APIs and background worker to the
  existing storage factory. Added document operations to the local adapter.
- Stored generated document identifiers and private object names in the existing
  batch JSONB schema. Kept one record per page and existing field wrappers/review rules.
- Preserved batch manifests through result/error saves. Timeouts retain a pending
  commitment record for that page. Downloaded originals use a disposable processing folder.
- Blocked reprocessing when records exist. Optimistic updated_at checks reject stale
  cloud review saves with HTTP 409 rather than overwriting reviewed values.
- Cloud mode refuses missing credentials and ephemeral fallback. Startup checks
  private bucket/schema access; deployment auth/CORS/mock-mode misconfiguration fails.
- Protected every API route including original document retrieval with shared demo
  authentication. Added frontend sign-in, authenticated document fetching, source-view
  access from the page table and an explicit synthetic-data banner.
- Replaced local-only health behavior with valid JSON and selected-backend readiness.
- Removed sensitive active processing error/candidate logging and suppressed Docker
  HTTP access logs. Errors returned by the application do not include provider details.
- Prepared Render Docker/static configuration, platform-specific magic dependencies,
  safer Docker copying/ignore rules, and updated deployment documentation.

## Outstanding evidence and blockers

No live schema, bucket policy, RLS, restart or latest-build evidence was collected.
Use the user's prior evidence as their testing, not as verification of these new changes.
New source/config edits are candidates for review/commit, not a freshly tested release.
Do not deploy until the owner accepts that validation gap and explicitly approves release.
Additional clinical/security limitations and exact approval-dependent deployment steps
are listed in DEPLOYMENT.md. No table structure or cloud data was changed.

## Candidate files for a future selective commit

- DEPLOYMENT.md
- docs/PERSISTENCE_READINESS_AUDIT.md
- render.yaml
- backend/.dockerignore
- backend/Dockerfile
- backend/docker-compose.yml
- backend/requirements.txt
- backend/app/core/config.py
- backend/app/core/access.py
- backend/app/main.py
- backend/app/api/upload.py
- backend/app/api/documents.py
- backend/app/api/process.py
- backend/app/services/storage/storage_adapter.py
- backend/app/services/storage/json_storage.py
- backend/app/services/processing/background.py
- frontend/src/App.tsx
- frontend/src/services/api.ts
- frontend/src/features/review/DocumentViewerModal.tsx
- frontend/src/features/review/ReviewScreenNew.tsx

Do not include the pre-existing modifications to e2e_batch_processing_test.py or
test_live_single_extraction.py, .agents, environment files, batch dumps, scripts,
PDFs or XLSX artifacts. No new commit was made because the original request limited
commits to verified changes and the updated instruction stops further verification.


## Checkpoint update - 2026-10-20

The previous no-commit statement records the earlier handoff. At the user's later
explicit instruction, exactly the 20 candidate files above were inspected/staged and
committed as `0f71767d62320d49b3869ca60dc7fde63b73139c`, message
`feat: integrate Supabase persistence and prepare secure deployment`.
The staged diff/credential-pattern and whitespace checks passed; no real patient
information, credentials, generated artifacts or unrelated changes were included.
This commit records implementation only, not production runtime validation.

Further deployment hardening is a separate uncommitted change set. See
docs/DEPLOYMENT_PREPARATION_STATUS.md for its exact file list, offline-static evidence
and remaining blockers. The user's earlier tests remain their evidence; they were
not repeated as live tests in this task.
