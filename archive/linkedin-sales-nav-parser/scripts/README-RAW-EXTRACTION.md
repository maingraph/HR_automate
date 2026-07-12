# Raw Data Extraction Tool

This script extracts raw HTML and text from LinkedIn Sales Navigator profile sidebars for pattern analysis.

## Purpose

Extract raw sidebar data to:
1. Analyze DOM structure patterns
2. Identify consistent selectors
3. Test AI-based extraction approaches
4. Debug extraction failures

## Usage

### Basic Usage (10 profiles)
```bash
npm run extract-raw -- "YOUR_SALES_NAV_SEARCH_URL"
```

### Extract More Profiles
```bash
npm run extract-raw -- "YOUR_SALES_NAV_SEARCH_URL" 20
```

### Example
```bash
npm run extract-raw -- "https://www.linkedin.com/sales/search/people?query=..." 15
```

## Output

The script creates files in `data/raw-extractions/`:

### Individual Profile Files
- `profile_1_<timestamp>.json`
- `profile_2_<timestamp>.json`
- etc.

Each file contains:
```json
{
  "profileIndex": 1,
  "cardName": "John Smith",
  "cardCompany": "Acme Corp",
  "cardHeadline": "CEO at Acme Corp",
  "sidebarHTML": "<div>...</div>",
  "sidebarText": "John Smith\n3rd\nCEO at Acme Corp...",
  "sidebarOuterHTML": "<aside>...</aside>",
  "timestamp": "2026-05-09T14:30:00.000Z",
  "pageUrl": "https://linkedin.com/sales/..."
}
```

### Combined File
- `all_profiles_<timestamp>.json` - All profiles in one file

### Summary File
- `summary_<timestamp>.json` - Quick overview of extraction results

## What Gets Extracted

### From Profile Card (Search Results)
- Name
- Company
- Headline

### From Sidebar (Detailed View)
- **sidebarHTML**: Inner HTML of sidebar container
- **sidebarText**: Plain text content of sidebar
- **sidebarOuterHTML**: Full HTML including container element

## Use Cases

### 1. Pattern Analysis
Feed the raw data to AI to identify patterns:
```bash
# Extract 20 profiles
npm run extract-raw -- "YOUR_URL" 20

# Feed data/raw-extractions/all_profiles_*.json to ChatGPT/Claude
# Ask: "Analyze these LinkedIn sidebar structures and identify patterns"
```

### 2. Selector Testing
Use the HTML to test new selectors:
```javascript
// Open profile_1_*.json
// Copy sidebarHTML
// Test selectors in browser console
```

### 3. AI Extraction Testing
Test if AI can reliably extract data:
```bash
# Extract profiles
npm run extract-raw -- "YOUR_URL" 10

# Write AI extraction script
# Compare AI results vs current parser results
```

## Notes

- Script uses your existing Chrome profile (must be logged into LinkedIn)
- Runs in non-headless mode so you can see what's happening
- Adds 2-second delays between profiles to be respectful
- Saves data incrementally (won't lose data if interrupted)
- Creates `data/raw-extractions/` directory automatically

## Troubleshooting

### "Could not find Chrome profile"
Make sure Chrome is installed and you've used it before.

### "URL must be a LinkedIn Sales Navigator search URL"
The URL must contain `linkedin.com/sales`.

### Extraction fails for some profiles
This is expected - the script will continue and extract what it can.

## Next Steps

After extraction:
1. Open `data/raw-extractions/summary_*.json` to see overview
2. Open individual profile files to inspect raw data
3. Feed `all_profiles_*.json` to AI for pattern analysis
4. Use findings to improve parser selectors or implement AI extraction
