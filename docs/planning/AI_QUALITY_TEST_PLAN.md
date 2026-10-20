# AI Quality Test Plan — תכנית בדיקות ואימות איכות

> **Version:** 1.0  
> **Date:** 2026-10-19  
> **Role:** Senior QA Architect, AI Evaluation Engineer, Document Understanding Specialist  
> **Status:** PLANNING PHASE — NO CODE, NO EXECUTION  
> **Purpose:** תכנון מערך בדיקות מקצועי למערכת חילוץ טפסים עם Gemini Vision

---

## 0. Executive Summary

### 0.1 מטרות התכנון

תכנית זו נועדה להוכיח בצורה מדעית, מדידה ושקופה:

1. **האם המנוע ההיברידי מדויק יותר מ-Gemini בלבד?**
2. **באילו שדות המנוע משתפר ובאילו הוא טועה?**
3. **האם המערכת מזהה אי-ודאות בצורה נכונה?**
4. **האם טעויות מסוכנות (False Acceptance) עוברות בשקט?**
5. **האם תיקונים ידניים וייצוא Excel נשארים תקינים?**

### 0.2 עקרונות מנחים

**1. Ground Truth First:** כל השוואה תלויה באמת מאומתת ידנית  
**2. No Synthetic Fantasies:** בדיקות Mock לעולם לא יוכיחו דיוק AI אמיתי  
**3. Measure Harm, Not Just Accuracy:** False Acceptance חשוב מאחוזי הצלחה  
**4. Transparency Over Vanity Metrics:** דיווח כנה על כשלונים  
**5. Ethical Testing:** אין בדיקות Live עם Gemini ללא אישור מפורש

### 0.3 לוח זמנים מוצע (לא מחייב)

- **Week 1:** הכנת Golden Dataset (תיוג ידני)
- **Week 2:** Baseline Measurement (Gemini בלבד)
- **Week 3-4:** Hybrid Engine Implementation (צוות מקביל)
- **Week 5:** Comparison Tests + Analysis
- **Week 6:** Regression Suite + Documentation

**הערה:** לוח זמנים משוער; תלוי באישורים וזמינות צוות.

---

## 1. Test Strategy — אסטרטגיה כללית

### 1.1 שלוש רמות בדיקה

```
┌─────────────────────────────────────────────────────┐
│ Level 1: Synthetic/Mock Tests (No Gemini)          │
│ ✓ Contract tests, validation logic, Excel export   │
│ ✓ Always runnable, no quota, no cost               │
│ ✗ Cannot prove AI accuracy                         │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Level 2: Local OCR Tests (Tesseract only)          │
│ ✓ Real document processing, no external API        │
│ ✓ Tests preprocessing, OCR quality                 │
│ ✗ Limited accuracy, not comparable to Gemini       │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Level 3: Live Gemini Tests (Requires approval)     │
│ ✓ True accuracy measurement                        │
│ ✓ Baseline vs Hybrid comparison                    │
│ ✗ Uses Free Tier quota, needs explicit approval    │
└─────────────────────────────────────────────────────┘
```

**Decision Rule:** Levels 1-2 are always safe to run. Level 3 requires:
- Explicit approval from project owner (D-01)
- Confirmed Free Tier quota availability (D-02)
- Golden Dataset ready with verified Ground Truth

### 1.2 Test Execution Policy

**When to Run Each Level:**

| Test Level | When to Execute | Frequency | Approval |
|-----------|----------------|-----------|----------|
| Level 1 (Mock) | Always (CI/CD safe) | Every commit | None |
| Level 2 (OCR) | Before PR merge | Daily | None |
| Level 3 (Live) | Before release only | Manual trigger | **REQUIRED** |

**Critical Rule:** אין להריץ Level 3 אוטומטית או ללא אישור מפורש.

---

## 2. Golden Dataset Design — מערך הנתונים המאומת

### 2.1 מטרת ה-Golden Dataset

**Golden Dataset** הוא מדגם מייצג של טפסים שתויגו **ידנית על ידי מומחה אנושי**.  
זהו **המקור המחייב** להשוואת תוצאות Gemini/Hybrid Engine.

**ללא Ground Truth אמיתי, אין אפשרות למדוד דיוק.**

### 2.2 גודל מדגם

לפי המלצת מסמך האתגר והספרות המקצועית:

- **MVP Minimum:** 10-15 טפסים מייצגים
- **Recommended:** 25-30 טפסים (כיסוי טוב יותר)
- **Ideal (Production):** 100+ טפסים (אמינות סטטיסטית)

**החלטה:** נתחיל ב-**15 טפסים** כ-MVP, עם אפשרות הרחבה.

**הערה קריטית:** מדגם של 15 טפסים אינו מספיק להוכחת דיוק כללי, אך מספיק לזיהוי בעיות מובנות.

### 2.3 אסטרטגיית דגימה

**לא דגימה אקראית — דגימה מובנית לפי תרחישים.**

#### 2.3.1 מטריצת תרחישים (Scenario Matrix)

```
┌──────────────────────────┬────────────────────────────────────────┐
│ Dimension                │ Coverage Requirements                  │
├──────────────────────────┼────────────────────────────────────────┤
│ Text Quality             │ • Printed text (clear)                 │
│                          │ • Handwritten Hebrew (challenging)     │
│                          │ • Mixed printed + handwritten          │
│                          │ • Degraded/faded (poor quality)        │
├──────────────────────────┼────────────────────────────────────────┤
│ Form Type                │ • Clalit (כללית)                       │
│                          │ • Maccabi (מכבי)                       │
│                          │ • Hospital forms (varied)              │
│                          │ • Unknown/unrecognized forms           │
├──────────────────────────┼────────────────────────────────────────┤
│ Document Structure       │ • Single page, single test             │
│                          │ • Multiple pages, single test          │
│                          │ • Multiple tests per page              │
│                          │ • Rotated pages (90°, 180°)            │
├──────────────────────────┼────────────────────────────────────────┤
│ Field Complexity         │ • All 7 fields present                 │
│                          │ • Missing required fields              │
│                          │ • Multiple central numbers (2-5)       │
│                          │ • Multiple commitment numbers          │
│                          │ • Conflicting values (stamp vs label)  │
├──────────────────────────┼────────────────────────────────────────┤
│ Visual Elements          │ • Barcodes                             │
│                          │ • Stickers                             │
│                          │ • Stamps ("התקבל")                     │
│                          │ • Logos                                │
│                          │ • Handwritten annotations              │
├──────────────────────────┼────────────────────────────────────────┤
│ Edge Cases               │ • Invalid ID checksum                  │
│                          │ • Ambiguous date (multiple dates)      │
│                          │ • Partially cropped scan               │
│                          │ • Low contrast/poor lighting           │
│                          │ • Background noise                     │
└──────────────────────────┴────────────────────────────────────────┘
```

