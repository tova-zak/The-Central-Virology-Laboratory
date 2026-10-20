# תכנית מימוש מאוחדת: חלוקת מסמכים ולוגיקת עסקית

**תאריך:** 2026-10-14  
**מצב:** תכנון בלבד - ממתין לאישור המשתמש  
**עדיפות:** P0 - קריטי

---

## 1. תקציר מנהלים

### 1.1 הבעיה המרכזית

המעבדה דורשת **שורה אחת ב-Excel עבור כל מספר התחייבות**, אבל המערכת הנוכחית מייצרת **שורה אחת לכל עמוד PDF**. זוהי בעיה קריטית שחוסמת את השימוש בפועל במערכת.

**דוגמה:**
- PDF: 30 עמודים
- טפסים: ~20 (חלקם עמוד 1, חלקם 2 עמודים)
- מספרי התחייבות: ~25 (חלק מהטפסים עם מספר התחייבויות)
- **התנהגות נוכחית:** 30 שורות ב-Excel (שגוי ❌)
- **התנהגות נדרשת:** 25 שורות ב-Excel (נכון ✅)

### 1.2 היקף הפתרון

תכנית זו משלבת שני שינויים קריטיים:

1. **חלוקת מסמכים (Document Segmentation):** זיהוי גבולות טפסים במסמך רב-עמודים
2. **מודל נתונים חדש:** מיפוי יחסים בין טפסים, דגימות והתחייבויות לייצוא Excel נכון

### 1.3 שימור עבודה קיימת

✅ **מה נשמר:**
- Stage 1: `patient_full_name_raw` extraction (committed d134c92)
- Stage 1.5: ReviewScreenNew 3-state display + export blocking (uncommitted in worktree)
- 72 backend tests + 18 integration tests
- כל ה-prompt engineering (Prompt V2.0)
- מנגנון retry והיברידי (OCR + Gemini)

❌ **מה משתנה:**
- מבנה processing loop (מ-page-based ל-form-based)
- מודל נתונים (הוספת LogicalForm, Sample, ExcelExportRow)
- לוגיקת Excel export (מ-test_records iteration ל-commitments iteration)
- UI (ReviewScreenNew יציג טפסים לא עמודים)

---

## 2. אימות הנחות קוד (Code Verification)

### 2.1 מה אושר מקוד בפועל ✅

**מיקום קבצים (מאומת):**
```
backend/app/domain/models.py          # TestRecord, CommitmentRecord
backend/app/api/process.py            # _create_commitment_records, export_batch
backend/app/services/processing/background.py  # _process_batch (page loop)
backend/app/services/export/excel_exporter.py  # ExcelExporter.export()
```

**Processing flow (מאומת - lines 273-391 in background.py):**
```python
for page_index, image_bytes in enumerate(images):  # Line 273
    extraction_result = await self._extract_with_retry(...)  # Lines 297-301
    test_record = _map_extraction_to_test_record(
        extraction_result, document_id, page_index
    )  # Lines 331-334
    test_records.append(test_record)  # Accumulates page-based records
    commitments = _create_commitment_records(test_record, extraction_result)
    commitment_records.extend(commitments)
```

**_create_commitment_records (מאומת - lines 442-464 in process.py):**
```python
def _create_commitment_records(test_record: TestRecord, extraction_result):
    commitment_numbers = extraction_result.fields.get("commitment_numbers", [])
    records = []
    for comm_num in commitment_numbers:
        record = CommitmentRecord(
            commitment_record_id=f"comm_{uuid.uuid4().hex[:12]}",
            test_id=test_record.test_id,
            commitment_number=FieldValue[str](...),
            central_number_refs=test_record.central_numbers.raw_value or [],
            relation_status="ambiguous"  # Line 460: Always ambiguous!
        )
        test_record.commitment_ids.append(record.commitment_record_id)
        records.append(record)
    return records
```

**❌ Gap #1 מאומת:** `central_number_refs` מועתק מה-TestRecord אבל אין לוגיקה לזיהוי יחסים. כל התחייבות מקבלת את **כל** המספרים המרכזיים מהעמוד.

**export_batch (מאומת - lines 470-539 in process.py):**
```python
async def export_batch(batch_id: str):
    batch_data = _storage.load_batch(batch_id)
    test_records = [TestRecord(**r) for r in batch_data["test_records"]]  # Line 496
    commitment_records = [CommitmentRecord(**c) for c in batch_data["commitment_records"]]  # Line 497
    
    # Export blocking check happens here (lines 500-518)
    
    exporter.export(
        test_records=test_records,
        commitment_records=commitment_records,
        output_path=output_file
    )  # Lines 528-532
```

