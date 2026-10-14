---
title: "Virology Lab Commitment Extraction - Tasks"
status: AWAITING_APPROVAL
version: "2.0"
---

# Tasks — רשימת משימות MVP

> **Status:** AWAITING APPROVAL  
> **Timeline:** ~7 days  
> **Budget:** 0 ₪

## Protocol

**Single Task Approval:**
1. Your approval: "מאשרת TASK-XXX" → IN_PROGRESS
2. Implementation → IN_REVIEW → Your approval → DONE
3. **One task at a time, no auto-continue**

**Priority:**
- 🔴 **MUST** — Required for MVP
- 🟡 **SHOULD** — Recommended
- 🟢 **OPTIONAL** — Can defer

---

## Phase 1: Foundation (Days 1-2)

- [x] **TASK-001: Git Setup & Project Structure** | 🔴 MUST | Dependencies: None | Time: 1-2h | ✅ **DONE** (Commit: 7f9c59a) | Goal: הקמת מאגר Git מאובטח עם `.gitignore` מוגן secrets. Steps: Initialize Git, create/update `.gitignore` (.env, reference/, temp/, tests/fixtures/), create `.env.example`, create `README.md` (setup, usage), verify no secrets in Git. Acceptance: `.gitignore` protects secrets, `.env.example` documented, README with instructions, no secrets in history. Files: `.gitignore`, `.env.example`, `README.md`

- [x] **TASK-002: Gemini API Verification** | 🔴 MUST | Dependencies: TASK-001 | Time: 1-2h | ✅ **DONE** (Model: gemini-3.5-flash-lite, IPv4 via curl) | Goal: אימות זמינות Gemini Vision Free Tier. Steps: Read Google AI Studio docs, verify model supports (image + JSON + Free Tier), create free API key, document model name/limits (req/min, req/day), test key (simple call), write `docs/GEMINI_SETUP.md`. Acceptance: Free model identified, API key created (in `.env` only), quota limits documented, no billing (0 ₪), capabilities confirmed. **Blocker:** If no suitable Free Tier model → CRITICAL BLOCKER. Files: `docs/GEMINI_SETUP.md`, `.env` (local)

- [ ] **TASK-003: Backend Stack Definition** | 🔴 MUST | Dependencies: TASK-001 | Time: 1-2h | Goal: הגדרת dependencies ו-`requirements.txt`. Steps: Choose Python 3.10+, create `backend/requirements.txt` with fastapi, uvicorn, pydantic, pydantic-settings, python-dotenv, google-genai, Pillow, PyMuPDF, openpyxl, python-multipart, pytest, pytest-asyncio, httpx. Document system requirements in README. **No installation yet**. Acceptance: `requirements.txt` complete, all deps free/open-source, SDK `google-genai`, includes `python-multipart`. Files: `backend/requirements.txt`

