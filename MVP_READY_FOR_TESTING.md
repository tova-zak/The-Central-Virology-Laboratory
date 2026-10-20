# MVP READY FOR MANUAL TESTING

**Date:** 2026-10-20  
**Integration Branch:** `integration/final-mvp`  
**Status:** ✅ READY FOR USER TESTING

---

## 🚀 LOCAL URLS

**Backend API:** http://localhost:8000  
**Frontend UI:** http://localhost:5173  
**API Documentation:** http://localhost:8000/docs

---

## ✅ AUTOMATED TEST RESULTS

### Backend Tests (37 passing)
- **Segmentation:** 4/4 ✓
- **Commitment Detection:** 14/14 ✓
- **Storage (JSON):** 10/10 ✓
- **Export Policy:** 8/8 ✓
- **Persistence:** 1/1 ✓

### Frontend Build
- **Status:** ✓ Built successfully (3.24s)
- **Bundle Size:** 239.96 KB (gzipped: 78.04 KB)

### Security
- **Secrets Scan:** ✓ No exposed API keys in code
- **Export Blocking:** ✓ Server-side validation working
- **Data Validation:** ✓ Field-level protection active

---

## 📋 TESTING INSTRUCTIONS

### 1. Upload Test Documents

**Use Anonymized Sample Forms:**
- The reference PDF in `d:\אקתון\The-Central-Virology-Laboratory\reference\` directory
- Or create synthetic test PDFs (no real patient data)

**Upload via UI:**
1. Navigate to http://localhost:5173
2. Click "Upload Files" or drag-and-drop PDF
3. Click "Process Batch"
4. Wait for processing to complete

### 2. Verify Multi-Page Segmentation

**Expected Behavior:**
- Multi-page forms with continuation notation ("עמוד 1/2", "עמוד 2/2") are grouped
- Each logical form has its own card
- All pages are accounted for (none lost)

**Check:**
- Number of forms matches expected logical forms
- Page indices are correct
- No duplicate pages

### 3. Verify Commitment Detection

**Expected Behavior:**
- Commitments with "התחייבות" label are detected
- "דגימה לאומית" from Leumit is detected as commitment
- "דגימה" from other senders (Clalit, Maccabi) is NOT detected
- Central lab numbers are NOT confused with commitments

**Check:**
- Commitment count matches form content
- Only valid commitments are shown
- Context-aware rules are applied correctly

### 4. Test Relationship Review

**Scenario:** Form with 3 commitments and 2 samples

**Expected:**
- `relationship_status` = "unresolved_relationship"
- `review_status` = "needs_review"
- UI shows warning indicator
- Export is BLOCKED

**Action:**
1. Click "Resolve Relationship" on a commitment
2. Select sample(s) to link
3. Confirm resolution

**Verify:**
- Status changes to `relationship_status` = "explicit"
- `review_status` = "human_verified"
- Export unblocks for that commitment

### 5. Test Field Editing

**Action:**
1. Click "Edit" on any field (e.g., patient name)
2. Modify value
3. Save changes

**Verify:**
- Field updates immediately
- `review_status` changes to "human_verified"
- Change persists after page refresh

### 6. Test Persistence

**Action:**
1. Make corrections (edit fields, resolve relationships)
2. Refresh browser (F5)
3. Or restart backend and frontend

**Verify:**
- All corrections persist
- `human_verified` status is preserved
- Resolved relationships remain resolved

### 7. Test Export Blocking

**Scenarios to Test:**

**A. Unresolved Relationships (should BLOCK):**
- Form with 3 commitments, 2 samples, none resolved
- Expected: Export button disabled or shows error

**B. Pending Review (should BLOCK):**
- Field with `review_status` = "needs_review"
- Expected: Export blocked until verified

**C. All Verified (should ALLOW):**
- All relationships resolved
- All problematic fields verified
- Expected: Export succeeds, downloads Excel file

### 8. Document Viewer

**Action:**
- Click "View Document" on any form

**Verify:**
- PDF renders correctly
- Page navigation works
- Can zoom in/out
- Modal closes properly

---

## 🔍 KNOWN LIMITATIONS

### Not Yet Implemented (Out of Scope for MVP)
- Real Supabase persistence (tests skipped without env vars)
- Multi-file upload progress tracking
- Advanced OCR preprocessing
- Batch-level statistics dashboard

### Deprecation Warnings (Non-Blocking)
- `datetime.utcnow()` in JSONStorage (Python 3.12+)
- Pydantic v2 class-based config in HybridConfig
- PyMuPDF `fitz` API (use `pymupdf` import in future)

---

## 🐛 ISSUE REPORTING

**When reporting issues, please include:**

1. **Steps to reproduce**
2. **Expected behavior**
3. **Actual behavior**
4. **Screenshots** (if UI issue)
5. **Browser console errors** (F12 → Console tab)
6. **Backend logs** (check terminal running uvicorn)

**Common Issues & Solutions:**

**Issue:** "Processing failed" immediately after upload  
**Check:** Backend terminal for Gemini API errors  
**Cause:** API key quota, network issue, or invalid PDF

**Issue:** Forms not appearing after processing  
**Check:** `test_records` array in batch status API response  
**Cause:** Extraction returned no valid forms

**Issue:** Export blocked unexpectedly  
**Check:** `/api/batches/{batch_id}/export-check` response  
**Cause:** Unresolved relationships or unverified fields

---

## 🔐 SECURITY REMINDERS

**CRITICAL:** API keys in `.env` must be rotated before any public deployment.

**Current keys are exposed in:**
- Session chat history
- Workflow agent reports
- This conversation thread

**Before deployment:**
1. Generate new Gemini API key
2. Generate new Supabase service key
3. Update `.env` files
4. Never commit `.env` to git
5. Use separate keys for prod/staging/dev

---

## 📊 SYSTEM HEALTH

**Backend Health Check:** http://localhost:8000/health

**Expected Response:**
```json
{
  "status": "healthy",
  "checks": {
    "tesseract": {"available": true, "hebrew": true, "english": true},
    "storage": {"writable": true},
    "gemini": {"configured": true, "demo_mode": false}
  }
}
```

**If unhealthy:**
- Check Tesseract installation (Hebrew language pack required)
- Check file system permissions for `backend/data/batches/`
- Check `.env` file exists with required variables

---

## 🎯 SUCCESS CRITERIA

**MVP is successful if:**

✅ Upload → Process → Extract workflow completes  
✅ Multi-page forms are segmented correctly  
✅ Commitment detection follows context-aware rules  
✅ One business record per commitment (not per page)  
✅ Unresolved relationships block export  
✅ Human corrections persist after refresh  
✅ Export generates valid Excel file when unblocked  
✅ No data loss or corruption  
✅ UI is responsive and usable  

---

## 📁 FILES & DIRECTORIES

**Worktree Location:**  
`d:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration`

**Branch:** `integration/final-mvp`

**Key Files:**
- Backend: `backend/app/services/processing/background.py` (segmentation integration)
- Backend: `backend/app/services/segmentation/segmenter.py` (multi-page logic)
- Backend: `backend/app/services/extraction/commitment_rules.py` (context-aware detection)
- Backend: `backend/app/api/process.py` (export blocking)
- Frontend: `frontend/src/features/review/ReviewScreenNew.tsx` (review UI)
- Frontend: `frontend/src/features/review/ResolveRelationshipModal.tsx` (relationship editor)

**Data Storage:**
- Local: `backend/data/batches/{batch_id}/batch.json`
- Supabase: (requires env vars, not yet configured for local testing)

---

## 🚦 NEXT STEPS AFTER TESTING

1. **Report Issues:** Send any bugs or UX issues found
2. **Supabase Setup:** Configure real cloud persistence if approved
3. **Docker Build:** Test containerized deployment if approved
4. **Merge to Main:** Fast-forward main branch after approval
5. **Deploy:** Push to Render or chosen hosting platform

---

**Testing Environment Ready!**  
**Start manual testing at:** http://localhost:5173