#### 2.3.2 מדגם מוצע (15 טפסים)

| # | Scenario | Form Type | Text Quality | Complexity | Why Selected |
|---|----------|-----------|-------------|-----------|--------------|
| 1 | Baseline clear | Clalit printed | ✓ Clear | Simple | Positive control |
| 2 | Handwritten Hebrew | Clalit | ⚠ Handwritten | Medium | Known AI weakness |
| 3 | Rotated 90° | Hospital | ✓ Clear | Medium | Orientation test |
| 4 | Multiple centrals | Maccabi | ✓ Clear | High | N:M relationship |
| 5 | Missing commitment | Hospital | ✓ Clear | High | Required field absent |
| 6 | Stamp + handwritten date | Clalit | Mixed | Medium | Conflicting sources |
| 7 | Degraded quality | Unknown form | ✗ Poor | High | Worst-case scenario |
| 8 | Multi-page test | Hospital | ✓ Clear | High | Page grouping |
| 9 | Invalid ID checksum | Maccabi | ✓ Clear | Medium | Validation test |
| 10 | Multiple tests/page | Clalit | ✓ Clear | High | Segmentation test |
| 11 | Barcode + stickers | Hospital | ✓ Clear | Medium | Visual elements |
| 12 | Ambiguous sender | Unknown | ✓ Clear | Medium | Classification test |
| 13 | Partially cropped | Maccabi | ⚠ Cropped | High | Incomplete data |
| 14 | Mixed languages | Hospital | Mixed | Medium | Hebrew + English |
| 15 | Clean negative | Clalit | ✓ Clear | Simple | Regression baseline |

**Coverage Achieved:**
- Text Quality: 9 clear, 3 handwritten, 2 degraded, 1 cropped
- Form Types: 5 Clalit, 3 Maccabi, 6 Hospital, 1 Unknown
- Complexity: 3 simple, 6 medium, 6 high
- Edge Cases: All major categories represented

### 2.4 תיוג ידני (Manual Annotation)

#### 2.4.1 Ground Truth Data Structure

```json
{
  "form_id": "GT-001",
  "source_file": "reference/sample_01.pdf",
  "page_number": 1,
  "annotation_date": "2026-10-19",
  "annotator": "Human Expert ID",
  "annotation_confidence": "high",
  
  "ground_truth": {
    "patient_first_name": {
      "value": "משה",
      "source_evidence": "Printed label, clear",
      "confidence": "certain"
    },
    "patient_last_name": {
      "value": "כהן",
      "source_evidence": "Printed label, clear",
      "confidence": "certain"
    },
    "patient_id_number": {
      "value": "123456789",
      "source_evidence": "Patient sticker, 9 digits",
      "confidence": "certain"
    },
    "sender": {
      "value": "כללית",
      "normalized": "Clalit",
      "source_evidence": "Header logo + text",
      "confidence": "certain"
    },
    "received_date": {
      "value": "15/03/2024",
      "normalized": "2024-03-15",
      "source_evidence": "Stamp 'התקבל' with date",
      "confidence": "certain"
    },
    "central_numbers": {
      "values": ["12345", "67890"],
      "source_evidence": "2 stickers labeled 'מרכזי'",
      "confidence": "certain"
    },
    "commitment_numbers": {
      "values": ["ABC123"],
      "source_evidence": "Field labeled 'התחייבות'",
      "confidence": "certain"
    }
  },
  
  "special_attributes": {
    "rotation": 0,
    "quality": "high",
    "completeness": "full",
    "ambiguous_fields": [],
    "known_challenges": ["None - baseline case"]
  },
  
  "relationships": {
    "test_records": 1,
    "commitment_records": 1,
    "central_to_commitment_mapping": {
      "ABC123": ["12345", "67890"]
    },
    "mapping_confidence": "certain"
  },
  
  "notes": "Baseline positive control. All fields clearly visible and labeled."
}
```

#### 2.4.2 כללי תיוג

**Annotation Rules:**

1. **Value Extraction:**
   - Copy EXACTLY as appears in document (no corrections)
   - Preserve leading zeros, spaces, formatting
   - If illegible → mark as `null` with `"confidence": "illegible"`

2. **Evidence Documentation:**
   - Specify WHERE value found (label, stamp, sticker, handwritten)
   - Include bbox coordinates if available (x, y, width, height)
   - Screenshot crop of evidence recommended

3. **Confidence Levels:**
   - `certain`: Clear, unambiguous, labeled
   - `probable`: Legible but context-based inference
   - `uncertain`: Multiple plausible readings
   - `illegible`: Cannot determine value

4. **Ambiguity Handling:**
   - If field has multiple plausible values → list ALL options
   - Document source of each option
   - Mark field as `"ambiguous_fields": ["field_name"]`

5. **Missing vs Empty:**
   - `missing`: Field expected but not present in document
   - `empty`: Field present but intentionally blank
   - `illegible`: Present but cannot be read

**Critical:** תיוג חייב להיעשות על ידי מומחה שמבין את ההקשר הרפואי והתבנית.

### 2.5 Validation of Ground Truth

**ערכת Ground Truth חייבת לעבור ביקורת עצמאית:**

- **Dual Annotation:** 20% מהמדגם מתויג על ידי שני מומחים בלתי תלויים
- **Inter-Annotator Agreement:** מדידת Kappa > 0.8 נדרשת
- **Conflict Resolution:** סתירות נפתרות בדיון או ע"י מומחה שלישי
- **Documentation:** כל החלטת תיוג מתועדת עם נימוק

**ללא Ground Truth מאומת, אין בסיס להשוואה.**

---

## 3. Baseline Measurement — מדידת Gemini בלבד

