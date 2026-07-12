"""Sales Navigator education extractor — extracts education history from sidebar."""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from app.core.logging import get_logger
from app.scrapers.salesnav_selectors import SIDEBAR_SELECTORS
from app.scrapers.salesnav_text_utils import sanitize_text

log = get_logger(__name__)


class EducationExtractor:
    """Extracts education history from sidebar."""

    async def extract_education_from_sidebar(
        self, page: Page
    ) -> Optional[list[dict[str, str]]]:
        """Extract education section from sidebar.

        Returns:
            List of education entries: [{"school": "...", "degree": "...", "field": "...", "years": "..."}]
        """
        try:
            # Find sidebar container
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return None

            education = []

            # Find all education entry elements
            education_entries = await container.query_selector_all(
                'li[class*="education-entry"]'
            )

            if not education_entries:
                log.debug("No education entries found using DOM selector")
                return None

            log.debug(f"Found {len(education_entries)} education entries using DOM")

            # Extract data from each entry
            for entry in education_entries:
                try:
                    # Extract school name
                    school_element = await entry.query_selector(
                        '[data-anonymize="school-name"]'
                    )
                    school = await school_element.text_content() if school_element else None

                    # Extract degree
                    degree_element = await entry.query_selector('[data-anonymize="degree"]')
                    degree = await degree_element.text_content() if degree_element else None

                    # Extract field of study
                    field_element = await entry.query_selector(
                        '[data-anonymize="field-of-study"]'
                    )
                    field = await field_element.text_content() if field_element else None

                    # Extract years (e.g., "2015 - 2019")
                    years_element = await entry.query_selector('span[class*="date-range"]')
                    years = await years_element.text_content() if years_element else None

                    # Only add if we have at least school name
                    if school:
                        clean_school = sanitize_text(school)

                        if len(clean_school) >= 2:
                            edu_entry = {"school": clean_school}

                            if degree:
                                edu_entry["degree"] = sanitize_text(degree)

                            if field:
                                edu_entry["field"] = sanitize_text(field)

                            if years:
                                edu_entry["years"] = sanitize_text(years)

                            education.append(edu_entry)
                            log.debug(f"Extracted: {clean_school}")

                except Exception as e:
                    log.debug(f"Error extracting individual education entry: {e}")
                    continue

            if education:
                log.info(f"Extracted {len(education)} education entries")
                return education

            log.debug("No valid education entries extracted")
            return None

        except Exception as e:
            log.error(f"Error extracting education: {e}")
            return None