**ExcelExporter.export (מאומת - lines 38-113 in excel_exporter.py):**
```python
def export(self, test_records: List[TestRecord], commitment_records: List[CommitmentRecord], ...):
    # Headers defined (line 52-60)
    headers = ["First Name", "Last Name", "ID Number", "Sender", 
               "Received Date", "Central Numbers", "Commitment Numbers"]
    
    # ❌ Gap #2 CONFIRMED: Iterates test_records (pages), not commitment_records!
    for row_idx, record in enumerate(test_records, start=2):  # Line 70
        # Gets commitment numbers from record.commitment_ids
        commitment_nums = []
        for comm_id in record.commitment_ids:
            comm = next((c for c in commitment_records if c.commitment_record_id == comm_id), None)
            if comm:
                comm_num = self._get_value(comm.commitment_number)
                if comm_num:
                    commitment_nums.append(comm_num)
        
        # Writes ONE row with comma-separated commitment numbers
        ws.cell(row=row_idx, column=7, value=self._format_list(commitment_nums))
```

**❌ Gap #2 מאומת:** `ExcelExporter` מקבל `commitment_records` אבל לא משתמש בהם לאיטרציה. הוא איטרטיבי על `test_records` (עמודים) ומצטבר commitments כרשימה מופרדת בפסיקים.

**TestRecord.page_indices (מאומת - line 157 in models.py):**
```python
class TestRecord:
    page_indices: list[int] = Field(default_factory=list)  # Multi-page support exists!
```

✅ **Gap #3 תוקן:** `page_indices` כבר רשימה, לא מספר בודד. זה מאפשר multi-page forms.

### 2.2 מה חסר (מאומת לא קיים)

**❌ אין LogicalForm model** - grep לא מצא, models.py לא מכיל  
**❌ אין Sample model** - grep לא מצא  
**❌ אין ExcelExportRow model** - grep לא מצא  
**❌ אין page_notation extraction** - grep מצא רק `page_index` (0-based counter), לא שדה `page_notation` (ערך "עמוד X/Y")  
**❌ אין form segmentation logic** - background.py סורק עמודים ליניארית ללא grouping  
**❌ אין context-aware commitment detection** - _create_commitment_records לא בודק sender (Leumit) לזיהוי "דגימה"

### 2.3 תקציב Gemini (מאומת קיים)

**מ-quota_manager.py:**
```python
FREE_TIER_LIMITS = {
    "requests_per_minute": 5,
    "requests_per_day": 20  # ❗ לא מאומת אמפירית, מבוסס על פורומים
}
```

**9 מפתחות זמינים:** `GEMINI_API_KEY` + `GEMINI_API_1` עד `GEMINI_API_8`  
**סה"כ תקציב תיאורטי:** 20 RPD × 9 = 180 RPD  
**⚠️ אזהרה:** 20 RPD לא אומת. המונה המקומי לא אמין (חוסם לפני המכסה האמיתית).

---

## 3. מודל נתונים מומלץ

### 3.1 ישויות חדשות

```python
class LogicalForm(BaseModel):
    """Logical form that may span multiple pages.
    
    Represents ONE commitment form, which is the unit the lab sees.
    May contain 1-2 pages (rarely more).
    """
    form_id: str  # Unique identifier
    document_id: str  # Which PDF this form came from
    page_indices: list[int]  # Pages 0-based: [4, 5] for pages 5-6
    
    # Segmentation evidence
    segmentation_method: str  # "page_notation" | "central_number" | "single_page"
    segmentation_confidence: float  # 0.0-1.0
    
    # Patient and source info (shared across form pages)
    patient_first_name: FieldValue[str]
    patient_last_name: FieldValue[str]
    patient_full_name_raw: FieldValue[str]
    patient_id_number: FieldValue[str]
    sender: FieldValue[str]
    
    # References
    sample_ids: list[str] = Field(default_factory=list)  # N samples
    commitment_ids: list[str] = Field(default_factory=list)  # M commitments


class Sample(BaseModel):
    """Sample = (central_number, received_date) pair.
    
    Represents a physical sample received by the lab.
    One form may contain multiple samples (multiple stickers).
    """
    sample_id: str
    form_id: str  # Which form this sample appears in
    
    central_number: FieldValue[str]  # Lab internal ID
    received_date: FieldValue[str]  # When sample arrived
    
    # Which commitments reference this sample?
    commitment_ids: list[str] = Field(default_factory=list)


class Commitment(BaseModel):
    """Commitment from HMO/hospital to lab.
    
    Represents ONE commitment number. This is the Excel export unit.
    """
    commitment_id: str
    form_id: str  # Which form this commitment appears in
    
    commitment_number: FieldValue[str]
    commitment_type: str  # "התחייבות" | "דרישה" | "דגימה_leumit"
    
    # Relationship to samples
    sample_ids: list[str] = Field(default_factory=list)
    relationship_status: str  # "explicit" | "inferred" | "ambiguous" | "none"
    relationship_confidence: float = 0.0
    
    # Review status
    review_status: ReviewState = ReviewState.pending


class ExcelExportRow(BaseModel):
    """One row in Excel export = one commitment.
    
    Denormalized view joining commitment + form + samples.
    """
    commitment_id: str
    
    # Patient (from form)
    patient_first_name: str
    patient_last_name: str
    patient_id_number: str
    
    # Source (from form)
    sender: str
    
    # Sample (from relationship mapping)
    received_date: str  # May be repeated if multiple samples
    central_numbers: list[str]  # May be multiple
    
    # Commitment
    commitment_number: str
```

