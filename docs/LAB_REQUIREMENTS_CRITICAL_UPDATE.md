# Lab Requirements - Critical Update from Sheba Central Virology Lab
**Date:** 2026-10-20  
**Priority:** CRITICAL - Fundamental change to data model and Excel export  
**Status:** Planning phase - NO implementation yet

---

## Executive Summary

**CRITICAL FINDING:** Current system exports **one row per PAGE**, but lab requires **one row per COMMITMENT NUMBER**.

This is a **fundamental mismatch** that requires:
1. Complete redesign of data model
2. New relationship mapping between entities
3. Modified Excel export logic
4. Enhanced segmentation to understand commitment-to-sample relationships

---

## Part 1: Business Requirements (from Lab)

### 1.1 Definition of "Form" (טופס התחייבות)

**What is a Commitment Form?**
- A document received WITH a lab sample
- May contain 1 or multiple pages
- Must identify form boundaries BEFORE extracting relationships

**NOT synonymous with:**
- Page (one form can be multi-page)
- Patient (one patient can have multiple forms)
- Central number (one form can have multiple central numbers)
- Commitment number (one form can have multiple commitments)

### 1.2 Excel Export Business Rule (THE CORE REQUIREMENT)

**Primary rule:** 
```
ONE ROW PER COMMITMENT NUMBER
```

**NOT one row per:**
- ❌ Page
- ❌ Form
- ❌ Patient
- ❌ Central number
- ❌ Sample

**Example scenario:**
```
One form (2 pages) →
  Contains: 3 commitment numbers (C-001, C-002, C-003)
  Contains: 2 central numbers (12345, 12346)
  Patient: John Doe
  
Excel output:
  Row 1: John Doe | 12345 | C-001 | ...
  Row 2: John Doe | 12345 | C-002 | ...
  Row 3: John Doe | 12345 | C-003 | ...
  
(Patient details repeated, relationships preserved)
```

### 1.3 Identifying Commitment Numbers

**Labels that indicate commitment number:**
- "התחייבות" (standard)
- "דרישה" (request/order)
- "דגימה" (sample) — **IN LEUMIT FORMS ONLY**

**CRITICAL:** "דגימה" (sample) is **context-dependent**:
- In Leumit forms: means commitment number
- In other contexts: may mean something else
- Must identify based on: form type + sender + context

**DO NOT treat as commitment number:**
- Test numbers (מספרי בדיקות)
- Central numbers (מספרים מרכזיים)
- Patient IDs
- Other identifiers

### 1.4 Central Numbers (מספרים מרכזיים)

**What is it?**
- Internal lab ID assigned when sample received
- Multiple central numbers possible for same test
- Appears on:
  - Sticker labeled "מרכזי"
  - Next to text "מספר מרכזי"
  - Sometimes handwritten

**Business rules:**
- ✅ **Preserve ALL central numbers** (not just first)
- ❌ **Never overwrite values**
- ❌ **Never arbitrarily choose one**
- ✅ **Store as list**

**Received date association:**
- Date may appear in "התקבל" stamp or handwritten near central number
- Must preserve relationship: central_number ↔ received_date
- If multiple dates don't match → **DO NOT auto-choose**, flag for review

### 1.5 Entity Relationships

**Must distinguish:**
1. **Source PDF / Uploaded Document** — the file
2. **Page** — individual image in PDF
3. **Logical Commitment Form** — business entity (1+ pages)
4. **Patient** — person submitting sample
5. **Sample / Laboratory Identifiers** — central numbers
6. **Commitment Number** — the billable/trackable unit
7. **Excel Export Row** — one per commitment number

**Cardinality:**
```
1 PDF → N Pages
N Pages → M Forms (grouping)
1 Form → 1 Patient (usually, but validate)
1 Form → N Commitment Numbers (common)
1 Form → M Central Numbers (possible)
1 Commitment Number → ? Central Numbers (relationship must be mapped)
1 Excel Row → 1 Commitment Number + related data
```

