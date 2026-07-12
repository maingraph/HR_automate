# LinkedIn Sales Navigator Parser

A stealth LinkedIn Sales Navigator parser that extracts comprehensive profile data from search results with anti-detection features.

## Features

✅ **Core Features:**
- Connects to your existing Chrome browser session (no login required)
- Extracts comprehensive profile data including experience, education, skills, and languages
- Automatic pagination through all search result pages
- Exports to timestamped CSV files
- Handles 50-200 profiles per session safely

✅ **Anti-Detection Features:**
- Human-like behavior (random delays, scrolling, mouse movements)
- Rate limiting (3-7 seconds between profiles)
- Scheduled breaks (every 20 profiles, 30-90 seconds)
- Stealth mode using existing browser session
- Configurable limits to stay under radar

✅ **Advanced Features:**
- **Auto-detect Chrome profile** - Automatically finds your Chrome profile on macOS
- **Resume capability** - Continue from where you left off if interrupted
- **Smart duplicate detection** - Search-based tracking with URL and name+company fallback
- **Race condition prevention** - Sidebar verification ensures correct profile data
- **Completion notification** - Sound alert when done
- **Detailed logging** - See each profile as it's scraped in real-time
- **Test mode** - Scrape only 10 profiles for testing
- **Modular architecture** - Clean, maintainable codebase with focused extractors

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and component details
- [Project Context](docs/PROJECT_CONTEXT.md) - Development history and technical decisions
- [Changelog](docs/CHANGELOG.md) - Version history and changes

## Installation

```bash
cd /Users/imjustchilling/Desktop/linkedin-sales-nav-parser
npm install
npm run build
```

## Usage

### First Time Setup

