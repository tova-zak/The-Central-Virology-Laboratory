# Design — ארכיטקטורה ועיצוב מערכת

> **Based on:** requirements.md, PLAN.md v2.1  
> **Approved:** 2026-10-14  
> **Approach:** Modular monolith, vertical slices

---

## 1. Architecture Overview

### 1.1 High-Level Design

```
┌─────────────────────────────────────────────┐
│           Frontend (React + TS)             │
│  Upload | Progress | Review | Export        │
└──────────────┬──────────────────────────────┘
               │ REST API
┌──────────────▼──────────────────────────────┐
│        Backend (FastAPI + Python)           │
│  ┌─────────────────────────────────────┐   │
│  │ API Layer (routes, validation)      │   │
│  └─────────────┬───────────────────────┘   │
│  ┌─────────────▼───────────────────────┐   │
│  │ Services (workflow coordinator)     │   │
│  │  ├─ Ingestion                       │   │
│  │  ├─ Document Rendering              │   │
│  │  ├─ Extraction (Gemini adapter)     │   │
│  │  ├─ Validation                      │   │
│  │  ├─ Review                          │   │
│  │  └─ Export                          │   │
│  └─────────────┬───────────────────────┘   │
│  ┌─────────────▼───────────────────────┐   │
│  │ Domain (models, business rules)     │   │
│  └─────────────┬───────────────────────┘   │
│  ┌─────────────▼───────────────────────┐   │
│  │ Storage (temp files + memory)       │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
               │
        ┌──────▼──────┐
        │   Gemini    │
        │  Free Tier  │
        └─────────────┘
```

### 1.2 Technology Stack

**Backend:**
- Python 3.10+
- FastAPI (API framework)
- Pydantic (data validation)
- `google-genai` (Gemini SDK)
- PyMuPDF (PDF rendering)
- Pillow (image processing)
- openpyxl (Excel export)
- pytest (testing)

**Frontend:**
- React 18
- TypeScript
- Vite (build tool)
- TanStack Query (data fetching)
- React Hook Form (forms)

**Infrastructure:**
- localhost only
- No database (temp storage)
- No queue (direct processing)
- No Docker (unless needed for demo)

---

## 2. Core Components

### 2.1 API Layer

**Purpose:** HTTP endpoints, request validation, error handling

**Endpoints:**

```
POST   /api/batches                    # Upload files
GET    /api/batches/{id}               # Batch status
GET    /api/batches/{id}/documents/{doc_id}/preview  # View source
PATCH  /api/batches/{id}/records/{rec_id}  # Manual correction
GET    /api/batches/{id}/export-status    # Can export?
POST   /api/batches/{id}/export           # Generate Excel
GET    /api/exports/{id}                  # Download Excel
DELETE /api/batches/{id}                  # Cleanup
GET    /health                            # Health check
```

**Security:**
- CORS: localhost only
- IDOR: validate batch/doc/record ownership
- MIME validation + magic bytes
- Size limits per D-14
- No path traversal

### 2.2 Domain Models

**Core Entities:**

```python
# Field states
class ExtractionState(Enum):
    found = "found"
    uncertain = "uncertain"
    missing = "missing"
    conflicting = "conflicting"
    invalid = "invalid"

class ReviewState(Enum):
    pending = "pending"          # Not flagged, no review needed
    needs_review = "needs_review"  # Flagged, requires human attention
    human_verified = "human_verified"  # Reviewed/corrected by human
    rejected = "rejected"

# Generic field wrapper
class FieldValue[T]:
    raw_value: T | None
    normalized_value: T | None
    reviewed_value: T | None
    extraction_state: ExtractionState
    review_state: ReviewState
    validation_issues: list[ValidationIssue]
    evidence_refs: list[EvidenceRef]
    extractor_id: str
    extraction_attempt_id: str

# Entities
class TestRecord:
    test_id: str
    patient_first_name: FieldValue[str]
    patient_last_name: FieldValue[str]
    patient_full_name_raw: FieldValue[str]  # fallback
    patient_id_number: FieldValue[str]
    sender: FieldValue[str]
    received_date: FieldValue[str]  # ISO or DD/MM/YYYY
    central_numbers: FieldValue[list[str]]
    commitment_ids: list[str]  # references

class CommitmentRecord:
    commitment_record_id: str
    test_id: str  # reference to TestRecord
    commitment_number: FieldValue[str]
    central_number_refs: list[str]  # which centrals?
    relation_status: str  # "related", "ambiguous", "unknown"
    review_status: ReviewState
```

