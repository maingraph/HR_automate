#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              CLEANING ALL PREVIOUS RUN DATA                          ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Clean tracking data
echo "🗑️  Cleaning tracking data..."
rm -f data/scraped-urls.json 2>/dev/null && echo "   ✓ Deleted scraped-urls.json" || echo "   ℹ️  No scraped-urls.json to delete"
rm -f data/checkpoint.json 2>/dev/null && echo "   ✓ Deleted checkpoint.json" || echo "   ℹ️  No checkpoint.json to delete"
echo ""

# Clean logs
echo "🗑️  Cleaning logs..."
LOG_COUNT=$(ls -1 logs/*.log 2>/dev/null | wc -l)
if [ "$LOG_COUNT" -gt 0 ]; then
    rm -f logs/*.log
    echo "   ✓ Deleted $LOG_COUNT log file(s)"
else
    echo "   ℹ️  No log files to delete"
fi
echo ""

# Clean old CSV files (older than 1 day)
echo "🗑️  Cleaning old CSV files (older than 1 day)..."
OLD_CSV_COUNT=$(find output -name "*.csv" -type f -mtime +1 2>/dev/null | wc -l)
if [ "$OLD_CSV_COUNT" -gt 0 ]; then
    find output -name "*.csv" -type f -mtime +1 -delete 2>/dev/null
    echo "   ✓ Deleted $OLD_CSV_COUNT old CSV file(s)"
else
    echo "   ℹ️  No old CSV files to delete"
fi
echo ""

echo "✅ All previous run data cleaned!"
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                    STARTING SCRAPER                                  ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "⚙️  Running with --no-dedup flag (disables duplicate detection)"
echo "   This will scrape ALL profiles LinkedIn shows, including duplicates"
echo ""

# Check if URL was provided
if [ -z "$1" ]; then
    echo "❌ ERROR: No URL provided"
    echo ""
    echo "Usage:"
    echo "  ./clean-and-run.sh \"YOUR_SEARCH_URL\""
    exit 1
fi

# Run the scraper with --no-dedup flag
npm start -- --url "$1" --no-dedup