**Relationship challenges:**
- One form, 3 commitments, 2 central numbers → which commitment maps to which central number?
- **Answer:** Cannot assume automatic mapping, must extract from document or flag as `unresolved_relationship`

---

## Part 2: Current System Analysis (Critical Gaps)

### 2.1 Current Data Model

**From `models.py`:**
```python
class TestRecord(BaseModel):
    test_id: str
    
    # Patient fields
    patient_first_name: FieldValue[str]
    patient_last_name: FieldValue[str]
    patient_id_number: FieldValue[str]
    
    # Sample/form fields
    sender: FieldValue[str]
    received_date: FieldValue[str]
    central_numbers: FieldValue[list[str]]  # ✅ Already a list
    
    # Relationships
    commitment_ids: list[str]  # ✅ N:M relationship exists
    
    # Metadata
    document_id: str
    page_indices: list[int]  # ✅ Multi-page support exists

class CommitmentRecord(BaseModel):
    commitment_record_id: str
    test_id: str  # Reference to TestRecord
    
    commitment_number: FieldValue[str]
    
    # ❓ Missing: Which central numbers relate to THIS commitment?
    # ❓ Missing: Which received date relates to THIS commitment?
```

### 2.2 Current Processing Flow

**From `background.py` (line 274):**
```python
for page_index, image_bytes in enumerate(images):
    extraction_result = await self._extract_with_retry(...)
    test_record = _map_extraction_to_test_record(
        extraction_result, document_id, page_index
    )
    test_records.append(test_record)  # ← One TestRecord per page
    
    commitments = _create_commitment_records(test_record, extraction_result)
    commitment_records.extend(commitments)
```

**Problem:** 
- ✅ Creates CommitmentRecords (good)
- ❌ One TestRecord per PAGE (not per FORM)
- ❌ Commitment numbers extracted per page, not per logical form
- ❌ No relationship mapping: commitment → central numbers

### 2.3 Current Excel Export

**From `process.py` (export_batch):**
```python
async def export_batch(batch_id: str):
    # ... load test_records and commitment_records ...
    
    rows = []
    for record in test_records:  # ← Iterating TestRecords, not CommitmentRecords!
        row = {
            "שם פרטי": record.patient_first_name.reviewed_value or ...,
            "שם משפחה": record.patient_last_name.reviewed_value or ...,
            "ת״ז": record.patient_id_number.reviewed_value or ...,
            "גורם שולח": record.sender.reviewed_value or ...,
            "תאריך קבלה": record.received_date.reviewed_value or ...,
            "מספר מרכזי": ...,  # ❓ Which one if multiple?
            "מספר התחייבות": ...  # ❓ Which one if multiple?
        }
        rows.append(row)
```

**Critical gaps:**
1. ❌ **Exports one row per TestRecord (page), not per CommitmentRecord**
2. ❌ **No logic to repeat patient data for each commitment**
3. ❌ **No relationship mapping: commitment ↔ central number**
4. ❌ **If form has 3 commitments → only first exported or all in one row (wrong)**

### 2.4 Gap Summary

| Requirement | Current State | Gap Severity |
|-------------|---------------|--------------|
| One row per commitment | One row per page/test | 🔴 CRITICAL |
| Multi-page form grouping | Each page separate | 🔴 CRITICAL |
| Commitment-to-central mapping | No explicit relationship | 🔴 CRITICAL |
| Multiple central numbers | Stored as list ✅ | 🟢 OK |
| Context-aware "דגימה" | Not implemented | 🟡 HIGH |
| Relationship flagging | Not implemented | 🟡 HIGH |
| Excel 7-column structure | Exists ✅ | 🟢 OK |

---

## Part 3: Proposed Data Model (Updated)

### 3.1 Core Entities