- [ ] **TASK-004: Frontend Stack Definition** | 🔴 MUST | Dependencies: TASK-001 | Time: 1-2h | Goal: scaffold Frontend עם React + TypeScript. Steps: Choose Node 18+, `npm create vite@latest frontend -- --template react-ts`, add to `package.json`: @tanstack/react-query, axios, react-hook-form. Configure RTL in `src/index.css`: `html { direction: rtl; }`. **No installation yet**. Acceptance: `package.json` with deps, RTL configured, TypeScript enabled. Files: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/src/index.css`

---

## Phase 2: Core Backend (Days 2-3)

- [ ] **TASK-005: Backend Skeleton + Extractor Interface** | 🔴 MUST | Dependencies: TASK-003 | Time: 3-4h | Goal: FastAPI app + **Extractor Interface** (for future Enterprise swap). Steps: Install `pip install -r requirements.txt`, create structure (app/main.py, core/config.py, api/, domain/models.py, services/extraction/extractor.py as ABC, services/validation/, review/, export/, storage/), main.py with FastAPI + CORS (localhost:5173) + `/health`, config.py loads `.env` with Pydantic, extractor.py defines abstract `Extractor` class. Run `uvicorn app.main:app --reload`, test `curl localhost:8000/health`. Acceptance: FastAPI runs, `/health` returns 200, CORS for localhost:5173, `.env` loaded, **Extractor Interface defined**. Why Interface: Enables future swap to Enterprise Gemini without breaking UI/Export. Files: `app/main.py`, `app/core/config.py`, `app/services/extraction/extractor.py`

- [ ] **TASK-006: Domain Models — 7 Fields + States** | 🔴 MUST | Dependencies: TASK-005 | Time: 3-4h | Goal: Pydantic models for 7 fields with extraction/review states. Steps: Create `domain/models.py` with ExtractionState enum (found, uncertain, missing, conflicting, invalid), ReviewState enum (pending, needs_review, human_verified, rejected), FieldValue[T] generic (raw_value, normalized_value, reviewed_value, extraction_state, review_state, validation_issues[], evidence_refs[]), TestRecord (test_id, patient_first_name, patient_last_name, patient_full_name_raw, patient_id_number, sender, received_date, central_numbers, commitment_ids), CommitmentRecord (commitment_record_id, test_id, commitment_number, central_number_refs[], relation_status, review_status). Write unit tests. Acceptance: All 7 fields defined, numbers as strings, extraction_state ≠ review_state, support multiple values, raw/normalized/reviewed separate. Files: `domain/models.py`, `tests/test_models.py`

- [ ] **TASK-007: Gemini Real API Integration** | 🔴 MUST | Dependencies: TASK-002, TASK-006 | Time: 4-6h | **⚠️ REQUIRES:** Approval to use sample forms | Goal: **חיבור אמיתי ל-Gemini** + test with one real sample. Steps: Implement `GeminiExtractor(Extractor)` with `__init__(api_key, model)` using `genai.Client`, `extract(image, doc_id, page)` with prompt for 7 fields (missing→null, uncertain→warnings, multiple→list, numbers→strings), handle timeout/429/5xx, return ExtractionResult. **Test with ONE real sample form:** convert PDF page→image, send to Gemini, print JSON, **manual comparison** vs original. Document: model, prompt version, sample result, issues. Acceptance: **Gemini API works (NOT Mock!)**, real image sent, structured JSON received, missing→null (not invented), errors handled, logs clean (no PII), manual comparison documented. Risk: HIGH. Files: `services/extraction/gemini_adapter.py`, `tests/test_gemini_real.py`, `docs/EXTRACTION_RESULTS.md`

- [ ] **TASK-008: Golden Dataset Creation** | 🔴 MUST | Dependencies: TASK-007 | Time: 4-6h | Goal: 10-15 טפסים מתויגים ידנית **מוקדם בפיתוח**. Steps: Select 10-15 representative forms (clear print, Hebrew/English handwriting, sticker, stamp, rotated, multiple numbers, poor quality). **Manual tagging** for all 7 fields with exact values. Save `tests/fixtures/golden_dataset.json` with dev_set (8 forms) and eval_set (7 forms). **Data leakage prevention:** dev/eval split, no overlap, same form pages in same set. Protect from Git (`.gitignore` includes `tests/fixtures/`). Document in `docs/GOLDEN_DATASET.md`. Acceptance: 10-15 forms tagged, manual tagging complete, dev/eval split clear, no leakage, protected from Git. Files: `tests/fixtures/golden_dataset.json`, `docs/GOLDEN_DATASET.md`

- [ ] **TASK-009: Accuracy Measurement — Real Gemini** | 🔴 MUST | Dependencies: TASK-008 | Time: 2-3h | Goal: מדידת דיוק אמיתית **מוקדם בפיתוח**. Steps: Create `tests/test_accuracy.py` that loads eval_set, for each sample: load image, call GeminiExtractor (REAL API), compare to expected_fields, calculate metrics (field accuracy per field, coverage, false extraction, unsafe acceptance, review burden, multi-value recall). Generate `tests/accuracy_report.txt` with actual results (not illustrative). Document specific errors. Acceptance: **Real Gemini calls (not Mock)**, full accuracy report, silent errors documented, hallucinations documented, distinction print vs handwriting. Note: Report numbers are measurement results, not guarantees. Files: `tests/test_accuracy.py`, `tests/accuracy_report.txt`

- [ ] **TASK-010: Validation Service — Deterministic Rules** | 🔴 MUST | Dependencies: TASK-006 | Time: 3-4h | Goal: אימות דטרמיניסטי (ID checksum, dates, conflicts). Steps: Create `services/validation/validator.py` with `validate_id_number` (Israeli ID checksum), `validate_date` (parse, check not future), `validate_required_fields` (check required present), `detect_conflicts` (multiple contradicting values). **No auto-correction** — only flag issues. Unit tests in `tests/test_validation.py`. Acceptance: ID checksum works, date validated, missing detected, conflicts flagged, no auto-fix, unit tests pass. Name Splitting (D-12): Keep `full_name_raw`, split only if clear evidence. Files: `services/validation/validator.py`, `tests/test_validation.py`

---

## Phase 3: Frontend & Processing (Days 3-4)

- [ ] **TASK-011: Frontend Skeleton** | 🔴 MUST | Dependencies: TASK-004, TASK-005 | Time: 2-3h | Goal: Frontend עם קריאה ל-`/health`. Steps: Install `npm install`, create `src/services/api.ts` with axios baseURL localhost:8000, export `healthCheck`, update `App.tsx` to call `/health` and display result. Run `npm run dev`, test open `localhost:5173`. Acceptance: Frontend runs, RTL works, API call succeeds, CORS works. Files: `src/services/api.ts`, `src/App.tsx`

- [ ] **TASK-012: File Upload with Validation** | 🔴 MUST | Dependencies: TASK-011 | Time: 4-5h | Goal: העלאת קובץ (PDF/image) עם validation. Steps: Backend `api/upload.py` with `POST /api/batches` accepting List[UploadFile], validate MIME + magic bytes, check size (20MB per D-14), save to `temp/{batch_id}/{uuid}.{ext}`, return `{batch_id, document_ids}`. Frontend `features/upload/UploadForm.tsx` with file input (accept .pdf,.png,.jpg), button "העלה קובץ". Test: upload valid→200, too large→413, invalid→400. Acceptance: Single file upload works, client + server validation, MIME + magic bytes checked, UUID returned, secure storage (not web root). Files: `api/upload.py`, `features/upload/UploadForm.tsx`

- [ ] **TASK-013: Processing Pipeline + Uncertainty Detection + Multi-Page/Multi-Values** | 🔴 MUST | Dependencies: TASK-007, TASK-010, TASK-012 | Time: 7-8h | Goal: עיבוד + **סימון אי-ודאות בזמן עיבוד** + multi-page + multi-values. Steps: Create `services/documents/renderer.py` with `pdf_to_images` (PyMuPDF), `detect_rotation` (return 0/90/180/270). Create `api/process.py` with `POST /api/batches/{batch_id}/process`: for each doc: convert to images, detect+fix rotation, for each page: call GeminiExtractor, map to TestRecord/CommitmentRecord. **Uncertainty detection (integrated):** for each field: if raw_value is None→extraction_state=missing, review_state=needs_review; if warnings indicate uncertain→extraction_state=uncertain, review_state=needs_review; if looks_uncertain→extraction_state=uncertain, review_state=needs_review. Run ValidationService, for each issue: attach to field.validation_issues, if severity=error→extraction_state=invalid, review_state=needs_review. **Multi-values (integrated):** preserve all central_numbers and commitment_numbers, no loss. **Multi-page (integrated, per D-06):** conservative default: each page=separate form; if clear evidence (same barcode/central)→group; if unclear→**mark as unresolved issue, don't merge silently**. Save. Test with one real form. Acceptance: **Real Gemini call**, **uncertainty detection works during processing**, missing→flagged, uncertain→flagged, invalid→flagged, multiple values preserved, multi-page handled (conservative or grouped), timeout handled. Files: `services/documents/renderer.py`, `api/process.py`

---

## Phase 4: Review UI (Days 4-5)

- [ ] **TASK-014: Review Screen — Display with Colors** | 🔴 MUST | Dependencies: TASK-013 | Time: 5-6h | Goal: מסך review עם סימון צבעים ומסמך מקור. Steps: Backend `GET /api/batches/{batch_id}` returns all records with fields+states, `GET /api/batches/{batch_id}/documents/{doc_id}/preview` returns image with ownership validation. Frontend `features/review/ReviewScreen.tsx` with flex layout: left side shows document image, right side shows table with fields (name, value, state, reason, edit button). Color function: if human_verified or pending→white, if uncertain→orange, if missing/invalid/conflicting→red. Acceptance: All 7 fields displayed, colors correct (white/orange/red), reason shown for flagged, source image displayed, RTL works. Files: `api/batches.py`, `api/documents.py`, `features/review/ReviewScreen.tsx`

- [ ] **TASK-015: Manual Correction — Full Support + Relationships** | 🔴 MUST | Dependencies: TASK-014 | Time: 6-7h | Goal: תיקון ידני **מלא** כולל אישור ריק, רשימות, **שיוכים בסיסיים**. Steps: Frontend `features/review/EditFieldModal.tsx` with: if field is list→map values with input per value + "הוסף ערך" button, else single input; checkbox "אישור שדה ריק (אין מידע במסמך)"; save button. **Basic relationship editing (for critical unresolved):** if CommitmentRecord has relation_status='unknown' and is_required_for_export→show UI to manually link to specific central_numbers or mark as "no clear link" (to unblock export). Backend `PATCH /api/batches/{batch_id}/records/{record_id}` with: load record, update field.reviewed_value (can be empty string if confirmed), set field.review_state=human_verified, re-validate after correction (if new issues→still needs_review), ETag to prevent race (409 if mismatch), save. Export priority: if human_verified→reviewed_value (even if empty!), else→normalized_value or raw_value or ''. **No truthy fallback**. Acceptance: Edit+save works, approve existing works, approve empty works, edit lists works, **basic relationship editing for unresolved links**, re-validation after edit, no AI overwrite, ETag prevents race, export uses reviewed (even empty). Files: `features/review/EditFieldModal.tsx`, `features/review/RelationshipEditor.tsx`, `api/records.py`

- [ ] **TASK-016: Focused Re-extraction** | 🟢 OPTIONAL | Dependencies: TASK-013 | Time: 3-4h | Goal: ניסיון חוזר ממוקד (רק אם יש bbox ונמצא שימושי). Deferred: Can skip for MVP, evaluate after initial testing.

---

## Phase 5: Excel & Batch (Day 5)

- [ ] **TASK-017: Batch Processing — Multiple Documents** | 🔴 MUST | Dependencies: TASK-013 | Time: 3-4h | Goal: עיבוד אצווה עם בידוד כשלים. Steps: Update `POST /api/batches` (multiple files), update `POST /api/batches/{id}/process`: process sequentially or limited concurrency (2-3), per-doc status (pending/processing/completed/failed), isolation (one failure doesn't cancel others). Update `GET /api/batches/{id}`: status for all docs. Acceptance: Multiple docs processed, failure isolation, progress tracking. Files: `api/upload.py`, `api/process.py`, `api/batches.py`

- [ ] **TASK-018: Excel Exporter — Provisional** | 🔴 MUST | Dependencies: TASK-015, TASK-017 | Time: 4-5h | **🔒 BLOCKED by:** D-04, D-05, D-13 (final format) | Goal: Excel עם mapping זמני. Steps: Create `services/export/excel_exporter.py` with `export_to_excel(records)`: create workbook, provisional headers (שם פרטי, שם משפחה, ת.ז, מספרים מרכזיים, תאריך קבלה, גורם שולח, מספר התחייבות), for each CommitmentRecord: get test, get export values using priority (human_verified→reviewed_value even if empty!, else→normalized or raw or ''), provisional N:M (centrals as `;` delimiter per D-05 pending), sanitize formula injection (`=+-@`→prefix `'`), append row, set numbers as text cells. Roundtrip test. Provisional decisions (until D-04/D-05/D-13): columns as above, N centrals→`;`, no commitment→**ask user when needed**. Acceptance: Excel generated, one row per commitment, zeros preserved, formula injection blocked, roundtrip works, export respects human_verified (even empty). Files: `services/export/excel_exporter.py`, `api/export.py`, `tests/test_excel_export.py`

