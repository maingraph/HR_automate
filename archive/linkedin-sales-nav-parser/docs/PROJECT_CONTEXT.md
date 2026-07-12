# Project Context & History

## Overview

LinkedIn Sales Navigator Parser is a TypeScript-based scraper that extracts profile data from LinkedIn Sales Navigator search results. The project uses Puppeteer for browser automation and includes anti-detection features to avoid LinkedIn's bot detection.

## Development Timeline

### May 6, 2026: Initial Development
- Created initial version with core scraping functionality
- Implemented profile data extraction from search results
- Added CSV export, logging, and checkpoint system
- Implemented anti-detection features (stealth mode, random delays)
- Added Chrome profile detection for realistic browser fingerprinting

### May 8, 2026: Duplicate Detection Issues
Multiple bugs were discovered related to duplicate profile detection:

#### Bug #1: Search-Based Tracking Issue
**Problem:** The scraper loaded URLs from previous searches and treated them as duplicates in new searches, causing valid profiles to be skipped.

**Root Cause:** The duplicate tracker stored all scraped URLs in a single file without distinguishing which search they came from. When running a new search, profiles that appeared in previous searches were incorrectly marked as duplicates.

**Solution:** Implemented search-based tracking using a hash of the search URL. Each search now maintains its own set of scraped URLs, isolated from other searches.

**Files Changed:**
- `src/core/types.ts` - Added `searchUrlHash` to `ScrapedUrlsData`
- `src/storage/duplicate-tracker.ts` - Implemented search-based tracking with hash
- `src/core/scraper.ts` - Pass search URL to tracker

#### Bug #2: Empty URL Matching
**Problem:** Profiles without LinkedIn URLs had empty string `""` which matched ALL other empty strings, causing false duplicates. For example, if Profile A had no URL (empty string) and Profile B also had no URL, Profile B would be skipped as "already scraped" even though they were different people.

**Root Cause:** The duplicate detection logic compared URLs directly: `"" === ""` always returns true, so all profiles without URLs were treated as the same profile.

**Initial Fix:** Don't track profiles with empty URLs at all.

**Problem with Initial Fix:** This caused profiles without URLs to be scraped multiple times if they appeared on different pages, resulting in duplicate entries in the CSV.

**Final Solution:** Use `name|company` as a fallback identifier for profiles without URLs. This allows duplicate detection even when LinkedIn URLs are missing.

**Files Changed:**
- `src/core/scraper.ts` - Added fallback identifier logic using name+company

#### Bug #3: LinkedIn Shows Dynamic Results
**Discovery:** LinkedIn search results are NOT static. The scraper was getting different profiles than expected because:
1. LinkedIn search results change over time
2. Different `sessionId` shows different results
3. LinkedIn personalizes results per user
4. Results can change between viewing and scraping

**Solution:** Added `--no-dedup` flag to disable duplicate detection entirely, allowing users to capture everything LinkedIn shows and deduplicate manually later.

### May 9, 2026: Race Condition Fix
**Problem:** The scraper was extracting data from the wrong profile due to a race condition. When clicking a profile card, the sidebar would update with the new profile's data, but the scraper would sometimes extract data before the sidebar finished updating, resulting in data from the previous profile.

**Root Cause:** The scraper clicked a profile card and immediately started extracting data from the sidebar without verifying that the sidebar had updated with the correct profile.

**Solution:** Implemented sidebar verification with fuzzy matching:
1. Extract expected name and company from the card BEFORE clicking
2. Click the profile card to open the sidebar
3. Wait for the sidebar to update and verify it matches the expected profile
4. Use fuzzy matching to handle slight variations in names (e.g., "John Smith" vs "John A. Smith")
5. Only proceed with data extraction after verification succeeds

**Files Changed:**
- `src/extractors/parser.ts` - Added `waitForSidebarToUpdate()` method with fuzzy matching
- `src/extractors/text-utils.ts` - Added `fuzzyMatch()` utility function

### May 9, 2026: Major Refactoring
**Problem:** The parser.ts file had grown to 1,381 lines (37% of the entire codebase), making it difficult to maintain and violating the Single Responsibility Principle.

**Solution:** Split the monolithic parser into 8 focused modules:
1. `text-utils.ts` - Text manipulation utilities (~80 lines)
2. `selectors.ts` - Centralized DOM selectors (~180 lines)
3. `card-extractor.ts` - Extract data from profile cards (~260 lines)
4. `sidebar-extractor.ts` - Extract basic data from sidebar (~520 lines)
5. `experience-extractor.ts` - Extract experience section (~130 lines)
6. `education-extractor.ts` - Extract education section (~120 lines)
7. `skills-extractor.ts` - Extract skills and languages (~160 lines)
8. `parser.ts` - Main orchestrator (~200 lines)