### 3.1 מטרה

לקבוע **baseline performance** של Gemini Vision בלבד, ללא OCR או Hybrid logic.

זהו הייחוס לכל השוואה עתידית.

### 3.2 Test Execution

**Input:** Golden Dataset (15 forms) + Ground Truth  
**Engine:** Gemini Vision API only (prompt v2.0)  
**Output:** Extraction results + metrics

**Test Script Structure:**

```python
# Pseudo-code (planning only)

def baseline_gemini_test():
    results = []
    
    for form in golden_dataset:
        # Extract using Gemini only
        extraction = gemini_extractor.extract(
            image=form.image,
            document_id=form.id,
            page_index=0
        )
        
        # Compare with Ground Truth
        comparison = compare_extraction(
            extraction=extraction,
            ground_truth=form.ground_truth
        )
        
        results.append({
            'form_id': form.id,
            'extraction': extraction,
            'ground_truth': form.ground_truth,
            'comparison': comparison
        })
    
    # Aggregate metrics
    metrics = calculate_metrics(results)
    
    # Generate report
    generate_baseline_report(metrics, results)
```

### 3.3 מדדי איכות (Quality Metrics)

#### 3.3.1 Per-Field Accuracy

**Definition:** אחוז שדות שחולצו נכון מתוך שדות עם Ground Truth.

```
Field Accuracy = (Correct Extractions) / (Total Fields with GT)
```

**Measured per field type:**

| Field | Total GT | Correct | Incorrect | Missing | Accuracy |
|-------|----------|---------|-----------|---------|----------|
| first_name | 15 | ? | ? | ? | ?% |
| last_name | 15 | ? | ? | ? | ?% |
| id_number | 15 | ? | ? | ? | ?% |
| sender | 15 | ? | ? | ? | ?% |
| received_date | 15 | ? | ? | ? | ?% |
| central_numbers | 15 | ? | ? | ? | ?% |
| commitment_numbers | 15 | ? | ? | ? | ?% |
| **Overall** | 105 | ? | ? | ? | **?%** |

**Correctness Criteria:**

- **Exact Match:** Value identical to GT (preferred)
- **Normalized Match:** After normalization (dates, sender names)
- **Semantic Match:** Functionally equivalent (e.g., "כהן" vs "Cohen")

**Decision:** Start with Exact Match, add Normalized if needed.

#### 3.3.2 Coverage Rate

**Definition:** אחוז שדות שהמערכת החזירה ערך (לא null, לא []).

```
Coverage = (Fields with Value) / (Total Fields)
```

**למה זה חשוב?**  
מערכת שמחזירה null לכל שדה תקבל Accuracy 0% אבל לא תיצור שגיאות מסוכנות.  
Coverage מודד את **השימושיות** של המערכת.

**Example:**

```
Coverage: 85% (89/105 fields returned a value)
Accuracy: 72% (76/105 fields correct)
→ Useful Accuracy: 72% of 85% = 61% fields both extracted AND correct
```

#### 3.3.3 False Extraction (Hallucination)

**Definition:** ערך שהמערכת החזירה אבל לא מופיע בטופס או שגוי.

**Categories:**

1. **Invented Value:** ערך שלא קיים בטופס (המצאה)
2. **Wrong Field:** ערך קיים אבל שוייך לשדה הלא נכון
3. **Partial Extraction:** חלק מהערך (e.g., "12345" במקום "123456789")
4. **Modified Value:** ערך שהמודל "תיקן" (e.g., added leading zero)

**Measurement:**

```
False Extraction Rate = (Incorrect Values) / (Total Extracted Values)
```

**Critical:** ההבדל בין "לא מצא" (null) ל"המציא" (wrong value).

#### 3.3.4 Unsafe Acceptance (Critical Metric)

**Definition:** ערך שגוי שהמערכת **לא סימנה לביקורת**.

זהו **המדד הקריטי ביותר** למערכת רפואית.

**Scenario Example:**

```
Ground Truth: patient_id = "123456789"
Gemini Output: patient_id = "123456780" (checksum error)
Gemini State: extraction_state = "found" (not "uncertain"!)
Review State: review_state = "pending" (not "needs_review"!)

→ UNSAFE ACCEPTANCE: שגיאה שעוברת בשקט.
```

**Measurement:**

```
Unsafe Acceptance Rate = (Incorrect AND not flagged) / (Total Incorrect)
```

**Target:** 0% (אפס שגיאות שקטות)

**Acceptable:** < 5% במקרים שאינם critical (e.g., sender typo)  
**Unacceptable:** > 0% ב-patient_id, central_numbers, commitment_numbers

#### 3.3.5 Review Burden

**Definition:** אחוז שדות/רשומות שדורשים ביקורת אנושית.

```
Review Burden = (Fields flagged needs_review) / (Total Fields)
```

**Balance Tradeoff:**

```
High Review Burden → Safe but labor-intensive
Low Review Burden → Efficient but risky
```

**Ideal Balance:**

- Flag ALL uncertain/conflicting/missing required fields
- Flag NO clear/confident extractions
- Target: 15-30% review rate (industry standard for assisted data entry)

#### 3.3.6 Multi-Value Recall

**Definition:** שיעור ערכים מרובים שנשמרו (לא אבדו).

**Example:**

```
Ground Truth: central_numbers = ["12345", "67890", "11111"]
Gemini Output: central_numbers = ["12345", "67890"]

→ Recall = 2/3 = 66.7% (missed one central number)
```

**Measurement per list field:**

```
Recall = (Extracted Values ∩ GT Values) / (GT Values)
Precision = (Extracted Values ∩ GT Values) / (Extracted Values)
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

**Critical for:** central_numbers, commitment_numbers

#### 3.3.7 Record/Link Accuracy

**Definition:** נכונות רשומות ושיוכים בין commitments למרכזיים.

**Measurement:**

1. **Record Count:** מספר TestRecords וCommitmentRecords נכון?
2. **Link Accuracy:** שיוכים בין רשומות נכונים?

**Example:**

```
Ground Truth:
  - Test 1: centrals [A, B], commitments [X, Y]
  - Mapping: X→[A,B], Y→[A,B]

Gemini Output:
  - Test 1: centrals [A, B], commitments [X, Y]
  - Mapping: X→[A], Y→[B]  (WRONG)

