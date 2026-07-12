"""Sales Navigator sidebar extractor — extracts detailed data from sidebar."""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from app.core.logging import get_logger
from app.scrapers.salesnav_selectors import SIDEBAR_SELECTORS, TIMEOUTS
from app.scrapers.salesnav_text_utils import PATTERNS, sanitize_text

log = get_logger(__name__)


class SidebarExtractor:
    """Extracts detailed data from the sidebar (profile detail view)."""

    async def extract_name_from_sidebar(self, page: Page) -> str:
        """Extract name from sidebar."""
        try:
            # Try to find aside first, then fallback to lead-details div
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                log.debug("No aside found, trying lead-details div")
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                log.warning("No sidebar container found")
                return ""

            container_text = await container.text_content()
            if not container_text:
                log.warning("Sidebar container has no text content")
                return ""

            log.debug(f"Sidebar text length: {len(container_text)} characters")

            # Look for name after "Basic lead information for"
            match = PATTERNS["name_after_basic_info"].search(container_text)
            if match:
                log.debug("Found name from 'Basic lead information for' pattern")
                return sanitize_text(match.group(1))

            # Alternative: after "Profile details loaded for"
            match = PATTERNS["name_after_profile_details"].search(container_text)
            if match:
                log.debug("Found name from 'Profile details loaded for' pattern")
                return sanitize_text(match.group(1))

            # Fallback: look for name pattern after connection degree
            lines = [l.strip() for l in container_text.split("\n") if l.strip()]
            log.debug(f"Parsed {len(lines)} lines from sidebar")

            for i, line in enumerate(lines):
                if PATTERNS["connection_degree"].match(line):
                    # Next line after connection degree might be name
                    if i + 1 < len(lines):
                        potential_name = lines[i + 1]
                        if PATTERNS["name_pattern"].match(potential_name):
                            log.debug("Found name after connection degree")
                            return sanitize_text(potential_name)

            log.warning("Could not find name in sidebar text")
            return ""
        except Exception as e:
            log.error(f"Error extracting name from sidebar: {e}")
            return ""

    async def extract_headline_from_sidebar(self, page: Page) -> str:
        """Extract headline from sidebar."""
        try:
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return ""

            container_text = await container.text_content()
            if not container_text:
                return ""

            # Headline appears after connection degree and before location
            match = PATTERNS["headline"].search(container_text)
            if match:
                headline = match.group(2).strip()
                if 5 < len(headline) < 200:
                    log.debug("Found headline between connection degree and location")
                    return sanitize_text(headline)

            # Alternative: look after connection degree line
            lines = [l.strip() for l in container_text.split("\n") if l.strip()]
            for i, line in enumerate(lines):
                if PATTERNS["connection_degree"].match(line):
                    if i + 1 < len(lines):
                        potential_headline = lines[i + 1]
                        # Skip if it's a location
                        if (
                            "Area" not in potential_headline
                            and "connections" not in potential_headline
                            and "Viewed" not in potential_headline
                            and 5 < len(potential_headline) < 200
                        ):
                            log.debug("Found headline after connection degree line")
                            return sanitize_text(potential_headline)

            return ""
        except Exception as e:
            log.error(f"Error extracting headline: {e}")
            return ""

    async def extract_company_from_sidebar(self, page: Page) -> str:
        """Extract company from sidebar."""
        try:
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return ""

            container_text = await container.text_content()
            if not container_text:
                return ""

            # Look for "Title at Company" pattern
            match = PATTERNS["company"].search(container_text)
            if match:
                company = match.group(1).strip()
                if (
                    "Area" not in company
                    and "connections" not in company
                    and not PATTERNS["connection_degree"].match(company)
                    and 1 < len(company) < 100
                ):
                    log.debug("Found company from 'at' pattern")
                    return sanitize_text(company)

            # Fallback: look for "Title at Company" in lines
            lines = [l.strip() for l in container_text.split("\n") if l.strip()]
            for line in lines:
                if " at " in line:
                    parts = line.split(" at ")
                    if len(parts) == 2:
                        company = parts[1].strip()
                        if 1 < len(company) < 100:
                            log.debug("Found company from job title line")
                            return sanitize_text(company)

            return ""
        except Exception as e:
            log.error(f"Error extracting company: {e}")
            return ""

    async def extract_location_from_sidebar(self, page: Page) -> str:
        """Extract location from sidebar."""
        try:
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return ""

            container_text = await container.text_content()
            if not container_text:
                return ""

            lines = [l.strip() for l in container_text.split("\n") if l.strip()]

            for line in lines:
                # Skip non-location lines
                if any(
                    x in line
                    for x in ["profile picture", "image", "reachable", "Viewed:"]
                ):
                    continue

                # Check if line looks like a location
                if (
                    (
                        "Metropolitan Area" in line
                        or "Area" in line
                        or "," in line
                        or any(
                            country in line
                            for country in [
                                "Cyprus",
                                "Poland",
                                "Armenia",
                                "Georgia",
                                "Serbia",
                                "Belarus",
                                "Kazakhstan",
                                "Russia",
                                "United Arab Emirates",
                                "United States",
                                "United Kingdom",
                            ]
                        )
                    )
                    and "connections" not in line
                    and "Viewed" not in line
                    and not PATTERNS["connection_degree"].match(line)
                    and "//" not in line
                    and 3 < len(line) < 100
                ):
                    log.debug("Found location from text parsing")
                    return sanitize_text(line)

            return ""
        except Exception as e:
            log.error(f"Error extracting location: {e}")
            return ""

    async def extract_profile_url_with_retry(
        self, page: Page, max_retries: int = 3
    ) -> str:
        """Extract profile URL from sidebar with retry logic."""
        for attempt in range(max_retries):
            url = await self._extract_profile_url_from_sidebar(page)

            if url and "/in/" in url:
                log.debug(f"Found LinkedIn URL on attempt {attempt + 1}")
                return url

            if attempt < max_retries - 1:
                log.debug(f"Retry {attempt + 1}: LinkedIn URL not found, waiting...")
                await page.wait_for_timeout(TIMEOUTS["retry_delay"])

        # Try alternative methods
        return await self._extract_url_from_alternatives(page)

    async def _extract_profile_url_from_sidebar(self, page: Page) -> str:
        """Extract profile URL from sidebar."""
        try:
            # Look for actual LinkedIn profile URL (not sales/lead)
            for selector in SIDEBAR_SELECTORS["profile_url"]:
                element = await page.query_selector(selector)
                if element:
                    href = await element.get_attribute("href")
                    if href and "/in/" in href:
                        log.debug(f"Found profile URL with selector: {selector}")
                        # Construct full URL if relative
                        if href.startswith("/"):
                            return f"https://www.linkedin.com{href}"
                        return href

            # Fallback: get sales lead URL from page URL
            url = page.url
            if "/sales/lead/" in url:
                return url

            return ""
        except Exception:
            return ""

    async def _extract_url_from_alternatives(self, page: Page) -> str:
        """Extract URL from alternative methods."""
        # Method 1: Search in all links
        try:
            all_links = await page.query_selector_all(
                'aside a[href*="/in/"], div[class*="lead-details"] a[href*="/in/"]'
            )
            for link in all_links:
                href = await link.get_attribute("href")
                if href and "/in/" in href and "/company/" not in href:
                    log.debug("Found LinkedIn URL from all links search")
                    return href
        except Exception:
            pass

        # No LinkedIn profile URL found
        log.warning("No LinkedIn profile URL found (profile may have privacy settings)")
        return ""

    async def extract_about_from_sidebar(self, page: Page) -> Optional[str]:
        """Extract about section from sidebar."""
        try:
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return None

            container_text = await container.text_content()
            if not container_text:
                return None

            # Look for "About" section
            import re

            match = re.search(
                r"About\s*\n\s*([^\n]+(?:\n(?!(?:Relationship|Recent activity|experience|Education|Featured skills|Languages))[^\n]+)*)",
                container_text,
                re.IGNORECASE,
            )
            if match:
                about = match.group(1).strip()
                # Remove "Show more" text if present
                clean_about = re.sub(r"…\s*Show more$", "", about, flags=re.IGNORECASE).strip()
                if len(clean_about) > 10:
                    log.debug("Found about section")
                    return sanitize_text(clean_about)

            return None
        except Exception:
            log.debug("Error extracting about section")
            return None
