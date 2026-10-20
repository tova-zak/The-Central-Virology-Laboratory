# Quota Management & Demo Mode Report
**Date:** October 14, 2026  
**Issue:** HTTP 429 RESOURCE_EXHAUSTED - Daily quota exceeded, system continued wasting calls  
**Solution:** Circuit breaker, quota manager, demo mode for testing  
**Status:** ✅ IMPLEMENTED - NO GEMINI CALLS MADE

---

## 1. Root Cause Analysis

### What User Reported

```
Google Gemini Error:
HTTP 429 RESOURCE_EXHAUSTED

Quota exceeded for:
generativelanguage.googleapis.com/generate_content_free_tier_requests

Limit: 20 requests per day
Model: gemini-2.0-flash-exp
Quota ID: GenerateRequestsPerDayPerProjectPerModel-FreeTier

RetryInfo: ~13.5 hours
```

**But the system continued:**
- ✅ Retrying after 5s and 10s (exponential backoff)
- ✅ Processing pages 5-22 of the same PDF
- ✅ Processing multiple batches in parallel
- ❌ **Total waste: ~40+ API calls after quota exhausted**

### Why It Happened

**Old retry logic (background.py):**
```python
except Exception as e:
    if "429" in str(e):
        # Retry after 5s, 10s... ❌ WRONG for daily quota
        await asyncio.sleep(delay)
    else:
        raise
```

**Problem:**
- Code assumed **all 429 errors are rate limits** (retry after seconds)
- Did NOT distinguish **daily quota exhausted** (retry after 13.5 hours!)
- No circuit breaker → each page tried independently
- No global quota state → batches didn't know quota was dead

---

## 2. The Solution: Quota Manager + Circuit Breaker

### New File: `backend/app/services/extraction/quota_manager.py`

**Key Components:**

1. **QuotaStatus Data Class:**
   ```python
   @dataclass
   class QuotaStatus:
       model: str                    # "gemini-2.0-flash-exp"
       quota_type: str                # "daily_quota" or "rate_limit"
       exhausted_at: datetime         # When it happened
       retry_after: Optional[datetime] # When quota resets
       retry_info_seconds: float      # From Google RetryInfo
       error_message: str             # Full error for debugging
   ```

2. **QuotaManager Class:**
   ```python
   class QuotaManager:
       _exhausted_quotas: Dict[str, QuotaStatus]  # model -> status
       
       def check_quota_available(model) -> (bool, Optional[QuotaStatus]):
           """Check if quota available BEFORE making API call."""
           if model in _exhausted_quotas:
               status = _exhausted_quotas[model]
               if now >= status.retry_after:
                   # Quota refreshed
                   return True, None
               else:
                   # Still blocked
                   return False, status
           return True, None
       
       def mark_quota_exhausted(model, error, retry_seconds, quota_type):
           """Mark quota as exhausted - stops ALL future calls."""
           status = QuotaStatus(...)
           _exhausted_quotas[model] = status
           logger.error(f"[QUOTA EXHAUSTED] {model} until {retry_after}")
   ```

3. **Error Parser:**
   ```python
   def parse_gemini_error(error) -> (is_daily_quota, retry_seconds, quota_type):
       """Distinguish daily quota from rate limit."""
       error_str = str(error).lower()
       
       is_daily_quota = (
           "quota exceeded" in error_str or
           "resource_exhausted" in error_str or
           "free tier" in error_str or
           "generaterequestsperdayperprojectpermodel" in error_str
       )
       
       # Extract RetryInfo seconds (regex for "13.5h", "3600s", etc.)
       retry_seconds = extract_retry_info(error_str)
       
       if is_daily_quota:
           return True, retry_seconds, "daily_quota"
       elif "429" in error_str:
           return False, retry_seconds, "rate_limit"
       else:
           return False, None, "unknown"
   ```

---

## 3. Integration with Background Processor

### Modified: `backend/app/services/processing/background.py`