### 3.2 יחסים בין ישויות

```
Document (PDF)
  └─> LogicalForm (1 or 2 pages)
       ├─> Sample (central_number + received_date)
       │    └─> Commitment (N:M relationship)
       └─> Commitment
            └─> Sample (M:N relationship)

Export: Iterate Commitments → Join with Form + Samples → Generate ExcelExportRow
```

### 3.3 השוואה: מודל ישן vs חדש

| **היבט**              | **מודל ישן (TestRecord)**                     | **מודל חדש (LogicalForm + Sample + Commitment)** |
|-----------------------|-----------------------------------------------|---------------------------------------------------|
| **יחידת עיבוד**      | עמוד (page)                                   | טופס (form)                                       |
| **יחידת ייצוא**      | TestRecord (1 row per page)                   | Commitment (1 row per commitment)                 |
| **Multi-page forms**  | `page_indices: list[int]` (קיים אבל לא בשימוש) | `page_indices: list[int]` (מרכזי)                 |
| **Sample tracking**   | `central_numbers: list[str]` בלבד             | Sample entity with received_date pair             |
| **Commitment mapping**| `commitment_ids: list[str]` (flat list)       | N:M with relationship_status                      |
| **Excel iteration**   | `for record in test_records`                  | `for commitment in commitments`                   |

---

## 4. תהליך עיבוד חדש

### 4.1 Phase 1: Document Segmentation (Form Boundary Detection)

**Input:** PDF → list of page images  
**Output:** list of LogicalForm (each with page_indices)

**אלגוריתם סקווינציאלי (Sequential Sliding Window):**

```python
def segment_forms(images: list[bytes], document_id: str) -> list[LogicalForm]:
    """Segment pages into logical forms using sequential evidence.
    
    Priority:
    1. Page notation "עמוד X/Y" (confidence 0.95)
    2. Central number continuity (confidence 0.7)
    3. Missing sticker ≠ auto-merge (confidence 0.3)
    """
    forms = []
    current_form_pages = [0]  # Start with page 0
    
    for i in range(1, len(images)):
        # Extract segmentation hints from page i
        hints = extract_segmentation_hints(images[i])
        
        # Decision: merge with current form or start new form?
        if should_merge(current_form_pages, i, hints):
            current_form_pages.append(i)
        else:
            # Finalize current form
            form = create_logical_form(
                document_id=document_id,
                page_indices=current_form_pages,
                method=get_segmentation_method(hints)
            )
            forms.append(form)
            
            # Start new form
            current_form_pages = [i]
    
    # Don't forget last form
    if current_form_pages:
        form = create_logical_form(document_id, current_form_pages, "end_of_document")
        forms.append(form)
    
    return forms


def extract_segmentation_hints(image: bytes) -> dict:
    """Extract hints for segmentation decision.
    
    This is a LIGHTWEIGHT extraction, NOT full Gemini call.
    Can use regex + OCR or minimal Gemini prompt.
    """
    return {
        "page_notation": None,  # e.g., "עמוד 2/2" or None
        "central_numbers": [],  # e.g., ["12345", "67890"]
        "has_patient_header": False,  # Does page have patient name fields?
    }


def should_merge(current_pages: list[int], next_page: int, hints: dict) -> bool:
    """Decide if next_page should merge with current form.
    
    Sequential algorithm: only check adjacent page.
    """
    # Rule 1: Page notation (highest confidence)
    if hints["page_notation"]:
        match = re.match(r"עמוד (\d+)/(\d+)", hints["page_notation"])
        if match:
            current_num, total_num = int(match.group(1)), int(match.group(2))
            if current_num == 2 and total_num == 2:
                return True  # This is page 2/2, merge with previous
            elif current_num == 1 and total_num == 1:
                return False  # Single-page form
    
    # Rule 2: Central number (medium confidence)
    # If previous page has central number and current doesn't, likely continuation
    prev_hints = get_cached_hints(current_pages[-1])
    if prev_hints["central_numbers"] and not hints["central_numbers"]:
        if not hints["has_patient_header"]:
            return True  # Continuation page (no sticker, no header)
    
    # Rule 3: Default to new form (conservative)
    return False
```

