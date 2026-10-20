# Pre-Live Test Validation Report

**Date**: 2026-10-14  
**Status**: ✅ **READY FOR SINGLE LIVE API CALL**

---

## Validation Checklist

### ✅ 1. API Key Configuration
- **Keys Found**: 9 keys (GEMINI_API_KEY + GEMINI_API_1-8)
- **Active**: 9/9
- **Duplicates**: None detected
- **Key Manager**: Round-robin operational
- **Test**: `backend/test_key_loading.py` - PASSED

### ✅ 2. Demo Mode Separation
- **DEMO_MODE=true**: Mock Gemini + Real OCR/Preprocessing allowed
- **DEMO_MODE=false**: Real Gemini + Real OCR/Preprocessing
- **Logging**: Explicit mode markers added
- **Test**: Verified in code, no Gemini calls in demo mode

### ✅ 3. Hebrew OCR Validation
- **Tesseract**: Operational at D:\Users\1\tesseract.exe
- **Languages**: heb + eng
- **Character codes**: ✅ Correct (U+05XX range)
- **RTL Issue**: Hebrew text reversed (known limitation)
- **Mitigation**: HybridVerifier now handles reversed comparison
- **Test**: `backend/test_hebrew_ocr.py` - PASSED

**Key Findings from Hebrew OCR Test**:
```
Hebrew text: "שם: דוד כהן" → OCR: "|הכ דוד :םש"
Character codes: 0x5d4 0x5db 0x5d3 0x5d5 0x5d3 (correct)
Numbers: Extracted with 93-96% confidence
Bounding boxes: Accurate
```

### ✅ 4. All Tests Passing
```
Test Suite                     Status    Count
───────────────────────────────────────────────
test_demo_mode_enforcement     PASSED    8/8
test_gemini_key_manager        PASSED   12/12
test_validation                PASSED   14/14
test_sender_normalization      PASSED   29/29
───────────────────────────────────────────────
TOTAL                          PASSED   63/63
```

### ✅ 5. Model Configuration
- **Current**: gemini-1.5-flash (in .env)
- **Availability**: Requires live verification
- **Free Tier Limits**: 15 RPM, 1500 RPD (typical, verify in AI Studio)
- **Circuit Breaker**: Operational
- **Quota Manager**: Tracking enabled

### ✅ 6. Safety Measures
- ✅ No API keys in logs/console
- ✅ Human-verified fields protected
- ✅ Focused retry disabled (quota=0)
- ✅ Circuit breaker blocks on 429
- ✅ No key rotation on quota exhaustion
- ✅ DEMO_MODE available for safe testing

---

## Live Test Plan

### Phase 1: Single Gemini API Call

**Script**: `backend/test_single_gemini_call.py`

**What it does**:
1. Creates synthetic Hebrew medical form (no real patient data)
2. Calls Gemini API once with gemini-1.5-flash
3. Verifies structured output (Pydantic schema)
4. Tracks quota usage
5. Assesses extraction accuracy
6. Tests multi-key round-robin

**Expected Outcomes**:
- ✅ API call succeeds
- ✅ Structured JSON returned
- ✅ Hebrew text extracted (may be reversed)
- ✅ Numbers extracted accurately
- ✅ Quota usage tracked: 1 request
- ✅ No errors or crashes

**Risk**: **VERY LOW**
- Only 1 API request
- Synthetic data (no privacy concerns)
- Circuit breaker will block if quota exhausted
- Rollback trivial (no state changes)

### Phase 2: Hybrid Pipeline Test (No Additional API Calls)

**After Phase 1 succeeds**:
1. Take same Gemini result from Phase 1
2. Run Tesseract OCR on same image
3. Run HybridVerifier to compare results
4. Assess verification logic

**Cost**: **ZERO** additional API requests (reuses Phase 1 result)

---

## Known Issues & Limitations

### Hebrew RTL in OCR
**Issue**: Tesseract returns Hebrew text in reversed character order  
**Example**: "דוד כהן" → "הכ דוד"  
**Impact**: Field matching may fail for Hebrew names  
**Mitigation**: HybridVerifier now tries reversed comparison  
**Recommendation**: Test with real forms, tune if needed  

### Model Availability
**Issue**: gemini-1.5-flash availability not verified yet  
**Impact**: API call may fail with model not found  
**Mitigation**: Test script will catch error, can switch to gemini-1.5-flash-latest  
**Recommendation**: Verify in Google AI Studio first  

### Quota Uncertainty
**Issue**: Actual Free Tier limits not confirmed for this project  
**Impact**: May hit quota faster than expected  
**Mitigation**: Circuit breaker stops on 429, single test call minimizes risk  
**Recommendation**: Check quota in Google Cloud Console  

---

## Execution Command

```powershell
# Set Tesseract path
$env:TESSERACT_CMD = "D:\Users\1\tesseract.exe"

# Run single API test
python backend/test_single_gemini_call.py
```

**Prerequisites**:
- .env file with valid keys
- DEMO_MODE=false in .env
- google-genai package installed
- Confirmed Free Tier (no billing)

---

## Fallback Plan

**If API call fails**:
1. Check error message for cause
2. If model not found → try gemini-1.5-flash-latest
3. If quota exhausted → respect Retry-After, test another day
4. If auth error → verify API key validity in AI Studio
5. If billing required → STOP, do not proceed

**If accuracy low**:
1. Analyze which fields failed
2. Check if Hebrew RTL is the cause
3. Tune HybridVerifier if needed
4. Consider prompt improvements

---

## Approval Confirmation

**User approved** to proceed with:
- ✅ Single Gemini API call (Phase 1)
- ✅ Hybrid verification test using same result (Phase 2)
- ✅ Max 1 real API request
- ✅ Synthetic data only (no real patient info)

**Next step**: Execute `test_single_gemini_call.py` when ready

---

## Post-Test Report Template

After test completes, document:
1. API call success/failure
2. Model response time
3. Structured output received (yes/no)
4. Field extraction accuracy (X/7 fields)
5. Hebrew handling (successful/issues)
6. Quota usage (1 request confirmed)
7. Circuit breaker status (open/closed)
8. Any errors or warnings
9. Hybrid verification results
10. Recommendations for production

---

*End of Pre-Live Test Validation*
