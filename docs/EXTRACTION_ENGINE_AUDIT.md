# Extraction Engine Audit — Current State Analysis
**Date:** 2026-10-14  
**Auditor:** Senior AI Engineer / Computer Vision Engineer / Software Architect  
**Purpose:** Deep analysis of current extraction pipeline before Hybrid Engine upgrade

---

## Executive Summary

**Current Architecture:** Single-pass Gemini Vision extraction with validation layer  
**Strengths:** Conservative prompt (v2.0), quota management, validation separation  
**Gaps:** No preprocessing, no OCR, no field-level verification, no focused retry  
**Readiness for Hybrid Upgrade:** ✅ Good foundation, modular design, clear extension points

---

## 1. Component Analysis

### 1.1 GeminiExtractor (`gemini_adapter.py`)

**Architecture:**
- Clean Extractor interface implementation
- Two prompt versions (v1.0, v2.0 available via config)
- Structured output via Pydantic schema
- Sender normalization integration
- Proper error handling and timeout logic

**Current Prompt (v2.0) — Analysis:**

✅ **Strengths:**
- Zero-guess policy: "NEVER guess, invent, autocomplete"
- Field-specific extraction rules for all 7 fields
- Explicit sender closed list (health funds + hospitals)
- Handwritten name caution built-in
- Clear null vs [] semantics
- Validation expectations separated from extraction

✅ **Good Practices:**
- Conservative uncertain → null (not "best guess + warning")
- Distinction between central_numbers, commitment_numbers, patient_id
- Multi-value support with empty list [] vs null
- Evidence requirement: "Must have explicit label or context"
- No auto-completion of partial numbers

⚠️ **Gaps:**
1. **No image quality assessment** — doesn't mention blur, rotation, poor contrast
2. **No confidence scoring** per field — only binary null/value + warnings array
3. **No bbox extraction** — cannot guide focused retry
4. **No OCR cross-reference instructions** — will need hybrid prompt
5. **Barcode handling implicit** — doesn't explicitly say "read barcode if present"
6. **Checksum validation missing** — ID checksum checked post-extraction, not during

🔍 **Improvement Opportunities:**
- Add image quality check instruction: "If image is rotated/blurred/low-contrast, note in warnings"
- Add per-field confidence scoring (0.0-1.0) for hybrid verification
- Request bbox when available: "If possible, provide bounding box [x,y,w,h] for each extracted value"
- Add barcode instruction: "Read barcodes using built-in capability if visible"
- Add cross-verification hint: "If printed text and handwritten text disagree, mark as conflicting"

---

### 1.2 DocumentRenderer (`renderer.py`)

**Current Capabilities:**
- ✅ PDF to PNG conversion (PyMuPDF/fitz)
- ✅ DPI control (default 300)
- ✅ Max dimension limiting (3000px)
- ✅ Aspect ratio preservation
- ✅ Image loading with format validation

**Rotation Detection:**
- ⚠️ **Primitive heuristic only** (aspect ratio > 2.0 → 90°, < 0.5 → 270°)
- ❌ **No actual rotation applied** — detection returns value but not used
- ❌ **TODO comment:** "Implement proper orientation detection if needed"

**Missing Preprocessing:**
- ❌ No deskew (skewed scan correction)
- ❌ No contrast enhancement
- ❌ No noise reduction
- ❌ No adaptive thresholding
- ❌ No comparison of preprocessing variants

🔍 **Critical for Hybrid Upgrade:**
This is the PRIMARY extension point for image preprocessing.

---

### 1.3 ValidationService (`validator.py`)

**Current Validation Rules:**
- ✅ Israeli ID checksum (Luhn-like algorithm) — correct implementation
- ✅ Date format validation (ISO + Israeli DD/MM/YYYY)
- ✅ Future date detection
- ✅ Required field checking
- ✅ Conflict detection (multiple different values)

**Architecture:**
- ✅ No auto-fix (flags only, never corrects)
- ✅ Returns ValidationIssue list
- ✅ Severity levels (error, warning)
- ✅ Suggested fixes as hints (not applied)

**Validation Issues Properly Attached:**
- ✅ Updates field.extraction_state (invalid, conflicting)
- ✅ Appends to field.validation_issues list
- ✅ Preserves raw_value unchanged