```python
class SourceDocument(BaseModel):
    """Uploaded PDF file."""
    document_id: str  # filename stem
    batch_id: str
    file_path: Path
    total_pages: int
    upload_timestamp: datetime

class PageMetadata(BaseModel):
    """Single page in PDF (OCR pre-scan)."""
    document_id: str
    page_index: int
    
    # Evidence for segmentation
    has_central_number: bool
    central_numbers_found: list[str]
    has_sticker: bool
    page_notation: Optional[tuple[int, int]]  # (1, 2) from "עמוד 1/2"
    patient_id_preview: Optional[str]
    sender_preview: Optional[str]
    commitment_numbers_preview: list[str]  # NEW: early detection
    
    # OCR quality
    ocr_text: str
    confidence: float
    status: PageStatus  # readable | illegible | blank | failed

class LogicalForm(BaseModel):
    """Business entity: commitment form (1+ pages)."""
    form_id: str  # UUID
    document_id: str
    page_indices: list[int]  # [0, 1] for 2-page form
    
    # Segmentation metadata
    classification: FormClassification  # start | continuation | standalone | uncertain
    segmentation_confidence: float
    segmentation_evidence: dict
    needs_segmentation_review: bool
    
    # Extraction status
    extraction_status: ExtractionStatus  # pending | extracted | failed
    extraction_timestamp: Optional[datetime]

class Patient(BaseModel):
    """Patient entity (normalized)."""
    patient_id: str  # UUID or normalized from ID number
    first_name: FieldValue[str]
    last_name: FieldValue[str]
    full_name_raw: FieldValue[str]
    id_number: FieldValue[str]

class Sample(BaseModel):
    """Lab sample with central number."""
    sample_id: str  # UUID
    form_id: str  # Which form does this sample come from
    
    central_number: FieldValue[str]
    received_date: FieldValue[str]  # Associated with this central number
    
    # Provenance
    source_page_index: int  # Which page was this extracted from
    evidence_refs: list[EvidenceRef]

class Commitment(BaseModel):
    """Commitment number (billable unit)."""
    commitment_id: str  # UUID
    form_id: str  # Which form does this commitment come from
    
    commitment_number: FieldValue[str]
    
    # Label/context
    label_type: str  # "התחייבות" | "דרישה" | "דגימה"
    sender_context: str  # e.g., "leumit" when "דגימה" means commitment
    
    # Relationships
    related_sample_ids: list[str]  # Which samples (central numbers) relate to this
    relationship_confidence: float  # 0.0-1.0
    relationship_status: RelationshipStatus  # resolved | unresolved | needs_review
    
    # Provenance
    source_page_index: int
    evidence_refs: list[EvidenceRef]

class FormExtractionResult(BaseModel):
    """Complete extraction for one logical form."""
    form_id: str
    
    # Entities extracted
    patient: Patient
    samples: list[Sample]  # Multiple central numbers
    commitments: list[Commitment]  # Multiple commitment numbers
    
    # Metadata
    sender: FieldValue[str]
    form_type: str  # "standard" | "leumit" | etc.
    
    # Quality
    extraction_confidence: float
    validation_issues: list[ValidationIssue]
    needs_review: bool

class ExcelExportRow(BaseModel):
    """One row in Excel = one commitment number."""
    row_id: str  # UUID
    
    # From Patient
    patient_first_name: str
    patient_last_name: str
    patient_id_number: str
    
    # From Form
    sender: str
    
    # From Sample (mapped to this commitment)
    central_number: str  # ❓ How to choose if multiple?
    received_date: str   # ❓ How to choose if multiple?
    
    # From Commitment
    commitment_number: str
    
    # Provenance
    form_id: str
    commitment_id: str
    sample_ids: list[str]  # Which samples contributed to this row
    
    # Status
    export_status: ExportStatus  # ready | blocked | needs_review
    blockers: list[str]
```

### 3.2 Key Changes

**Before:**
```
Page → TestRecord → CommitmentRecords
         ↓ (1 row per TestRecord)
       Excel
```

**After:**
```
Pages → FormSegmentation → LogicalForms
          ↓
        Extraction (per form)
          ↓
        Patient + Samples + Commitments
          ↓
        Relationship Mapping
          ↓
        ExcelExportRow (1 per commitment)
```

