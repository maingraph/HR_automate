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
        for selector in SEARCH_SELECTORS["profile_cards"]:
            cards = await page.query_selector_all(selector)
            if cards:
                log.debug(f"Found {len(cards)} cards using selector: {selector}")
                return cards

        return []

    async def _parse_profile_card(self, card, page: Page) -> Optional[dict[str, Any]]:
        """Parse a profile card and extract all data."""
        try:
            # STEP 1: Get expected data from card BEFORE clicking
            expected_name = await self.card_extractor.extract_name(card)
            expected_company = await self.card_extractor.extract_company(card)
            card_url = await self.card_extractor.extract_profile_url(card)

            log.debug(f"Clicking profile: {expected_name or '(empty)'} at {expected_company or '(empty)'}")

            # STEP 2: Click on the profile card to open sidebar
            await self._click_profile_card(card, page)

            # STEP 3: Wait for sidebar to appear
            await self._wait_for_sidebar_to_appear(page)

            # STEP 4: If card name is empty, extract from sidebar for verification
            if not expected_name or not expected_name.strip():
                log.debug("Card name empty, extracting from sidebar for verification")
                expected_name = await self.sidebar_extractor.extract_name_from_sidebar(page)

                if not expected_name:
                    log.warning("Could not extract name from sidebar either")
                    return None

                log.debug(f"Using sidebar name for verification: {expected_name}")

            # STEP 5: Verify sidebar updated with correct profile
            await self._wait_for_sidebar_to_update(page, expected_name, expected_company)

            # STEP 6: Extract data from sidebar
            profile_url = await self.sidebar_extractor.extract_profile_url_with_retry(page, 3)
            full_name = await self.sidebar_extractor.extract_name_from_sidebar(page)
            headline = await self.sidebar_extractor.extract_headline_from_sidebar(page)
            current_company = await self.sidebar_extractor.extract_company_from_sidebar(page)
            location = await self.sidebar_extractor.extract_location_from_sidebar(page)
            about = await self.sidebar_extractor.extract_about_from_sidebar(page)

            # Extract detailed data
            experience = await self.experience_extractor.extract_experience_from_sidebar(page)
            education = await self.education_extractor.extract_education_from_sidebar(page)
            skills = await self.skills_extractor.extract_skills_from_sidebar(page)
            languages = await self.skills_extractor.extract_languages_from_sidebar(page)

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
                "source": "linkedin_salesnav",
            }

        except Exception as e:
            log.error(f"Failed to parse profile card: {e}")
            return None

    async def _click_profile_card(self, card, page: Page) -> None:
        """Click on a profile card to open the sidebar."""
        try:
            # Try to find and click the profile link/button
            from app.scrapers.salesnav_selectors import CARD_SELECTORS

            for selector in CARD_SELECTORS["clickable"]:
                element = await card.query_selector(selector)
                if element:
                    await element.click()
                    log.debug("Clicked profile to open sidebar")
                    return

            # Fallback: click the card itself
            await card.click()
            log.debug("Clicked profile card")

        except Exception:
            log.warning("Failed to click profile card")

    async def _wait_for_sidebar_to_appear(self, page: Page) -> None:
        """Wait for sidebar to appear (without verification)."""
        try:
            await page.wait_for_selector(
                ", ".join(SIDEBAR_SELECTORS["container"]),
                timeout=TIMEOUTS["sidebar_appear"],
                state="visible",
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
        """Scroll to load all results on page."""
        await page.evaluate(
            """
            async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 100;
                    const timer = setInterval(() => {
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if (totalHeight >= document.body.scrollHeight) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 100);
                });
            }
        """
        )
        await page.wait_for_timeout(1000)

    async def _has_next_page(self, page: Page) -> bool:
        """Check if there's a next page."""
        try:
            next_button_selectors = [
                'button[aria-label="Next"]',
                'button.artdeco-pagination__button--next',
                'button[data-test-pagination-page-btn="next"]',
            ]

            for selector in next_button_selectors:
                button = await page.query_selector(selector)
                if button:
                    is_disabled = await button.is_disabled()
                    if not is_disabled:
                        return True

            return False
        except Exception:
            return False

    async def _go_to_next_page(self, page: Page) -> None:
        """Navigate to next page."""
        next_button_selectors = [
            'button[aria-label="Next"]',
            'button.artdeco-pagination__button--next',
            'button[data-test-pagination-page-btn="next"]',
        ]

        for selector in next_button_selectors:
            button = await page.query_selector(selector)
            if button:
                is_disabled = await button.is_disabled()
                if not is_disabled:
                    await button.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)
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