**Why this structure:**
- Separates `extraction_state` (what was found) from `review_state` (human oversight)
- `pending` = not flagged, no review needed ≠ human verified
- `needs_review` = flagged, blocks export
- `raw`/`normalized`/`reviewed` preserved separately (NFR-02)
- Evidence references for provenance
- Validation issues attached to fields

### 2.3 Extractor Interface

**Purpose:** Abstract Gemini API, enable future replacement

```python
class Extractor(ABC):
    @abstractmethod
    def extract(
        self, 
        image: bytes, 
        document_id: str,
        page_index: int
    ) -> ExtractionResult:
        pass

class ExtractionResult:
    schema_version: str
    fields: dict  # 7 fields with values/lists
    warnings: list[str]
    model_id: str
    prompt_version: str
    processing_time_ms: float

class GeminiExtractor(Extractor):
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model
    
    def extract(self, image: bytes, document_id: str, page_index: int):
        # Call Gemini Vision API
        # Return structured JSON
        # Handle errors (timeout, 429, 5xx)
        pass
```

**Benefits:**
- Single point to swap Gemini for Enterprise/OCR/other
- Testable with mocks
- Isolates API changes from business logic

### 2.4 Validation Service

**Purpose:** Deterministic rules, no guessing

**Rules:**
- ID number checksum (Israeli)
- Date format + not future
- Required fields present
- Detect conflicts (multiple values contradict)
- Detect invalid format

**Output:**
- `ValidationIssue` per problem
- Severity: error/warning
- Suggested fix (not auto-applied)

**No auto-correction:** validation marks issues, doesn't fix them

### 2.5 Review Service

**Purpose:** Track human corrections

**Operations:**
- Update `reviewed_value` for a field
- Change `review_state` to `human_verified`
- Store edit metadata (when, what changed)
- Preserve `raw_value` (never overwrite)
- ETag/versioning to prevent concurrent overwrites

### 2.6 Export Service

**Purpose:** Generate Excel per approved mapping

**Blocked by:** D-04 (format), D-05 (N:M), D-13 (no commitment)

**Provisional approach:**
```
Columns: first_name | last_name | id_number | central_numbers | 
         received_date | sender | commitment_number

One row per CommitmentRecord
central_numbers: semicolon-delimited string (provisional)
Numbers: stored as text cells
Dates: ISO or DD/MM/YYYY (to be decided)
Formula injection: prefix `=+-@` with `'`
```

**Validation:**
- Roundtrip test: write → read → compare
- No zeros lost
- No formula execution

### 2.7 Storage

**Purpose:** Temporary file and metadata storage

**Implementation:**
- Uploaded files: `temp/{batch_id}/{uuid}.{ext}`
- Metadata: in-memory dict or JSON files
- TTL: 24 hours (configurable)
- Cleanup: scheduled or on-demand

**No permanent database in MVP**

---

## 3. Workflows

### 3.1 Upload & Process (Single Document)

```
1. POST /api/batches + file
   ├─ Validate MIME, size, extension
   ├─ Generate batch_id, document_id
   ├─ Save file to temp storage
   └─ Return {batch_id, document_ids}

2. Auto-trigger or POST /api/batches/{id}/process
   ├─ Load file from storage
   ├─ Render PDF → images (PyMuPDF)
   ├─ Detect orientation (if needed)
   ├─ For each page:
   │  ├─ Call GeminiExtractor.extract()
   │  ├─ Map to TestRecord/CommitmentRecord
   │  ├─ Run ValidationService
   │  └─ Mark fields as found/uncertain/missing/invalid
   ├─ Save results to storage
   └─ Return {test_records, warnings}