**⚠️ קריטי:** `extract_segmentation_hints()` צריך להיות זול. אפשרויות:
1. OCR בלבד (Tesseract) - ללא Gemini
2. Gemini lightweight prompt (רק page_notation, לא full extraction)
3. היברידי: OCR + regex למציאת "עמוד X/Y"

**💡 המלצה:** התחל ב-OCR + regex. אם דיוק נמוך, שדרג ל-Gemini minimal prompt.

### 4.2 Phase 2: Multi-page Extraction (Gemini Calls)

**Input:** LogicalForm with page_indices  
**Output:** Populated LogicalForm with extracted fields

```python
async def extract_form_fields(form: LogicalForm, images: list[bytes]) -> LogicalForm:
    """Extract fields from logical form (may be multi-page).
    
    Strategy:
    - Single-page form: 1 Gemini call (page 0)
    - Two-page form: 2 Gemini calls (page 0, page 1), then merge results
    """
    if len(form.page_indices) == 1:
        # Single page - existing logic works
        page_idx = form.page_indices[0]
        result = await gemini_extract(images[page_idx], form.document_id, page_idx)
        populate_form_from_extraction(form, result)
    
    elif len(form.page_indices) == 2:
        # Two pages - extract both and merge
        results = []
        for page_idx in form.page_indices:
            result = await gemini_extract(images[page_idx], form.document_id, page_idx)
            results.append(result)
        
        # Merge logic: page 0 = patient info, page 1 = additional commitments/samples
        merge_multi_page_results(form, results)
    
    else:
        # 3+ pages (rare) - same as 2-page
        results = [await gemini_extract(images[i], form.document_id, i) 
                   for i in form.page_indices]
        merge_multi_page_results(form, results)
    
    return form
```

**Gemini quota impact:**
- **לפני:** 1 call per page
- **אחרי:** 1 call per page (same!)
- **⚠️ הוספה:** segmentation hints extraction (if using Gemini - see Phase 1)

### 4.3 Phase 3: Sample and Commitment Detection

```python
def create_samples_and_commitments(form: LogicalForm, extraction_results: list) -> tuple[list[Sample], list[Commitment]]:
    """Create Sample and Commitment entities from form extraction.
    
    Implements context-aware commitment detection:
    - "התחייבות" → always commitment
    - "דרישה" → always commitment
    - "דגימה" → commitment ONLY if sender is Leumit/לאומית
    """
    samples = []
    commitments = []
    
    # Step 1: Create samples from (central_number, received_date) pairs
    central_numbers = form.get_all_central_numbers(extraction_results)
    received_dates = form.get_all_received_dates(extraction_results)
    
    # Pair central numbers with received dates (may be N:M)
    for central_num in central_numbers:
        # Strategy: if 1 date, use it for all; if N dates, pair sequentially
        date = received_dates[0] if len(received_dates) == 1 else match_date_to_central(central_num)
        
        sample = Sample(
            sample_id=f"sample_{uuid.uuid4().hex[:12]}",
            form_id=form.form_id,
            central_number=FieldValue[str](raw_value=central_num, ...),
            received_date=FieldValue[str](raw_value=date, ...)
        )
        samples.append(sample)
    
    # Step 2: Create commitments with context-aware detection
    commitment_candidates = extract_commitment_candidates(extraction_results)
    
    for candidate in commitment_candidates:
        # Filter: is this a real commitment or a test number?
        if is_real_commitment(candidate, form.sender):
            commitment = Commitment(
                commitment_id=f"comm_{uuid.uuid4().hex[:12]}",
                form_id=form.form_id,
                commitment_number=FieldValue[str](raw_value=candidate["number"], ...),
                commitment_type=candidate["type"]  # "התחייבות", "דרישה", "דגימה_leumit"
            )
            commitments.append(commitment)
    
    return samples, commitments


def is_real_commitment(candidate: dict, sender: FieldValue[str]) -> bool:
    """Context-aware commitment detection.
    
    Rules:
    1. "התחייבות" or "דרישה" label → always True
    2. "דגימה" label → True ONLY if sender is Leumit/לאומית
    3. Reject test numbers (e.g., "12345678" without label)
    4. Reject central numbers (already in samples)
    """
    label = candidate.get("label", "").strip()
    number = candidate.get("number", "").strip()
    
    # Rule 1: Explicit commitment labels
    if label in ["התחייבות", "דרישה"]:
        return True
    
    # Rule 2: Context-dependent "דגימה"
    if label == "דגימה":
        sender_value = sender.raw_value or sender.normalized_value or ""
        return "לאומית" in sender_value or "leumit" in sender_value.lower()
    
    # Rule 3: No label → reject (likely test number or central number)
    return False
```

