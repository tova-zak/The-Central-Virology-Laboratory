# Document Segmentation - User Requirements Clarification
**Date:** 2026-10-20  
**Priority:** CRITICAL - Must be incorporated into DOCUMENT_SEGMENTATION_PLAN.md

---

## Key Insight from User

**Observation from actual forms:**  
Continuation pages marked **"עמוד 2/2"** typically appear **immediately after** their first page ("עמוד 1/2") in the PDF sequence.

**Impact on algorithm design:**  
This changes the segmentation approach from random/global grouping to **Sequential Page Segmentation** (window-based, examining adjacent pages).

---

## Updated Design Priorities (Ordered)

### 1. Sequential Processing ← NEW PRIORITY
- **Examine pages in PDF order**
- **Look at adjacent pages first** (page N and N+1)
- **Sliding window approach** rather than global analysis
- **Assume continuations are consecutive** unless evidence contradicts

### 2. Page Notation = Primary Evidence
- **"עמוד 1/2"** → START of 2-page form (expect next page to be "2/2")
- **"עמוד 2/2"** → CONTINUATION (link to previous page if it's "1/2")
- **Strength:** Highest (0.95 confidence if no contradictions)

### 3. Central Number = Secondary Evidence
- **Presence of מספר מרכזי** → indicates form START
- **Absence** → neutral (NOT proof of continuation)
- **Strength:** Medium (0.7 confidence alone)

### 4. Missing Sticker/Number ≠ Auto-Merge ⚠️
- **Absence of central number** is a **hint only**
- **NOT sufficient reason to merge** with previous page
- **Must have additional evidence** (page notation, patient ID match, etc.)

### 5. Check Contradictions (Blocking Evidence)
If any of these differ between adjacent pages → **DO NOT merge:**
- **Patient ID number mismatch** (different patients)
- **Sender mismatch** (different organizations)
- **Form structure mismatch** (visual layout significantly different)
- **Date mismatch** (received dates >7 days apart)

**Example blocking scenario:**
```
Page 3: Patient 123456782, Sender כללית, "עמוד 2/2"
Page 2: Patient 987654321, Sender מכבי, "עמוד 1/2"
→ DO NOT merge (patient mismatch blocks even though notation suggests continuation)
```

### 6. Insufficient Evidence → Human Review
**Conservative threshold:** If confidence < 0.8 → flag `needs_segmentation_review = True`

**Common uncertain cases:**
- Page with no notation + no central number + same patient as previous
- "עמוד 2/2" but previous page was not "1/2"
- "עמוד 1/2" but next page is not "2/2"
- Same patient in non-consecutive pages

### 7. Full Page Mapping Required
**Every page must have status:**
- `processed` — grouped into FormGroup
- `needs_review` — uncertain, awaiting human decision
- `failed` — OCR failed, cannot classify
- `skipped` — deliberately excluded (blank, illegible)

**NO page can be unaccounted for.**

### 8. Manual Correction Before Final Processing
**UI Flow:**
```
Upload PDF
  ↓
Auto-Segmentation (sequential algorithm)
  ↓
IF uncertain cases exist:
  → Show Segmentation Review UI
  → Human approves/modifies grouping
  → Save corrected FormSegmentation
  ↓
THEN proceed to Gemini extraction
```

**Key:** Segmentation decisions are **finalized before Gemini calls**, not after.

---

## Algorithm Design: Sequential Window Approach

### Pseudo-Code

```python
def segment_forms_sequential(pages: list[PageMetadata]) -> list[FormGroup]:
    """
    Sequential page-by-page segmentation.
    Examines adjacent pages with sliding window.
    """
    form_groups = []
    current_group = None
    
    for i, page in enumerate(pages):
        prev_page = pages[i-1] if i > 0 else None
        next_page = pages[i+1] if i < len(pages)-1 else None
        
        # Rule 1: Page notation "X/Y" (PRIMARY EVIDENCE)
        if page.page_notation:
            current_num, total_num = page.page_notation
            
            if current_num == 1:
                # Start new form group
                current_group = FormGroup(
                    form_id=generate_uuid(),
                    page_indices=[i],
                    expected_pages=total_num,
                    classification=PageRole.START,
                    confidence=0.95
                )
                
                if total_num == 1:
                    # Standalone page (1/1)
                    form_groups.append(current_group)
                    current_group = None
                # else: wait for continuation pages
            
            elif current_num > 1:
                # Continuation page
                if current_group and current_group.expected_pages == total_num:
                    # Matches expected continuation
                    if not has_contradictions(current_group, page):
                        current_group.page_indices.append(i)
                        current_group.confidence = 0.95
                        
                        if current_num == total_num:
                            # Last page of form
                            form_groups.append(current_group)
                            current_group = None
                    else:
                        # Contradiction detected
                        mark_uncertain(current_group, page, reason="contradiction")
                else:
                    # Orphan continuation (no matching start)
                    create_uncertain_group(page, reason="orphan_continuation")
        
        # Rule 2: Central number present (SECONDARY EVIDENCE)
        elif page.has_central_number:
            # Likely form start
            if current_group:
                # Close previous group (was expecting continuation but didn't get it)
                form_groups.append(current_group)
            
            current_group = FormGroup(
                form_id=generate_uuid(),
                page_indices=[i],
                expected_pages=1,  # assume single-page unless notation says otherwise
                classification=PageRole.START,
                confidence=0.7  # lower than notation
            )
            # Don't close yet, might be multi-page
        
        # Rule 3: No notation, no central number (AMBIGUOUS)
        else:
            if current_group and not current_group_is_complete(current_group):
                # Might be continuation of current group
                if prev_page and same_patient_and_sender(prev_page, page):
                    # Add tentatively with low confidence
                    current_group.page_indices.append(i)
                    current_group.confidence = min(current_group.confidence, 0.6)
                    current_group.needs_review = True
                else:
                    # Close previous group, start uncertain new group
                    if current_group:
                        form_groups.append(current_group)
                    create_uncertain_group(page, reason="no_clear_evidence")
            else:
                # Standalone uncertain page
                create_uncertain_group(page, reason="no_clear_evidence")
    
    # Close any open group at end
    if current_group:
        if current_group.expected_pages > len(current_group.page_indices):
            # Incomplete form (missing continuation)
            current_group.needs_review = True
            current_group.classification = PageRole.INCOMPLETE
        form_groups.append(current_group)
    
    return form_groups


def has_contradictions(group: FormGroup, new_page: PageMetadata) -> bool:
    """Check if new page contradicts existing group."""
    first_page = pages[group.page_indices[0]]
    
    # Patient ID mismatch
    if first_page.patient_id and new_page.patient_id:
        if first_page.patient_id != new_page.patient_id:
            return True
    
    # Sender mismatch
    if first_page.sender and new_page.sender:
        if first_page.sender != new_page.sender:
            return True
    
    # Date mismatch (>7 days)
    if first_page.received_date and new_page.received_date:
        if abs(first_page.received_date - new_page.received_date) > 7:
            return True
    
    # TODO: Visual structure mismatch (layout similarity)
    
    return False
```

### Key Differences from Global Approach

**Before (global grouping):**
- Analyze all pages, find patterns
- Group pages by similarity (could be non-consecutive)
- Higher complexity, slower

**After (sequential):**
- Process pages in order
- Look at immediate neighbors first
- Simpler, faster, more deterministic
- Matches user observation (continuations are consecutive)

---

## Edge Cases to Handle

### 1. Non-Consecutive Continuation (Rare)
```
Page 0: "עמוד 1/2" (form A)
Page 1: "עמוד 1/1" (form B - complete standalone)
Page 2: "עמוד 2/2" (form A continued?!)
```
**Solution:** Page 2 flagged as `orphan_continuation`, needs review.

### 2. Missing "1/2" (Continuation without Start)
```
Page 0: No notation, central number 12345
Page 1: "עמוד 2/2", no central number
```
**Solution:** 
- Page 0 = uncertain start (confidence 0.7)
- Page 1 = orphan continuation (needs review)
- **DO NOT auto-merge** despite "2/2"

### 3. Missing "2/2" (Incomplete Form)
```
Page 0: "עמוד 1/2"
Page 1: New form with central number
```
**Solution:** 
- Page 0 = incomplete form (flagged `needs_review`)
- Page 1 = new form start

### 4. Same Patient, Multiple Forms
```
Page 0: Patient 123456782, Central 12345
Page 1: Patient 123456782, Central 12346
```
**Solution:** 
- Different central numbers → **two separate forms**
- Same patient ≠ same form

### 5. No Evidence at All
```
Page 0: No notation, no central number, no patient ID visible
```
**Solution:**
- Mark as `needs_review`
- OCR quality check — if OCR failed, mark `failed`

---

## Validation Requirements

### Test Dataset Must Include:

**Sequential cases (expected):**
- [ ] "1/2" → "2/2" consecutive (merge)
- [ ] "1/1" single page with central number (standalone)
- [ ] Page with central number followed by page without (start → uncertain)

**Non-sequential cases (edge):**
- [ ] "1/2" → standalone form → "2/2" (orphan, don't merge)
- [ ] "2/2" without preceding "1/2" (orphan)
- [ ] "1/2" without following "2/2" (incomplete)

**Contradiction cases (blocking):**
- [ ] "1/2" → "2/2" but different patients (don't merge)
- [ ] "1/2" → "2/2" but different senders (don't merge)
- [ ] Same patient, two consecutive pages, both with central numbers (two forms)

**Ambiguous cases (uncertain):**
- [ ] No notation, no central number, same patient (uncertain)
- [ ] Same patient, non-consecutive pages (uncertain)

---

## Success Metrics (Updated)

### Primary Metrics:
- **False Merge Rate < 2%** ← CRITICAL (was 5%, now stricter)
- **False Split Rate < 10%** ← acceptable
- **Coverage = 100%** ← every page has status
- **Correct Sequential Grouping ≥ 95%** ← NEW metric

### Performance Metrics:
- **OCR time per page** < 200ms (Tesseract, local)
- **Segmentation time per PDF** < 1s (rule-based, deterministic)
- **Total overhead** < 10% vs. current flow

### User Experience Metrics:
- **Review queue size** < 15% of pages (was 20%, now tighter)
- **UI decision time** < 30s per uncertain case
- **Manual correction rate** < 5% after auto-segmentation

---

## Implementation Notes

### Preferred Approach:
1. ✅ **Simple rule-based sequential algorithm** (as pseudo-code above)
2. ✅ **OCR-only evidence** (Tesseract, no Gemini for segmentation)
3. ✅ **Deterministic decisions** (same input → same output)
4. ✅ **Conservative thresholds** (prefer `needs_review` over auto-merge)

### Avoid:
- ❌ **ML/AI models for segmentation** (overkill, not needed yet)
- ❌ **Global optimization** (complex, slower)
- ❌ **Additional Gemini calls** (cost, quota)
- ❌ **Heuristics that assume non-consecutive pages** (rare case)

---

## Integration with Existing Work

### Must NOT Break:
- ✅ **Stage 1:** `patient_full_name` schema and prompt
- ✅ **Stage 1.5:** Name display and export blocking
- ✅ **Hybrid Engine:** OCR verification and preprocessing
- ✅ **Existing tests:** All 72 backend + 18 integration tests must pass

### Can Modify:
- ✅ **`background.py`:** Add segmentation phase before extraction
- ✅ **`models.py`:** Add `form_group_id`, `page_role` to TestRecord
- ✅ **`process.py`:** Modify to handle multi-page forms
- ✅ **Frontend:** Add Segmentation Review UI

---

## Questions for Design Review

1. **Is sequential algorithm sufficient?** Or do we need to handle non-consecutive edge cases?
2. **What if "2/2" appears before "1/2"?** (pages scanned out of order)
3. **How to handle partial OCR failures?** (page notation unreadable)
4. **Should we store segmentation decisions permanently?** (for audit/undo)
5. **What's the rollback plan if segmentation fails mid-batch?**

---

**Status:** Requirements clarification complete. Workflow planner should incorporate these priorities into DOCUMENT_SEGMENTATION_PLAN.md.

**Next:** Design reviewer validates plan addresses these requirements.