---

## Part 4: Processing Flow (Revised)

### 4.1 Phase 1: Form Segmentation (Sequential)

```python
def segment_forms(document_id: str, pages: list[PageMetadata]) -> list[LogicalForm]:
    """
    Group pages into logical forms.
    Sequential algorithm (adjacent pages first).
    """
    forms = []
    current_form = None
    
    for i, page in enumerate(pages):
        # Use evidence: page notation, central numbers, patient ID
        # Rules from SEGMENTATION_REQUIREMENTS_CLARIFICATION.md
        
        if is_form_start(page, prev_page):
            if current_form:
                forms.append(current_form)
            current_form = LogicalForm(
                form_id=generate_uuid(),
                page_indices=[i],
                ...
            )
        elif is_continuation(page, current_form):
            current_form.page_indices.append(i)
        else:
            # Uncertain
            current_form.needs_segmentation_review = True
    
    if current_form:
        forms.append(current_form)
    
    return forms
```

### 4.2 Phase 2: Form Extraction (Per Logical Form)

```python
async def extract_form(form: LogicalForm) -> FormExtractionResult:
    """
    Extract from all pages of a logical form.
    ONE Gemini call per form (not per page).
    """
    # Merge page images if multi-page
    if len(form.page_indices) > 1:
        merged_image = merge_pages([images[i] for i in form.page_indices])
    else:
        merged_image = images[form.page_indices[0]]
    
    # Gemini extraction
    extraction_result = await gemini_extractor.extract(
        image=merged_image,
        document_id=form.document_id,
        page_indices=form.page_indices  # Pass context
    )
    
    # Parse into structured entities
    patient = extract_patient(extraction_result)
    samples = extract_samples(extraction_result, form)  # Multiple central numbers
    commitments = extract_commitments(extraction_result, form)  # Multiple commitments
    
    return FormExtractionResult(
        form_id=form.form_id,
        patient=patient,
        samples=samples,
        commitments=commitments,
        ...
    )
```

### 4.3 Phase 3: Relationship Mapping

```python
def map_relationships(form_result: FormExtractionResult) -> FormExtractionResult:
    """
    Map commitments to samples (central numbers).
    
    Strategies:
    1. Explicit indicators in document (e.g., "C-001: מרכזי 12345")
    2. Proximity (commitment and central number close together)
    3. Structural cues (table layout, same row)
    4. Heuristics (if 1 commitment + 1 sample → map automatically)
    
    If ambiguous → flag unresolved_relationship.
    """
    for commitment in form_result.commitments:
        # Try to find related samples
        related_samples = find_related_samples(commitment, form_result.samples)
        
        if len(related_samples) == 0:
            # No clear relationship
            commitment.relationship_status = RelationshipStatus.unresolved
            commitment.relationship_confidence = 0.0
        elif len(related_samples) == 1:
            # Clear 1:1 mapping
            commitment.related_sample_ids = [related_samples[0].sample_id]
            commitment.relationship_confidence = 0.9
            commitment.relationship_status = RelationshipStatus.resolved
        elif has_explicit_mapping(commitment, form_result.samples):
            # Document explicitly states relationship
            commitment.related_sample_ids = [...]
            commitment.relationship_confidence = 0.95
            commitment.relationship_status = RelationshipStatus.resolved
        else:
            # Ambiguous N:M relationship
            commitment.relationship_status = RelationshipStatus.needs_review
            commitment.relationship_confidence = 0.5
    
    return form_result
```

### 4.4 Phase 4: Excel Row Generation