### 4.4 Phase 4: Relationship Mapping

```python
def map_commitment_to_samples(commitment: Commitment, samples: list[Sample], form: LogicalForm) -> None:
    """Map commitment to relevant samples (N:M relationship).
    
    Heuristics:
    1. Explicit: Commitment and sample on same line (bbox proximity)
    2. Inferred: Single sample + multiple commitments → all map to sample
    3. Ambiguous: Multiple samples + multiple commitments → flag for review
    """
    if len(samples) == 0:
        commitment.relationship_status = "none"
        commitment.relationship_confidence = 0.0
        return
    
    if len(samples) == 1:
        # Simple case: only one sample, all commitments map to it
        commitment.sample_ids = [samples[0].sample_id]
        commitment.relationship_status = "inferred"
        commitment.relationship_confidence = 0.8
        samples[0].commitment_ids.append(commitment.commitment_id)
        return
    
    # Complex case: multiple samples
    # Check spatial proximity (if bbox available from extraction)
    closest_sample = find_closest_sample_by_bbox(commitment, samples)
    
    if closest_sample:
        commitment.sample_ids = [closest_sample.sample_id]
        commitment.relationship_status = "explicit"
        commitment.relationship_confidence = 0.95
        closest_sample.commitment_ids.append(commitment.commitment_id)
    else:
        # Ambiguous - flag for human review
        commitment.relationship_status = "ambiguous"
        commitment.relationship_confidence = 0.3
        commitment.sample_ids = [s.sample_id for s in samples]  # Link to all
```

### 4.5 Phase 5: Excel Export Generation

```python
async def export_batch_v2(batch_id: str):
    """Export batch to Excel - NEW LOGIC.
    
    Iterate commitments (not forms), generate one row per commitment.
    """
    batch_data = _storage.load_batch(batch_id)
    
    forms = [LogicalForm(**f) for f in batch_data["forms"]]
    samples = [Sample(**s) for s in batch_data["samples"]]
    commitments = [Commitment(**c) for c in batch_data["commitments"]]
    
    # Check for ambiguous relationships (export blocker)
    ambiguous_commitments = [c for c in commitments if c.relationship_status == "ambiguous"]
    if ambiguous_commitments:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Export blocked: some commitments have ambiguous sample relationships",
                "ambiguous_count": len(ambiguous_commitments)
            }
        )
    
    # Generate export rows (one per commitment)
    export_rows = []
    for commitment in commitments:
        form = next(f for f in forms if f.form_id == commitment.form_id)
        commitment_samples = [s for s in samples if s.sample_id in commitment.sample_ids]
        
        # Handle multiple samples: create one row, list all central numbers + dates
        row = ExcelExportRow(
            commitment_id=commitment.commitment_id,
            patient_first_name=get_value(form.patient_first_name),
            patient_last_name=get_value(form.patient_last_name),
            patient_id_number=get_value(form.patient_id_number),
            sender=get_value(form.sender),
            received_date=", ".join([get_value(s.received_date) for s in commitment_samples]),
            central_numbers=[get_value(s.central_number) for s in commitment_samples],
            commitment_number=get_value(commitment.commitment_number)
        )
        export_rows.append(row)
    
    # Write to Excel
    exporter = ExcelExporterV2()
    output_file = exporter.export(export_rows, output_path)
    
    return FileResponse(path=output_file, filename=f"commitments_{batch_id}.xlsx")
```

---

## 5. השפעה על ממשקים קיימים

