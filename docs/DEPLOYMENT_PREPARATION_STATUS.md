# Deployment preparation handoff - 2026-10-20

## Git checkpoint

Worktree: final-integration. Branch: integration/final-mvp.
Persistence checkpoint: `0f71767d62320d49b3869ca60dc7fde63b73139c`.
Message: `feat: integrate Supabase persistence and prepare secure deployment`.

Exactly 20 files were committed from the candidate list in PERSISTENCE_READINESS_AUDIT.md:

1. DEPLOYMENT.md
2. docs/PERSISTENCE_READINESS_AUDIT.md
3. render.yaml
4. backend/.dockerignore
5. backend/Dockerfile
6. backend/docker-compose.yml
7. backend/requirements.txt
8. backend/app/core/config.py
9. backend/app/core/access.py
10. backend/app/main.py
11. backend/app/api/upload.py
12. backend/app/api/documents.py
13. backend/app/api/process.py
14. backend/app/services/storage/storage_adapter.py
15. backend/app/services/storage/json_storage.py
16. backend/app/services/processing/background.py
17. frontend/src/App.tsx
18. frontend/src/services/api.ts
19. frontend/src/features/review/DocumentViewerModal.tsx
20. frontend/src/features/review/ReviewScreenNew.tsx

The exact staged allowlist, credential-pattern and diff inspection passed. No real
patient data, keys, environment files, generated artifacts or unrelated changes were
included. This is an implementation checkpoint, NOT production validation.

## Accepted 22-file deployment-preparation milestone

The following exact 22-file set is separate from the persistence checkpoint and is
now authorized for the `chore: prepare Render staging and production security gates`
Git checkpoint (implementation milestone only):

- DECISIONS.md
- DEPLOYMENT.md
- backend/Dockerfile
- backend/app/api/process.py
- backend/app/api/upload.py
- backend/app/core/config.py
- backend/app/core/request_limits.py (new)
- backend/app/main.py
- backend/app/production_preflight.py (new, blocker stub only)
- backend/app/services/processing/background.py
- backend/app/services/storage/storage_adapter.py
- backend/docker-compose.yml
- docs/PERSISTENCE_READINESS_AUDIT.md
- docs/PRODUCTION_ARCHITECTURE.md (new)
- docs/DEPLOYMENT_PREPARATION_STATUS.md (this file, new)
- frontend/src/App.tsx
- frontend/src/services/api.ts
- frontend/tsconfig.node.json
- frontend/vite.config.ts
- render.yaml
- render.production.yaml.template (new, intentionally non-deployable)
- scripts/validate_render_preparation.py (new, offline checks only)

Completed preparation: explicit local/staging/production separation with cloud alias;
production fail-closed gate; exact HTTPS endpoints/CORS; request/file/MIME/PDF/image
limits; modest demo throttling and processing capacity; retained accepted page counts
and missing-page pending records; non-root bounded Docker API; separate live/ready
endpoints; public-build-variable allowlist; login loading/401 state handling; separate
staging Blueprint and blocked production API/worker/private-queue topology; operational,
security, resource and approval runbooks. No clinical business rules were replaced.

## Verification boundary

- Python AST parsing passed for 47 application source files; none imported/executed.
- Offline YAML parse/duplicate-key, monorepo paths, staging env/public-variable and
  template structural checks passed. This is NOT full Render API/schema validation.
- TypeScript no-emit checks passed for the application and Vite configuration.
  The initial Vite check failed on missing process/old target types; corrected by
  avoiding process globals and selecting modern config libraries, then rechecked.
- Git diff whitespace checks passed.
- No runtime tests, E2E campaign, live Supabase checks, backend restart experiment,
  Linux/Docker build, frontend build or dependency installation was performed here.
- No Gemini request, schema/RLS change, paid service, GitHub push, merge or deployment.
- The owner's earlier Supabase/application testing remains their evidence; the prior
  57 passing tests/build apply to baseline 71c56ee, not these new implementation edits.

## Readiness and blockers

Staging: implementation/configuration prepared for a restricted synthetic demo;
focused runtime/build validation and release/deployment approval remain outstanding.
Production: intentionally cannot start. The separate worker is a nonfunctional stub;
no durable consumer/outbox/lease mechanism or clinical identity/audit policy was implemented.

P0: institutional identity/MFA/RBAC/tenant authorization; durable job/outbox/worker and
restart/idempotency recovery; audit ledger; approved RLS/service-role/data-residency/
privacy/security requirements; exact focused runtime release evidence.
P1: distributed abuse controls and malware/quarantine; backup/restore/retention policy;
operational alerts/on-call; reproducibly locked/scanned production dependencies/images.
P2: localization/accessibility, CSP refinement and operator recovery UX.

The production template includes unapproved paid resource estimates and deliberately
unresolved region/release-branch placeholders. Do not apply it. No flag bypasses the
production code block. Clinical data remains prohibited. No compliance certification.

## Preserved unrelated uncommitted changes/artifacts

Modified before this task:
- backend/tests/e2e_batch_processing_test.py
- backend/tests/test_live_single_extraction.py

Untracked before this task:
- .agents/
- backend/batch_dump.json
- backend/dump_batch.py
- backend/inspect_excel.py
- backend/test_3_pages_final.pdf
- backend/test_3page_synthetic.pdf
- backend/test_batch_submit.py
- backend/test_export.xlsx
- backend/test_export_check.py
- backend/verify_batch.py

They were not staged, read for patient values, removed or committed. Do not add them
to the deployment-preparation commit. No environment file was staged.

## Approval-dependent next actions

The owner accepted and authorized this deployment checkpoint; approve a push separately. Follow the
exact dashboard/command runbook in DEPLOYMENT.md for staging. Deployment/Blueprint
Apply, paid infrastructure, schema/RPC or RLS changes, destructive operations and any
real-extraction/clinical enablement require explicit approval. Institutional IdP,
roles, residency, vendors, retention/RPO/RTO and production release decisions remain
unresolved. Full architecture and closure criteria are in PRODUCTION_ARCHITECTURE.md.