**New Status:**
```python
class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    QUOTA_EXHAUSTED = "quota_exhausted"  # ✅ NEW
```

**Check Quota BEFORE API Call:**
```python
async def _extract_with_retry(...):
    # 1. Check quota status FIRST
    quota_manager = get_quota_manager()
    model = self._extractor.model
    
    is_available, quota_status = quota_manager.check_quota_available(model)
    
    if not is_available:
        # Quota exhausted - DON'T EVEN TRY
        raise Exception(
            f"Gemini quota exhausted ({quota_status.quota_type}). "
            f"Retry after: {quota_status.retry_after.isoformat()}"
        )
    
    # 2. Try extraction
    for attempt in range(retries):
        try:
            result = await gemini.extract(...)
            return result
        
        except Exception as e:
            # 3. Parse error
            is_quota, retry_secs, quota_type = parse_gemini_error(e)
            
            if is_quota:
                # Daily quota exhausted - STOP ALL PROCESSING
                quota_manager.mark_quota_exhausted(
                    model=model,
                    error_message=str(e),
                    retry_info_seconds=retry_secs,
                    quota_type=quota_type
                )
                raise Exception(f"Gemini daily quota exhausted...")
            
            elif "429" in str(e):
                # Rate limit - retry with backoff
                await asyncio.sleep(backoff_delay)
            
            else:
                # Permanent error
                raise
```

**Stop Processing on Quota Exhausted:**
```python
try:
    result = await self._extract_with_retry(...)
    test_records.append(result)

except Exception as e:
    if "quota exhausted" in str(e).lower():
        # STOP processing remaining pages/files
        job.status = ProcessingStatus.QUOTA_EXHAUSTED
        job.error = (
            f"מכסת Gemini החינמית הסתיימה. "
            f"ניתן לנסות שוב ב-{quota_status.retry_after.strftime('%Y-%m-%d %H:%M UTC')}."
        )
        break  # Exit page loop
    else:
        errors.append({"error": str(e)})

# Check if quota exhausted - stop file loop too
if job.status == ProcessingStatus.QUOTA_EXHAUSTED:
    break  # Exit file loop
```

---

## 4. Demo Mode for Testing

### Problem
- User wants to test E2E workflow
- But quota exhausted → can't call Gemini
- Need way to test without API calls

### Solution: Mock Extractor

**New File: `backend/app/services/extraction/mock_extractor.py`**

**Features:**
- ✅ NO API calls (pure local code)
- ✅ Generates synthetic test data
- ✅ Deterministic (same document_id → same data)
- ✅ Valid Israeli IDs (Luhn checksum)
- ✅ Simulates realistic delay (1-3s)
- ✅ Compatible with Extractor interface

**Example Output:**
```python
{
    "patient_first_name": "דוד",
    "patient_last_name": "כהן",
    "patient_id_number": "123456782",  # Valid checksum
    "sender": "בית חולים איכילוב",
    "received_date": "15/03/2024",
    "central_numbers": ["12345", "67890"],
    "commitment_numbers": ["AB123", "CD456"],
    "warnings": ["generated_data: This is synthetic test data"]
}
```

**Security:**
- Only enabled via `DEMO_MODE=true` in .env
- Shows warning banner in UI
- Logged in backend on startup
- NOT intended for production

### Configuration

**`.env` / `.env.example`:**
```bash
# Demo Mode (for testing without Gemini API calls)
DEMO_MODE=false  # Set to true to use mock extractor
```

**`backend/app/core/config.py`:**
```python
class Settings(BaseSettings):
    demo_mode: bool = False
```

**`backend/app/services/processing/background.py`:**
```python
def __init__(self):
    if settings.demo_mode:
        from app.services.extraction.mock_extractor import MockExtractor
        self._extractor = MockExtractor()
        logger.warning("⚠️ DEMO MODE ENABLED - Using mock extractor")
    else:
        self._extractor = GeminiExtractor(...)
```

### UI Indicator

