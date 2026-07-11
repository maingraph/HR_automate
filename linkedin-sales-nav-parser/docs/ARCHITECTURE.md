# Architecture Overview

## System Design

The LinkedIn Sales Navigator Parser is built with a modular architecture that separates concerns into distinct layers: core application logic, data extraction, utilities, and storage.

## Design Patterns

### Dependency Injection
All classes receive their dependencies through constructors rather than creating them internally. This makes the code more testable and maintainable.

```typescript
class Parser {
  constructor(logger: Logger) {
    this.logger = logger;
    this.cardExtractor = new CardExtractor(logger);
    this.sidebarExtractor = new SidebarExtractor(logger);
    // ...
  }
}
```

### Strategy Pattern (Extractors)
Each extractor implements a specific extraction strategy. The parser orchestrates these extractors without knowing their internal implementation details.

- `CardExtractor` - Extracts data from profile cards in search results
- `SidebarExtractor` - Extracts basic data from the sidebar
- `ExperienceExtractor` - Extracts experience section
- `EducationExtractor` - Extracts education section
- `SkillsExtractor` - Extracts skills and languages

### Observer Pattern (Logging)
The Logger class acts as an observer that all components use to report their status. This centralizes logging and makes it easy to add new logging destinations.

### Factory Pattern (CSV Exporter)
The CSV exporter creates CSV writers with the appropriate configuration based on the data structure.

## Module Structure

```
src/
├── core/                   # Core application logic
│   ├── index.ts           # CLI entry point, argument parsing
│   ├── scraper.ts         # Main orchestration, pagination, session management
│   └── types.ts           # TypeScript type definitions
│
├── extractors/             # Data extraction layer
│   ├── parser.ts          # Orchestrates all extractors, handles clicking and verification
│   ├── card-extractor.ts  # Extracts data from profile cards (search results)
│   ├── sidebar-extractor.ts # Extracts basic data from sidebar (profile details)
│   ├── experience-extractor.ts # Extracts experience section
│   ├── education-extractor.ts  # Extracts education section
│   ├── skills-extractor.ts     # Extracts skills and languages
│   ├── selectors.ts       # Centralized DOM selectors
│   └── text-utils.ts      # Text manipulation utilities
│
├── utils/                  # Utility layer
│   ├── logger.ts          # Logging with file output
│   ├── stealth.ts         # Anti-detection features
│   ├── rate-limiter.ts    # Rate limiting and delays
│   ├── chrome-detector.ts # Chrome profile detection
│   └── notifier.ts        # Desktop notifications
│
└── storage/                # Data persistence layer
    ├── csv-exporter.ts    # CSV file generation
    ├── checkpoint.ts      # Session checkpoint management
    └── duplicate-tracker.ts # Duplicate detection
```

## Data Flow

```
User Input (CLI)
    ↓
index.ts (Parse arguments)
    ↓
Scraper (Main orchestrator)
    ↓
┌─────────────────────────────────────┐
│ For each page:                      │
│   1. Get all profile cards          │
│   2. For each card:                 │
│      ↓                               │
│   Parser (Click & Extract)          │
│      ↓                               │
│   ┌──────────────────────────────┐  │
│   │ CardExtractor                │  │
│   │ (Get expected name/company)  │  │
│   └──────────────────────────────┘  │
│      ↓                               │
│   Click profile card                │
│      ↓                               │
│   Wait for sidebar update           │
│   (Verify with fuzzy matching)      │
│      ↓                               │
│   ┌──────────────────────────────┐  │
│   │ SidebarExtractor             │  │
│   │ (Basic profile data)         │  │
│   └──────────────────────────────┘  │
│      ↓                               │
│   ┌──────────────────────────────┐  │
│   │ ExperienceExtractor          │  │
│   │ EducationExtractor           │  │
│   │ SkillsExtractor              │  │
│   └──────────────────────────────┘  │
│      ↓                               │
│   Return ProfileData                │
│      ↓                               │
│   DuplicateTracker (Check)          │
│      ↓                               │
│   CSVExporter (Write)               │
│      ↓                               │
│   CheckpointManager (Save progress) │
└─────────────────────────────────────┘
    ↓
CSV File Output
```

## Component Responsibilities

### Core Layer

#### index.ts
- Parse CLI arguments
- Load configuration
- Handle graceful shutdown
- Initialize and run scraper

#### scraper.ts
- Browser lifecycle management
- Page navigation and pagination
- Session management
- Profile iteration
- Coordinate all other components
- Handle errors and retries

#### types.ts
- Define all TypeScript interfaces
- Ensure type safety across the application

### Extractors Layer

#### parser.ts (Orchestrator)
- Click profile cards
- Wait for sidebar updates
- Verify correct profile loaded (fuzzy matching)
- Coordinate all extractors
- Return complete ProfileData

#### card-extractor.ts
- Extract name from card
- Extract headline from card
- Extract company from card
- Extract location from card
- Extract profile URL from card
- Extract profile image from card
- Extract connection degree
- Extract premium status
- Extract shared connections