- [ ] **TASK-019: Export Blocking — Comprehensive** | 🔴 MUST | Dependencies: TASK-018 | Time: 3-4h | Goal: חסימה **מקיפה** של ייצוא. Steps: Create `GET /api/batches/{batch_id}/export-status`: check ALL blocking conditions: (1) fields with review_state=needs_review, (2) documents with status pending/processing/failed, (3) unresolved relationships (commitment↔central marked ambiguous/unknown and required for export), (4) any other issue per PLAN.md 8.1. Return `{can_export: bool, blockers: [{type, details}], blocker_count: int}`. Blocker types: unresolved_field, incomplete_document, unresolved_relationship, other. Create `POST /api/batches/{batch_id}/export`: re-check all conditions, if ANY blocker→409 with full list, else generate Excel and return FileResponse. Frontend `features/export/ExportButton.tsx`: disable button if !can_export, show blocker count and detailed list with links to fix. Write tests for each blocker type. Acceptance: Button disabled when blockers exist, **API enforces blocking (not just UI)**, blocks on: unresolved fields/docs/relationships, clear blocker list displayed, link to fix blockers, backend enforcement. Files: `api/export.py`, `features/export/ExportButton.tsx`, `tests/test_export_blocking.py`

---

## Phase 6: Quality (Day 6)