**`frontend/src/App.tsx`:**
```typescript
useEffect(() => {
    const health = await healthCheck();
    if (health.demo_mode) {
        setDemoMode(true);
    }
}, []);

{demoMode && (
    <div className="demo-mode-banner">
        ⚠️ מצב דמו - הנתונים הם סינתטיים ולא נשלחות קריאות ל-Gemini
    </div>
)}
```

---

## 5. What Changed - Before vs After

### Before (Quota Wasted)

```
1. PDF uploaded (22 pages)
2. Processing starts
3. Page 1 → Gemini → 429 (quota exhausted)
4. Retry after 5s → 429
5. Retry after 10s → 429
6. Page 2 → Gemini → 429
7. Retry after 5s → 429
8. Retry after 10s → 429
9. ... repeat for pages 3-22
10. Total wasted: 22 pages × 3 attempts = 66 API calls ❌
```

### After (Quota Protected)

```
1. PDF uploaded (22 pages)
2. Processing starts
3. Page 1 → Gemini → 429 (quota exhausted)
4. Parse error: "daily_quota" + RetryInfo: 13.5h
5. Mark quota exhausted for "gemini-2.0-flash-exp"
6. STOP immediately - don't try pages 2-22 ✅
7. Save partial results (page 1 if succeeded before quota hit)
8. Return status: "quota_exhausted" with Hebrew message
9. Total API calls: 1 (or however many succeeded before limit) ✅
```

---

## 6. Files Changed

```diff
Added:
+ backend/app/services/extraction/quota_manager.py    (Quota management - 186 lines)
+ backend/app/services/extraction/mock_extractor.py   (Mock for demo - 168 lines)

Modified:
+ backend/app/services/processing/background.py       (Quota checks + QUOTA_EXHAUSTED status)
+ backend/app/core/config.py                          (Added demo_mode setting)
+ backend/app/main.py                                 (Health endpoint shows demo_mode)
+ frontend/src/services/api.ts                        (Added quota_exhausted status)
+ frontend/src/features/workflow/WorkflowScreen.tsx   (Handle quota_exhausted)
+ frontend/src/App.tsx                                (Demo mode banner)
+ frontend/src/App.css                                (Banner styling)
+ .env.example                                        (DEMO_MODE setting)
```

---

## 7. Testing E2E Without Gemini

### Enable Demo Mode:

**1. Set environment variable:**
```bash
# .env
DEMO_MODE=true
```

**2. Restart backend:**
```bash
cd backend
python -m uvicorn app.main:app --reload

# Should see in logs:
# ⚠️ DEMO MODE ENABLED - Using mock extractor (no Gemini API calls)
```

**3. Start frontend:**
```bash
cd frontend
npm run dev

# Should see orange banner:
# ⚠️ מצב דמו - הנתונים הם סינתטיים ולא נשלחות קריאות ל-Gemini
```

**4. Test full workflow:**
- ✅ Upload PDF
- ✅ Process (uses mock, no Gemini)
- ✅ Review synthetic data
- ✅ Edit fields
- ✅ Export to Excel
- ✅ Verify persistence (F5 refresh)

**5. Verify NO Gemini calls:**
- Check backend logs → no "Calling Gemini" messages
- Check Google Cloud Console → no new requests
- Processing completes in 2-6 seconds (not 60-180s)

---

## 8. Quota Management Behavior

### Scenario 1: Daily Quota Exhausted

**Error received:**
```
HTTP 429 RESOURCE_EXHAUSTED
Quota exceeded: generativelanguage.googleapis.com/generate_content_free_tier_requests
Limit: 20
RetryInfo: 13.5h
```

**System response:**
1. ✅ Parse error → `is_daily_quota=True`, `retry_seconds=48600`
2. ✅ Mark quota exhausted for `gemini-2.0-flash-exp`
3. ✅ Calculate retry_after: now + 13.5 hours
4. ✅ Stop current batch processing
5. ✅ Reject future API calls with cached quota status
6. ✅ Return `status="quota_exhausted"` to frontend
7. ✅ Display Hebrew message with retry time

