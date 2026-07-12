#!/usr/bin/env python3
"""Test Sales Navigator URL builder against real LinkedIn URLs.

Usage:
    cd backend
    python3 ../scripts/test_salesnav_url.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.scrapers.salesnav_url_builder import (
    build_sales_nav_url,
    parse_sales_nav_url,
    validate_url_structure,
)


def test_basic_build():
    """Test basic URL building."""
    print("=== Test 1: Basic URL Build ===")

    url = build_sales_nav_url(
        title="React Developer",
        location="San Francisco Bay Area",
        seniority="mid-senior",
    )

    print(f"Generated URL:\n{url}\n")

    # Parse it back
    filters = parse_sales_nav_url(url)
    print(f"Parsed filters: {filters}\n")

    # Validate
    is_valid = validate_url_structure(url)
    print(f"Valid structure: {is_valid}\n")


def test_complex_build():
    """Test complex URL with all parameters."""
    print("=== Test 2: Complex URL Build ===")

    url = build_sales_nav_url(
        keywords="AI Machine Learning",
        title="Senior Product Manager",
        location="United States",
        seniority="director",
        company="Google",
        years_experience=(5, 10),
        skills=["Python", "TensorFlow", "Product Strategy"],
    )

    print(f"Generated URL:\n{url}\n")

    filters = parse_sales_nav_url(url)
    print(f"Parsed filters:")
    for key, values in filters.items():
        print(f"  {key}: {values}")
    print()


def test_location_resolution():
    """Test location URN resolution."""
    print("=== Test 3: Location Resolution ===")

    test_locations = [
        "United States",
        "San Francisco Bay Area",
        "London",
        "Berlin",
        "Remote",  # Should fallback to keywords
        "Kyiv",
        "Poland",
    ]

    for loc in test_locations:
        url = build_sales_nav_url(location=loc)
        filters = parse_sales_nav_url(url)

        has_geo = "geoUrn" in filters
        has_keywords = "keywords" in filters

        print(f"{loc:30} → geoUrn: {has_geo:5} | keywords: {has_keywords}")

    print()


def test_seniority_resolution():
    """Test seniority URN resolution."""
    print("=== Test 4: Seniority Resolution ===")

    test_seniorities = [
        "entry",
        "mid-senior",
        "senior",
        "director",
        "executive",
        "manager",
        "vp",
        "c-level",
    ]

    for sen in test_seniorities:
        url = build_sales_nav_url(seniority=sen)
        filters = parse_sales_nav_url(url)

        if "seniority" in filters:
            urn = filters["seniority"][0]
            print(f"{sen:15} → {urn}")
        else:
            print(f"{sen:15} → NOT RESOLVED")

    print()


def compare_with_real_url():
    """Compare generated URL with a real Sales Nav URL.

    MANUAL STEP:
    1. Open https://www.linkedin.com/sales/search/people
    2. Apply filters: Title="Product Manager", Location="San Francisco Bay Area"
    3. Copy URL from address bar
    4. Paste below and run this test
    """
    print("=== Test 5: Compare with Real URL ===")
    print("MANUAL TEST:")
    print("1. Open https://www.linkedin.com/sales/search/people")
    print("2. Apply filters manually")
    print("3. Copy URL and paste here to compare structure")
    print()

    # Example real URL (paste yours here):
    real_url = input("Paste real Sales Nav URL (or press Enter to skip): ").strip()

    if not real_url:
        print("Skipped.\n")
        return

    print(f"\nReal URL filters:")
    real_filters = parse_sales_nav_url(real_url)
    for key, values in real_filters.items():
        print(f"  {key}: {values}")

    print(f"\nGenerated URL filters:")
    generated_url = build_sales_nav_url(
        title="Product Manager",
        location="San Francisco Bay Area",
    )
    generated_filters = parse_sales_nav_url(generated_url)
    for key, values in generated_filters.items():
        print(f"  {key}: {values}")

    print(f"\nFilter keys match: {set(real_filters.keys()) == set(generated_filters.keys())}")
    print()


if __name__ == "__main__":
    print("Sales Navigator URL Builder Test Suite\n")
    print("=" * 60)
    print()

    test_basic_build()
    test_complex_build()
    test_location_resolution()
    test_seniority_resolution()
    compare_with_real_url()

    print("=" * 60)
    print("\n✓ All tests complete")
    print("\nNEXT STEPS:")
    print("1. Run this script: cd backend && python3 ../scripts/test_salesnav_url.py")
    print("2. Open generated URL in Chrome (logged into Sales Nav)")
    print("3. Verify filters applied correctly")
    print("4. If LinkedIn changed structure, update FILTER_KEYS in salesnav_url_builder.py")
