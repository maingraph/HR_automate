# Quick Testing Guide - Phase 4B

## Setup (5 minutes)

### 1. Start Backend Services
```bash
# Terminal 1 - Backend API
cd /Users/imjustchilling/Desktop/sourcer/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Celery Worker
cd /Users/imjustchilling/Desktop/sourcer/backend
source venv/bin/activate
celery -A app.core.celery_app worker --loglevel=info

# Terminal 3 - Redis (if not running)
redis-server
```

### 2. Start Frontend
```bash
# Terminal 4 - Frontend
cd /Users/imjustchilling/Desktop/sourcer/frontend
npm run dev
```

Open browser: http://localhost:3000

---

## Test Checklist

### ✅ Dark Mode Toggle (30 seconds)
1. Click moon/sun icon in top-right header
2. Page should switch between light/dark themes
3. Refresh page - theme should persist
4. Check localStorage in DevTools: `localStorage.getItem('theme')`

**Expected:** Smooth theme transition, colors invert properly

---

### ✅ Dashboard (1 minute)
1. Navigate to http://localhost:3000/dashboard
2. Check metrics cards display correctly
3. Click "New Job" button → should go to `/jobs/new`
4. Recent jobs list shows jobs with status badges

**Expected:** Clean layout, no console errors

---

### ✅ Job Creation Wizard (2 minutes)
1. Click "New Job" or go to `/jobs/new`
2. **Step 1:** Fill in job title, description, skills
3. **Step 2:** Add Telegram channels (optional) or upload CSV
4. **Step 3:** Review and submit
5. Should redirect to job detail page

**Expected:** 3-step wizard works, validation shows errors

---

### ✅ Job Detail Page - NEW DESIGN (3 minutes)
1. Go to any job detail page (e.g., `/jobs/1`)
2. **Check Pipeline Tracker:**
   - Horizontal stepper with 5 stages
   - Active stage should pulse/highlight
   - Completed stages show green checkmark
3. **Check Stats Cards:**
   - Phase 1 Collected
   - Deep Scanned
   - Scored
   - Geo Excluded
4. **Check Candidate Cards:**
   - Score badge (colored by score)
   - Click "View Details" to expand
   - Shows AI reasoning, skills, experience
   - Search bar filters candidates
   - Min score filter works
5. **Check Logs Table:**
   - Shows pipeline stages
   - Status badges (ok/error/started)
   - Real-time updates if job is running

**Expected:** Clean modern design, no layout issues

---

### ✅ Pause/Resume/Cancel (2 minutes)
1. Create a new job with Telegram channels
2. Job starts running automatically
3. Click "Pause" button → job status changes to "paused"
4. Click "Resume" button → job continues
5. Click "Cancel" button → confirms, then cancels job

**Expected:** Buttons appear/disappear based on job status

---

### ✅ Scoring Checkpoint Resume (5 minutes)
**This tests the critical bug fix from previous session**

1. Create job with Telegram channels (e.g., `@python_jobs`)
2. Wait for Phase 1 to complete
3. Trigger deep scan
4. Wait for scoring to start (you'll see candidates getting scores)
5. **Pause at ~30-40% progress**
6. Check database:
   ```sql
   SELECT checkpoint FROM jobs WHERE id = <job_id>;
   ```
   Should show: `{"stage": "score", "scored_count": 30, "total_count": 79, ...}`
7. **Resume the job**
8. Check logs - should say "Resuming from checkpoint" and continue from candidate #31

**Expected:** Resume continues from checkpoint, doesn't restart scoring

---

### ✅ Export (30 seconds)
1. Wait for job to complete (status = "done")
2. Click "Export" button
3. Should download XLSX file with all candidates

**Expected:** Excel file downloads with candidate data

---

## Common Issues

### Dark mode not working
- Check browser console for errors
- Verify `document.documentElement.classList` contains "dark"
- Clear localStorage and try again

### Job not starting
- Check Celery worker is running
- Check Redis is running
- Check backend logs for errors

### Candidates not showing
- Check job has completed Phase 1
- Check filters (min score, source) aren't too restrictive
- Check browser console for API errors

### WebSocket not connecting
- Check backend is running on port 8000
- Check `NEXT_PUBLIC_API_URL` in frontend `.env.local`
- Check browser console for WebSocket errors

---

## Quick Smoke Test (2 minutes)

If you're short on time, just test:
1. ✅ Dark mode toggle works
2. ✅ Dashboard loads
3. ✅ Job detail page shows new design
4. ✅ No console errors

---

## What's New in Phase 4B

### Dark Mode Toggle
- Icon in header (moon/sun)
- Persists to localStorage
- System preference detection

### Job Detail Redesign
- **Before:** 1046 lines, cluttered
- **After:** 650 lines, clean modern design
- Horizontal pipeline tracker
- Expandable candidate cards
- Better search/filter UX

### Design System
- Executive Talent Engine colors
- Consistent spacing and typography
- Material Symbols icons throughout

---

## Next Phase (Phase 4C)

After testing, we can move to:
- **Batch LLM scoring** (10x speedup)
- **Telegram auto-discovery**
- **Advanced filtering**