### Scenario 2: Rate Limit (Short Term)

**Error received:**
```
HTTP 429 Too Many Requests
Rate limit exceeded
RetryInfo: 60s
```

**System response:**
1. ✅ Parse error → `is_daily_quota=False`, `retry_seconds=60`
2. ✅ Retry after 60s (NOT marked as exhausted)
3. ✅ Continue processing if retry succeeds
4. ✅ Don't block other batches

### Scenario 3: Quota Refreshes

**After 13.5 hours:**
1. ✅ User tries new processing
2. ✅ `check_quota_available()` sees `retry_after` passed
3. ✅ Clears quota block automatically
4. ✅ Allows new API calls

---

## 9. User Experience Improvements

### Before Quota Manager

```
User: *clicks Process*
[5 minutes later...]
Error: "Processing failed: timeout"

User: *clicks Process again*
[5 minutes later...]
Error: "Processing failed: timeout"

User: "Why isn't it working?!" 😡
[No visibility into quota issue]
```

### After Quota Manager

```
User: *clicks Process*
[Processing...]
Progress: "Processing file 1 of 5..."
[30 seconds later...]

Status: "quota_exhausted"
Message: "מכסת Gemini החינמית הסתיימה. ניתן לנסות שוב ב-2026-10-15 04:30 UTC."

User: "Oh, quota ran out. I'll use demo mode for testing." ✅
[Enables DEMO_MODE=true]
[Tests full workflow with synthetic data]
```

---

## 10. Demo Mode vs Production

| Feature | Production | Demo Mode |
|---------|-----------|-----------|
| **API Calls** | Real Gemini | None ✅ |
| **Data Source** | OCR from PDF | Synthetic |
| **Processing Time** | 60-180s/page | 1-3s/page |
| **Accuracy** | Real extraction | N/A (test data) |
| **Quota Usage** | Consumes quota | Zero ✅ |
| **Cost** | Free tier limits | Free unlimited |
| **Use Case** | Real patients | Testing only |
| **Security** | Prod data | Safe for dev |
| **Banner** | None | Orange warning |

---

## 11. Quota Manager API

### Check Quota Before Call

```python
from app.services.extraction.quota_manager import get_quota_manager

quota_manager = get_quota_manager()
model = "gemini-2.0-flash-exp"

is_available, status = quota_manager.check_quota_available(model)

if not is_available:
    print(f"Quota blocked until {status.retry_after}")
    print(f"Type: {status.quota_type}")
    print(f"Error: {status.error_message}")
else:
    # Safe to call API
    result = gemini.extract(...)
```

### Mark Quota Exhausted

```python
try:
    result = gemini.extract(...)
except Exception as e:
    is_quota, retry_secs, quota_type = parse_gemini_error(e)
    
    if is_quota:
        quota_manager.mark_quota_exhausted(
            model="gemini-2.0-flash-exp",
            error_message=str(e),
            retry_info_seconds=retry_secs,  # 48600 (13.5h)
            quota_type="daily_quota"
        )
```

### Get All Exhausted Quotas

```python
exhausted = quota_manager.get_all_exhausted_quotas()

for model, status in exhausted.items():
    print(f"{model}: blocked until {status.retry_after}")
```

### Manually Clear Block

```python
# If you know quota refreshed
quota_manager.clear_quota_block("gemini-2.0-flash-exp")
```

---

## 12. Logging Improvements

### Before (No Visibility)

```
INFO - Processing batch_abc123
ERROR - Processing failed: <some error>
```

### After (Full Context)

