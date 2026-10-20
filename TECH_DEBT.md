# Technical Debt - Final Integration

## Test Collection sys.exit() Issue

**Status**: Deferred  
**Priority**: P2  
**Created**: 2026-10-20

### Problem
Several legacy test files call `sys.exit()` at module import time when .env prerequisites are not met, causing pytest collection to fail with `SystemExit` internal error.

**Affected files**:
- `tests/test_live_verification.py` (line 205)
- `tests/test_gemini_real.py` (line 154)
- `tests/final_live_test_single.py` (lines 45, 251, 256)
- `tests/smoke_test_mvp.py` (line 143)
- `tests/docker_resource_test.py` (lines 258, 262)

### Root Cause
Tests were written as standalone scripts with `if __name__ == "__main__"` entry points and `sys.exit()` for prerequisite validation. When pytest imports these modules during test discovery, the `sys.exit()` calls at module level cause collection to abort.

### Solution (Deferred)
Replace all module-level `sys.exit()` calls with `pytest.skip(..., allow_module_level=True)` for proper pytest collection skipping.

**Example fix**:
```python
# BEFORE:
if not env_path.exists():
    logger.error("❌ .env not found")
    sys.exit(1)

# AFTER:
if not env_path.exists():
    pytest.skip(".env not found", allow_module_level=True)
```

### Workaround
Run tests with explicit file selection or exclusion filters:
```bash
pytest tests/test_export_check_commitments.py -v
pytest tests/ -k "not (live or docker or e2e or smoke)"
```

### Notes
- **e2e_batch_processing_test.py**: Fixed (uses pytest.skip)
- **test_live_single_extraction.py**: Fixed (uses pytest.skip)
- Remaining files are optional integration tests not required for MVP
- Does not block manual testing or deployment