#### sidebar-extractor.ts
- Extract name from sidebar
- Extract headline from sidebar
- Extract company from sidebar
- Extract location from sidebar
- Extract profile URL with retry logic
- Extract profile image from sidebar
- Extract connection degree from sidebar
- Extract premium status from sidebar
- Extract shared connections from sidebar
- Extract years at company
- Extract industry
- Extract about section

#### experience-extractor.ts
- Parse experience section DOM
- Extract job titles
- Extract company names
- Extract date ranges and durations
- Extract locations

#### education-extractor.ts
- Parse education section text
- Extract school names
- Extract degrees
- Extract fields of study
- Extract date ranges

#### skills-extractor.ts
- Parse skills section
- Extract skill names
- Extract endorsement counts
- Parse languages section
- Extract language names
- Extract proficiency levels

#### selectors.ts
- Centralize all DOM selectors
- Provide fallback selectors for each element
- Define text patterns for regex matching
- Define timeout constants

#### text-utils.ts
- Sanitize text (remove extra whitespace)
- Fuzzy matching for name verification
- URL normalization

### Utils Layer

#### logger.ts
- Console logging with colors
- File logging
- Log levels (debug, info, warn, error)
- Session statistics

#### stealth.ts
- Random mouse movements
- Random scrolling
- Page interactions
- Timing randomization
- Human-like behavior simulation

#### rate-limiter.ts
- Delays between profiles
- Delays for scrolling
- Delays for page loads
- Break scheduling

#### chrome-detector.ts
- Detect Chrome installation
- Find Chrome profiles
- Select appropriate profile for realistic fingerprinting

#### notifier.ts
- Desktop notifications
- Sound notifications
- Completion alerts

### Storage Layer

#### csv-exporter.ts
- Generate CSV files
- Format profile data
- Handle nested data (experience, education, etc.)
- Create timestamped filenames

#### checkpoint.ts
- Save session progress
- Load previous session
- Enable resume functionality
- Track current page and profile count

#### duplicate-tracker.ts
- Track scraped profiles per search
- Use URL as primary identifier
- Use name+company as fallback identifier
- Search-based isolation with hash
- Support for fresh mode

## Anti-Detection Strategy

### Browser Fingerprinting
- Use real Chrome profile with history and cookies
- Maintain consistent user agent
- Preserve browser fingerprint across sessions

### Human-Like Behavior
- Random delays between actions
- Random mouse movements
- Random scrolling patterns
- Variable timing for all operations

### Rate Limiting
- Configurable delays between profiles
- Scheduled breaks after N profiles
- Random delay variations

### Stealth Mode
- Disable automation flags
- Inject stealth scripts
- Mask Playwright/Puppeteer detection

## Extraction Strategy

### Two-Phase Extraction

#### Phase 1: Card Extraction
Extract expected data from the profile card before clicking:
- Name
- Company
- Headline

This data is used for verification in Phase 2.

#### Phase 2: Sidebar Extraction
After clicking the card and verifying the sidebar updated:
- Extract all detailed profile data
- Use multiple selector fallbacks
- Retry failed extractions
- Handle missing data gracefully

### Verification Strategy
To prevent race conditions:
1. Extract expected name and company from card
2. Click the profile card
3. Wait for sidebar to appear
4. Extract name from sidebar
5. Use fuzzy matching to verify it matches expected name
6. Retry up to 15 times (15 seconds)
7. Throw error if verification fails

### Fallback Strategy
Multiple levels of fallbacks ensure data extraction succeeds:

1. **Selector Fallbacks**: Try multiple selectors for each element
2. **Text Parsing Fallbacks**: Parse text content if DOM selectors fail
3. **Identifier Fallbacks**: Use name+company if URL is missing
4. **Retry Logic**: Retry failed extractions with delays

## Error Handling

### Graceful Degradation
- Missing data fields are set to undefined or empty string
- Extraction continues even if some fields fail
- Profile is included in CSV with available data

### Checkpoint System
- Progress is saved after each profile
- Session can be resumed with `--resume` flag
- Prevents data loss on interruption

### Logging
- All errors are logged with context
- Debug logs help troubleshoot issues
- Session statistics track success rate

## Performance Considerations

### Memory Management
- ElementHandles are cleaned up after use
- Large objects are not stored in memory
- Data is streamed to CSV incrementally

### Speed Optimization
- Parallel operations where possible
- Efficient DOM queries
- Minimal page interactions
- Cached selectors

### Resource Usage
- Configurable limits on profiles and pages
- Rate limiting prevents overwhelming LinkedIn
- Browser resources are properly cleaned up

## Security Considerations

### Credentials
- Never commit credentials
- Use environment variables
- Don't log sensitive data
- Sanitize URLs in logs

### Data Privacy
- Only scrape publicly available data
- Respect LinkedIn's terms of service
- Don't store unnecessary personal data
- Provide data deletion mechanisms

## Testing Strategy

### Manual Testing
- Test with small batches (10 profiles)
- Verify CSV output
- Check logs for errors
- Monitor for detection

### Validation
- TypeScript type checking
- Build validation
- Import path verification

### Future: Automated Testing
- Unit tests for extractors
- Integration tests for full flow
- Mock LinkedIn responses
- Test error handling
