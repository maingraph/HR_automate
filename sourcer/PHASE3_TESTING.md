# Phase 3 Testing Plan & Checklist

**Date:** 2026-04-27  
**Status:** Ready for Testing  
**Build Status:** ✅ Frontend builds successfully | ✅ Backend syntax validated

---

## Pre-Testing Setup

### 1. Database Migration
```bash
# Run the new indexes migration in Supabase SQL editor
cat supabase/migrations/003_performance_indexes.sql
# Copy and paste into Supabase SQL editor and execute
```

### 2. Backend Setup
```bash
cd backend

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Restart Celery workers to load new code
celery -A app.core.celery_app worker --loglevel=info --reload

# Start FastAPI server
uvicorn app.main:app --reload
```

### 3. Frontend Setup
```bash
cd frontend

# Dependencies already installed (react-window added)
npm install

# Start development server
npm run dev

# Or build for production
npm run build
npm start
```

---

## Test Suite

### ✅ Phase 3A: Quick Wins

#### Test 3A.1: Database Indexes
**Status:** ⏳ Pending

**Steps:**
1. Run migration: `003_performance_indexes.sql`
2. Verify indexes created:
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN ('candidates', 'jobs', 'pipeline_runs')
ORDER BY tablename, indexname;
```

**Expected Results:**
- 9 new indexes created
- No errors during migration
- Indexes show in pg_indexes table

**Verification:**
```sql
-- Check index usage after running some queries
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as scans
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND indexname LIKE '%_idx'
ORDER BY idx_scan DESC;
```

---

#### Test 3A.2: Redis Caching
**Status:** ⏳ Pending

**Steps:**
1. Create a new job (triggers rubric generation)
2. Check Redis for cached rubric:
```bash
redis-cli KEYS "rubric:*"
redis-cli GET "rubric:<key>"
```
3. Create another job with same parameters
4. Verify rubric is loaded from cache (check logs)

**Expected Results:**
- First job: "Generating rubric..." in logs
- Second job: "Loading rubric from cache..." in logs
- 7-day TTL on cache keys
- Significant speed improvement (5-10s → <1s)

---

### ✅ Phase 3B: Real-Time WebSocket Updates

#### Test 3B.1: WebSocket Connection
**Status:** ⏳ Pending

**Steps:**
1. Open job detail page in browser
2. Open browser DevTools → Network → WS tab
3. Verify WebSocket connection established
4. Check console for connection messages

**Expected Results:**
- WebSocket connection shows in Network tab
- Console log: "WebSocket connected: job:xxx"
- Connection status: "connected"
- No errors in console

**Manual Test:**
```javascript
// In browser console
const ws = new WebSocket('ws://localhost:8000/ws/job/test-id');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', e.data);
ws.onerror = (e) => console.error('Error:', e);
```

---

#### Test 3B.2: Real-Time Job Updates
**Status:** ⏳ Pending

**Steps:**
1. Open job detail page
2. Trigger pipeline run from another tab/API
3. Watch for real-time updates without page refresh

**Expected Results:**
- Job status updates instantly
- Pipeline logs appear in real-time
- No polling requests in Network tab
- Smooth UI updates without flicker

**Verification:**
- Check Network tab: No repeated GET requests to `/jobs/{id}`
- Check WebSocket messages: Should see `job_update` and `pipeline_log` messages

---

#### Test 3B.3: WebSocket Reconnection
**Status:** ⏳ Pending

**Steps:**
1. Open job detail page (WebSocket connected)
2. Stop backend server
3. Wait 5 seconds
4. Restart backend server
5. Observe reconnection behavior

**Expected Results:**
- Console shows: "WebSocket closed"
- Console shows: "Reconnecting in Xms (attempt 1/5)"
- Automatic reconnection after server restart
- No manual page refresh needed
- Connection status updates correctly

---

#### Test 3B.4: WebSocket Fallback
**Status:** ⏳ Pending

**Steps:**
1. Open job detail page
2. Block WebSocket connection (browser DevTools → Network → Block request pattern)
3. Verify fallback behavior

**Expected Results:**
- Error message: "Max reconnection attempts reached. Falling back to polling."
- App continues to work (graceful degradation)
- No crashes or blank screens

---

### ✅ Phase 3C: Database Optimization

#### Test 3C.1: Query Performance
**Status:** ⏳ Pending

**Steps:**
1. Create test data (1000+ candidates)
2. Run queries with EXPLAIN ANALYZE:

```sql
-- Test 1: Filter by status and score
EXPLAIN ANALYZE
SELECT * FROM candidates
WHERE job_id = 'test-job-id'
    AND status = 'scored'
    AND gemini_score >= 70