- [ ] **TASK-020: Regression Tests** | 🔴 MUST | Dependencies: TASK-009 | Time: 2-3h | Goal: בדיקות רגרסיה מכשלים ידועים. Steps: Create `tests/test_regression.py` with `test_handwritten_name_not_invented`: load handwritten name case, call extract, assert extraction_state in [uncertain, missing], assert review_state=needs_review. Add other failures from golden benchmark. Acceptance: Regression tests exist, handwritten name case included. Files: `tests/test_regression.py`

- [ ] **TASK-021: Unit & Integration Tests — Mock** | 🟡 SHOULD | Dependencies: TASK-006, TASK-010 | Time: 4-5h | Goal: בדיקות טכניות עם Mock. Steps: Create `tests/unit/test_models.py`, `tests/unit/test_validation.py`. Create `tests/integration/test_extraction_contract.py` with MockExtractor class. **Mark clearly: Mock for tech tests, NOT accuracy**. Acceptance: Unit tests pass, integration with Mock passes, documented Mock only. Files: `tests/unit/`, `tests/integration/`

- [ ] **TASK-022: Security Hardening** | 🔴 MUST | Dependencies: TASK-018 | Time: 3-4h | Goal: בדיקות אבטחה בסיסיות. Steps: Verify: API key not in Git, `.env` in `.gitignore`, CORS restricted, MIME validation, IDOR blocked, formula injection blocked, timeout defined, logs clean (no PII). Dependency scan: `pip-audit`, `npm audit`. Write `docs/SECURITY.md`. Acceptance: Secrets protected, IDOR blocked, formula injection handled, dependencies scanned, logs clean. Files: `docs/SECURITY.md`, `tests/test_security.py`