```python
def generate_excel_rows(form_results: list[FormExtractionResult]) -> list[ExcelExportRow]:
    """
    ONE ROW PER COMMITMENT NUMBER.
    Repeat patient/form data as needed.
    """
    rows = []
    
    for form_result in form_results:
        patient = form_result.patient
        
        for commitment in form_result.commitments:
            # Find related sample (central number) for this commitment
            if commitment.relationship_status == RelationshipStatus.resolved:
                sample = get_sample_by_id(commitment.related_sample_ids[0])
                central_number = sample.central_number.reviewed_value or sample.central_number.raw_value
                received_date = sample.received_date.reviewed_value or sample.received_date.raw_value
            elif commitment.relationship_status == RelationshipStatus.unresolved:
                # ❓ How to handle? Options:
                # A. Use first sample (risky)
                # B. Leave blank and flag (safer)
                # C. Block export (safest)
                central_number = ""  # or form_result.samples[0] ?
                received_date = ""
                blockers.append("unresolved_commitment_to_sample_relationship")
            else:
                # needs_review
                blockers.append("commitment_relationship_needs_review")
            
            row = ExcelExportRow(
                row_id=generate_uuid(),
                # Repeat patient data
                patient_first_name=patient.first_name.reviewed_value or ...,
                patient_last_name=patient.last_name.reviewed_value or ...,
                patient_id_number=patient.id_number.reviewed_value or ...,
                # Form data
                sender=form_result.sender.reviewed_value or ...,
                # Sample data (mapped)
                central_number=central_number,
                received_date=received_date,
                # Commitment data
                commitment_number=commitment.commitment_number.reviewed_value or ...,
                # Provenance
                form_id=form_result.form_id,
                commitment_id=commitment.commitment_id,
                sample_ids=commitment.related_sample_ids,
                # Status
                export_status=ExportStatus.ready if not blockers else ExportStatus.blocked,
                blockers=blockers
            )
            rows.append(row)
    
    return rows
```

---

## Part 5: Commitment Number Identification

### 5.1 Context-Aware Detection

```python
def identify_commitment_numbers(
    extraction_result: dict,
    form_type: str,
    sender: str
) -> list[CommitmentCandidate]:
    """
    Identify commitment numbers with context awareness.
    """
    candidates = []
    
    # Standard labels
    if "התחייבות" in text:
        candidates.append(extract_near("התחייבות", text))
    
    if "דרישה" in text:
        candidates.append(extract_near("דרישה", text))
    
    # Context-specific: "דגימה" in Leumit
    if "דגימה" in text:
        if sender.lower() in ["leumit", "לאומית"]:
            # In Leumit forms, "דגימה" means commitment
            candidates.append(CommitmentCandidate(
                number=extract_near("דגימה", text),
                label_type="דגימה",
                context="leumit_sample_as_commitment",
                confidence=0.9
            ))
        else:
            # In other forms, "דגימה" is NOT commitment
            # Might be sample description, ignore or flag
            pass
    
    # Filter out non-commitment numbers
    candidates = [c for c in candidates if not is_test_number(c.number)]
    candidates = [c for c in candidates if not is_central_number(c.number)]
    candidates = [c for c in candidates if not is_patient_id(c.number)]
    
    return candidates

def is_test_number(num: str) -> bool:
    """Check if this is a test number, not commitment."""
    # Heuristics:
    # - Very long numbers (>12 digits) unlikely to be commitment
    # - Starts with specific prefix
    # - Near label "בדיקה" or "test"
    pass

def is_central_number(num: str) -> bool:
    """Check if this is already identified as central number."""
    # Check if near "מרכזי" label or on sticker
    pass
```

### 5.2 Extraction Schema Update

**Gemini schema must include:**
```python
class CommitmentFormExtraction(BaseModel):
    # Patient
    patient_first_name: Optional[str]
    patient_last_name: Optional[str]
    patient_full_name: Optional[str]
    patient_id_number: Optional[str]
    
    # Form metadata
    sender: Optional[str]
    
    # Samples (list of central numbers with dates)
    samples: list[SampleData] = []  # NEW: structured samples
    
    # Commitments (list of commitment numbers with labels)
    commitments: list[CommitmentData] = []  # NEW: structured commitments
    
    # Legacy (for backward compatibility)
    central_numbers: list[str] = []
    commitment_numbers: list[str] = []

class SampleData(BaseModel):
    """One central number with metadata."""
    central_number: str
    received_date: Optional[str]
    location_hint: str  # "top_left" | "sticker_1" | etc.

class CommitmentData(BaseModel):
    """One commitment number with metadata."""
    commitment_number: str
    label_type: str  # "התחייבות" | "דרישה" | "דגימה"
    related_central_number: Optional[str]  # If explicitly linked in document
    location_hint: str
```

