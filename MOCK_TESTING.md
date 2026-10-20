# MOCK MODE TESTING STATUS

**Date:** 2026-10-20  
**Purpose:** Test UI workflow without consuming Gemini API quota

---

## STATUS: IN PROGRESS

### Environment Configuration
- DEMO_MODE set to `true` in main `.env`
- Backend reading from parent directory `.env`
- MockExtractor enhanced with:
  - Context-aware commitment types
  - Multi-commitment scenarios
  - patient_full_name_raw support (Stage 1.5)
  - Deterministic Leumit/Clalit/Maccabi sender scenarios

### Next Steps
1. Verify backend actually using MockExtractor
2. Upload test PDF and verify mock extraction
3. Test full UI workflow with mock data
4. Implement Gemini quota error handling (429/RESOURCE_EXHAUSTED)
5. Document mock vs real extraction mode separation

### Testing Scenarios
- Multi-page form segmentation
- Multiple commitments per form
- Context-aware detection (Leumit דגימה vs Clalit דגימה)
- Relationship resolution
- Field editing and persistence
- Export blocking

---

**Current Backend:** http://localhost:8000  
**Current Frontend:** http://localhost:5173
