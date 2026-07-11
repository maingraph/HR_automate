"""LinkedIn Profile Mapper — standalone CLI.

Usage:

    # Default: opens browser, you log in, then it scrapes everything:
    python main.py https://www.linkedin.com/in/inovik/details/experience/

    # With li_at cookie (skip manual login if cookie is valid):
    python main.py --li-at "AQEDAX..." https://www.linkedin.com/in/someuser/

    # Only specific sections:
    python main.py --sections experience,education,skills https://www.linkedin.com/in/someuser/

    # Headless mode (requires valid --li-at):
    python main.py --li-at "AQEDAX..." --headless https://www.linkedin.com/in/someuser/

Output lands in ``output/<username>/``:
    - ``raw_html/overview.html``, ``raw_html/experience.html``, …
    - ``profile.json``   (full structured profile)
    - ``profile_summary.txt``   (human-readable digest)

Requirements:
    pip install playwright beautifulsoup4 pycryptodome
    playwright install chromium
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Browser, BrowserContext

from walker import ProfileWalker
from parser import merge_profile, write_outputs


DEFAULT_OUT_DIR = Path(__file__).parent / "output"


def _build_context(pw, li_at: Optional[str] = None, headless: bool = False) -> BrowserContext:
    """Launch a Chromium browser.  If li_at is provided, inject it as a cookie."""
    browser = pw.chromium.launch(
        headless=headless,
        channel="chromium",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="Europe/Berlin",
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    if li_at:
        context.add_cookies([
            {
                "name": "li_at",
                "value": li_at,
                "domain": ".linkedin.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            },
        ])

    return context


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Map a full LinkedIn profile — all sections, HTML + JSON output.",
    )
    ap.add_argument("url", help="LinkedIn profile URL (any /in/<slug>/... page)")
    ap.add_argument(
        "--li-at",
        default=None,
        help="li_at cookie value (attempt auto-login; may not work on newer LinkedIn)",
    )
    ap.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (requires a valid --li-at cookie)",
    )
    ap.add_argument(
        "--sections",
        default=None,
        help="Comma-separated list of sections (default: all known + discovered)",
    )
    ap.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Output directory (default: ./output/)",
    )
    args = ap.parse_args()

    headless = args.headless

    slug = ProfileWalker._slug_from_url(args.url)
    out_dir = Path(args.out_dir) / slug

    print(f"\nMapping profile: https://www.linkedin.com/in/{slug}/")
    print(f"Output dir:      {out_dir}")
    print(f"Headless:        {headless}")

    if not headless:
        print("\nA browser window will open.")
        print("If you're not logged into LinkedIn, please log in manually.")
        print("The tool will automatically continue once authenticated.\n")

    pw = sync_playwright().start()
    context = None
    try:
        context = _build_context(pw, li_at=args.li_at, headless=headless)
        walker = ProfileWalker(context, out_dir, headless=headless)

        print("Walking sections…")
        t0 = time.time()
        paths = walker.walk(args.url)
        elapsed = time.time() - t0
        print(f"  Done in {elapsed:.1f}s — {len(paths)} sections scraped")

        if args.sections:
            wanted = {s.strip() for s in args.sections.split(",")}
            paths = {k: v for k, v in paths.items() if k in wanted}

        print("Parsing HTML → JSON…")
        overview_path = paths.get("overview", out_dir / "raw_html" / "overview.html")
        profile = merge_profile(slug, paths, overview_path)
        json_path, summary_path = write_outputs(profile, out_dir)

        print(f"\nResults:")
        print(f"  HTML dumps:    {out_dir / 'raw_html'}/")
        print(f"  Profile JSON:  {json_path}")
        print(f"  Summary:       {summary_path}")
        print(f"\nDone — {profile.get('name', slug)} mapped in {elapsed:.1f}s")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    except PlaywrightTimeout as e:
        print(f"\nERROR: Page load timed out — {e}", file=sys.stderr)
        print("Try re-running without --headless to solve any CAPTCHA.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        raise
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        try:
            pw.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