---

## Part 6: Test Scenarios (Updated)

### 6.1 Core Scenarios

**Scenario 1: Simple (1 page, 1 commitment)**
```
Input: 1 page
  Patient: John Doe, ID 123456782
  Central: 12345, Date: 2024-01-15
  Commitment: C-001
  
Expected output: 1 Excel row
  John Doe | 123456782 | כללית | 12345 | 2024-01-15 | C-001
```

**Scenario 2: Multi-page form, single commitment**
```
Input: 2 pages (marked "עמוד 1/2", "עמוד 2/2")
  Page 1: Patient data, Central 12345
  Page 2: Commitment C-001
  
Expected: 1 LogicalForm, 1 Excel row
```

**Scenario 3: Single form, multiple commitments (CRITICAL)**
```
Input: 2 pages
  Patient: Jane Smith, ID 987654321
  Central: 12345
  Commitments: C-001, C-002, C-003
  
Expected output: 3 Excel rows
  Jane Smith | 987654321 | מכבי | 12345 | 2024-01-15 | C-001
  Jane Smith | 987654321 | מכבי | 12345 | 2024-01-15 | C-002
  Jane Smith | 987654321 | מכבי | 12345 | 2024-01-15 | C-003
```

**Scenario 4: Multiple central numbers**
```
Input: 1 form
  Patient: John Doe
  Centrals: 12345, 12346
  Commitment: C-001
  
Expected: 1 Excel row
  Question: Which central number to use? 
  Options:
    A. First: 12345 (risky if wrong)
    B. Both somehow (doesn't fit 7-column structure)
    C. Flag for review (safest)
```

**Scenario 5: Leumit "דגימה" as commitment**
```
Input: Leumit form
  Label: "דגימה: 12345"
  (NOT "התחייבות")
  
Expected: Identify 12345 as commitment number
  commitment.label_type = "דגימה"
  commitment.sender_context = "leumit"
```

**Scenario 6: Ambiguous "דרישה"**
```
Input: Form with "דרישה: 999"
  
Expected: Identify 999 as commitment number
  commitment.label_type = "דרישה"
```

**Scenario 7: Continuation page with new central number**
```
Input: 2 pages
  Page 1 ("1/2"): Central 12345, Commitment C-001
  Page 2 ("2/2"): Central 12346, Commitment C-002
  
Expected: 1 LogicalForm, 2 Samples, 2 Commitments
  Excel rows:
    Row 1: ... | 12345 | ... | C-001
    Row 2: ... | 12346 | ... | C-002
```

**Scenario 8: Unresolved relationship**
```
Input: 1 form
  Centrals: 12345, 12346
  Commitments: C-001, C-002
  No explicit mapping in document
  
Expected: Flag relationship_status = unresolved
  Block export OR flag for human review
```

**Scenario 9: Same patient, multiple forms**
```
Input: 5 pages (PDF)
  Pages 0-1: Form A (patient John, centrals 12345, commitments C-001)
  Pages 2-3: Form B (patient John, centrals 12346, commitments C-002)
  Page 4: Form C (patient John, centrals 12347, commitments C-003)
  
Expected: 3 LogicalForms, 3 Excel rows
  (NOT merged despite same patient)
```

**Scenario 10: Test number misidentified as commitment**
```
Input: Form with
  "בדיקה: 999888777" (test code)
  "התחייבות: C-001"
  
Expected: Only C-001 identified as commitment
  999888777 filtered out (is_test_number = True)
```

### 6.2 Success Metrics (Revised)

**Form Segmentation:**
- Page segmentation accuracy > 95%
- Form grouping accuracy > 90%
- False merge rate < 2%
- False split rate < 10%