⚠️ **Gaps for Hybrid:**
1. **No cross-field verification** — e.g., "ID checksum fails BUT name matches sticker"
2. **No OCR vs Gemini comparison** — will need new validator for hybrid verification
3. **No sender list validation against closed list** — assumes normalization handles it
4. **No central_number vs commitment_number disambiguation check**
5. **No bbox-based verification** — cannot check "is this ID near patient name area?"

🔍 **Extension Needed:**
New `HybridVerifier` class for field-level cross-source validation.

---

### 1.4 QuotaManager (`quota_manager.py`)

**Features:**
- ✅ Circuit breaker pattern
- ✅ Daily quota vs rate limit distinction
- ✅ RetryInfo parsing from Google errors
- ✅ Thread-safe with Lock
- ✅ Automatic reset at midnight UTC
- ✅ Manual clear capability

**Integration:**
- ✅ Used in BackgroundProcessor
- ✅ Properly handles 429, quota_exceeded, resource_exhausted
- ✅ Logs clear warnings with retry time

**Readiness for Hybrid:**
- ✅ Already handles Gemini quota
- ✅ Can track multiple models (but currently only one)
- ⚠️ **Will need extension** for focused retry quota tracking (separate counter)

---

### 1.5 BackgroundProcessor (`background.py`)

**Processing Pipeline:**
1. Render PDF/image to PNG
2. Extract with Gemini (with retry on transient errors)
3. Map to TestRecord
4. Detect uncertainty
5. Validate
6. Create CommitmentRecords
7. Save to JSON storage

