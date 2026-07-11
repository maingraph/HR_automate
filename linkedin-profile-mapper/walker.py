"""LinkedIn profile walker.

Given a profile URL (everything under https://www.linkedin.com/in/{slug}/...),
we:

1. Open the profile root once to discover the section list from the sidebar
   nav (``/details/{section}/`` links).  The set of sections LinkedIn shows
   varies per profile (recruiter shows extra, student shows less).
2. For every section — known + discovered — navigate to the corresponding
   ``/details/...`` URL, wait until network is idle, then dump the rendered
   HTML to ``<slug>/<section>.html``.
3. After the loop, return a ``{section: html_path, ...}`` mapping.

All access goes via a single persistent Chromium context bound to the
user's real Chrome profile (cookies inherited), so no login is needed.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout


SECTION_SLUGS = [
    "experience",
    "education",
    "licenses",
    "certifications",
    "skills",
    "projects",
    "publications",
    "honors",
    "test-scores",
    "languages",
    "volunteer-experience",
    "volunteering",
    "recommendations",
    "about",
    "interests",
    "posts",
    "details",  # the consolidated/details root (catch-all)
]


@dataclass
class ProfilePaths:
    raw_dir: Path            # folder holding per-section .html files
    combined_html: Path      # full <slug>.html dump of the profile root page
    combined_json: Path      # final merged profile.json


class ProfileWalker:
    """Walks every section URL on a LinkedIn public profile."""

    def __init__(self, context: BrowserContext, out_dir: Path, headless: bool = True):
        self.context = context
        self.out_dir = out_dir
        self.raw_dir = out_dir / "raw_html"
        self.headless = headless

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _slug_from_url(url: str) -> str:
        u = urlparse(url)
        parts = [p for p in u.path.split("/") if p]
        if "in" in parts:
            i = parts.index("in")
            if i + 1 < len(parts):
                return parts[i + 1]
        return "unknown-profile"

    @staticmethod
    def _section_from_url(url: str) -> str:
        u = urlparse(url)
        parts = [p for p in u.path.split("/") if p]
        # /in/<slug>/details/<section>/  
        try:
            i = parts.index("details")
        except ValueError:
            return "overview"
        if i + 1 < len(parts):
            return parts[i + 1]
        return "overview"

    @staticmethod
    def _safe_filename(name: str) -> str:
        name = re.sub(r"[^a-z0-9_.-]+", "_", name.lower())
        return name or "unknown"

    def _human_delay(self, page: Page) -> None:
        # Tiny pause so LinkedIn's behavioural-bot checks stay calm.
        page.wait_for_timeout(600)

    # -------------------------------------------------------------- discovery

    def _open_profile_root(self, page: Page, profile_url: str) -> None:
        root = profile_url.split("?")[0].rstrip("/")
        slug = self._slug_from_url(root)
        if not slug or "linkedin.com/in/" not in root:
            raise ValueError(f"URL doesn't look like a LinkedIn profile page: {profile_url}")

        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # Navigate to the feed first to check/establish auth.
        # If li_at works, the server will set session cookies.
        # If not, the user will see the login page and can log in manually.
        print("  Navigating to LinkedIn…")
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeout:
            pass

        # Check login state. If not logged in, wait for the user.
        self._ensure_logged_in(page)

        # Close any extra tabs LinkedIn may have opened (notifications, etc.)
        all_pages = self.context.pages
        for extra in all_pages[:-1]:
            try:
                extra.close()
            except Exception:
                pass

        # Now navigate to the actual profile URL
        sparse = f"https://www.linkedin.com/in/{slug}"
        print(f"  Navigating to profile: {sparse}")
        try:
            page.goto(sparse, wait_until="domcontentloaded", timeout=60_000)
        except Exception:
            # LinkedIn may interrupt with a redirect — wait for it to settle
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception:
                pass
            # If we still ended up on a login page, one more attempt
            try:
                url = page.url
            except Exception:
                url = ""
            if "/login" in url or "/authwall" in url:
                print("  Session expired mid-run — please log in again.")
                self._ensure_logged_in(page)
                try:
                    page.goto(sparse, wait_until="domcontentloaded", timeout=60_000)
                except Exception:
                    page.wait_for_load_state("domcontentloaded", timeout=15_000)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeout:
            pass
        self._human_delay(page)

    def _ensure_logged_in(self, page: Page) -> None:
        """Check if LinkedIn considers us logged in; if not, prompt user."""
        def _is_logged_in() -> bool:
            try:
                url = page.url
            except Exception:
                return False
            # Any authenticated LinkedIn page (feed, profile, messaging, etc.)
            if "linkedin.com" in url:
                if "/login" in url or "/authwall" in url or "/checkpoint/" in url:
                    return False
                # On a profile page with a non-zero member-id
                try:
                    mid = page.evaluate(
                        "() => {"
                        "  const el = document.querySelector('[data-member-id]');"
                        "  return el ? el.getAttribute('data-member-id') : null;"
                        "}"
                    )
                    if mid and mid != "0":
                        return True
                except Exception:
                    pass
                # On feed / homepage / any non-login page — assume logged in
                if "/feed" in url or "/mynetwork" in url or "/in/" in url:
                    return True
                # Any non-authwall page counts as logged in if it's on linkedin.com
                return True
            return False

        # Quick check first
        page.wait_for_timeout(2000)
        if _is_logged_in():
            print("  ✓ Already authenticated")
            return

        print("\n" + "=" * 60)
        print("  LinkedIn session not authenticated!")
        print("  The browser window is open — please log in manually.")
        print("  Once you see your LinkedIn feed, the tool will continue.")
        print("=" * 60)

        # Wait up to 5 minutes for user to log in
        for i in range(300):
            page.wait_for_timeout(1000)
            if _is_logged_in():
                print("\n  ✓ Logged in successfully! Continuing…\n")
                page.wait_for_timeout(1500)
                return
            if i > 0 and i % 30 == 0:
                print(f"  …still waiting for login ({i}s elapsed)")

        raise RuntimeError(
            "Timed out waiting for LinkedIn login (5 min). "
            "Re-run and make sure you can log in."
        )

    def _discover_section_urls(self, page: Page) -> Dict[str, str]:
        """Return ``{section_slug: full_url}`` for every nav link on the profile.

        LinkedIn renders the section nav with ``href*='details/<section>/'``.
        """
        seen: Dict[str, str] = {}
        try:
            anchors = page.locator('a[href*="/details/"]').all()
        except Exception:
            anchors = []
        for a in anchors:
            try:
                href = a.get_attribute("href")
            except Exception:
                continue
            if not href:
                continue
            if href.startswith("/"):
                href = "https://www.linkedin.com" + href
            path = urlparse(href).path
            parts = [p for p in path.split("/") if p]
            try:
                i = parts.index("details")
                slug = parts[i + 1].strip("/")
            except (ValueError, IndexError):
                continue
            if not slug:
                continue
            # normalise to canonical URL
            full = f"https://www.linkedin.com/in/{self._slug_from_url(href)}/details/{slug}/"
            seen.setdefault(slug, full)
        return seen

    # ------------------------------------------------------------------ core

    def _get_active_page(self) -> Page:
        """Return the most recently opened page in the context."""
        pages = self.context.pages
        if pages:
            return pages[-1]
        return self.context.new_page()

    def walk(self, profile_url: str) -> Dict[str, Path]:
        """Navigate every section and dump raw HTML.

        Returns `{section_slug: html_path}`.
        """
        page = self.context.new_page()
        try:
            self._open_profile_root(page, profile_url)

            # 1. overview
            overview_path = self.raw_dir / "overview.html"
            overview_path.write_text(page.content(), encoding="utf-8")

            # 2. discover all in-page section links
            discovered = self._discover_section_urls(page)

            # 3. merge with known-section URL list (deduplicated)
            slug = self._slug_from_url(profile_url)
            urls: Dict[str, str] = {**{"overview": profile_url}, **discovered}
            for s in SECTION_SLUGS:
                if s in ("details",):
                    continue
                full = f"https://www.linkedin.com/in/{slug}/details/{s}/"
                urls.setdefault(s, full)

            paths: Dict[str, Path] = {"overview": overview_path}
            for section, url in urls.items():
                if section == "overview":
                    continue
                target = self.raw_dir / f"{self._safe_filename(section)}.html"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                except Exception:
                    page.wait_for_timeout(3000)
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    except Exception:
                        continue
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except PlaywrightTimeout:
                    pass
                self._scroll_to_bottom(page)
                self._human_delay(page)
                try:
                    target.write_text(page.content(), encoding="utf-8")
                    paths[section] = target
                    print(f"    ✓ {section}")
                except Exception:
                    print(f"    ✗ {section} (page error)")
                    continue
            return paths
        finally:
            for p in self.context.pages:
                try:
                    p.close()
                except Exception:
                    pass

    @staticmethod
    def _scroll_to_bottom(page: Page, max_passes: int = 12) -> None:
        """Trigger LinkedIn's infinite scroll lazy-loader to dump everything."""
        try:
            page.evaluate("window.scrollTo(0, 0)")
            for i in range(max_passes):
                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                page.wait_for_timeout(700)
        except Exception:
            pass
