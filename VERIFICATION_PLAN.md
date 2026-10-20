# Final Verification Plan - One Page One Commitment

## After Reviewer Completes

### Phase 1: Backend Verification
- [ ] 1. Start Backend with DEMO_MODE=true
- [ ] 2. Run all Backend regression tests
- [ ] 3. Upload 3-page synthetic PDF via API
- [ ] 4. Verify exactly 3 commitment_records in response
- [ ] 5. Verify status=completed
- [ ] 6. Verify zero Gemini API calls (check logs)
- [ ] 7. Verify each commitment has correct page_index

### Phase 2: Frontend/Backend Contract
- [ ] 1. Verify BatchStatusResponse structure matches frontend types
- [ ] 2. Check commitment_records array is present
- [ ] 3. Check test_records/forms/samples not required
- [ ] 4. Verify field update API still works
- [ ] 5. Verify verify field API still works

### Phase 3: Frontend Verification
- [ ] 1. Build Frontend (`npm run build`)
- [ ] 2. Start Frontend dev server
- [ ] 3. Navigate to upload page
- [ ] 4. Upload 3-page PDF
- [ ] 5. Verify all 3 records appear in review screen
- [ ] 6. Edit a field and save
- [ ] 7. Verify change persists

### Phase 4: Persistence & Restart
- [ ] 1. Make a field edit
- [ ] 2. Refresh page (F5)
- [ ] 3. Verify edit still there
- [ ] 4. Restart Backend
- [ ] 5. Refresh Frontend
- [ ] 6. Verify data survived restart

### Phase 5: Export Blocking
- [ ] 1. Check export eligibility API
- [ ] 2. Verify blocking works for incomplete records
- [ ] 3. Complete all required fields
- [ ] 4. Verify export becomes available

### Phase 6: Quota Isolation
- [ ] 1. Verify DEMO_MODE quota checks are bypassed
- [ ] 2. Verify real mode quota checks still active
- [ ] 3. Check quota_manager references only in non-demo paths

## Success Criteria
✅ All 9 acceptance criteria pass
✅ No infinite loops
✅ Frontend displays correctly
✅ Edits persist
✅ Export blocking works
✅ Both servers running stable

## Commands

### Start Backend
```powershell
cd "d:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration\backend"
$env:DEMO_MODE="true"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start Frontend
```powershell
cd "d:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration\frontend"
npm run dev
```

### Run Backend Tests
```powershell
cd "d:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration\backend"
$env:DEMO_MODE="true"
pytest tests/test_one_page_one_commitment.py -v
```

### Build Frontend
```powershell
cd "d:\אקתון\The-Central-Virology-Laboratory\.worktrees\final-integration\frontend"
npm run build
```
