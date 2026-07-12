# Phase 3 Manual Testing Checklist

**Time Required:** 15 minutes  
**Date:** 2026-04-27

---

## Test 1: Database Migration (5 min)

### Steps
1. Open Supabase dashboard → SQL Editor
2. Copy contents of `supabase/migrations/003_performance_indexes.sql`
3. Paste and click "Run"
4. Verify: "Success. No rows returned"

### Verification
```sql
SELECT COUNT(*) FROM pg_indexes 
WHERE schemaname = 'public' 
AND indexname LIKE '%_idx';
```
**Expected:** Returns 9+ (new indexes)

**Checklist:**
- [ ] Migration executed without errors
- [ ] 9 new indexes created
- [ ] No warnings in Supabase

---

## Test 2: Backend Services (3 min)

### Steps
```bash
cd backend

# Terminal 1: Start Celery
source venv/bin/activate
celery -A app.core.celery_app worker --loglevel=info

# Terminal 2: Start FastAPI
source venv/bin/activate
uvicorn app.main:app --reload
```

**Checklist:**
- [ ] Celery worker starts without errors
- [ ] FastAPI starts on http://localhost:8000
- [ ] No import errors in logs

---

## Test 3: Frontend (2 min)

### Steps
```bash
cd frontend
npm run dev
```

**Checklist:**
- [ ] Dev server starts on http://localhost:3000
- [ ] No console errors
- [ ] Page loads

---

## Test 4: WebSocket Connection (2 min)

### Steps
1. Open http://localhost:3000
2. Create or open a job
3. Open DevTools → Network → WS tab
4. Check console logs

**Checklist:**
- [ ] WebSocket connection appears in Network tab
- [ ] Console shows: "WebSocket connected: job:xxx"
- [ ] No connection errors

---

## Test 5: Real-Time Updates (3 min)

### Steps
1. Keep job detail page open
2. In another tab/Postman, trigger pipeline:
   ```bash
   curl -X POST http://localhost:8000/api/jobs/{job_id}/run
   ```
3. Watch job detail page (don't refresh)

**Checklist:**
- [ ] Status updates appear instantly
- [ ] Pipeline logs appear in real-time
- [ ] No polling requests in Network tab
- [ ] UI updates smoothly

---

## Quick Verification (Optional)

### Performance Monitoring
Run a pipeline and check backend logs for:
```
============================================================
Performance Summary
============================================================
scrape_telegram            | count:   1 | avg:  12.45s
...
============================================================
```

**Checklist:**
- [ ] Performance summary appears in logs
- [ ] All operations tracked
- [ ] Timings look reasonable

---

## Sign-Off

**All tests passed?**
- [ ] Database migration ✓
- [ ] Services start ✓
- [ ] WebSocket connects ✓
- [ ] Real-time updates work ✓
- [ ] Performance monitoring visible ✓

**If YES:** Phase 3 complete ✅  
**If NO:** Note issues below

---

**Issues Found:**
_[Leave blank if none]_

---

**Tested By:** _______________  
**Date:** 2026-04-27  
**Time Taken:** _____ minutes