→ Record count: ✓ Correct
→ Link accuracy: ✗ Incorrect
```

#### 3.3.8 Export Integrity

**Definition:** נכונות קובץ Excel המיוצא.

**Checks:**

1. **Row Count:** מספר שורות = מספר CommitmentRecords?
2. **Column Mapping:** כל 7 שדות נמצאים בעמודות נכונות?
3. **Value Preservation:** ערכים זהים לתוצאות הפנימיות?
4. **Type Correctness:** מספרים כטקסט (אפסים מובילים)?
5. **Formula Injection:** אין נוסחאות מסוכנות?
6. **Roundtrip:** קריאת Excel חוזרת נותנת אותם ערכים?

**Measurement:**

```
Export Integrity = (Passed Checks) / (Total Checks)
```

#### 3.3.9 Latency & Cost

**Definition:** זמן עיבוד ועלות API.

**Measurements:**

- **Time per page:** Average processing time (seconds)
- **Time per form:** Average for multi-page forms
- **API calls:** Number of Gemini requests
- **Tokens:** Input/output token count
- **Cost:** ₪0 (Free Tier) or calculated cost

**Budgeting:**

```
Free Tier Limit: 20-500 requests/day (model dependent)
Golden Dataset: 15 forms = 15 requests (Baseline)
Hybrid Test: 15 forms × 2 engines = 30 requests
Regression Suite: ≈ 100 requests

→ Total Budget Needed: ~150 requests
→ Strategy: Spread tests over multiple days if needed
```

### 3.4 Baseline Report Template

```markdown
# Baseline Measurement Report — Gemini Vision Only

**Date:** YYYY-MM-DD
**Model:** gemini-2.0-flash-exp
**Prompt Version:** 2.0
**Dataset:** Golden Dataset v1.0 (15 forms)

## Summary

| Metric | Value |
|--------|-------|
| Overall Field Accuracy | ?% |
| Coverage Rate | ?% |
| False Extraction Rate | ?% |
| **Unsafe Acceptance Rate** | **?%** |
| Review Burden | ?% |
| Multi-Value Recall | ?% |

## Per-Field Performance

| Field | Accuracy | Coverage | False Ext | Unsafe Accept |
|-------|----------|----------|-----------|---------------|
| first_name | ?% | ?% | ?% | ?% |
| last_name | ?% | ?% | ?% | ?% |
| id_number | ?% | ?% | ?% | ?% |
| sender | ?% | ?% | ?% | ?% |
| received_date | ?% | ?% | ?% | ?% |
| central_numbers | ?% | ?% | ?% | ?% |
| commitment_numbers | ?% | ?% | ?% | ?% |

## Failure Analysis

### Known Failures (Examples)

1. **Form GT-002 (Handwritten Hebrew):**
   - Field: `patient_first_name`
   - GT: "משה"
   - Extracted: "מרדכי" (hallucination)
   - State: `found` (NOT flagged)
   - **Impact:** UNSAFE ACCEPTANCE

2. **Form GT-005 (Missing Commitment):**
   - Field: `commitment_numbers`
   - GT: [] (truly missing)
   - Extracted: null
   - State: `missing` (correctly flagged)
   - **Impact:** Safe (review triggered)

### Patterns Identified

- Handwritten Hebrew: 0% accuracy (all invented or null)
- Rotated pages: 80% accuracy (slight degradation)
- Multiple centrals: 67% recall (one value often missed)
- Sender field: 87% accuracy (normalization issues)

## Recommendations

1. **Immediate:** Add uncertainty detection for handwritten fields
2. **Short-term:** Implement OCR verification for centrals/commitments
3. **Long-term:** Multi-engine voting system

## Raw Data

[Attached: baseline_results.json]
```

---

## 4. Hybrid Engine Comparison — השוואת מנועים

### 4.1 מטרה

להוכיח שהמנוע ההיברידי (Gemini + OCR + Verification) משפר את הדיוק והבטיחות.

**השאלה המרכזית:**  
**האם Hybrid Engine מצדיק את המורכבות הנוספת?**

### 4.2 Comparison Design

**Test Setup:**

```
Input: Same Golden Dataset (15 forms)
Engines:
  1. Baseline: Gemini Only
  2. Hybrid: Gemini + Tesseract OCR + Cross-Verification

Output: Side-by-side comparison report
```

**Execution Plan:**

1. Run Baseline (if not already done)
2. Run Hybrid Engine
3. Compare results field-by-field
4. Generate delta report

### 4.3 Hybrid-Specific Metrics

#### 4.3.1 Verification Impact

**Definition:** כמה שדות שופרו/הורעו על ידי Hybrid logic?

**Categories:**

1. **Corrected:** Gemini wrong → Hybrid correct
2. **Confirmed:** Gemini correct → Hybrid agrees (confidence boost)
3. **Conflicted:** Gemini vs OCR disagree → flagged for review
4. **Degraded:** Gemini correct → Hybrid wrong (regression!)

**Measurement:**

```
Improvement Rate = (Corrected) / (Baseline Incorrect)
Regression Rate = (Degraded) / (Baseline Correct)
Net Benefit = Improvement Rate - Regression Rate
```

**Target:** Net Benefit > 10% (משמעותי)

#### 4.3.2 Uncertainty Detection Accuracy

**Definition:** האם המנוע מזהה נכון מתי ערך לא בטוח?

**Truth Table:**

```
┌────────────────┬─────────────────┬────────────────┐
│ Ground Truth   │ Flagged?        │ Classification │
├────────────────┼─────────────────┼────────────────┤
│ Correct value  │ No (pending)    │ True Negative  │
│ Correct value  │ Yes (flagged)   │ False Positive │
│ Incorrect value│ No (pending)    │ False Negative │
│ Incorrect value│ Yes (flagged)   │ True Positive  │
└────────────────┴─────────────────┴────────────────┘
```

**Metrics:**

```
Sensitivity (Recall) = TP / (TP + FN)
  → "What % of errors did we catch?"

Specificity = TN / (TN + FP)
  → "What % of correct values did we NOT flag?"

Precision = TP / (TP + FP)
  → "Of flagged fields, what % were actually wrong?"
