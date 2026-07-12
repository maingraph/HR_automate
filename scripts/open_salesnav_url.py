"""Helper to build Sales Nav URL from job params and open in browser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.scrapers.salesnav_url_builder import build_sales_nav_url

# Example job params
url = build_sales_nav_url(
    title="Senior React Developer",
    location="San Francisco Bay Area",
    seniority="mid-senior",
    years_experience=(3, 7),
    skills=["React", "TypeScript", "Node.js"],
)

print("Generated Sales Navigator URL:")
print(url)
print()
print("Opening in Chrome...")
print("Verify that filters applied correctly.")

import subprocess
subprocess.run(["open", "-a", "Google Chrome", url])
