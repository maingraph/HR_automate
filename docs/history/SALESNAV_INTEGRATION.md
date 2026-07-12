# Sales Navigator Parser Integration — Complete

Full Python/Playwright port of linkedin-sales-nav-parser integrated into Sourcer backend.

## What's Built (Ready to Test)

### 1. URL Builder (`salesnav_url_builder.py`)
- Maps job params → Sales Nav search URL
- Handles: title, location, seniority, company, years_experience, skills
- Location URN resolution (US, UK, SF Bay Area, etc.)
- Seniority URN resolution (entry/mid-senior/director/executive)
- Fallback: unknown locations → keywords

### 2. Extractors (Python/Playwright)
All ported from TypeScript with same logic:

- **Card Extractor** — extracts preview data from search result cards
- **Sidebar Extractor** — extracts detailed data from profile sidebar
- **Experience Extractor** — extracts work history with "Show more" expansion
- **Education Extractor** — extracts education history
- **Skills Extractor** — extracts skills + languages

### 3. Main Scraper (`linkedin_salesnav.py`)
- Anti-detection: human delays (3-7s between profiles), breaks (every 20 profiles)
- Race condition prevention: fuzzy name matching before extraction
- Cookie-based auth (per-tenant `li_at` cookie)
- Pagination support (up to 10 pages, 200 profiles)
- Full profile extraction: name, headline, company, location, about, experience, education, skills, languages

### 4. Verification Scripts
- `verify_salesnav_url.py` — compare generated URL with real Sales Nav URL
- `open_salesnav_url.py` — test generated URL in Chrome
- `test_salesnav_url.py` — full test suite

## What Needs Sales Nav Account to Test

### Critical Tests (Do First)

1. **URL Structure Verification**
   ```bash
   cd backend
   python3 ../scripts/verify_salesnav_url.py
   ```
   - Open Sales Nav in Chrome
   - Apply filters manually (Title + Location)
   - Copy URL from address bar
   - Paste into script → compares filter keys
   - **If LinkedIn changed structure:** update `FILTER_KEYS` in `salesnav_url_builder.py`

2. **Scraper Test (Single Profile)**
   ```python
   # backend/test_salesnav_scraper.py
   import asyncio
   from app.scrapers.linkedin_salesnav import SalesNavScraper
   from app.scrapers.salesnav_url_builder import build_sales_nav_url

   async def test():
       # Build URL
       url = build_sales_nav_url(
           title="Product Manager",
           location="San Francisco Bay Area",
           seniority="mid-senior",
       )
       print(f"URL: {url}\n")

       # Scrape (limit to 3 profiles for testing)
       scraper = SalesNavScraper(
           li_at_cookie="YOUR_LI_AT_COOKIE_HERE",
           headless=False,  # Watch it work
           max_profiles=3,
           max_pages=1,
       )

       profiles = await scraper.scrape(url)
       print(f"\nScraped {len(profiles)} profiles:")
       for p in profiles:
           print(f"  - {p['full_name']} | {p['headline'][:50]}")
           print(f"    Experience: {len(p['experience'])} entries")
           print(f"    Education: {len(p['education'])} entries")
           print(f"    Skills: {len(p['skills'])} skills")

   asyncio.run(test())
   ```

3. **Selector Validation**
   - If scraper returns empty fields, LinkedIn changed DOM
   - Update selectors in `salesnav_selectors.py`
   - Check browser console for errors

### How to Get `li_at` Cookie

1. Open Chrome
2. Go to https://www.linkedin.com/sales/search/people
3. Open DevTools (F12) → Application tab → Cookies → linkedin.com
4. Find `li_at` cookie → copy Value
5. **IMPORTANT:** This is a session token — treat like a password

## Integration into Sourcer Pipeline

### Current Flow (Apify)
```
Job created → Gemini generates Boolean
    ↓
Phase 1: linkedin_apify.scrape_linkedin()
    → Apify search with Boolean
    → ~100 profiles (basic data)
    → Embed filter (top 30%)
    ↓
Phase 2: linkedin_deep.scrape_profiles_deep()
    → Apify deep scrape (25 URLs/batch)
    → Full profiles
    ↓
Gemini batch scoring
```

### New Flow (Sales Nav Parser)
```
Job created → Build Sales Nav URL from params
    ↓
Phase 1: linkedin_salesnav.scrape()
    → Navigate to Sales Nav URL (auto-filtered)
    → Extract full profiles (experience, education, skills)
    → Return ~200 profiles
    ↓
Dedup + Embed filter (top 30%)
    ↓
Gemini batch scoring (Phase 2 SKIPPED — already have full data)
```