1. **Open Chrome and log into LinkedIn Sales Navigator**
   - Make sure you're logged in
   - Keep Chrome open (don't close it)

2. **Perform your search in Sales Navigator**
   - Go to https://www.linkedin.com/sales/search/people
   - Apply your filters (location, industry, title, etc.)
   - Copy the URL from the address bar

3. **Run the scraper**

```bash
# Test mode (recommended for first run - only 10 profiles)
npm start -- --url "YOUR_SALES_NAV_URL" --test

# Full scrape (up to 200 profiles)
npm start -- --url "YOUR_SALES_NAV_URL"

# Custom limits
npm start -- --url "YOUR_SALES_NAV_URL" --max-profiles 100 --max-pages 5
```

### Command Line Options

```bash
--url <url>              Sales Navigator search URL (required)
--max-profiles <number>  Maximum profiles to scrape (default: 200)
--max-pages <number>     Maximum pages to scrape (default: 10)
--test                   Test mode (limit to 10 profiles)
--resume                 Resume from last checkpoint
--clear-history          Clear duplicate tracking history
--fresh                  Start fresh (ignore previous tracking)
--no-dedup               Disable duplicate detection
--list-profiles          List available Chrome profiles
--no-sound               Disable completion sound
--config <path>          Path to custom config file
```

### Examples

```bash
# Test with 10 profiles
npm start -- --url "https://www.linkedin.com/sales/search/people?query=..." --test

# Scrape 50 profiles max
npm start -- --url "https://www.linkedin.com/sales/search/people?query=..." --max-profiles 50

# Resume interrupted session
npm start -- --resume

# Clear duplicate history and start fresh
npm start -- --clear-history
npm start -- --url "https://www.linkedin.com/sales/search/people?query=..."
```

## Output

### CSV Files
- Location: `output/linkedin_export_YYYY-MM-DD_HH-MM-SS.csv`
- Columns:
  - Full Name
  - Headline
  - Current Company
  - Location
  - LinkedIn Profile URL
  - Profile Image URL
  - Connection Degree
  - Premium Badge
  - Shared Connections
  - Years at Company
  - Industry
  - About
  - Experience (JSON array)
  - Education (JSON array)
  - Skills (JSON array)
  - Languages (JSON array)
  - Scraped At

### Log Files
- Location: `logs/session_YYYY-MM-DD_HH-MM-SS.log`
- Contains detailed session information and any errors

## Configuration

Edit `config/config.json` to customize behavior:

```json
{
  "delays": {
    "betweenProfiles": { "min": 3000, "max": 7000 },
    "scrolling": { "min": 1000, "max": 3000 },
    "pageLoad": { "min": 2000, "max": 4000 }
  },
  "breaks": {
    "afterProfiles": 20,
    "duration": { "min": 30000, "max": 90000 }
  },
  "limits": {
    "maxProfilesPerSession": 200,
    "maxPagesPerSession": 10
  }
}
```

## Safety Recommendations

### Daily Limits
- **Conservative:** 100-150 profiles per day
- **Moderate:** 200-300 profiles per day (split into 2 sessions)
- **Aggressive:** 400-500 profiles per day (not recommended)

### Best Practices
- Run during business hours (9am-5pm your timezone)
- Space sessions 3-4 hours apart
- Start with test mode to verify everything works
- Monitor for any LinkedIn warnings
- If you see a CAPTCHA, solve it and the scraper will continue

### Warning Signs
- CAPTCHA challenges
- "Unusual activity" messages
- Forced logout
- Slow page loads

If you see any warning signs:
1. Stop immediately
2. Wait 24-48 hours
3. Reduce daily limits
4. Increase delays in config

## Troubleshooting

### Can't connect to Chrome
**Solution:** Make sure Chrome is running and you're logged into LinkedIn Sales Navigator.

### Selectors not finding elements
**Solution:** LinkedIn may have changed their DOM structure. The parser includes multiple fallback selectors and will log which fields couldn't be extracted.

### Getting CAPTCHAs
**Solution:**
- Reduce `maxProfilesPerSession` in config
- Increase delays in config
- Space out your scraping sessions more
- Run during business hours only

### Missing data in CSV
**Solution:** Some fields may not be visible for all profiles (e.g., years at company, industry). The parser handles missing fields gracefully.

### Scraper stops mid-session
**Solution:** Check logs for errors. The scraper saves progress after each page, so you can resume with `--resume` flag.

## Project Structure

```
linkedin-sales-nav-parser/
├── src/
│   ├── core/                 # Core application logic
│   │   ├── index.ts         # CLI entry point
│   │   ├── scraper.ts       # Main scraping orchestration
│   │   └── types.ts         # TypeScript interfaces
│   ├── extractors/          # Data extraction modules
│   │   ├── parser.ts        # Main orchestrator
│   │   ├── card-extractor.ts      # Extract from profile cards
│   │   ├── sidebar-extractor.ts   # Extract from sidebar
│   │   ├── experience-extractor.ts # Extract experience
│   │   ├── education-extractor.ts  # Extract education
│   │   ├── skills-extractor.ts     # Extract skills & languages
│   │   ├── selectors.ts     # Centralized DOM selectors
│   │   └── text-utils.ts    # Text manipulation utilities
│   ├── utils/               # Utility modules
│   │   ├── logger.ts        # Detailed console logging
│   │   ├── stealth.ts       # Anti-detection utilities
│   │   ├── rate-limiter.ts  # Human-like delays
│   │   ├── chrome-detector.ts # Auto-detect Chrome profile
│   │   └── notifier.ts      # Completion notifications
│   └── storage/             # Data persistence
│       ├── csv-exporter.ts  # CSV file generation
│       ├── checkpoint.ts    # Resume capability
│       └── duplicate-tracker.ts # Track scraped profiles
├── config/
│   └── config.json          # User settings
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md      # System design
│   ├── PROJECT_CONTEXT.md   # Development history
│   └── CHANGELOG.md         # Version history
├── scripts/                 # Utility scripts
├── data/                    # Runtime data (gitignored)
├── output/                  # CSV exports (gitignored)
├── logs/                    # Session logs (gitignored)
└── README.md
```

## Technical Details

### Anti-Detection Strategy
1. **Browser Fingerprinting** - Uses your existing Chrome profile (already trusted by LinkedIn)
2. **Human Behavior Simulation** - Random delays, scrolling, mouse movements
3. **Rate Limiting** - Configurable delays and session limits
4. **Error Handling** - CAPTCHA detection, resume capability, logging

### Data Extraction
The parser uses a modular extraction strategy with multiple fallbacks:
- **Card Extraction** - Quick preview data from search results
- **Sidebar Extraction** - Detailed profile data with verification
- **Race Condition Prevention** - Fuzzy matching ensures correct profile
- **Multiple Selectors** - Fallback selectors handle LinkedIn DOM changes
- **Comprehensive Data** - Name, headline, company, location, experience, education, skills, languages

### Architecture Highlights
- **Modular Design** - 8 focused extractors instead of monolithic parser
- **Separation of Concerns** - Core, extractors, utils, and storage layers
- **Type Safety** - Full TypeScript with strict mode
- **Smart Duplicate Detection** - Search-based tracking with URL and name+company fallback
- **Graceful Degradation** - Missing data handled elegantly

For detailed architecture information, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with LinkedIn's Terms of Service. The authors are not responsible for any misuse or violations.