```

**Ideal Balance:**

- High Sensitivity (catch ALL errors) → Safety
- High Specificity (don't over-flag) → Efficiency

**Target:**

- Sensitivity > 95% (miss < 5% errors)
- Specificity > 70% (flag < 30% correct values)

#### 4.3.3 OCR Contribution

**Definition:** כמה שדות שופרו ספציפית על ידי OCR?

**Measurement per field type:**

```
OCR Contribution = (Fields where OCR correct AND Gemini wrong) / (Total Fields)
```

**Expected Results:**

- High contribution: central_numbers, commitment_numbers (numeric, clear labels)
- Low contribution: patient names (OCR struggles with Hebrew handwriting)
- Medium contribution: dates, ID numbers

#### 4.3.4 Preprocessing Impact

**Definition:** האם deskewing/rotation detection שיפר דיוק?

**Test:**

```
For each rotated form:
  - Run Gemini without rotation fix
  - Run Gemini with rotation fix
  - Compare accuracy
```

**Measurement:**

```
Preprocessing Benefit = (Accuracy with fix) - (Accuracy without fix)
```

### 4.4 Comparison Report Template

```markdown
# Hybrid Engine Comparison Report

**Date:** YYYY-MM-DD
**Dataset:** Golden Dataset v1.0 (15 forms)
**Baseline:** Gemini v2.0
**Hybrid:** Gemini + Tesseract + Verification Logic

## Summary

| Metric | Baseline | Hybrid | Delta |
|--------|----------|--------|-------|
| Overall Accuracy | ?% | ?% | **+?%** |
| Unsafe Acceptance | ?% | ?% | **-?%** |
| Review Burden | ?% | ?% | +?% |
| Sensitivity (Error Detection) | ?% | ?% | **+?%** |

## Per-Field Improvement

| Field | Baseline Acc | Hybrid Acc | Improvement |
|-------|-------------|-----------|-------------|
| first_name | ?% | ?% | +?% |
| last_name | ?% | ?% | +?% |
| id_number | ?% | ?% | +?% |
| central_numbers | ?% | ?% | **+?%** ← OCR |
| commitment_numbers | ?% | ?% | **+?%** ← OCR |

## Verification Impact Analysis

### Corrections (Gemini wrong → Hybrid correct)

**Count:** ? fields corrected

**Examples:**

- Form GT-004: `central_numbers` 
  - Gemini: ["12345"] (missed one)
  - OCR: ["12345", "67890"]
  - Hybrid: ["12345", "67890"] ✓ Corrected

### Conflicts (Gemini ≠ OCR → Review)

**Count:** ? conflicts detected

**Examples:**

- Form GT-008: `patient_id_number`
  - Gemini: "123456789"
  - OCR: "123456780"
  - Hybrid: Flagged `conflicting`, needs_review ✓

### Regressions (Gemini correct → Hybrid wrong)

**Count:** ? regressions (CRITICAL)

**Examples:**

[If any regressions found, list here]

## OCR Contribution by Field Type

| Field Type | OCR Helpful | OCR Neutral | OCR Harmful |
|-----------|-------------|-------------|-------------|
| Numeric (centrals, commitments) | ?% | ?% | ?% |
| Alphanumeric (ID) | ?% | ?% | ?% |
| Text (names) | ?% | ?% | ?% |
| Dates | ?% | ?% | ?% |

## Decision: Is Hybrid Worth It?

### Benefits

- Accuracy improvement: +?%
- Unsafe acceptance reduction: -?%
- Conflict detection: ? new conflicts found

### Costs

- Implementation complexity: +? hours
- Review burden increase: +?%
- Processing time: +? seconds/form

### Recommendation

[Based on measured Net Benefit]

✓ **PROCEED:** If Net Benefit > 10% AND Unsafe Acceptance < 2%
⚠ **REFINE:** If Net Benefit < 10% OR regressions detected
✗ **ABORT:** If Hybrid degrades safety (higher Unsafe Acceptance)
```

---

## 5. Regression Test Suite — מניעת נסיגות

### 5.1 מטרה

להבטיח ששינויים עתידיים לא ישברו תיקונים/שיפורים קיימים.

**Use Cases:**

- Prompt changes (v2.0 → v3.0)
- Model upgrades (gemini-2.0 → gemini-3.0)
- Code refactoring
- Bug fixes

### 5.2 Regression Test Design

**Strategy:** Capture known failures + fixes as permanent test cases.

#### 5.2.1 Known Failure Cases

**From Baseline Measurement:**

```python
# tests/regression/test_known_failures.py

def test_handwritten_hebrew_name_not_invented():
    """
    REGRESSION: Form GT-002 (Handwritten name)
    
    HISTORY:
    - 2026-10-19: Gemini invented "מרדכי" instead of reading "משה"
    - Expected: extraction_state = 'uncertain' OR review_state = 'needs_review'
    
    CRITICAL: This test ensures AI does NOT invent names.
    """
    form = load_golden_form("GT-002")
    result = gemini_extractor.extract(form.image, form.id, 0)
    
    # Assert: Either field is null OR flagged for review
    first_name_field = result.fields['patient_first_name']
    
    assert (
        first_name_field.raw_value is None  # Didn't extract
        OR first_name_field.extraction_state == ExtractionState.uncertain
        OR first_name_field.review_state == ReviewState.needs_review
    ), "Handwritten name must be flagged or null, not confidently wrong"
    
    # Assert: No confident incorrect value
    if first_name_field.raw_value is not None:
        assert first_name_field.raw_value == form.ground_truth.first_name, \
            f"If extracted, must be correct. Got: {first_name_field.raw_value}"
```

**Additional Known Failures:**

```python
def test_multiple_centrals_not_lost():
    """Form GT-004: Multiple central numbers (N>1)"""
    # Assert: All central numbers extracted
    pass

def test_rotated_page_detected():
    """Form GT-003: 90° rotation"""
    # Assert: Rotation detected and corrected
    pass

def test_invalid_id_checksum_flagged():
    """Form GT-009: Invalid ID checksum"""
    # Assert: Validation catches checksum error
    pass

def test_ambiguous_date_not_chosen():
    """Form GT-006: Multiple dates on form"""
    # Assert: Conflicting dates trigger review
    pass