**Commitment Extraction:**
- Commitment detection precision > 90%
- Commitment detection recall > 85%
- False positive rate (non-commitments detected) < 5%
- Context-aware "דגימה" accuracy > 90%

**Excel Export:**
- Row count correctness: actual_rows == expected_commitments (100%)
- No duplicate rows for same commitment
- No missing rows for extracted commitments
- Relationship accuracy > 80% (resolved correctly)

**Overall:**
- Zero skipped pages
- Every page has status (processed | failed | needs_review)
- Export blockers clearly documented

---

## Part 7: Critical Gaps in Current System

### 7.1 Data Model Gaps

| Required Entity | Current State | Gap |
|----------------|---------------|-----|
| LogicalForm (multi-page) | Not modeled | 🔴 MISSING |
| Sample (central + date pair) | Flattened in TestRecord | 🔴 NEEDS RESTRUCTURE |
| Commitment (with relationships) | Exists but incomplete | 🟡 INCOMPLETE |
| ExcelExportRow | Not modeled | 🔴 MISSING |
| Relationship mapping | Not implemented | 🔴 MISSING |

### 7.2 Processing Gaps

| Required Step | Current State | Gap |
|--------------|---------------|-----|
| Form segmentation | Page-by-page | 🔴 MISSING |
| Multi-page form extraction | Per-page extraction | 🔴 WRONG APPROACH |
| Commitment-to-sample mapping | Not implemented | 🔴 MISSING |
| Context-aware label detection | Not implemented | 🟡 MISSING |
| Relationship resolution UI | Not implemented | 🟡 MISSING |

### 7.3 Excel Export Gaps

| Requirement | Current State | Gap |
|------------|---------------|-----|
| One row per commitment | One row per page/test | 🔴 FUNDAMENTALLY WRONG |
| Repeat patient data | Not implemented | 🔴 MISSING |
| Relationship-aware export | Not implemented | 🔴 MISSING |
| Multiple central numbers | Stored but not mapped | 🟡 PARTIAL |

---

## Part 8: Implementation Priority (Revised)

### Phase 0: Critical Foundation (MUST)
1. ✅ **Form segmentation** (sequential algorithm)
   - Group pages into LogicalForms
   - Handle "עמוד X/Y" notation
   - Detect form boundaries

2. ✅ **Data model redesign**
   - Add LogicalForm, Sample, Commitment entities
   - Add relationship fields
   - Add ExcelExportRow model

3. ✅ **Multi-page extraction**
   - Modify _process_batch to extract per form, not per page
   - Merge page images for multi-page forms
   - Single Gemini call per form

### Phase 1: Commitment Detection (MUST)
4. ✅ **Enhanced Gemini schema**
   - Add samples: list[SampleData]
   - Add commitments: list[CommitmentData]
   - Context fields for label types

5. ✅ **Context-aware parsing**
   - Identify "התחייבות", "דרישה", "דגימה"
   - Filter out test numbers, central numbers
   - Sender-specific logic (Leumit "דגימה")

6. ✅ **Relationship mapping (basic)**
   - 1:1 mapping (1 commitment + 1 sample)
   - Flag unresolved N:M cases

### Phase 2: Excel Export Fix (MUST)
7. ✅ **Rewrite export logic**
   - Iterate CommitmentRecords, not TestRecords
   - Generate one row per commitment
   - Repeat patient/form data

8. ✅ **Relationship-aware export**
   - Map commitment → sample (central number)
   - Handle unresolved relationships (block export)

9. ✅ **Export validation**
   - Row count == commitment count
   - No duplicates
   - No missing commitments

### Phase 3: UI Updates (SHOULD)
10. ✅ **Segmentation Review UI**
    - Show form groupings
    - Allow manual corrections
    - Approve before extraction

11. ✅ **Relationship Resolution UI**
    - Show unresolved mappings
    - Manual assignment: commitment → sample
    - Save relationships

12. ✅ **Modified ReviewScreen**
    - Display by form, not by page
    - Show commitments per form
    - Indicate relationships