```
INFO - [batch_abc123] Starting batch processing
INFO - [batch_abc123] Found 5 files to process
INFO - [batch_abc123] Processing file 1/5: doc_001.pdf
INFO - [batch_abc123][doc_001] Rendering document
INFO - [batch_abc123][doc_001] Rendered 2 pages in 1.85s
INFO - [doc_001] Calling Gemini (attempt 1/3)
ERROR - [doc_001] Daily quota exhausted detected: HTTP 429 RESOURCE_EXHAUSTED...
ERROR - [QUOTA EXHAUSTED] gemini-2.0-flash-exp - daily_quota - All processing stopped until 2026-10-15 04:30:00
ERROR - [batch_abc123][doc_001] Quota exhausted, stopping batch
INFO - [batch_abc123] Processing complete: status=quota_exhausted, records=0, errors=1
```

---

## 13. Verification Steps

### Test Quota Protection (Without Wasting Quota)

**Since quota already exhausted, verification steps:**

1. **Check Backend Logs:**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   
   # Should see on startup:
   # INFO - Starting server...
   # (No Gemini calls on startup)
   ```

2. **Enable Demo Mode:**
   ```bash
   # .env
   DEMO_MODE=true
   
   # Restart backend
   # Should see:
   # WARNING - ⚠️ DEMO MODE ENABLED - Using mock extractor (no Gemini API calls)
   ```

3. **Test Full E2E:**
   - Upload PDF
   - Click "Process"
   - Should complete in 2-6 seconds
   - Review shows synthetic data
   - Edit fields work
   - Export Excel works
   - **ZERO Gemini calls** ✅

4. **Verify No API Calls:**
   ```bash
   # Check logs - should NOT see:
   # "Calling Gemini"
   
   # Should see:
   # INFO - [batch_xxx] Processing file 1/1: test.pdf
   # INFO - [batch_xxx][doc_xxx] Rendered 1 pages in X.XXs
   # INFO - [batch_xxx] Processing complete: records=1, errors=0
   ```

---

## 14. Future: When Quota Resets

**Tomorrow (after reset):**

1. **Disable Demo Mode:**
   ```bash
   # .env
   DEMO_MODE=false
   ```

2. **Verify Quota Available:**
   ```bash
   # Backend will auto-clear quota block when retry_after passes
   ```

3. **Test Real Processing:**
   - Upload 1-page PDF
   - Process
   - Should call Gemini successfully
   - Quota manager tracks usage

4. **If Quota Hits Again:**
   - Circuit breaker activates immediately
   - No waste of remaining calls
   - Clear error message in Hebrew

---

## 15. git status

```bash
$ git status --short

M  backend/app/api/process.py
M  backend/app/api/upload.py
M  backend/app/core/config.py
M  backend/app/main.py
M  backend/app/services/processing/background.py
M  frontend/src/App.css
M  frontend/src/App.tsx
M  frontend/src/services/api.ts
M  frontend/src/features/workflow/WorkflowScreen.tsx

?? backend/app/services/extraction/quota_manager.py    (NEW)
?? backend/app/services/extraction/mock_extractor.py   (NEW)
?? backend/app/services/processing/                    (Dir)
?? QUOTA_MANAGEMENT_REPORT.md                          (This file)
?? ASYNC_PROCESSING_FIX_REPORT.md
?? ENDPOINT_COLLISION_FINAL_REPORT.md
?? PDF_RENDERING_FIX_REPORT.md
?? BUGFIX_REPORT.md
...
```

---

## Conclusion

**Problem:** Quota exhausted, system wasted 40+ API calls  
**Root Cause:** No distinction between rate limit vs daily quota  
**Solution:** Quota manager + circuit breaker + demo mode  

**Benefits:**
- ✅ Stops immediately on daily quota exhaustion
- ✅ No wasted API calls
- ✅ Clear Hebrew error messages
- ✅ Demo mode for testing without quota
- ✅ Full E2E testing capability
- ✅ Synthetic data for development

**Status:** ✅ Implemented, NO Gemini calls made during fix  
**Next:** Enable DEMO_MODE=true and test full workflow  

---

**Report generated:** October 14, 2026  
**Zero Gemini calls made:** ✅  
**Ready for:** Demo mode E2E testing