```

**Error handling:**
- File corrupt → 400 Bad Request
- Gemini timeout → 504 Gateway Timeout, retry limited
- Gemini 429 → 429 Too Many Requests, wait
- Gemini error → 502 Bad Gateway, show error

### 3.2 Review & Correct

```
1. GET /api/batches/{id}
   └─ Return all records with fields + states

2. GET /api/batches/{id}/documents/{doc_id}/preview
   └─ Return original image/PDF page

3. PATCH /api/batches/{id}/records/{rec_id}
   ├─ Validate field exists
   ├─ Update reviewed_value
   ├─ Set review_state = human_verified
   ├─ Check ETag to prevent race
   └─ Save changes
```

**UI behavior:**
- Display fields with colors:
  - Normal (white/gray): found, no issues, or human_verified
  - Orange: uncertain
  - Red: missing/conflicting/invalid
- Show reason for flagging
- Allow edit
- Remove flag after correction

### 3.3 Export with Comprehensive Blocking

```
1. GET /api/batches/{id}/export-status
   ├─ Check ALL blocking conditions:
   │  ├─ Fields with review_state = needs_review
   │  ├─ Documents with status: pending/processing/failed
   │  ├─ Unresolved relationships (commitment ↔ central, marked ambiguous/unknown and required)
   │  └─ Any other issue preventing reliable export per PLAN.md 8.1
   └─ Return {can_export: bool, blockers: [{type, details}], blocker_count: int}

2. POST /api/batches/{id}/export
   ├─ Re-check ALL conditions
   ├─ If ANY blocker → 409 Conflict with full blocker list
   ├─ If clear → Generate Excel
   │  ├─ One row per CommitmentRecord
   │  ├─ Apply provisional mapping (D-04/D-05 pending)
   │  ├─ Use reviewed_value if human_verified (even if empty string!)
   │  ├─ Sanitize formula injection
   │  └─ Return file
```

**Blocker Types:**
1. `unresolved_field`: Field marked `needs_review` not yet corrected
2. `incomplete_document`: Document not fully processed (pending/processing/failed)
3. `unresolved_relationship`: Required link between test/commitment/central unclear
4. `other`: Any issue identified per PLAN.md 8.1

**Frontend:**
- "Export" button disabled if `can_export = false`
- Show blocker count and detailed list
- Link to each blocker for resolution

**Backend Enforcement:**
- NOT just UI — API enforces blocking
- Comprehensive checks before allowing export
- Clear error messages with blocker details

---

## 4. Data Flow

### 4.1 Extraction → Domain

```
Gemini JSON → ExtractionResult → Adapter → TestRecord/CommitmentRecord

Adapter responsibilities:
- Map JSON fields to domain entities
- Handle null/missing → FieldValue with state=missing
- Handle multiple values → lists
- Preserve raw response
- Generate evidence_refs if bbox available
```

### 4.2 Validation → Flagging

```
TestRecord → ValidationService → List[ValidationIssue]

For each issue:
- Attach to relevant FieldValue.validation_issues
- If severity=error → set extraction_state=invalid
- If low confidence → set extraction_state=uncertain
- If error or uncertain → set review_state=needs_review
```

### 4.3 Review → Export

```
FieldValue with review_state=needs_review → Human edits → 
  reviewed_value updated, review_state=human_verified →
  Export uses reviewed_value (NO TRUTHY FALLBACK — empty if verified empty!)

Export value priority:
1. If human_verified → reviewed_value (even if empty string)
2. Else → normalized_value or raw_value or ''