### 5.1 Excel Export (HIGH IMPACT)

**שינויים נדרשים:**
- ✅ 7 עמודות (ללא שינוי): First Name, Last Name, ID Number, Sender, Received Date, Central Numbers, Commitment Numbers
- ⚠️ לוגיקת איטרציה: מ-`test_records` ל-`commitments`
- ⚠️ ערכים מרובים: `received_date` ו-`central_numbers` עשויים להיות רשימות (אם התחייבות מתייחסת למספר דגימות)

**דוגמה:**

| First Name | Last Name | ID Number | Sender    | Received Date      | Central Numbers | Commitment Numbers |
|------------|-----------|-----------|-----------|--------------------|-----------------|--------------------|
| יוסי       | כהן      | 123456789 | כללית     | 2024-01-15         | 001122          | HTZ987654          |
| יוסי       | כהן      | 123456789 | כללית     | 2024-01-15         | 001122          | HTZ987655          |
| שרה        | לוי       | 987654321 | מכבי      | 2024-01-10, 2024-01-11 | 223344, 223345  | REQ112233          |

**שורה 3:** התחייבות אחת מתייחסת לשתי דגימות → תאריכים ומספרים מופרדים בפסיקים.

### 5.2 Review UI (MEDIUM IMPACT)

**ReviewScreenNew.tsx - שינויים נדרשים:**

```typescript
// Before (page-based):
interface TestRecord {
  test_id: string;
  page_indices: number[];  // Was always [single_page]
  // ...
}

// After (form-based):
interface LogicalForm {
  form_id: string;
  page_indices: number[];  // May be [4, 5] for 2-page form
  samples: Sample[];
  commitments: Commitment[];
  // ...
}
```

**UI changes:**
1. **Card header:** "טופס 1" instead of "עמוד 1"
2. **Multi-page indicator:** Show "עמודים 5-6" if `page_indices.length > 1`
3. **Document viewer:** Display all pages in form (side-by-side or stacked)
4. **Samples section:** Show all samples with central numbers + dates
5. **Commitments section:** Show all commitments with relationship status
6. **Ambiguous relationships:** Highlight in orange, allow manual assignment

**שימור קיים:**
- ✅ 3-state patient name display (Stage 1.5)
- ✅ Export blocking for flagged fields
- ✅ Field editing + verification buttons

### 5.3 Batch Status API (LOW IMPACT)

**GET /api/batch/{batch_id}/status:**

```json
{
  "batch_id": "batch_abc123",
  "status": "completed",
  "statistics": {
    "total_pages": 30,
    "total_forms": 20,       // NEW
    "total_samples": 22,     // NEW
    "total_commitments": 25, // NEW
    "ambiguous_relationships": 3  // NEW (blocks export)
  },
  "forms": [/* LogicalForm objects */],
  "samples": [/* Sample objects */],  // NEW
  "commitments": [/* Commitment objects */],  // NEW
  "errors": []
}
```

---

## 6. מימוש מדורג (Phased Implementation)

### 6.1 P0 (קריטי - חוסם ייצוא)

**מטרה:** Excel export מייצא שורה אחת לכל התחייבות (לא לכל עמוד)

**משימות:**
1. ✅ **Form segmentation:** Implement `segment_forms()` with sequential algorithm
   - Input: list[page_images], Output: list[LogicalForm]
   - Use OCR + regex for page notation (no Gemini)
   - Conservative: if uncertain, split to separate forms
   
2. ✅ **Data model:** Add `LogicalForm`, `Sample`, `Commitment`, `ExcelExportRow` to `models.py`
   - Preserve `TestRecord` and `CommitmentRecord` for backward compatibility (tests)
   - Add migration path (new batches use new model, old batches keep old)
   
3. ✅ **Multi-page extraction:** Modify `_process_batch()` to process forms not pages
   - Segment first: `forms = segment_forms(images, document_id)`
   - Extract per form: `for form in forms: await extract_form_fields(form, images)`
   - Create samples and commitments: `samples, commitments = create_samples_and_commitments(form)`
   
4. ✅ **Excel export rewrite:** Change `ExcelExporter.export()` iteration
   - FROM: `for record in test_records:`
   - TO: `for commitment in commitments:`
   - Join with form + samples to populate row
   
5. ✅ **Export blocking:** Block export if any commitment has `relationship_status == "ambiguous"`

**משך זמן משוער:** 3-5 ימי פיתוח  
**תקציב Gemini:** אפס (OCR בלבד לsegmentation)  
**תלויות:** אין - עצמאי  