def test_missing_commitment_not_invented():
    """Form GT-005: No commitment number in document"""
    # Assert: Field is null or empty [], not invented
    pass
```

#### 5.2.2 Regression Suite Execution

**Frequency:**

- **Before merge:** Run full suite
- **Before release:** Run full suite + manual spot-checks
- **After prompt changes:** Run full suite (MANDATORY)
- **After model upgrade:** Run full suite (MANDATORY)

**Pass Criteria:**

```
✓ All regression tests pass (0 failures)
✓ No new Unsafe Acceptances introduced
✓ Baseline metrics maintained or improved
```

**Fail Action:**

```
✗ BLOCK MERGE if regression test fails
✗ INVESTIGATE immediately
✗ FIX before proceeding
```

### 5.3 Regression Report Template

```markdown
# Regression Test Report

**Date:** YYYY-MM-DD
**Change:** [e.g., Prompt v2.0 → v2.1]
**Commit:** [hash]

## Test Results

| Test Case | Before | After | Status |
|-----------|--------|-------|--------|
| Handwritten name safety | PASS | PASS | ✓ |
| Multiple centrals recall | PASS | FAIL | **✗ REGRESSION** |
| Rotated page detection | PASS | PASS | ✓ |
| Invalid ID flagging | PASS | PASS | ✓ |
| Ambiguous date handling | PASS | PASS | ✓ |
| Missing commitment safety | PASS | PASS | ✓ |

## Regressions Detected

### CRITICAL: Multiple centrals lost

**Test:** `test_multiple_centrals_not_lost`

**Before:**
- Form GT-004: 3 central numbers
- Extracted: ["12345", "67890", "11111"]
- Recall: 100%

**After:**
- Form GT-004: 3 central numbers
- Extracted: ["12345", "67890"]
- Recall: 67% ← **REGRESSION**

**Root Cause:** [Investigation needed]

**Action:** BLOCK MERGE until fixed

## Decision

