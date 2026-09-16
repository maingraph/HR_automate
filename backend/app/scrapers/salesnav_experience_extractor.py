"""Sales Navigator experience extractor — extracts work history from sidebar."""
from __future__ import annotations

import re
from typing import Optional

from playwright.async_api import Page

from app.core.logging import get_logger
from app.scrapers.salesnav_semantic_sections import read_profile_section
from app.scrapers.salesnav_selectors import SIDEBAR_SELECTORS
from app.scrapers.salesnav_text_utils import sanitize_text

log = get_logger(__name__)


class ExperienceExtractor:
    """Extracts experience/work history from sidebar."""

    async def extract_experience_from_sidebar(
        self, page: Page
    ) -> Optional[list[dict[str, str]]]:
        """Extract experience section from sidebar.

        Returns:
            List of experience entries: [{"title": "...", "company": "...", "duration": "...", "location": "..."}]
        """
        try:
            # Find sidebar container
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return await self._extract_semantic_experience(page)

            # Try to expand all experiences first
            await self._expand_all_experiences(page)

            experience = []

            # Find all experience entry elements
            experience_entries = await container.query_selector_all(
                'li[class*="experience-entry"]'
            )

            if not experience_entries:
                log.debug("No experience entries found using DOM selector")
                return await self._extract_semantic_experience(page)

            log.debug(f"Found {len(experience_entries)} experience entries using DOM")

            # Extract data from each entry
            for entry in experience_entries:
                try:
                    # Extract title
                    title_element = await entry.query_selector('[data-anonymize="job-title"]')
                    title = await title_element.text_content() if title_element else None

                    # Extract company
                    company_element = await entry.query_selector(
                        '[data-anonymize="company-name"]'
                    )
                    company = (
                        await company_element.text_content() if company_element else None
                    )

                    # Extract date range
                    date_elements = await entry.query_selector_all(
                        'span[class*="aPktgOMiFRRKWEmHFKHOkBGcyUKfUHAcqyQI"]'
                    )
                    date_range = None
                    if date_elements:
                        date_range = await date_elements[0].text_content()

                    # Extract duration (e.g., "2 yrs")
                    duration = None
                    if date_range:
                        # Find parent <p> element and get all text
                        date_parent = await entry.query_selector(
                            'p[class*="_bodyText_1e5nen"][class*="_sizeXSmall_1e5nen"]:has(span[class*="aPktgOMiFRRKWEmHFKHOkBGcyUKfUHAcqyQI"])'
                        )
                        if date_parent:
                            full_date_text = await date_parent.text_content()
                            if full_date_text:
                                # Extract duration pattern like "2 yrs" or "1 yr 3 mos"
                                import re

                                duration_match = re.search(
                                    r"(\d+\s+(?:yr|mo|year|month)s?(?:\s+\d+\s+(?:yr|mo|year|month)s?)?)",
                                    full_date_text,
                                    re.IGNORECASE,
                                )
                                if duration_match:
                                    duration = duration_match.group(1)

                    # Extract location
                    location_element = await entry.query_selector(
                        'p[class*="ynAatejktGJGyTaATOFatmgcBydwPXbc"]'
                    )
                    location = (
                        await location_element.text_content() if location_element else None
                    )

                    # Only add if we have at least title and company
                    if title and company:
                        clean_title = sanitize_text(title)
                        clean_company = sanitize_text(company)

                        # Sales Navigator rotates generated class names for date
                        # spans.  The complete entry's rendered text is stable,
                        # though, and contains the date range and tenure.
                        if not date_range:
                            entry_text = sanitize_text(await entry.inner_text() or "")
                            date_match = re.search(
                                r"(?:[A-Z][a-z]{2}\s+)?(?:19|20)\d{2}\s*[–-]\s*"
                                r"(?:Present|(?:[A-Z][a-z]{2}\s+)?(?:19|20)\d{2})"
                                r"(?:\s*[·•]\s*\d+\s*(?:yr|yrs|year|years|mo|mos|month|months).*)?",
                                entry_text,
                                re.IGNORECASE,
                            )
                            if date_match:
                                date_range = date_match.group(0)

                        # Skip if title or company is too short
                        if len(clean_title) >= 3 and len(clean_company) >= 2:
                            exp_entry = {
                                "title": clean_title,
                                "company": clean_company,
                                "duration": "",  # Default to empty string
                            }

                            if date_range:
                                clean_date = sanitize_text(date_range)
                                if duration:
                                    exp_entry["duration"] = (
                                        f"{clean_date} ({sanitize_text(duration)})"
                                    )
                                else:
                                    exp_entry["duration"] = clean_date

                            if location:
                                exp_entry["location"] = sanitize_text(location)

                            experience.append(exp_entry)
                            log.debug(f"Extracted: {clean_title} at {clean_company}")

                except Exception as e:
                    log.debug(f"Error extracting individual experience entry: {e}")
                    continue

            if experience:
                log.info(f"Extracted {len(experience)} experience entries")
                return experience

            log.debug("No valid experience entries extracted")
            return await self._extract_semantic_experience(page)

        except Exception as e:
            log.error(f"Error extracting experience: {e}")
            return await self._extract_semantic_experience(page)

    async def _extract_semantic_experience(self, page: Page) -> Optional[list[dict[str, str]]]:
        """Fallback for current profile drawer markup with generated classes."""
        try:
            section = await read_profile_section(page, r"experience$")
            entries: list[dict[str, str]] = []
            for item in section.get("items") or []:
                title = sanitize_text(next(iter(item.get("headings") or []), ""))
                company = sanitize_text(next(
                    (link.get("text", "") for link in item.get("links") or [] if link.get("text")),
                    "",
                ))
                if not title or not company:
                    continue
                paragraphs = [sanitize_text(value) for value in item.get("paragraphs") or []]
                date_parts = [value for value in paragraphs if any(char.isdigit() for char in value)]
                entry = {
                    "title": title,
                    "company": company,
                    "duration": date_parts[0] if date_parts else "",
                }
                location = next((value for value in paragraphs if "," in value), "")
                if location:
                    entry["location"] = location
                entries.append(entry)
            if entries:
                return entries

            # Modern drawer groups entries in divs, not list items.  Its
            # rendered order is title, company, date/duration, location.
            lines = [sanitize_text(value) for value in section.get("lines") or []]
            date_re = re.compile(r"(?:19|20)\d{2}.*?(?:Present|(?:19|20)\d{2})", re.I)
            for index, value in enumerate(lines):
                if not date_re.search(value) or index < 2:
                    continue
                title = lines[index - 2]
                company = lines[index - 1]
                if title.lower().endswith("experience") or company.lower().endswith("experience"):
                    continue
                entry = {"title": title, "company": company, "duration": value}
                if index + 1 < len(lines) and "," in lines[index + 1]:
                    entry["location"] = lines[index + 1]
                if entry not in entries:
                    entries.append(entry)
            return entries or None
        except Exception:
            log.debug("No semantic experience section found")
            return None

    async def _expand_all_experiences(self, page: Page) -> None:
        """Expand all experiences by clicking 'Show more' or 'Show all' button."""
        try:
            # Possible selectors for "Show more" button
            show_more_selectors = [
                'button:has-text("Show all")',
                'button:has-text("Show more")',
                'button[aria-label*="Show all"]',
                'button[aria-label*="Show more"]',
                'button[aria-label*="experience"]',
                'aside button:has-text("Show")',
                'div[class*="lead-details"] button:has-text("Show")',
            ]

            for selector in show_more_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        # Check if button is visible
                        is_visible = await button.is_visible()
                        if not is_visible:
                            continue

                        # Get button text to verify it's the right button
                        button_text = await button.text_content()
                        if not button_text:
                            continue

                        # Only click if it mentions "experience" or "all" or "Show more"
                        lower_text = button_text.lower()
                        if (
                            "experience" in lower_text
                            or "all" in lower_text
                            or "show more" in lower_text
                        ):
                            log.debug(f'Found "Show more" button: "{button_text.strip()}"')

                            # Use JS native click to avoid sidebar closing issues
                            await button.evaluate("btn => btn.click()")

                            log.debug('Clicked "Show more" button to expand experiences')

                            # Wait for content to expand
                            await page.wait_for_timeout(800)
                            return

                except Exception:
                    continue

            log.debug(
                'No "Show more" button found for experiences (all may already be visible)'
            )

        except Exception:
            log.debug("Error expanding experiences, continuing with visible entries")