**Acceptance tests:**
1. PDF 30 עמודים, 20 טפסים, 25 התחייבויות → Excel 25 שורות ✅
2. טופס עם 2 עמודים (עמוד 1/2, עמוד 2/2) → 1 LogicalForm עם `page_indices=[0,1]` ✅
3. טופס עם 3 התחייבויות → 3 שורות ב-Excel עם פרטי מטופל זהים ✅
4. התחייבות עם 2 דגימות → 1 שורה עם `central_numbers="001, 002"` ✅

### 6.2 P1 (חשוב - דיוק זיהוי)

**מטרה:** Context-aware commitment detection + relationship mapping

**משימות:**
1. ✅ **Context-aware detection:** Implement `is_real_commitment()`
   - "דגימה" → commitment ONLY if sender is Leumit
   - Filter out test numbers and central numbers
   
2. ✅ **Relationship mapping:** Implement `map_commitment_to_samples()`
   - Use bbox proximity if available
   - Heuristic: 1 sample → all commitments map to it
   - Flag ambiguous cases (multiple samples + multiple commitments)
   
3. ✅ **Review UI for ambiguous:** Add manual assignment UI
   - Show commitments and samples side-by-side
   - Drag-and-drop or dropdown to assign
   - Update `relationship_status` to "explicit" after manual assignment

**משך זמן משוער:** 2-3 ימי פיתוח  
**תקציב Gemini:** אפס  
**תלויות:** P0 complete  

### 6.3 P2 (שיפור UX)

**מטרה:** UI improvements for multi-page forms

**משימות:**
1. ✅ **ReviewScreenNew:** Display forms not pages
   - Card header: "טופס 1 (עמודים 5-6)"
   - Document viewer: side-by-side pages for 2-page forms
   
2. ✅ **Samples section:** Show all samples with indicators
   - Central number + received date pairs
   - Visual indicator if sample has no commitments
   
3. ✅ **Commitments section:** Show relationship status
   - Green: explicit/inferred
   - Orange: ambiguous (needs review)
   - Red: none (orphaned commitment)

**משך זמן משוער:** 2-3 ימי פיתוח  
**תקציב Gemini:** אפס  
**תלויות:** P1 complete  

---

## 7. סיכונים והחלטות פתוחות

### 7.1 סיכונים

**R1: Page notation OCR accuracy (HIGH)**
- **סיכון:** OCR לא תמיד מזהה "עמוד 2/2" נכון (רזולוציה נמוכה, טשטוש)
- **הפחתה:** Fallback to central number continuity (Rule 2)
- **Plan B:** Add lightweight Gemini call (quota impact: +30 calls for 30-page PDF)

**R2: Central number pairing with dates (MEDIUM)**
- **סיכון:** אם 2 מספרים מרכזיים + 2 תאריכים, איך לזווג?
- **הפחתה:** Heuristic: sequential pairing (order in extraction)
- **Plan B:** Flag ambiguous if >1 sample → force manual review

**R3: Gemini quota exhaustion (MEDIUM)**
- **סיכון:** Multi-page extraction doubles Gemini calls if using hints extraction
- **הפחתה:** Use OCR-only for segmentation (P0), defer Gemini hints to P3
- **ניטור:** Log quota usage per batch, alert at 80%

**R4: Backward compatibility (LOW)**
- **סיכון:** Old batches (TestRecord-based) break after model change
- **הפחתה:** Migration path: detect batch model version, use old export for legacy
- **Test:** Export old batch after P0 implementation

### 7.2 החלטות פתוחות (למשתמש)

**D1: Segmentation hints - OCR only or Gemini?**
- **אפשרות A:** OCR + regex (zero quota, lower accuracy)
- **אפשרות B:** Gemini lightweight prompt (quota impact: +1 call per page, higher accuracy)
- **המלצה:** Start with A, upgrade to B if accuracy <90%

**D2: Multiple samples + multiple commitments - default behavior?**
- **אפשרות A:** Auto-link all (commitment.sample_ids = all samples) → may create wrong rows
- **אפשרות B:** Leave unlinked (relationship_status = "ambiguous") → blocks export, forces review
- **המלצה:** B (fail-safe, force human decision)

**D3: Export format for multiple samples?**
- **אפשרות A:** Comma-separated in single cell: "001, 002" + "2024-01-10, 2024-01-11"
- **אפשרות B:** Multiple rows per commitment (denormalized)
- **המלצה:** A (matches current central_numbers format, avoids row explosion)