[✓ PASS | ✗ FAIL]
```

---

## 6. End-to-End Integration Tests

### 6.1 מטרה

לבדוק את **המערכת כמכלול**, לא רק מנוע החילוץ.

**Test Scope:**

```
Upload → Processing → Review → Manual Correction → Export → Excel Validation
```

### 6.2 E2E Test Scenarios

#### 6.2.1 Happy Path

**Scenario:** Upload clear form, review flagged fields, export Excel.

**Steps:**

1. Upload `GT-001.pdf` (clear, simple form)
2. Wait for processing to complete
3. Verify: Some fields flagged (e.g., uncertain sender)
4. Review: Approve/correct flagged fields
5. Export: Generate Excel
6. Validate: Excel matches corrected values

**Pass Criteria:**

```
✓ All 7 fields appear in Excel
✓ Manual corrections preserved (not overwritten)
✓ Row count = number of commitments
✓ Numbers stored as text (leading zeros preserved)
✓ No formula injection
✓ Roundtrip: Re-reading Excel gives same values
```

#### 6.2.2 Export Blocking

**Scenario:** Upload form with unresolved issues, verify export is blocked.

**Steps:**

1. Upload form with missing required field
2. Wait for processing
3. Verify: Field flagged `needs_review`
4. Attempt export WITHOUT resolving
5. Verify: Export button disabled
6. Verify: API call returns 409 Conflict
7. Resolve issue (approve empty or enter value)
8. Verify: Export now enabled
9. Export succeeds

**Pass Criteria:**

```
✓ Export blocked when unresolved issues exist
✓ Block enforced in BOTH UI and API
✓ Clear error message shown
✓ Export enabled after all issues resolved
```

#### 6.2.3 Batch Processing

**Scenario:** Upload multiple forms, verify failure isolation.

**Steps:**

1. Upload batch: 3 forms (2 valid, 1 corrupted)
2. Wait for processing
3. Verify: 2 forms completed, 1 failed
4. Verify: Failed form does NOT block others
5. Export: Only successful forms exported

**Pass Criteria:**

```
✓ Failure isolation (one bad form doesn't break batch)
✓ Per-document status tracking
✓ Clear error messages for failed forms
```

#### 6.2.4 Concurrent Editing

**Scenario:** Two users edit same field (race condition test).

**Steps:**

1. User A: Opens form, edits `patient_first_name`
2. User B: Opens same form, edits `patient_first_name` (different value)
3. User A: Saves → Success (gets ETag)
4. User B: Saves → Should get 409 Conflict (stale ETag)

**Pass Criteria:**

```
✓ ETag prevents race condition
✓ Last writer does NOT silently overwrite
✓ User B notified to refresh and retry
```

---

## 7. Test Data Management — ניהול נתונים

### 7.1 Test Data Categories

#### 7.1.1 Synthetic Test Data

**Purpose:** Contract tests, validation logic, export formatting.

**Characteristics:**

- Manually crafted JSON payloads
- No real documents
- No Gemini calls
- Always runnable

**Example:**

```json
{
  "test_id": "SYNTHETIC-001",
  "patient_first_name": {
    "raw_value": "John",
    "extraction_state": "found",
    "review_state": "pending"
  },
  "patient_id_number": {
    "raw_value": "000123456",
    "extraction_state": "found",
    "review_state": "pending"
  }
}
```

**Use Cases:**

- Unit tests for validation rules
- Excel export formatting tests
- API contract tests

#### 7.1.2 Sample Documents (De-identified)

**Purpose:** Visual/layout testing without real PII.

**Characteristics:**

- Real form templates
- Filled with synthetic data ("Test Patient", "000000000")
- Clearly marked "SAMPLE — NOT REAL DATA"
- Safe to commit to Git

**Use Cases:**

- Frontend UI testing
- Document rendering tests
- OCR preprocessing tests

#### 7.1.3 Golden Dataset (Real or Realistic)

**Purpose:** Ground truth for accuracy measurement.

**Characteristics:**

- Real forms (with PII removed/replaced) OR
- Realistic forms with diverse characteristics
- Manually annotated Ground Truth
- **NEVER committed to Git** (stored in `reference/` ignored folder)

**Use Cases:**

- Baseline measurement
- Hybrid comparison
- Regression tests

**Security:**

```
reference/
  golden_dataset/
    GT-001.pdf       # ← .gitignored
    GT-002.pdf
    ...
    annotations.json  # ← .gitignored
```

### 7.2 Test Data Security

**Rules:**

1. **Synthetic data:** Safe to commit, clearly marked
2. **Sample documents:** Safe if de-identified, verify before commit
3. **Golden dataset:** NEVER commit, store locally only
4. **API responses:** Scrub PII before logging
5. **Screenshots:** Blur/redact PII before sharing

**Verification:**

```bash
# Before committing:
git diff --staged | grep -E "patient|ID|ת.ז"
# If any real-looking data found → ABORT
```

---

## 8. Test Execution Plan — סדר ביצוע

### 8.1 Phase-by-Phase Execution

**Phase 0: Preparation (No Gemini)**

```
Week 1:
  ✓ Select 15 forms for Golden Dataset
  ✓ Manual annotation (Ground Truth)
  ✓ Dual annotation for 3 forms (validation)
  ✓ Create synthetic test data
  ✓ Write Mock/contract tests
  → Deliverable: Golden Dataset v1.0 + Unit tests passing
```

**Phase 1: Baseline Measurement (Gemini)**

```
Week 2:
  ⚠ REQUIRES APPROVAL: D-01, D-02 confirmed
  ⚠ Gemini Free Tier quota available
  
  Steps:
  1. Verify API key active
  2. Test 1 form manually (smoke test)
  3. Run Baseline measurement (15 forms)
  4. Generate Baseline Report
  5. Identify known failures
  
  → Deliverable: Baseline Report + Known failure list
```

**Phase 2: Hybrid Engine Development (Parallel work)**

```
Week 3-4:
  [Separate team implements Hybrid Engine]
  
  Meanwhile:
  - Write regression test cases
  - Prepare comparison test scripts
  - Design E2E test scenarios
  
  → Deliverable: Regression test suite (using Mock)
```

**Phase 3: Hybrid Comparison (Gemini)**

```
Week 5:
  ⚠ REQUIRES APPROVAL: Hybrid engine ready
  ⚠ Gemini Free Tier quota available
  
  Steps:
  1. Run Hybrid engine on Golden Dataset (15 forms)
  2. Generate Comparison Report
  3. Calculate Net Benefit
  4. Decision: Proceed with Hybrid or revert to Baseline
  
  → Deliverable: Comparison Report + Go/No-Go decision
```

**Phase 4: Regression & E2E (Mixed)**

```
Week 6:
  - Run regression suite (Mock + selective Gemini)
  - Execute E2E tests (Upload → Export)
  - Validate Excel integrity
  - Spot-check on NEW forms (not in Golden Dataset)
  
  → Deliverable: Final Test Report + Production readiness assessment
```

### 8.2 Quota Management Strategy

**Problem:** Gemini Free Tier limited to ~20-500 requests/day (model dependent).

**Solution:**

1. **Spread tests over multiple days:**
   - Day 1: Baseline (15 requests)
   - Day 2-3: Rest
   - Day 4: Hybrid (15 requests)
   - Day 5-6: Rest
   - Day 7: Regression spot-checks (10 requests)

2. **Cache results:**
   - Store Baseline results for reuse
   - Don't re-run Baseline unnecessarily

3. **Use Mocks for development:**
   - Most tests use Mock responses
   - Live Gemini only for accuracy measurement

4. **Monitor quota:**
   - Track requests/day
   - Alert if approaching limit
   - Automatic throttling

**Worst Case:** If quota exhausted, wait 24 hours.

---

## 9. Success Criteria & Acceptance Gates

### 9.1 MVP Acceptance Criteria

**המערכת עוברת MVP רק אם:**

| Criterion | Target | Measured | Status |
|-----------|--------|----------|--------|
| **Overall Field Accuracy** | > 70% | ?% | ? |
| **Unsafe Acceptance Rate** | < 5% | ?% | ? |
| **Handwritten Hebrew Safety** | 0 hallucinations | ? | ? |
| **Multi-Value Recall** | > 90% | ?% | ? |
| **Export Integrity** | 100% checks pass | ? | ? |
| **Regression Tests** | 0 failures | ? | ? |

**Hard Gates:**

- **Unsafe Acceptance < 5%** (NON-NEGOTIABLE)
- **Handwritten safety** (NO invented names)
- **Export integrity** (NO data corruption)

**Soft Gates:**

- Overall accuracy (can be lower if safe)
- Review burden (can be higher if safe)

### 9.2 Hybrid Engine Acceptance

**המנוע ההיברידי מתקבל רק אם:**

| Criterion | Target | Status |
|-----------|--------|--------|
| **Net Benefit** | > 10% improvement | ? |
| **No Regressions** | 0 degraded fields | ? |
| **Unsafe Acceptance** | < Baseline OR ≤ 2% | ? |
| **OCR Contribution** | > 5% fields improved | ? |

**Decision Matrix:**

```
IF Net Benefit > 10% AND Unsafe < 2% → ✓ PROCEED
IF Net Benefit < 5% → ✗ ABORT (not worth complexity)
IF Regressions detected → ⚠ FIX FIRST
IF Unsafe > Baseline → ✗ ABORT (safety degraded)
```

---

## 10. Reporting & Documentation

### 10.1 Required Reports

**1. Baseline Measurement Report**

- File: `docs/testing/baseline_report_YYYY-MM-DD.md`
- Content: All metrics from Section 3.4
- Audience: Project owner, technical team

**2. Hybrid Comparison Report**

- File: `docs/testing/hybrid_comparison_YYYY-MM-DD.md`
- Content: All metrics from Section 4.4
- Audience: Project owner, decision-makers

**3. Regression Test Report**

- File: `docs/testing/regression_report_YYYY-MM-DD.md`
- Content: Pass/fail status per test case
- Audience: Engineering team

**4. Final Test Summary**

- File: `docs/testing/FINAL_TEST_SUMMARY.md`
- Content: Aggregated results, recommendations, production readiness
- Audience: All stakeholders

### 10.2 Test Data Archive

**Structure:**

```
docs/testing/
  baseline_report_2026-10-19.md
  hybrid_comparison_2026-10-26.md
  regression_report_2026-11-02.md
  FINAL_TEST_SUMMARY.md
  
  data/
    golden_dataset_v1.0_annotations.json  # Ground Truth (encrypted)
    baseline_results.json                 # Gemini outputs
    hybrid_results.json                   # Hybrid outputs
    regression_history.json               # Historical test runs
    
  artifacts/
    confusion_matrices/
    error_examples/
    excel_samples/
```

### 10.3 Transparency Requirements

**Every test report MUST include:**

1. **Date and context** (model version, prompt version, dataset version)
2. **Raw numbers** (not just percentages)
3. **Failure examples** (concrete cases, not generalities)
4. **Known limitations** (what was NOT tested)
5. **Confidence intervals** (especially for small datasets)
6. **Approval status** (who authorized Live Gemini tests)

**Anti-Pattern:**

```
❌ "Accuracy: 95% — System works great!"
✓ "Accuracy: 72% (76/105 fields correct, 15-form dataset).
   Known failures: Handwritten Hebrew (0% accuracy).
   Unsafe acceptances: 3 fields (2.8%).
   Recommendation: Add OCR for numeric fields."
```

---

## 11. Risks & Mitigation

### 11.1 Test Execution Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|-----------|
| **Gemini quota exhausted mid-test** | High | Medium | Spread tests over days, cache results |
| **Ground Truth errors** | High | Medium | Dual annotation, expert review |
| **Small dataset (15 forms)** | Medium | High | Acknowledge limitations, expand if possible |
| **Prompt changes invalidate results** | Medium | Medium | Version all prompts, re-run on changes |
| **Model upgrade breaks everything** | High | Low | Pin model version, test upgrades separately |
| **Time pressure → skip tests** | Critical | High | **Non-negotiable: No prod without tests** |

### 11.2 Safety Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **False Acceptance (silent errors)** | **CRITICAL** | Focus on Unsafe Acceptance metric, zero tolerance |
| **Hallucination (invented names)** | **CRITICAL** | Regression test, uncertainty detection |
| **Data loss (missing centrals)** | High | Multi-value recall metric, alert on count mismatch |
| **Export corruption (wrong patient)** | **CRITICAL** | E2E tests, Excel validation, manual spot-checks |

### 11.3 Ethical Risks

| Risk | Mitigation |
|------|-----------|
| **Unauthorized Gemini use (real PII)** | Explicit approval gate (D-01, D-02) |
| **Ground Truth leakage to Git** | `.gitignore`, pre-commit hooks |
| **Over-reliance on small dataset** | Transparent reporting, confidence intervals |
| **Claiming accuracy without proof** | No marketing before measurement |

---

## 12. Future Enhancements (Out of Scope)

**Not included in MVP test plan:**

1. **A/B Testing:** Multiple prompt versions in parallel
2. **Active Learning:** Iterative re-training with corrections
3. **Adversarial Testing:** Intentionally malicious inputs
4. **Performance Testing:** Load/stress tests (1000+ forms)
5. **Cross-Model Comparison:** GPT-4 Vision vs Gemini vs Claude
6. **Fine-Tuning Evaluation:** Custom-trained model vs base
7. **Longitudinal Testing:** Accuracy over time, model drift
8. **User Acceptance Testing:** Real lab staff feedback
9. **Accessibility Testing:** Screen readers, keyboard navigation
10. **Localization Testing:** English vs Hebrew UI

**When to add:**

- After MVP validation proves concept
- When production deployment planned
- When budget allows (Paid Tier)

---

## 13. Summary & Next Steps

### 13.1 Deliverables from This Plan

**Artifacts to Create:**

1. ✓ **This document** (AI_QUALITY_TEST_PLAN.md)
2. ⏳ Golden Dataset v1.0 (15 forms + annotations)
3. ⏳ Baseline Measurement Report
4. ⏳ Hybrid Comparison Report
5. ⏳ Regression Test Suite (code)
6. ⏳ Final Test Summary

**Timeline (Estimated):**

- Week 1: Golden Dataset preparation
- Week 2: Baseline measurement
- Week 5: Hybrid comparison
- Week 6: Regression + Final report

### 13.2 Prerequisites for Execution

**Before ANY Live testing:**

- [x] D-01 approved (sample forms for Gemini)
- [x] D-02 approved (Free Tier only, 0 ₪)
- [ ] Golden Dataset v1.0 ready
- [ ] Ground Truth validated (dual annotation)
- [ ] Test scripts prepared (dry-run with Mock)
- [ ] Quota budget confirmed (requests/day)

### 13.3 Decision Points

**Go/No-Go Gates:**

1. **After Baseline:** Continue with Hybrid or abort if accuracy < 50%?
2. **After Hybrid Comparison:** Deploy Hybrid or stick with Baseline?
3. **After Regression:** Production-ready or need more work?

**Each gate requires explicit decision from project owner.**

---

## 14. Appendix

### A. Glossary

- **Ground Truth:** ערכי אמת ידועים, מתויגים ידנית
- **Baseline:** מדידת ביצועים ראשונית (Gemini בלבד)
- **Hybrid Engine:** שילוב Gemini + OCR + Verification
- **False Acceptance:** ערך שגוי שלא סומן לבדיקה (מסוכן)
- **Unsafe Acceptance:** כנ"ל (מונח נרדף)
- **Hallucination:** המצאת ערך שלא קיים במסמך
- **Review Burden:** אחוז שדות הדורשים בדיקה אנושית
- **Net Benefit:** שיפור נטו (תיקונים פחות נסיגות)
- **Regression:** נסיגה (דבר שעבד ונשבר)

### B. References

**Internal Documents:**

- `PLAN.md` — תכנון כללי של המערכת
- `DECISIONS.md` — החלטות מחייבות
- `tasks.md` — רשימת משימות MVP
- `domain/models.py` — מבני נתונים
- `gemini_adapter.py` — מימוש Gemini API

**External Resources:**

- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- Industry standards for assisted data entry (15-30% review rate)
- Medical AI accuracy benchmarks (varied by task)

### C. Contact

**Questions about this test plan:**

- Planning phase: Contact QA Architect
- Execution phase: Coordinate with project owner
- Approval needed: Consult DECISIONS.md (D-01, D-02)

---

**Document Status:** ✅ PLANNING COMPLETE — Ready for review

**Next Action:** Review with project owner → Approve Golden Dataset creation → Begin execution

**Last Updated:** 2026-10-19