**Additional Changes:**
- Reorganized files into logical directories: `core/`, `extractors/`, `utils/`, `storage/`
- Moved test files to `scripts/` directory
- Updated all import paths
- Added path aliases in tsconfig.json
- Created `.opencode-rules` for AI assistant guidelines

## Technical Decisions

### Why Search-Based Tracking?
LinkedIn search results are dynamic and personalized. Tracking scraped profiles per search URL ensures that:
- Different searches maintain independent tracking
- Re-running the same search skips already-scraped profiles
- Running a new search starts fresh automatically

### Why Name+Company Fallback?
Some LinkedIn profiles have privacy settings that hide their public profile URL. Without a fallback identifier:
- These profiles couldn't be tracked for duplicates
- They would be scraped multiple times if they appeared on different pages
- The CSV would contain duplicate entries

Using `name|company` as a fallback provides:
- Duplicate detection even without URLs
- Reasonable uniqueness (rare for two people with same name at same company)
- Graceful degradation when URLs are unavailable

### Why --no-dedup Flag?
LinkedIn's dynamic search results mean the scraper might see different profiles than the user expects. The `--no-dedup` flag allows users to:
- Capture everything LinkedIn shows, including potential duplicates
- Deduplicate the data manually later with their own criteria
- Work around LinkedIn's result inconsistencies

### Why Sidebar Verification?
LinkedIn's UI updates asynchronously. Without verification:
- Race conditions cause data extraction from wrong profiles
- Data integrity is compromised
- Debugging is difficult because errors are intermittent

Sidebar verification with fuzzy matching ensures:
- Data is always extracted from the correct profile
- Slight name variations don't cause false mismatches
- Errors are caught early with clear error messages

### Why Split Parser into Modules?
A 1,381-line file is difficult to:
- Understand and navigate
- Test in isolation
- Modify without introducing bugs
- Review in code reviews

The modular architecture provides:
- Clear separation of concerns
- Each module has a single responsibility
- Easier to test individual extractors
- Better code organization and maintainability

## Known Limitations

### LinkedIn Shows Dynamic Results
LinkedIn search results are not static. The scraper can only extract profiles that LinkedIn shows during the scraping session. Results may differ from what the user sees in their browser due to:
- Time delay between viewing and scraping
- Different session IDs
- LinkedIn's personalization algorithms
- A/B testing by LinkedIn

### Profile Data Varies by Privacy Settings
Some profiles have privacy settings that limit what data is visible:
- LinkedIn profile URLs may be hidden (empty)
- Experience details may be limited
- Education information may be restricted
- Skills and endorsements may not be visible

### 8 Profiles Fail Name Extraction from Cards
Approximately 8 profiles (16% in some searches) fail to extract names from profile cards due to DOM variations. This is a known issue that will be addressed in Phase 9 with a fallback flow that extracts the name from the sidebar instead.

## Architecture Evolution

### Version 0.9.0 (Initial)
```
src/
├── index.ts
├── scraper.ts
├── parser.ts (1,381 lines!)
├── types.ts
├── logger.ts
├── stealth.ts
├── rate-limiter.ts
├── chrome-detector.ts
├── checkpoint.ts
├── duplicate-tracker.ts
├── csv-exporter.ts
└── notifier.ts
```

### Version 1.1.0 (Current)
```
src/
├── core/
│   ├── index.ts
│   ├── scraper.ts
│   └── types.ts
├── extractors/
│   ├── parser.ts (orchestrator)
│   ├── card-extractor.ts
│   ├── sidebar-extractor.ts
│   ├── experience-extractor.ts
│   ├── education-extractor.ts
│   ├── skills-extractor.ts
│   ├── selectors.ts
│   └── text-utils.ts
├── utils/
│   ├── logger.ts
│   ├── stealth.ts
│   ├── rate-limiter.ts
│   ├── chrome-detector.ts
│   └── notifier.ts
└── storage/
    ├── checkpoint.ts
    ├── duplicate-tracker.ts
    └── csv-exporter.ts
```

## CLI Flags Reference

```bash
--url <url>              # Sales Navigator search URL (required)
--max-profiles <number>  # Maximum profiles to scrape
--max-pages <number>     # Maximum pages to scrape
--test                   # Test mode (limit to 10 profiles)
--resume                 # Resume from last checkpoint
--clear-history          # Clear duplicate tracking history
--fresh                  # Start fresh (ignore previous tracking)
--no-dedup               # Disable duplicate detection
--no-sound               # Disable completion sound
--list-profiles          # List available Chrome profiles
--config <path>          # Path to custom config file
```

## Future Improvements

### Planned for Phase 9
- Implement fallback logic for profiles where name extraction from cards fails
- Use sidebar name extraction as fallback
- Reduce profile loss from 16% to 0%

### Potential Future Enhancements
- Add unit tests for extractors
- Add integration tests
- Create monitoring dashboard
- Document API for each module
- Add more extraction strategies
- Implement caching layer
- Add retry mechanisms for failed extractions
- Create plugin system for custom extractors