**Error Handling:**
- ✅ Per-document isolation (one failure doesn't cancel batch)
- ✅ Transient error retry (max 2 retries, 5s delay)
- ✅ Timeout per page (90s)
- ✅ Quota exhaustion detection
- ✅ Demo mode fallback (MockExtractor)

**Retry Logic:**
- ✅ Retries transient errors (network, timeout, 5xx)
- ❌ **No focused retry** on uncertain fields
- ❌ **No preprocessing variants** tried on failure
- ❌ **No multi-pass extraction** (single Gemini call per page)

**Extension Points:**
- Easy to insert preprocessing before extraction
- Easy to add OCR step in parallel
- Easy to add field-level retry loop
- ⚠️ Will need refactoring for hybrid pipeline orchestration

---

### 1.6 Domain Models (`models.py`)

**FieldValue Architecture:**
- ✅ Triple value tracking: raw / normalized / reviewed
- ✅ ExtractionState: found, uncertain, missing, conflicting, invalid
- ✅ ReviewState: pending, needs_review, human_verified, rejected
- ✅ ValidationIssue list attached to field
- ✅ EvidenceRef for bbox (structure exists but unused)
- ✅ extractor_id and extraction_attempt_id for provenance

**Critical Feature:**
- ✅ `reviewed_value` **can be empty string** (explicit "confirmed empty")
- ✅ Separation between AI extraction and human review
- ✅ Never overwrites raw_value

**Missing for Hybrid:**
- ❌ **No confidence score** per field
- ❌ **No OCR value storage** (only raw/normalized/reviewed)
- ❌ **No preprocessing variant metadata** (which preprocessing produced this?)
- ❌ **No focused retry tracking** (how many retry attempts?)
- ❌ **EvidenceRef.bbox unused** — Gemini doesn't return it currently

🔍 **Schema Extension Needed:**
```python
class FieldValue:
    # Existing fields...
    
    # NEW for Hybrid:
    ocr_value: Optional[T] = None  # OCR extracted value
    gemini_confidence: Optional[float] = None  # 0.0-1.0
    ocr_confidence: Optional[float] = None  # 0.0-1.0
    verification_status: str = "unverified"  # "verified" | "conflicting" | "unverified"
    preprocessing_method: Optional[str] = None  # "original" | "deskewed" | "enhanced"
    retry_count: int = 0  # How many focused retries
```

---

## 2. Critical Gaps for Hybrid Extraction

### 2.1 Image Preprocessing — MISSING

**Currently:** Raw image → Gemini (no preprocessing)

**Needed:**
1. **Deskew** — fix rotated/skewed scans
2. **Contrast Enhancement** — CLAHE for low-contrast forms
3. **Noise Reduction** — bilateral filter for speckled scans
4. **Adaptive Thresholding** — binarization for faded text
5. **Variant Comparison** — try original + 2-3 preprocessed versions

**Implementation Location:**
- Extend `DocumentRenderer` with new `ImagePreprocessor` class
- Add config flags: `enable_deskew`, `enable_contrast_enhancement`, etc.
- Return list of image variants: `[(image_bytes, method_name), ...]`

---

### 2.2 OCR Layer — MISSING

**Currently:** No local OCR

**Needed:**
1. **Tesseract OCR** with Hebrew + English
2. **Per-field confidence** from OCR
3. **Text block detection** for field isolation
4. **Barcode reading** (if Tesseract supports, or use pyzbar)

**Use Cases:**
- Cross-verify Gemini extraction (especially numbers)
- Fallback for printed text if Gemini uncertain
- **Not authoritative for handwriting** (OCR weak on Hebrew handwriting)

**Implementation:**
- New `OCRExtractor` class implementing `Extractor` interface
- Returns same `ExtractionResult` structure
- Runs in parallel with Gemini (not sequential dependency)

---

### 2.3 Field-Level Verification — MISSING

**Currently:** Only post-extraction validation (ID checksum, date format)

**Needed:**
1. **Gemini vs OCR comparison** — if both agree → high confidence
2. **Checksum verification during extraction** — ID must pass checksum
3. **Sender list validation** — must be from closed list (done via normalizer, but not enforced)
4. **Number type disambiguation** — central vs commitment vs patient ID
5. **Conflict detection** — if Gemini says X but OCR says Y → needs_review

**Implementation:**
- New `HybridVerifier` class
- Takes Gemini result + OCR result → produces verified FieldValue
- Sets `verification_status` and `gemini_confidence` / `ocr_confidence`

---

### 2.4 Focused Retry — MISSING

**Currently:** Single-pass extraction only

**Needed:**
1. **Trigger:** Field marked uncertain or missing
2. **Bbox detection:** Crop region around suspected field location
3. **Focused prompt:** "Extract only patient_id_number from this cropped image"
4. **Retry limit:** Max 2-3 focused retries per field
5. **Quota tracking:** Separate counter (don't exhaust daily quota on retries)
6. **Provenance:** Store retry_count, which attempt succeeded

**Implementation:**
- New `FocusedRetryOrchestrator` class
- Bbox extraction: Use OCR block detection or heuristic (e.g., "patient ID in top-left")
- Gemini call with cropped image + focused prompt
- Update field only if confidence improves

---

## 3. Architecture for Hybrid Engine

### 3.1 Proposed Pipeline

```
Input: Raw Image
│
├─ Step 1: Image Preprocessing (NEW)
│   ├─ Original
│   ├─ Deskewed (OpenCV)
│   ├─ Contrast Enhanced (CLAHE)
│   └─ Denoised (bilateral filter)
│
├─ Step 2: Parallel Extraction
│   ├─ Gemini Vision (primary)
│   └─ Tesseract OCR (verification) — NEW
│
├─ Step 3: Hybrid Verification (NEW)
│   ├─ Compare Gemini vs OCR
│   ├─ Run deterministic checks (ID checksum, date format)
│   ├─ Set verification_status per field
│   └─ Flag conflicts for human review
│
├─ Step 4: Focused Retry (NEW) — only for uncertain/missing fields
│   ├─ Detect bbox (OCR blocks or heuristic)
│   ├─ Crop region
│   ├─ Gemini focused call (max 2-3 retries)
│   └─ Update field if confidence improves
│
└─ Output: TestRecord with verified fields
```

---

### 3.2 Configuration Flags (Feature Toggles)

```python
class HybridConfig:
    # Image Preprocessing
    enable_preprocessing: bool = True
    enable_deskew: bool = True
    enable_contrast_enhancement: bool = True
    enable_noise_reduction: bool = True
    enable_adaptive_thresholding: bool = False  # Use carefully
    
    # OCR
    enable_ocr: bool = True
    ocr_languages: list[str] = ["heb", "eng"]
    ocr_confidence_threshold: float = 0.7
    
    # Hybrid Verification
    enable_hybrid_verification: bool = True
    require_agreement_for_high_confidence: bool = True  # Gemini AND OCR agree
    
    # Focused Retry
    enable_focused_retry: bool = True
    max_focused_retries: int = 2
    focused_retry_quota_limit: int = 50  # Per day
    
    # A/B Testing
    prompt_version: str = "2.0"  # "1.0" or "2.0"
    preprocessing_profile: str = "default"  # "none" | "light" | "default" | "aggressive"
```

---

### 3.3 Modular Design Principles

**✅ Keep:**
1. Extractor interface — OCR can implement it
2. Separate validation layer — don't mix extraction and validation
3. Triple value tracking (raw/normalized/reviewed) — extend with ocr_value
4. QuotaManager — extend for focused retry tracking
5. Demo mode — add MockOCRExtractor

**🆕 Add:**
1. `ImagePreprocessor` class (in documents module)
2. `OCRExtractor` class (in extraction module)
3. `HybridVerifier` class (in validation module, or new hybrid module)
4. `FocusedRetryOrchestrator` class (in extraction module)
5. `HybridPipeline` orchestrator (replaces direct Gemini call in BackgroundProcessor)

**❌ Avoid:**
1. Merging extraction and validation logic
2. Hardcoding preprocessing steps (use config)
3. Auto-choosing between Gemini and OCR (flag conflicts, let human decide)
4. Complex multi-model ensemble (not needed for MVP)

---

## 4. Identified Bugs and Risks

### 4.1 Rotation Detection Not Applied

**Location:** `renderer.py:detect_rotation()`  
**Issue:** Method returns rotation angle (0, 90, 180, 270) but result is never used  
**Impact:** Rotated scans sent to Gemini as-is  
**Fix:** Apply rotation in `pdf_to_images()` or `load_image()` after detection

---

### 4.2 EvidenceRef.bbox Unused

**Location:** `models.py:EvidenceRef`  
**Issue:** Bbox structure exists but Gemini doesn't return it, and it's never populated  
**Impact:** Cannot do focused retry (no bbox to crop)  
**Fix:** Either request bbox in prompt (may not work reliably) OR use OCR block detection to populate

---

### 4.3 Sender Normalization Silent Mismatch

**Location:** `gemini_adapter.py:extract()` calls `SenderNormalizer`  
**Issue:** If no match found, `canonical_sender` = None, warning added, but not marked as needs_review  
**Impact:** Export may proceed with sender=None  
**Fix:** If `is_confident=False`, set `field.review_state = ReviewState.needs_review`

---

### 4.4 No Focused Retry Quota Limit

**Location:** Not implemented yet  
**Risk:** If focused retry enabled, could exhaust daily quota on retry loops  
**Mitigation:** Separate quota counter for focused retries (e.g., max 50/day)

---

### 4.5 Demo Mode Inconsistency

**Location:** `background.py:BackgroundProcessor.__init__()`  
**Issue:** MockExtractor used in demo mode, but prompt_version not passed  
**Impact:** Cannot A/B test prompts in demo mode  
**Fix:** Pass `prompt_version` to MockExtractor (even if ignored)

---

## 5. Compatibility with Existing System

### 5.1 API Contracts — Safe ✅

**Extractor Interface:**
- Returns `ExtractionResult` with `fields`, `warnings`, `model_id`, etc.
- OCRExtractor and FocusedRetryOrchestrator will return same structure
- ✅ No breaking changes

**FieldValue Structure:**
- Adding optional fields (`ocr_value`, `gemini_confidence`, etc.) is backward-compatible
- Existing code ignores unknown fields
- ✅ No migration needed

**BackgroundProcessor:**
- Internal refactoring only (replace single Gemini call with HybridPipeline)
- Still returns same TestRecord structure
- ✅ No API changes

---

### 5.2 ReviewScreenNew Integration — Safe ✅

**Frontend expects:**
- `extraction_state`: found, uncertain, missing, conflicting, invalid
- `review_state`: pending, needs_review, human_verified
- `validation_issues` array
- `raw_value`, `normalized_value`, `reviewed_value`

**Hybrid additions:**
- `ocr_value`, `gemini_confidence`, `ocr_confidence` — **optional**, frontend can ignore
- `verification_status` — **optional**, can be used for UI badging (e.g., "✓ Verified by OCR")
- All existing review logic works unchanged

**No Frontend Changes Required** — but optional enhancements possible:
- Show OCR value in tooltip: "OCR also found: X"
- Show confidence score: "Gemini confidence: 85%"
- Show verification badge: "✓ Cross-verified" if Gemini and OCR agree

---

### 5.3 Export Logic — Safe ✅

**Excel Export Priority:**
1. `reviewed_value` (human correction, even if empty string)
2. `normalized_value` (cleaned by validator)
3. `raw_value` (original extraction)

**Hybrid doesn't change this:**
- `ocr_value` is for verification only, not exported directly
- Export still uses `reviewed_value` > `normalized_value` > `raw_value`
- ✅ No export logic changes

---

## 6. Testing Strategy for Hybrid Upgrade

### 6.1 Unit Tests Needed

**Image Preprocessing:**
- `test_deskew()` — verify skewed image straightened
- `test_contrast_enhancement()` — verify low-contrast improved
- `test_noise_reduction()` — verify speckled image cleaned
- `test_preprocessing_preserves_original()` — original not modified

**OCR Extraction:**
- `test_ocr_printed_hebrew()` — extract printed Hebrew text
- `test_ocr_printed_numbers()` — extract numbers with leading zeros
- `test_ocr_confidence_scoring()` — verify confidence 0.0-1.0
- `test_ocr_mock()` — MockOCRExtractor for tests

**Hybrid Verification:**
- `test_gemini_ocr_agreement()` — both return same value → high confidence
- `test_gemini_ocr_disagreement()` — conflict flagged for review
- `test_checksum_during_verification()` — invalid ID rejected even if both agree
- `test_sender_closed_list_enforcement()` — unknown sender → needs_review

**Focused Retry:**
- `test_focused_retry_triggers_on_uncertain()` — uncertain field triggers retry
- `test_focused_retry_quota_limit()` — stops after max retries
- `test_focused_retry_updates_field()` — success updates field with provenance
- `test_focused_retry_mock()` — no real Gemini calls

---

### 6.2 Integration Tests Needed

**End-to-End Hybrid Pipeline:**
- `test_hybrid_pipeline_all_features_enabled()` — full flow with all features
- `test_hybrid_pipeline_preprocessing_only()` — preprocessing but no OCR
- `test_hybrid_pipeline_ocr_only()` — OCR but no preprocessing
- `test_hybrid_pipeline_demo_mode()` — mock extractors
- `test_hybrid_pipeline_quota_exhaustion()` — graceful degradation

**Known Edge Cases:**
- `test_handwritten_name_not_invented()` — regression test (TASK-020)
- `test_id_checksum_invalid()` — ID with bad checksum rejected
- `test_multiple_central_numbers()` — preserve all values
- `test_rotated_image()` — rotation detection and correction
- `test_blurry_image()` — preprocessing improves or flags as needs_review

---

### 6.3 A/B Evaluation Framework

**Goal:** Measure improvement vs baseline

**Baseline:** Current Gemini v2.0 prompt, no preprocessing, no OCR

**Variants to Test:**
1. **Gemini v2.0 + Preprocessing**
2. **Gemini v2.0 + OCR + Verification**
3. **Gemini v2.0 + Preprocessing + OCR + Verification**
4. **Gemini v2.0 + Preprocessing + OCR + Verification + Focused Retry**

**Metrics:**
- **Accuracy:** % fields correct vs ground truth
- **Completeness:** % fields extracted (not null)
- **Precision:** % extracted fields that are correct
- **Recall:** % ground truth fields found
- **needs_review Rate:** % fields flagged for human review
- **API Calls:** Total Gemini calls (baseline + focused retries)
- **Processing Time:** Average time per document

**Evaluation:**
- Run all variants on Golden Dataset (12-14 forms)
- Compare metrics vs baseline
- Document which features contribute most to accuracy
- Determine recommended default config

---

## 7. Gemini API Call Estimation

### 7.1 Current Baseline (No Hybrid)

**Per Document:**
- 1 Gemini call per page
- Single-page PDF: 1 call
- 3-page PDF: 3 calls

**Batch of 10 documents (15 pages total):**
- 15 Gemini calls

---

### 7.2 With Preprocessing Only

**No Additional API Calls**
- Preprocessing is local (OpenCV)
- Gemini still called once per page
- Cost: 0 additional calls

---

### 7.3 With OCR + Verification

**No Additional API Calls**
- OCR is local (Tesseract)
- Gemini still called once per page
- Cost: 0 additional calls

---

### 7.4 With Focused Retry (Worst Case)

**Assumptions:**
- 30% of fields uncertain/missing (realistic for difficult forms)
- 7 fields per form
- 2.1 uncertain fields per form on average
- Max 2 focused retries per uncertain field
- 50% of focused retries succeed on first attempt (1 call), 50% need 2nd (2 calls)
- Average: 1.5 calls per uncertain field

**Per Document:**
- Initial extraction: 1 call (baseline)
- Focused retries: 2.1 fields × 1.5 calls = 3.15 calls
- **Total: ~4 calls per page** (1 + 3.15)

**Batch of 10 documents (15 pages):**
- Baseline: 15 calls
- With focused retry: 15 × 4 = 60 calls
- **4x increase** (worst case)

**Mitigation:**
- Daily focused retry quota limit: 50 calls/day
- Stops retrying after quota exhausted
- Falls back to needs_review flagging

**Best Case (Good Quality Forms):**
- 10% of fields uncertain: 0.7 fields × 1.5 = 1.05 calls
- **Total: ~2 calls per page**
- **2x increase** (acceptable)

---

### 7.5 Recommended Strategy

**Phase 1: Preprocessing + OCR + Verification**
- **Cost:** 0 additional API calls
- **Benefit:** Better accuracy from preprocessed images, cross-verification catches errors
- **Deploy immediately**

**Phase 2: Focused Retry (with strict quota)**
- **Cost:** 2-4x API calls (depends on form quality)
- **Benefit:** Recover uncertain/missing fields
- **Deploy with:** Daily quota limit (50 focused retries/day), configurable per-field thresholds

---

## 8. Implementation Roadmap

### Phase 1: Image Preprocessing (0 API calls, Pure Local)

**Goal:** Improve image quality before Gemini  
**Time:** 1-2 days  
**Risk:** Low

**Tasks:**
1. Create `ImagePreprocessor` class with deskew, contrast, denoise
2. Add config flags for each preprocessing method
3. Extend `DocumentRenderer` to return preprocessing variants
4. Update `BackgroundProcessor` to use preprocessed images
5. Unit tests for each preprocessing method
6. A/B test preprocessed vs original on Golden Dataset

---

### Phase 2: OCR Layer (0 API calls, Pure Local)

**Goal:** Add local OCR for verification  
**Time:** 2-3 days  
**Risk:** Low (OCR optional, doesn't break existing)

**Tasks:**
1. Install Tesseract with Hebrew language pack
2. Create `OCRExtractor` implementing `Extractor` interface
3. Add `ocr_value` and `ocr_confidence` to `FieldValue`
4. Update `BackgroundProcessor` to run OCR in parallel with Gemini
5. Unit tests for OCR extraction
6. Compare OCR vs Gemini on printed text (Golden Dataset)

---

### Phase 3: Hybrid Verification (0 API calls, Pure Local)

**Goal:** Cross-verify Gemini vs OCR, detect conflicts  
**Time:** 2-3 days  
**Risk:** Medium (logic complexity)

**Tasks:**
1. Create `HybridVerifier` class
2. Implement field-level comparison (Gemini vs OCR)
3. Add `verification_status` to `FieldValue`
4. Update validation logic to use hybrid verification
5. Flag conflicts as `needs_review`
6. Unit tests for all verification scenarios
7. Measure reduction in false positives (Golden Dataset)

---

### Phase 4: Focused Retry (+API calls, Gemini)

**Goal:** Retry uncertain/missing fields with cropped regions  
**Time:** 3-4 days  
**Risk:** High (quota management, complexity)

**Tasks:**
1. Create `FocusedRetryOrchestrator` class
2. Implement bbox detection (OCR blocks or heuristic)
3. Create focused prompts per field
4. Add focused retry quota tracking to `QuotaManager`
5. Update `BackgroundProcessor` to orchestrate retries
6. Add `retry_count` and `preprocessing_method` to `FieldValue`
7. Unit tests with MockExtractor (no real API calls)
8. Integration test with real Gemini on synthetic data ONLY
9. **DO NOT test on real medical data without approval**
10. Measure accuracy improvement vs API cost trade-off

---

### Phase 5: A/B Evaluation & Tuning

**Goal:** Measure hybrid vs baseline, optimize config  
**Time:** 2 days  
**Risk:** Low (evaluation only)

**Tasks:**
1. Run all variants on Golden Dataset (verified ground truth)
2. Compare metrics: accuracy, completeness, API calls, time
3. Document which features provide most value
4. Recommend default config
5. Create deployment guide

---

**Total Time Estimate:** 10-14 days  
**Total Cost:** 0 ₪ (development), 0 ₪ (API — synthetic data only with approval)

---

## 9. Decision Points Before Implementation

**❓ DECISION-001:** Approve focused retry with API calls?
- **If YES:** Implement Phase 4 with strict quota limits
- **If NO:** Skip Phase 4, deploy Phases 1-3 only (0 API calls)

**❓ DECISION-002:** Which preprocessing methods to enable by default?
- **Recommended:** Deskew + Contrast Enhancement (conservative)
- **Optional:** Noise Reduction (test first)
- **Risky:** Adaptive Thresholding (may harm handwriting)

**❓ DECISION-003:** OCR as verification only or fallback?
- **Verification only (recommended):** OCR never overwrites Gemini unless human approves
- **Fallback:** If Gemini uncertain AND OCR confident → use OCR value
  - Risk: OCR may hallucinate on handwriting

**❓ DECISION-004:** Bbox detection method?
- **Option A:** Use OCR text blocks (Tesseract provides them)
- **Option B:** Heuristic based on field name (e.g., "patient ID in top-left 25%")
- **Option C:** Request bbox from Gemini in prompt (may not work)
- **Recommended:** Option A (OCR blocks)

**❓ DECISION-005:** Prompt upgrade for hybrid?
- **Option A:** Keep v2.0 as-is, add OCR instructions separately
- **Option B:** Create v3.0 hybrid prompt with OCR cross-reference hints
- **Recommended:** Option B (v3.0)

---

## 10. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Preprocessing degrades handwriting | Medium | High | Make all preprocessing optional, A/B test |
| OCR hallucinations on Hebrew handwriting | High | Medium | Never use OCR alone for handwriting, verification only |
| Focused retry exhausts quota | Medium | High | Strict daily limit (50), per-field threshold |
| Bbox detection unreliable | Medium | Medium | Fall back to whole-image retry if bbox fails |
| Increased complexity → bugs | Medium | Medium | Comprehensive unit tests, feature flags for rollback |
| Performance degradation | Low | Medium | Profile preprocessing time, parallelize where possible |
| Config sprawl | Medium | Low | Document recommended profiles ("light", "default", "aggressive") |

---

## 11. Recommendation

**✅ PROCEED WITH HYBRID UPGRADE**

**Rationale:**
1. Current architecture is solid and extensible
2. Preprocessing + OCR add **0 API calls** (pure local improvement)
3. Focused retry is optional (can deploy Phases 1-3 without it)
4. Modular design allows feature flags for A/B testing
5. No breaking changes to API or Frontend
6. Clear extension points identified

**Proposed Next Steps:**
1. Get approval for focused retry decision (DECISION-001)
2. Implement Phase 1 (Preprocessing) — 1-2 days, 0 API calls
3. Verify preprocessing improves accuracy on Golden Dataset
4. If successful, proceed to Phase 2 (OCR)
5. Pause for evaluation before Phase 4 (Focused Retry with API calls)

**Estimated Total Improvement (based on industry benchmarks):**
- Preprocessing alone: +5-10% accuracy on low-quality scans
- OCR verification: +10-15% precision (fewer false positives)
- Focused retry: +10-20% completeness (recover missing fields)
- **Combined: +20-35% overall improvement** (to be measured on Golden Dataset)

**Cost:**
- Phases 1-3: **0 ₪** (pure local)
- Phase 4: **2-4x API calls** (mitigated by quota limits)

---

**END OF AUDIT**