Example:
field.reviewed_value = ""  # Human confirmed empty
field.review_state = human_verified
→ Export: "" (not falling back to old value!)
```

---

## 5. UI/UX Design

### 5.1 Screens

**1. Upload:**
- File input (single or multiple)
- Drag & drop (optional)
- Size/type validation client-side
- Progress bar

**2. Processing:**
- Show batch status
- Per-document status: pending/processing/completed/failed
- Progress indicator
- Errors displayed inline

**3. Review:**
- Left: document preview (PDF/image)
- Right: table of fields
  - Columns: Field Name | Value | Status | Action
  - Color coding: white/orange/red
  - Reason for flagging shown
  - Edit button per field
- Filter: show all / show flagged only
- Navigation: prev/next document

**4. Export:**
- Summary: X records, Y flagged fields remaining
- "Export to Excel" button (disabled if flagged fields exist)
- Download link after generation

### 5.2 RTL Support

- Direction: rtl for Hebrew UI
- Align text: right for Hebrew, left for English/numbers
- Field values: LTR for IDs/dates/numbers

### 5.3 Accessibility

- Color + icon for status (not color alone)
- Keyboard navigation
- Screen reader labels
- Error messages clear and actionable

---

## 6. Security Design

### 6.1 Secrets Management

- API keys in `.env` file
- `.env` in `.gitignore`
- `.env.example` with placeholders
- Load via `python-dotenv` or `pydantic-settings`

### 6.2 Input Validation

- MIME type check (Content-Type header)
- Magic bytes verification (first bytes of file)
- File size limit per D-14
- Page count limit per D-14
- Resolution limit (prevent decompression bombs)

### 6.3 Authorization

- Single user MVP: no auth needed
- IDOR prevention: validate `batch_id` ownership (in-memory session)
- If future multi-user: add session/JWT

### 6.4 Injection Prevention

**Formula Injection (Excel):**
```python
def sanitize_excel_value(value: str) -> str:
    if value.startswith(('=', '+', '-', '@')):
        return "'" + value  # Prefix with single quote
    return value
```

**Path Traversal:**
- No user-supplied paths in file operations
- Use UUIDs for filenames
- Store outside web root

**Prompt Injection:**
- Treat document text as data, not instructions
- No execution of content from Gemini response

### 6.5 Logging

**Do log:**
- Request method, path, status
- Duration, error codes
- Document/batch IDs

**Don't log:**
- Field values (PII)
- API keys
- Raw images
- Patient names, ID numbers

---

## 7. Testing Strategy

### 7.1 Unit Tests

- Domain models: Pydantic validation
- FieldValue states
- Validation rules: ID checksum, dates
- Excel sanitization

### 7.2 Integration Tests

- API endpoints with test client
- Gemini mock: return fixture JSON
- File upload → storage → retrieval
- Review: update field → retrieve → verify

### 7.3 E2E Tests

- Upload PDF → process → review → export
- Flagged field → edit → export enabled
- Error cases: invalid file, timeout

### 7.4 Golden Benchmark

- 10-15 manually tagged forms
- Real Gemini API calls (not mock)
- Measure: accuracy, coverage, false extraction, unsafe acceptance
- Document failures

### 7.5 Regression Tests

- Known failure: handwritten name hallucination
- Expectation: flagged as `uncertain` or `needs_review`
- Other cases from golden benchmark failures

---

## 8. Non-Goals (Deferred)

- Automatic page grouping
- Crop retry with bbox
- Second extractor (OCR, GPT)
- Real-time progress (SSE/WebSocket)
- Undo/redo
- Detailed audit log
- Database persistence
- Queue/workers
- Multi-tenant
- Public deployment

---

## 9. Open Design Questions

Linked to DECISIONS.md:

**D-04: Excel column names, order, cell types**
- Impacts: ExportService implementation
- Blocker for: Final Excel export

**D-05: N:M representation (N centrals, M commitments)**
- Options: delimiter, multiple rows, extra columns
- Impacts: CommitmentRecord → Excel mapping

**D-13: Test without commitment number**
- Options: skip row, empty cell, separate sheet
- Impacts: Export logic

**D-12: Name splitting**
- Auto-split or keep full_name_raw?
- Impacts: Domain models, validation

**D-06: Page grouping**
- One page = one form, or try to group?
- Impacts: Document processing workflow

---

## 10. Deployment (MVP)

**Environment:** localhost only

**Setup:**
1. Install Python 3.10+, Node 18+
2. Create `.env` with `GEMINI_API_KEY=...`
3. Install backend: `pip install -r requirements.txt`
4. Install frontend: `npm install` (in frontend/)
5. Run backend: `uvicorn app.main:app --reload`
6. Run frontend: `npm run dev`
7. Open `http://localhost:5173`

**No Docker, no cloud, no CI/CD in MVP**

---

**This design is approved and ready for task breakdown.**