ORDER BY gemini_score DESC
LIMIT 100;

-- Test 2: Filter by open_to_work
EXPLAIN ANALYZE
SELECT * FROM candidates
WHERE job_id = 'test-job-id'
    AND open_to_work = true;

-- Test 3: Filter by scan_depth
EXPLAIN ANALYZE
SELECT * FROM candidates
WHERE job_id = 'test-job-id'
    AND scan_depth = 2;
```

**Expected Results:**
- All queries use indexes (check "Index Scan" in EXPLAIN output)
- Query time < 50ms for 1000 rows
- No "Seq Scan" on candidates table

**Benchmark:**
- Before: ~500-1000ms
- After: ~20-50ms
- Improvement: 90-95%

---

### ✅ Phase 3D: Batch Processing

#### Test 3D.1: Embedding Progress Logging
**Status:** ⏳ Pending

**Steps:**
1. Run pipeline with 200+ candidates
2. Watch backend logs during embedding stage

**Expected Results:**
- Progress logs every 100 embeddings:
  - "Embedded 100/200 texts (50.0%)"
  - "Embedded 200/200 texts (100.0%)"
- No silent periods > 30 seconds
- Clear visibility into progress

---

#### Test 3D.2: Scoring Progress Logging
**Status:** ⏳ Pending

**Steps:**
1. Run deep scan with 50+ candidates
2. Watch backend logs during scoring stage

**Expected Results:**
- Progress logs every 10 candidates:
  - "Scored 10/50 candidates (20.0%)"
  - "Scored 20/50 candidates (40.0%)"
- Clear progress tracking
- No confusion about pipeline status

---

### ✅ Phase 3E: Frontend Performance

#### Test 3E.1: Memoized Components
**Status:** ⏳ Pending

**Steps:**
1. Open job detail page with 100+ candidates
2. Open React DevTools → Profiler
3. Expand/collapse a candidate
4. Check re-render count

**Expected Results:**
- Only the toggled candidate re-renders
- Other candidates do NOT re-render
- Smooth expand/collapse animation
- No lag or jank

---

#### Test 3E.2: Virtualized List (Optional)
**Status:** ⏳ Pending (Component created but not integrated)

**Steps:**
1. Integrate VirtualizedCandidateList into job detail page
2. Load 2000+ candidates
3. Scroll through list
4. Check performance

**Expected Results:**
- Smooth scrolling (60fps)
- Only ~20 DOM nodes rendered (visible rows)
- Memory usage < 200MB
- No lag when scrolling

**Note:** This is optional - only integrate if needed for large candidate lists.

---

### ✅ Phase 3F: Testing & Monitoring

#### Test 3F.1: Performance Monitoring
**Status:** ⏳ Pending

**Steps:**
1. Run complete pipeline (Phase 1 + Phase 2)
2. Check backend logs for performance summary

**Expected Results:**
- Performance summary logged at end of pipeline:
```
============================================================
Performance Summary
============================================================
scrape_telegram            | count:   1 | avg:  12.45s | ...
stage1_embed_filter        | count:   1 | avg:  23.67s | ...
persist_candidates         | count:   1 | avg:   3.12s | ...
deep_scrape_batch_1        | count:   1 | avg:  45.23s | ...
stage2_scoring             | count:   1 | avg: 156.89s | ...
============================================================
```
- All major operations tracked
- Clear bottleneck identification

---

#### Test 3F.2: End-to-End Pipeline
**Status:** ⏳ Pending

**Steps:**
1. Create new job with Telegram source
2. Run Phase 1 pipeline
3. Verify WebSocket updates during pipeline
4. Run Phase 2 deep scan
5. Verify performance monitoring logs

**Expected Results:**
- Real-time updates throughout pipeline
- No polling in Network tab
- Performance summary at end
- All candidates scored successfully
- No errors or crashes

---

## Performance Benchmarks

### Database Queries
| Query Type | Before | Target | Test Result |
|------------|--------|--------|-------------|
| Candidate filter (1000 rows) | 500ms | <50ms | ⏳ |
| Status + score filter | 800ms | <50ms | ⏳ |
| Open to work filter | 600ms | <30ms | ⏳ |
| Pipeline runs query | 300ms | <50ms | ⏳ |

### Frontend
| Metric | Before | Target | Test Result |
|--------|--------|--------|-------------|
| Polling requests/hour | 900 | 0 | ⏳ |
| WebSocket latency | N/A | <100ms | ⏳ |
| Candidate list render (100 items) | 500ms | <100ms | ⏳ |
| Page load time | 3s | <2s | ⏳ |

### Backend
| Metric | Before | Target | Test Result |
|--------|--------|--------|-------------|
| Embedding 100 texts | 60s | 60s | ⏳ |
| Scoring 100 candidates | 21min | 21min | ⏳ |
| Deep scan 100 profiles | 60min | 60min | ⏳ |

**Note:** Backend timing targets unchanged - focus is on visibility and monitoring, not speed improvements for LLM operations.

---

## Known Issues & Limitations

### 1. WebSocket Not Implemented in Backend
**Status:** Code written but not tested  
**Impact:** Real-time updates won't work until backend WebSocket endpoint is implemented  
**Workaround:** Polling still works as fallback

### 2. Virtualized List Not Integrated
**Status:** Component created but not used in job detail page  
**Impact:** Large candidate lists (2000+) may be slow  
**Workaround:** Use pagination or limit results

### 3. Batch LLM Scoring Not Implemented
**Status:** Deferred to future phase  
**Impact:** Scoring still sequential (21min for 100 candidates)  
**Workaround:** None - this is acceptable for now

### 4. Materialized Views Not Created
**Status:** Deferred - indexes sufficient  
**Impact:** Campaign stats still computed in Python  
**Workaround:** Indexes provide good enough performance

---

## Rollback Plan

If critical issues are found:

### 1. Database Indexes
```sql
-- Drop new indexes if they cause issues
DROP INDEX IF EXISTS candidates_status_idx;
DROP INDEX IF EXISTS candidates_otw_idx;
DROP INDEX IF EXISTS candidates_scan_depth_idx;
DROP INDEX IF EXISTS candidates_job_status_score_idx;
DROP INDEX IF EXISTS candidates_updated_at_idx;
DROP INDEX IF EXISTS pipeline_runs_started_at_idx;
DROP INDEX IF EXISTS pipeline_runs_job_stage_idx;
DROP INDEX IF EXISTS jobs_created_at_idx;
DROP INDEX IF EXISTS jobs_updated_at_idx;
```

### 2. Frontend
```bash
# Revert to previous commit
git checkout HEAD~1 frontend/