### Phase 4: Advanced Features (OPTIONAL)
13. ⚪ Visual sticker detection
14. ⚪ Layout-based relationship hints
15. ⚪ ML model for commitment detection

---

## Part 9: Open Questions

### 9.1 Excel 7-Column Structure

**Current columns (from Stage 1.5):**
1. שם פרטי
2. שם משפחה
3. ת"ז
4. גורם שולח
5. תאריך קבלה
6. מספר מרכזי
7. מספר התחייבות

**Question:** How to handle multiple central numbers per commitment?
- **Option A:** Use first central number (risky if wrong)
- **Option B:** Add column "מספרים מרכזיים נוספים" (requires approval)
- **Option C:** Create multiple rows (but then row ≠ commitment)
- **Option D:** Store as comma-separated in single cell (parsing issues)

**Recommendation:** Clarify with lab which approach is acceptable.

### 9.2 Unresolved Relationships

**When commitment-to-sample mapping is ambiguous:**
- **Option A:** Block export entirely (safest, may frustrate users)
- **Option B:** Export with blank central number (allows manual correction)
- **Option C:** Use first sample (risky, could assign wrong data)

**Recommendation:** Block export (Option A) for critical relationships.

### 9.3 Relationship Resolution Timing

**When to resolve relationships?**
- **Option A:** During extraction (Gemini tries to identify from layout/proximity)
- **Option B:** Post-extraction via rules (deterministic logic)
- **Option C:** Manual UI before export (human decision)

**Recommendation:** Try B (rules) first, fall back to C (UI) if unresolved.

---

## Part 10: Next Steps

### 10.1 Planning Tasks (Current Phase)

- [ ] Update DOCUMENT_SEGMENTATION_PLAN.md with new requirements
- [ ] Design detailed data model (LogicalForm, Sample, Commitment, ExcelExportRow)
- [ ] Design relationship mapping algorithm
- [ ] Design Excel export logic (one row per commitment)
- [ ] Create test scenarios dataset
- [ ] Define success metrics
- [ ] Estimate implementation effort

### 10.2 Implementation Tasks (After Approval)

**NOT AUTHORIZED YET** — Planning only

- [ ] Implement LogicalForm segmentation
- [ ] Modify extraction to work per-form
- [ ] Update Gemini schema (samples + commitments)
- [ ] Implement relationship mapping
- [ ] Rewrite Excel export
- [ ] Add Segmentation Review UI
- [ ] Add Relationship Resolution UI
- [ ] Write tests for all scenarios
- [ ] Validate with lab stakeholders

---

## Part 11: Risk Assessment

### 11.1 High-Risk Areas

**1. Relationship Mapping Ambiguity**
- Risk: Cannot automatically determine commitment-to-sample mapping
- Impact: Export blocked or wrong data
- Mitigation: Conservative thresholds, manual resolution UI

**2. Breaking Existing Functionality**
- Risk: Stage 1/1.5 name extraction affected
- Impact: Regression in already-working features
- Mitigation: Preserve existing extraction, add layers on top

**3. Excel Structure Change**
- Risk: Lab workflow disrupted if columns change
- Impact: User confusion, rejection
- Mitigation: Keep 7-column structure, clarify multiple-central-number handling

**4. Gemini Cost Increase**
- Risk: More complex schema → more tokens → higher cost
- Impact: Quota exhaustion
- Mitigation: Multi-page forms reduce call count (30 pages → 20 forms = -33% calls)

### 11.2 Critical Success Factors

1. ✅ **Accurate form segmentation** — foundation for everything
2. ✅ **Reliable commitment detection** — core business requirement
3. ✅ **Correct Excel row generation** — what lab actually uses
4. ✅ **Zero data loss** — every commitment must export
5. ✅ **Zero false merges** — never mix different patients/forms

---

**Status:** Critical requirements documented. Awaiting user review before updating segmentation plan.

**Recommendation:** Pause workflow, incorporate these requirements, restart planning with updated scope.
