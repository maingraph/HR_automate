"""Quick Sales Nav URL verification — paste real URL to compare structure."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.scrapers.salesnav_url_builder import build_sales_nav_url, parse_sales_nav_url

print("=" * 70)
print("Sales Navigator URL Structure Verification")
print("=" * 70)
print()
print("STEP 1: Open https://www.linkedin.com/sales/search/people in Chrome")
print("STEP 2: Apply filters manually (e.g., Title + Location)")
print("STEP 3: Copy URL from address bar")
print("STEP 4: Paste below")
print()

real_url = input("Paste real Sales Nav URL: ").strip()

if not real_url:
    print("No URL provided. Exiting.")
    sys.exit(0)

print("\n" + "=" * 70)
print("REAL URL STRUCTURE")
print("=" * 70)

real_filters = parse_sales_nav_url(real_url)
if not real_filters:
    print("❌ Could not parse URL. Check format.")
    sys.exit(1)

print(f"Found {len(real_filters)} filters:\n")
for key, values in real_filters.items():
    print(f"  {key:20} = {values}")

print("\n" + "=" * 70)
print("GENERATED URL STRUCTURE")
print("=" * 70)

# Try to generate similar URL
print("\nEnter parameters to test (press Enter to skip):")
title = input("  Title (e.g., Product Manager): ").strip() or None
location = input("  Location (e.g., San Francisco): ").strip() or None
seniority = input("  Seniority (entry/mid-senior/director): ").strip() or None

generated_url = build_sales_nav_url(
    title=title,
    location=location,
    seniority=seniority,
)

print(f"\nGenerated URL:\n{generated_url}\n")

generated_filters = parse_sales_nav_url(generated_url)
print(f"Found {len(generated_filters)} filters:\n")
for key, values in generated_filters.items():
    print(f"  {key:20} = {values}")

print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)

real_keys = set(real_filters.keys())
gen_keys = set(generated_filters.keys())

print(f"\nReal filter keys:      {sorted(real_keys)}")
print(f"Generated filter keys: {sorted(gen_keys)}")

if real_keys == gen_keys:
    print("\n✅ Filter keys MATCH")
else:
    missing = real_keys - gen_keys
    extra = gen_keys - real_keys
    if missing:
        print(f"\n⚠️  Missing in generated: {missing}")
    if extra:
        print(f"\n⚠️  Extra in generated: {extra}")

print("\n" + "=" * 70)
print("NEXT STEPS")
print("=" * 70)
print("\n1. Open generated URL in Chrome (logged into Sales Nav)")
print("2. Verify filters applied correctly")
print("3. If structure changed, update FILTER_KEYS in salesnav_url_builder.py")
print(f"\nGenerated URL:\n{generated_url}")