# Rebuild
cd frontend && npm run build
```

### 3. Backend
```bash
# Revert to previous commit
git checkout HEAD~1 backend/

# Restart workers
celery -A app.core.celery_app worker --loglevel=info
```

---

## Sign-Off Checklist

- [ ] All database indexes created successfully
- [ ] Redis caching working correctly
- [ ] WebSocket connection established
- [ ] Real-time updates working
- [ ] WebSocket reconnection working
- [ ] Query performance improved (>50% faster)
- [ ] Progress logging visible in backend
- [ ] Performance monitoring working
- [ ] Frontend builds successfully
- [ ] Backend syntax validated
- [ ] No regressions in existing functionality
- [ ] Documentation updated

---

## Next Steps After Testing

1. **If all tests pass:**
   - Mark Phase 3 as complete
   - Update PHASE3_PLAN.md status to "✅ COMPLETE"
   - Begin Phase 4 planning

2. **If issues found:**
   - Document issues in GitHub issues
   - Prioritize fixes
   - Re-test after fixes

3. **Production deployment:**
   - Deploy database migration
   - Deploy backend changes
   - Deploy frontend changes
   - Monitor for 24 hours
   - Verify performance improvements

---

**Test Plan Created:** 2026-04-27T15:05:00Z  
**Last Updated:** 2026-04-27T15:05:00Z  
**Status:** Ready for Testing
