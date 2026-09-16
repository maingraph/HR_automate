"""Sales Navigator scraper — main orchestrator with anti-detection.

Ports TypeScript linkedin-sales-nav-parser to Python/Playwright.
Includes:
- Anti-detection (human delays, scrolling, breaks)
- Profile card → sidebar extraction
- Race condition prevention (fuzzy name matching)
- Per-tenant cookie support
"""
from __future__ import annotations

import asyncio
import random
import re
from typing import Any, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.logging import get_logger
from app.scrapers.salesnav_card_extractor import CardExtractor
from app.scrapers.salesnav_education_extractor import EducationExtractor
from app.scrapers.salesnav_experience_extractor import ExperienceExtractor
from app.scrapers.salesnav_selectors import SEARCH_SELECTORS, SIDEBAR_SELECTORS, TIMEOUTS
from app.scrapers.salesnav_sidebar_extractor import SidebarExtractor
from app.scrapers.salesnav_skills_extractor import SkillsExtractor
from app.scrapers.salesnav_text_utils import fuzzy_match

log = get_logger(__name__)


class SalesNavScraper:
    """Sales Navigator scraper with anti-detection."""

    def __init__(
        self,
        *,
        li_at_cookie: str,
        headless: bool = True,
        max_profiles: int = 200,
        max_pages: int = 10,
    ):
        """Initialize scraper.

        Args:
            li_at_cookie: LinkedIn li_at cookie value
            headless: Run browser in headless mode
            max_profiles: Maximum profiles to scrape
            max_pages: Maximum pages to scrape
        """
        self.li_at_cookie = li_at_cookie
        self.headless = headless
        self.max_profiles = max_profiles
        self.max_pages = max_pages

        # Extractors
        self.card_extractor = CardExtractor()
        self.sidebar_extractor = SidebarExtractor()
        self.experience_extractor = ExperienceExtractor()
        self.education_extractor = EducationExtractor()
        self.skills_extractor = SkillsExtractor()

        # State
        self.profiles_scraped = 0
        self.profiles_skipped = 0

    async def scrape(self, search_url: str) -> list[dict[str, Any]]:
        """Scrape Sales Navigator search results.

        Args:
            search_url: Sales Navigator search URL

        Returns:
            List of profile dicts with full data
        """
        log.info(f"Starting Sales Nav scrape: {search_url}")
        log.info(f"Limits: {self.max_profiles} profiles, {self.max_pages} pages")

        all_profiles = []

        async with async_playwright() as p:
            # Launch browser with cookie
            browser = await p.chromium.launch(headless=self.headless)
            context = await self._create_context_with_cookie(browser)
            page = await context.new_page()

            try:
                # Navigate to search
                log.info("Navigating to Sales Navigator search...")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                await self._delay("page_load")

                # Check if logged in
                if "/login" in page.url:
                    log.error("Redirected to login — cookie invalid or expired")
                    raise RuntimeError("LinkedIn cookie invalid or expired")

                log.info("✓ Page loaded")

                # Wait for results
                await self._wait_for_results(page)
                log.info("✓ Search results loaded")

                # Main scraping loop
                current_page = 1

                while current_page <= self.max_pages:
                    log.info(f"Processing page {current_page}...")

                    # Scroll to load all results
                    await self._scroll_to_load_all(page)

                    # Get all profile cards
                    cards = await self._get_all_profile_cards(page)

                    if not cards:
                        log.warning("No profiles found on this page")
                        break

                    log.info(f"Found {len(cards)} profiles on page {current_page}")

                    # Extract each profile
                    for i, card in enumerate(cards):
                        try:
                            profile = await self._parse_profile_card(card, page)

                            if profile:
                                all_profiles.append(profile)
                                self.profiles_scraped += 1

                                log.info(
                                    f"[{i + 1}/{len(cards)}] {profile['full_name']} — {profile['headline'][:50]}"
                                )

                                # Human-like delay
                                await self._delay("between_profiles")

                                # Take break if needed
                                if self.profiles_scraped % 20 == 0:
                                    await self._take_break()

                                # Check limit
                                if self.profiles_scraped >= self.max_profiles:
                                    log.info("Max profiles reached")
                                    break

                        except Exception as e:
                            log.error(f"Error processing profile {i + 1}: {e}")
                            continue

                    # Check if we should continue
                    if self.profiles_scraped >= self.max_profiles:
                        break

                    # Move to next page
                    if await self._has_next_page(page):
                        log.info("Moving to next page...")
                        await self._go_to_next_page(page)
                        await self._delay("page_load")
                        current_page += 1
                    else:
                        log.info("No more pages available")
                        break

            finally:
                await context.close()
                await browser.close()

        log.info(f"Scraping complete: {len(all_profiles)} profiles extracted")
        return all_profiles

    async def _create_context_with_cookie(self, browser: Browser) -> BrowserContext:
        """Create browser context with LinkedIn cookie."""
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )

        # Add LinkedIn cookie
        await context.add_cookies(
            [
                {
                    "name": "li_at",
                    "value": self.li_at_cookie,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                }
            ]
        )

        return context

    async def _wait_for_results(self, page: Page) -> None:
        """Wait for search results to load."""
        # Global `li.artdeco-list__item` also matches filter/sidebar lists.
        # A real lead link inside Sales Navigator's result scroller is the
        # stable readiness signal.
        try:
            await page.wait_for_selector(
                '#search-results-container a[href*="/sales/lead/"], '
                '[data-x--search-results-container] a[href*="/sales/lead/"]',
                timeout=10_000,
            )
            return
        except Exception:
            pass
        for selector in SEARCH_SELECTORS["profile_cards"]:
            try:
                await page.wait_for_selector(selector, timeout=10000)
                log.debug(f"Found results using selector: {selector}")
                return
            except Exception:
                continue

        raise RuntimeError("Search results did not load")

    async def _get_all_profile_cards(self, page: Page) -> list:
        """Get all profile cards from the search results page."""
        query_container = getattr(page, "query_selector", None)
        container = await query_container(
            "#search-results-container, [data-x--search-results-container]"
        ) if query_container else None
        if container:
            cards = await container.query_selector_all("li.artdeco-list__item")
            lead_cards = [
                card for card in cards
                if await card.query_selector('a[href*="/sales/lead/"]')
            ]
            if lead_cards:
                log.debug("Found %s lead cards in results container", len(lead_cards))
                return lead_cards
        for selector in SEARCH_SELECTORS["profile_cards"]:
            cards = await page.query_selector_all(selector)
            lead_cards = [
                card for card in cards
                if await card.query_selector('a[href*="/sales/lead/"]')
            ]
            if lead_cards:
                log.debug(f"Found {len(lead_cards)} cards using selector: {selector}")
                return lead_cards

        return []

    async def _parse_profile_card(self, card, page: Page) -> Optional[dict[str, Any]]:
        """Parse a profile card and extract all data."""
        try:
            # STEP 1: Get expected data from card BEFORE clicking
            expected_name = await self.card_extractor.extract_name(card)
            expected_company = await self.card_extractor.extract_company(card)
            card_url = await self.card_extractor.extract_profile_url(card)
            visible = await self.card_extractor.extract_visible_details(card)
            log.info("SalesNav detailed parse: card=%s", expected_name or "unknown")
            card_url = str(visible.get("salesnav_url") or card_url)

            log.debug(f"Clicking profile: {expected_name or '(empty)'} at {expected_company or '(empty)'}")

            # Card fields are reliable baseline data. Sidebar adds detail when
            # it is available, but a slow or absent sidebar must not discard a
            # valid search result.
            profile_url = str(visible.get("linkedin_url") or "")
            full_name = expected_name
            headline = await self.card_extractor.extract_headline(card)
            current_company = expected_company
            location = await self.card_extractor.extract_location(card)
            about = str(visible.get("about") or "")
            experience = self._parse_card_experience(str(visible.get("experience") or ""))
            education: list[dict[str, Any]] = []
            skills: list[str] = []
            languages: list[str] = []

            # STEP 2: Open drawer unless browser-agent already opened exact
            # live card.  Re-clicking its name anchor closes/toggles drawer.
            drawer_text = ""
            drawer = await page.query_selector("div.lead-sidesheet")
            if drawer:
                drawer_text = await drawer.text_content() or ""
            drawer_matches = bool(
                expected_name
                and re.search(
                    rf"Basic lead information for\s+{re.escape(expected_name.rstrip('.'))}(?:\.)*",
                    drawer_text,
                    re.IGNORECASE,
                )
            )
            if not drawer_matches:
                await self._click_profile_card(card, page, expected_name=expected_name)
            log.info("SalesNav detailed parse: click finished card=%s", expected_name or "unknown")

            # STEP 3: Wait for sidebar to appear
            await self._wait_for_sidebar_to_appear(page)
            log.info("SalesNav detailed parse: drawer wait finished card=%s", expected_name or "unknown")

            # STEP 4: Merge richer sidebar fields without making them required.
            try:
                sidebar_name = await self.sidebar_extractor.extract_name_from_sidebar(page)
                # Presence of the profile-actions button is tied to the lead
                # drawer itself, unlike a generic `aside` selector.  It is a
                # stronger and faster readiness signal than repeatedly fuzzy
                # matching names against the page's navigation rail.
                if expected_name and not await page.query_selector(
                    'button[aria-label="Open actions overflow menu"]'
                ):
                    await self._wait_for_sidebar_to_update(page, expected_name, expected_company)
                log.info("SalesNav detailed parse: drawer matched card=%s", expected_name or "unknown")
                profile_url = profile_url or await self.sidebar_extractor.extract_profile_url_with_retry(page, 3)
                log.info("SalesNav detailed parse: public URL=%s card=%s", bool(profile_url), expected_name or "unknown")
                full_name = sidebar_name or full_name
                headline = await self.sidebar_extractor.extract_headline_from_sidebar(page) or headline
                current_company = await self.sidebar_extractor.extract_company_from_sidebar(page) or current_company
                location = await self.sidebar_extractor.extract_location_from_sidebar(page) or location
                about = await self.sidebar_extractor.extract_about_from_sidebar(page) or about
                experience = await self.experience_extractor.extract_experience_from_sidebar(page) or experience
                education = await self.education_extractor.extract_education_from_sidebar(page) or education
                skills = await self.skills_extractor.extract_skills_from_sidebar(page) or skills
                languages = await self.skills_extractor.extract_languages_from_sidebar(page) or languages
            except Exception as error:
                log.info("Sidebar detail unavailable; saving visible result card: %s", error)

            # Validate required fields
            if not full_name:
                log.warning("Skipping profile: missing required fields (name)")
                return None

            return {
                "full_name": full_name,
                "headline": headline or "",
                "current_company": current_company or "",
                "location": location or "",
                "profile_url": profile_url or "",
                "salesnav_url": card_url or (page.url if "/sales/lead/" in page.url else ""),
                "about": about,
                "experience": experience or [],
                "education": education or [],
                "skills": skills or [],
                "languages": languages or [],
                "visible_links": visible.get("links") or [],
                "source": "linkedin_salesnav",
            }

        except Exception as e:
            log.error(f"Failed to parse profile card: {e}")
            return None

    async def parse_profile_card_fast(self, card, page: Page) -> Optional[dict[str, Any]]:
        """Return all data rendered in a search card without opening its drawer.

        This is the reliable bulk path when Sales Navigator's lead drawer is
        slow.  It keeps the exact Sales Navigator URL and every visible link;
        detailed drawer enrichment remains available as a separate pass.
        """
        try:
            full_name = await self.card_extractor.extract_name(card)
            if not full_name:
                return None
            visible = await self.card_extractor.extract_visible_details(card)
            headline = await self.card_extractor.extract_headline(card)
            current_company = await self.card_extractor.extract_company(card)
            location = await self.card_extractor.extract_location(card)
            salesnav_url = str(visible.get("salesnav_url") or await self.card_extractor.extract_profile_url(card))
            return {
                "full_name": full_name,
                "headline": headline or "",
                "current_company": current_company or "",
                "location": location or "",
                "profile_url": str(visible.get("linkedin_url") or ""),
                "salesnav_url": salesnav_url or (page.url if "/sales/lead/" in page.url else ""),
                "about": str(visible.get("about") or ""),
                "experience": self._parse_card_experience(str(visible.get("experience") or "")),
                "education": [],
                "skills": [],
                "languages": [],
                "visible_links": visible.get("links") or [],
                "source": "linkedin_salesnav",
            }
        except Exception as error:
            log.warning("Fast card parse failed: %s", error)
            return None

    @staticmethod
    def _parse_card_experience(text: str) -> list[dict[str, str]]:
        """Convert card's compact Experience block into one position record."""
        parts = [part.strip(" ·") for part in text.splitlines() if part.strip(" ·")]
        if not parts:
            return []
        duration_parts = [part for part in parts if re.search(r"(?:19|20)\d{2}|\b\d+\s*(?:mo|yr|year)", part, re.I)]
        details = [part for part in parts if part not in duration_parts]
        if len(details) < 2:
            return [{"title": "", "company": "", "duration": " ".join(duration_parts), "raw": " ".join(parts)}]
        return [{
            "title": details[-1],
            "company": details[-2],
            "duration": " ".join(duration_parts),
            "raw": " ".join(parts),
        }]

    async def _click_profile_card(
        self, card, page: Page, *, expected_name: str = ""
    ) -> None:
        """Click on a profile card to open the sidebar."""
        try:
            # Try to find and click the profile link/button
            from app.scrapers.salesnav_selectors import CARD_SELECTORS

            # Image and name anchors share a lead URL.  Only the *name*
            # anchor reliably opens the lead drawer; image clicks can be
            # swallowed by Sales Navigator's virtual results list.
            # This anchor opens the lead drawer.  The preceding image anchor
            # shares the same URL but only changes the main page location.
            preferred = 'a[data-control-name="view_lead_panel_via_search_lead_name"]'
            # Resolve through a Locator, not the virtual-list element handle.
            # LinkedIn replaces individual cards while scrolling; a Locator
            # performs the click against the currently mounted name anchor.
            if expected_name:
                live_card = page.locator(
                    '#search-results-container li.artdeco-list__item'
                ).filter(
                    has=page.locator('a[href*="/sales/lead/"]')
                ).filter(has_text=expected_name).first
                live_name_link = live_card.locator(preferred)
                if await live_name_link.count():
                    await live_name_link.scroll_into_view_if_needed(timeout=3_000)
                    await live_name_link.click(timeout=8_000)
                    log.debug("Clicked live lead name to open sidebar")
                    return
            element = await card.query_selector(preferred)
            if not element:
                links = await card.query_selector_all('a[href*="/sales/lead/"]')
                element = links[-1] if links else None
            if element:
                await element.scroll_into_view_if_needed(timeout=3_000)
                # Use a trusted browser click.  LinkedIn ignores synthetic DOM
                # click events for opening its lead drawer.
                await element.click(timeout=8_000)
                log.debug("Clicked lead name to open sidebar")
                return

            for selector in CARD_SELECTORS["clickable"]:
                element = await card.query_selector(selector)
                if element:
                    # Result cards live in a virtual scroller.  Playwright's
                    # default 30-second click wait can hang the whole run when
                    # LinkedIn replaces a card between lookup and click.  A
                    # forced, bounded click either opens the drawer promptly
                    # or lets us retain the already-parsed card data.
                    await element.scroll_into_view_if_needed(timeout=3_000)
                    await element.click(timeout=5_000, force=True)
                    log.debug("Clicked profile to open sidebar")
                    return

            # Fallback: click the card itself
            await card.click()
            log.debug("Clicked profile card")

        except Exception as error:
            log.warning("Failed to click profile card: %s", error)

    async def _wait_for_sidebar_to_appear(self, page: Page) -> None:
        """Wait for sidebar to appear (without verification)."""
        try:
            await page.wait_for_selector(
                'button[aria-label="Open actions overflow menu"]',
                timeout=5_000,
                state="attached",
            )
            # Give it a moment to start loading content
            await page.wait_for_timeout(TIMEOUTS["after_click"])
            log.debug("✓ Sidebar appeared")
        except Exception:
            log.warning("Sidebar did not appear, proceeding anyway")
            await page.wait_for_timeout(2000)

    async def _wait_for_sidebar_to_update(
        self, page: Page, expected_name: str, expected_company: str
    ) -> None:
        """Wait for sidebar to update with the correct profile.

        Prevents race conditions where we extract data from the wrong profile.
        """
        max_attempts = 15  # 15 seconds max
        last_seen_name = ""

        # Verify the content matches what we clicked
        for i in range(max_attempts):
            await page.wait_for_timeout(TIMEOUTS["sidebar_update"])

            try:
                sidebar_name = await self.sidebar_extractor.extract_name_from_sidebar(page)
                last_seen_name = sidebar_name

                # Fuzzy match (handles slight variations)
                name_match = fuzzy_match(sidebar_name, expected_name)

                if name_match:
                    log.debug(f"✓ Sidebar updated in {i + 1}s: {sidebar_name}")
                    # Give it one more second to fully load all content
                    await page.wait_for_timeout(TIMEOUTS["after_click"])
                    return

                log.debug(
                    f"⏳ Waiting for sidebar to update... ({i + 1}s) Expected: {expected_name}, Got: {sidebar_name}"
                )

            except Exception:
                # Continue waiting
                log.debug(f"⏳ Waiting for sidebar content... ({i + 1}s)")

        # If we get here, sidebar didn't update - throw error
        raise RuntimeError(
            f"Sidebar did not update after 15s.\n"
            f"Expected: {expected_name}\n"
            f"Got: {last_seen_name or 'no name found'}"
        )

    async def _scroll_to_load_all(self, page: Page) -> None:
        """Render every result card on the current Sales Navigator page.

        Sales Navigator virtualizes cards inside ``#search-results-container``.
        Scrolling ``window`` leaves most cards unmounted, which previously made
        a 63-result search stop after 37 records. Scroll real list container;
        never enlarge headed Chromium window because it can move off-screen in
        noVNC.
        """
        await page.evaluate(
            """
            async () => {
                const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
                const container = document.querySelector('#search-results-container')
                    || document.querySelector('[data-x--search-results-container]');
                if (!container) {
                    window.scrollTo(0, document.body.scrollHeight);
                    await pause(300);
                    return;
                }
                let stablePasses = 0;
                let previousHeight = -1;
                for (let attempt = 0; attempt < 20; attempt += 1) {
                    container.scrollTop = container.scrollHeight;
                    await pause(300);
                    const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 2;
                    if (atBottom && container.scrollHeight === previousHeight) {
                        stablePasses += 1;
                        if (stablePasses >= 2) break;
                    } else {
                        stablePasses = 0;
                    }
                    previousHeight = container.scrollHeight;
                }
                container.scrollTop = 0;
                await pause(200);
            }
        """
        )
        await page.wait_for_timeout(500)

    async def _has_next_page(self, page: Page) -> bool:
        """Check if there's a next page."""
        try:
            next_button_selectors = [
                'button.artdeco-pagination__button--next',
                'button[data-test-pagination-page-btn="next"]',
                'button[aria-label="Next"]',
            ]

            for selector in next_button_selectors:
                buttons = await page.query_selector_all(selector)
                for button in buttons:
                    if await button.is_visible() and not await button.is_disabled():
                        return True

            return False
        except Exception:
            return False

    async def _first_result_signature(self, cards: list) -> str:
        """Return stable-enough identity for first visible result card.

        Sales Navigator pagination is a client-side update. It commonly keeps
        analytics requests open forever, so `networkidle` is not a completion
        signal. A changed first result (or URL) is.
        """
        if not cards:
            return ""
        card = cards[0]
        try:
            lead_link = await card.query_selector('a[href*="/sales/lead/"]')
            if lead_link:
                href = await lead_link.get_attribute("href")
                if href:
                    return href
            text = await card.text_content()
            return " ".join((text or "").split())[:500]
        except Exception:
            return ""

    async def _current_pagination_label(self, page: Page) -> str:
        """Read selected Sales Navigator page, if pagination exposes it."""
        try:
            buttons = await page.query_selector_all(
                'button[aria-current="true"], button[aria-current="page"]'
            )
            for button in buttons:
                if await button.is_visible():
                    return await button.get_attribute("aria-label") or ""
        except Exception:
            pass
        return ""

    async def _wait_for_next_results(
        self,
        page: Page,
        *,
        previous_url: str,
        previous_signature: str,
        previous_page_label: str = "",
        timeout_ms: int = 20_000,
    ) -> None:
        """Wait for Sales Navigator results to advance after pagination."""
        elapsed_ms = 0
        while elapsed_ms < timeout_ms:
            cards = await self._get_all_profile_cards(page)
            signature = await self._first_result_signature(cards)
            current_page_label = await self._current_pagination_label(page)
            if cards and (
                page.url != previous_url
                or signature != previous_signature
                or (previous_page_label and current_page_label != previous_page_label)
            ):
                return
            await page.wait_for_timeout(500)
            elapsed_ms += 500
        raise RuntimeError("Next page did not show new Sales Navigator results")

    async def _go_to_next_page(self, page: Page) -> None:
        """Navigate to next page."""
        next_button_selectors = [
            'button.artdeco-pagination__button--next',
            'button[data-test-pagination-page-btn="next"]',
            'button[aria-label="Next"]',
        ]

        for selector in next_button_selectors:
            buttons = await page.query_selector_all(selector)
            for button in buttons:
                if await button.is_visible() and not await button.is_disabled():
                    previous_url = page.url
                    previous_cards = await self._get_all_profile_cards(page)
                    previous_signature = await self._first_result_signature(previous_cards)
                    previous_page_label = await self._current_pagination_label(page)
                    await button.scroll_into_view_if_needed()
                    await button.click()
                    await self._wait_for_next_results(
                        page,
                        previous_url=previous_url,
                        previous_signature=previous_signature,
                        previous_page_label=previous_page_label,
                    )
                    return

        raise RuntimeError("Could not find next page button")

    async def _delay(self, delay_type: str) -> None:
        """Human-like delay."""
        delays = {
            "between_profiles": (3000, 7000),  # 3-7 seconds
            "page_load": (2000, 4000),  # 2-4 seconds
            "scrolling": (1000, 3000),  # 1-3 seconds
        }

        min_ms, max_ms = delays.get(delay_type, (1000, 2000))
        delay_ms = random.randint(min_ms, max_ms)
        await asyncio.sleep(delay_ms / 1000)

    async def _take_break(self) -> None:
        """Take a break (every 20 profiles)."""
        break_duration = random.randint(30000, 90000)  # 30-90 seconds
        log.info(f"Taking break for {break_duration // 1000}s...")
        await asyncio.sleep(break_duration / 1000)