**D4: Stage 1/1.5 merge - before or after P0?**
- **אפשרות A:** Merge now (simpler branch management)
- **אפשרות B:** Merge after P0 (avoid conflicts during rewrite)
- **המלצה:** A - Stage 1/1.5 doesn't conflict with P0 (different files)

---

## 8. תכנית אימות

### 8.1 Unit Tests (Backend)

**New test file: `tests/test_segmentation.py`**
```python
def test_single_page_form():
    """Single page → 1 LogicalForm with page_indices=[0]"""
    
def test_two_page_form_with_notation():
    """Pages with "עמוד 1/2", "עמוד 2/2" → 1 LogicalForm with page_indices=[0,1]"""
    
def test_missing_sticker_not_merged():
    """Page 2 has no sticker but has patient header → 2 separate forms"""
    
def test_continuation_page_merged():
    """Page 2 has no sticker AND no patient header → merged with page 1"""
```

**New test file: `tests/test_commitment_detection.py`**
```python
def test_context_aware_dagima_leumit():
    """'דגימה' + sender='לאומית' → is_commitment=True"""
    
def test_context_aware_dagima_clalit():
    """'דגימה' + sender='כללית' → is_commitment=False"""
    
def test_explicit_commitment_labels():
    """'התחייבות', 'דרישה' → always is_commitment=True"""
```

### 8.2 Integration Tests (End-to-End)

**Test case 1: Reference PDFs (30 pages)**
- Input: `reference/התחייבויות - דוגמאות, חלק 1+2 (PDF).pdf`
- Expected: ~20 forms, ~25 commitments
- Verify: Excel row count == commitment count

**Test case 2: Golden dataset (from Stage 2)**
- Input: 6 synthetic PDFs (`backend/tests/fixtures/forms/form_*.pdf`)
- Ground truth: commitment counts from `golden_dataset_ground_truth.json`
- Verify: segmentation accuracy, commitment detection accuracy

**Test case 3: Multi-commitment form**
- Input: Synthetic PDF with 1 form, 1 sample, 3 commitments
- Expected: 3 Excel rows with identical patient data

### 8.3 Manual Validation (Lab Manager)

**Checklist for user:**
1. ✅ Upload 30-page PDF → verify Excel row count matches commitment count (not page count)
2. ✅ Check 2-page form → verify single entry in ReviewScreen, both pages visible
3. ✅ Check form with 3 commitments → verify 3 Excel rows with repeated patient data
4. ✅ Check Leumit form with "דגימה" → verify recognized as commitment
5. ✅ Check Clalit form with "דגימה" → verify NOT recognized as commitment
6. ✅ Check ambiguous relationship → verify export blocked, manual assignment UI shown

---

## 9. סיכום למשתמש

### מה צריך לקרות עכשיו?

1. **סקירה:** קרא תכנית זו, אשר/דחה את ההחלטות הפתוחות (סעיף 7.2)
2. **אישור P0:** אשר שהיקף P0 פותר את הבעיה הקריטית שלך
3. **Stage 1/1.5 merge:** האם למזג עכשיו או אחרי P0? (המלצה: עכשיו)
4. **Launch workflow:** אחרי אישור, אשיק workflow עם wf-coder + wf-design-reviewer ל-P0

### מה לא יקרה עכשיו?

❌ כתיבת קוד (ממתין לאישור)  
❌ Gemini API calls (לא נחוץ לתכנון)  
❌ Merge/commit/push (שומר על worktree נקי)  
❌ אובדן עבודה (Stage 1/1.5 נשמר במלואו)

### Timeline משוער

| Phase | משימות | זמן פיתוח | זמן בדיקה | סה"כ |
|-------|--------|-----------|-----------|------|
| P0    | Segmentation + data model + Excel rewrite | 3-5 ימים | 1-2 ימים | **4-7 ימים** |
| P1    | Context-aware detection + relationship mapping | 2-3 ימים | 1 יום | **3-4 ימים** |
| P2    | UI improvements | 2-3 ימים | 1 יום | **3-4 ימים** |
| **Total** | | **7-11 ימים** | **3-4 ימים** | **10-15 ימים** |

**קריטי:** P0 לבדו פותר את בעיית ייצוא ה-Excel (שורה לכל התחייבות). P1+P2 משפרים דיוק וחוויית משתמש אבל לא חוסמים שימוש בסיסי.

---

**המלצה אחרונה:** אשר P0 ללא דחייה. זו הנקודה שבה המערכת הופכת שמישה למעבדה. P1+P2 יכולים להמתין.