- [ ] **TASK-023: Test New Form Types** | 🟡 SHOULD | Dependencies: TASK-009 | Time: 2-3h | Goal: בדיקת טפסים חדשים. Steps: Take 3-5 forms NOT in golden dataset, process with system, document results in `docs/TESTED_FORMS.md`. Acceptance: New forms tested, results documented. Files: `docs/TESTED_FORMS.md`

---

## Phase 7: Demo (Day 7)

- [ ] **TASK-024: Cold Start & Demo** | 🔴 MUST | Dependencies: TASK-019, TASK-022 | Time: 3-4h | Goal: הוכחה שהמערכת עובדת מאפס. Steps: Update `README.md` (install, usage), create `demo/demo_script.sh` (start backend+frontend, demo: upload→process→review→export). **Cold start test:** delete temp files, fresh install, run demo, upload→extract→review→export. Acceptance: Cold start works, demo script complete, README clear, **full E2E test including export blocking**. Files: `README.md`, `demo/demo_script.sh`

- [ ] **TASK-025: Documentation & Limitations** | 🔴 MUST | Dependencies: TASK-024 | Time: 2-3h | Goal: תיעוד מגבלות וצעדים לייצור. Steps: Create `docs/LIMITATIONS.md` (MVP prototype, NOT production-ready: Free Tier only, accuracy not guaranteed, single user localhost, no auth, temporary storage 24h, conservative page grouping). Create `docs/PRODUCTION_READINESS.md` (before real medical data: privacy officer approval, data processing agreement Google, organizational access control, key management, backup/recovery, load testing, comprehensive accuracy measurement, professional review). Update PLAN.md status→COMPLETED, update Spec status→COMPLETED. Acceptance: Limitations documented, production steps documented, no false claims. Files: `docs/LIMITATIONS.md`, `docs/PRODUCTION_READINESS.md`

---

## Summary

**Total Tasks:** 25  
**Critical Path:** 001→002→005→006→007→008→009→010→013→014→015→017→018→019→024  
**Timeline:** 6-7 days for critical path

**Priority Breakdown:**
- 🔴 **MUST: 19** (required for MVP)
- 🟡 **SHOULD: 3** (recommended)
- 🟢 **OPTIONAL: 3** (can defer)

**Blockers:**
- D-04, D-05, D-13 → TASK-018 (Excel format) — can use provisional
- D-06 → TASK-013 (page grouping) — use conservative default
- D-12 → TASK-010 (name splitting) — keep full_name_raw

**Key Integrations:**
- TASK-013 includes: uncertainty detection, multi-page handling, multi-values
- TASK-015 includes: basic relationship editing for unresolved links
- TASK-019 includes: comprehensive export blocking (fields, docs, relationships)

---

## Next Step

**"מאשרת TASK-001"** ← to begin