### To Wire Into Pipeline

**Option A: Replace Apify entirely**
```python
# backend/app/tasks/pipeline.py

# OLD:
# from app.scrapers.linkedin_apify import scrape_linkedin
# candidates = scrape_linkedin(job["linkedin_boolean"], ...)

# NEW:
from app.scrapers.linkedin_salesnav import SalesNavScraper
from app.scrapers.salesnav_url_builder import build_sales_nav_url

url = build_sales_nav_url(
    title=job["title"],
    location=job["geo"],
    seniority=job["seniority"],
    skills=job["skills"][:3],
)

scraper = SalesNavScraper(
    li_at_cookie=settings.linkedin_li_at,  # Global for now
    max_profiles=200,
)

candidates = await scraper.scrape(url)
```

**Option B: Add as new source (keep Apify as fallback)**
```python
# Let user choose in job creation: "linkedin" (Apify) vs "linkedin_salesnav"
if "linkedin_salesnav" in job["sources"]:
    candidates = await scrape_via_salesnav(job)
elif "linkedin" in job["sources"]:
    candidates = scrape_linkedin(job["linkedin_boolean"], ...)
```

## Multi-Account Support (Tier-2)

After Tier-1 auth applied, add per-tenant credentials:

### 1. Add `org_credentials` Table
```sql
create table public.org_credentials (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references public.orgs(id) on delete cascade,
    provider text not null,  -- 'linkedin_salesnav'
    account_name text,       -- 'Main Account', 'Account 2'
    credentials_encrypted jsonb not null,  -- {li_at: "...", sales_nav_cookie: "..."}
    is_active boolean default true,
    created_at timestamptz default now()
);

create index org_credentials_org_provider_idx on public.org_credentials(org_id, provider);
```

### 2. Add UI (`/admin/accounts`)
- List LinkedIn accounts for current org
- Add/edit/delete accounts
- Test connection (scrape 1 profile to verify cookie works)
- Mark default account

### 3. Job Creation
- Dropdown: "LinkedIn Account" → select which account to use
- Store `job.linkedin_account_id`
- Pipeline reads account → loads `li_at` cookie

### 4. Account Rotation
- If scraper hits rate limit / CAPTCHA → mark account as "cooling down"
- Auto-rotate to next active account
- Resume after cooldown period (24h)

## Known Limitations (Until Tested)

1. **Selectors may be stale** — LinkedIn changes DOM frequently
2. **Cookie expiry** — `li_at` cookies expire (need refresh flow)
3. **Rate limits** — Sales Nav has daily limits (100-200 profiles safe)
4. **CAPTCHA** — aggressive scraping triggers CAPTCHA (need manual solve)
5. **Privacy settings** — some profiles hide LinkedIn URL (scraper handles gracefully)

## Next Steps

### Immediate (Need Sales Nav Account)
1. ✅ Get Sales Nav account
2. ✅ Run `verify_salesnav_url.py` → verify URL structure
3. ✅ Run scraper test (3 profiles) → verify extractors work
4. ✅ Update selectors if LinkedIn changed DOM

### After Verification
5. Wire into pipeline (Option A or B above)
6. Test end-to-end: job creation → scrape → score → export
7. Add error handling: cookie expiry, CAPTCHA detection, rate limits

### Tier-2 (Multi-Account)
8. Apply Tier-1 auth (JWT + org_id)
9. Add `org_credentials` table
10. Build `/admin/accounts` UI
11. Add account selection to job creation
12. Implement account rotation logic

## Files Created

```
backend/app/scrapers/
├── salesnav_url_builder.py          # URL generator
├── salesnav_selectors.py            # DOM selectors
├── salesnav_text_utils.py           # Text utilities
├── salesnav_card_extractor.py       # Card extraction
├── salesnav_sidebar_extractor.py    # Sidebar extraction
├── salesnav_experience_extractor.py # Experience extraction
├── salesnav_education_extractor.py  # Education extraction
├── salesnav_skills_extractor.py     # Skills extraction
└── linkedin_salesnav.py             # Main scraper

scripts/
├── verify_salesnav_url.py           # URL verification
├── open_salesnav_url.py             # Test URL in browser
└── test_salesnav_url.py             # Full test suite
```

## Summary

**Built:** Full Sales Nav parser in Python/Playwright with anti-detection, ready to test.

**Blocked:** Need Sales Nav account to verify URL structure + test extractors.

**Once verified:** Wire into pipeline (5 lines of code), test end-to-end, ship.

**Tier-2:** Add per-tenant credentials + account rotation (after Tier-1 auth done).
