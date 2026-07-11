"""Sales Navigator card extractor — extracts data from profile cards in search results."""
from __future__ import annotations

from typing import Optional

from playwright.async_api import ElementHandle

from app.core.logging import get_logger
from app.scrapers.salesnav_selectors import CARD_SELECTORS
from app.scrapers.salesnav_text_utils import PATTERNS, sanitize_text

log = get_logger(__name__)


class CardExtractor:
    """Extracts data from profile cards in search results."""

    async def extract_name(self, card: ElementHandle) -> str:
        """Extract name from profile card."""
        for selector in CARD_SELECTORS["name"]:
            try:
                element = await card.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and text.strip():
                        return sanitize_text(text)
            except Exception:
                continue
        return ""

    async def extract_headline(self, card: ElementHandle) -> str:
        """Extract headline from profile card."""
        for selector in CARD_SELECTORS["headline"]:
            try:
                element = await card.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and text.strip():
                        return sanitize_text(text)
            except Exception:
                continue
        return ""

    async def extract_company(self, card: ElementHandle) -> str:
        """Extract company from profile card."""
        for selector in CARD_SELECTORS["company"]:
            try:
                element = await card.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and text.strip():
                        return sanitize_text(text)
            except Exception:
                continue

        # Fallback: extract from headline if not found
        headline = await self.extract_headline(card)
        if " at " in headline:
            parts = headline.split(" at ")
            if len(parts) > 1:
                return sanitize_text(parts[1])

        return ""

    async def extract_location(self, card: ElementHandle) -> str:
        """Extract location from profile card."""
        for selector in CARD_SELECTORS["location"]:
            try:
                elements = await card.query_selector_all(selector)
                for element in elements:
                    text = await element.text_content()
                    if text and text.strip() and "•" not in text:
                        sanitized = sanitize_text(text)
                        # Check if it looks like a location
                        if "," in sanitized or "Area" in sanitized:
                            return sanitized
            except Exception:
                continue
        return ""

    async def extract_profile_url(self, card: ElementHandle) -> str:
        """Extract profile URL from profile card."""
        for selector in CARD_SELECTORS["profile_url"]:
            try:
                element = await card.query_selector(selector)
                if element:
                    href = await element.get_attribute("href")
                    if href:
                        # Construct full URL if relative
                        if href.startswith("/"):
                            return f"https://www.linkedin.com{href}"
                        return href
            except Exception:
                continue
        return ""

    async def extract_connection_degree(self, card: ElementHandle) -> str:
        """Extract connection degree from profile card."""
        try:
            text = await card.text_content()
            if not text:
                return "Unknown"

            # Look for degree indicators
            match = PATTERNS["connection_degree"].search(text)
            if match:
                return f"{match.group(1)}{match.group(2)}"

            # Check for specific text
            if "1st" in text:
                return "1st"
            if "2nd" in text:
                return "2nd"
            if "3rd" in text:
                return "3rd"
            if "3rd+" in text:
                return "3rd+"

            return "Unknown"
        except Exception:
            return "Unknown"

    async def extract_shared_connections(self, card: ElementHandle) -> int:
        """Extract shared connections count from profile card."""
        try:
            text = await card.text_content()
            if not text:
                return 0

            match = PATTERNS["shared_connections"].search(text)
            if match:
                return int(match.group(1))

            return 0
        except Exception:
            return 0
