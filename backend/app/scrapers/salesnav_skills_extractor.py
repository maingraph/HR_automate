"""Sales Navigator skills extractor — extracts skills and languages from sidebar."""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from app.core.logging import get_logger
from app.scrapers.salesnav_selectors import SIDEBAR_SELECTORS
from app.scrapers.salesnav_text_utils import sanitize_text

log = get_logger(__name__)


class SkillsExtractor:
    """Extracts skills and languages from sidebar."""

    async def extract_skills_from_sidebar(self, page: Page) -> Optional[list[str]]:
        """Extract skills section from sidebar.

        Returns:
            List of skill names
        """
        try:
            # Find sidebar container
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return None

            skills = []

            # Find skills section
            for selector in SIDEBAR_SELECTORS["skills"]:
                skills_section = await container.query_selector(selector)
                if skills_section:
                    # Extract all skill items
                    skill_elements = await skills_section.query_selector_all(
                        'li[class*="skill-item"], span[class*="skill-name"]'
                    )

                    for element in skill_elements:
                        text = await element.text_content()
                        if text:
                            clean_skill = sanitize_text(text)
                            if len(clean_skill) >= 2 and clean_skill not in skills:
                                skills.append(clean_skill)

                    if skills:
                        log.info(f"Extracted {len(skills)} skills")
                        return skills

            log.debug("No skills found")
            return None

        except Exception as e:
            log.error(f"Error extracting skills: {e}")
            return None

    async def extract_languages_from_sidebar(self, page: Page) -> Optional[list[str]]:
        """Extract languages section from sidebar.

        Returns:
            List of language names
        """
        try:
            # Find sidebar container
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return None

            languages = []

            # Find languages section
            for selector in SIDEBAR_SELECTORS["languages"]:
                languages_section = await container.query_selector(selector)
                if languages_section:
                    # Extract all language items
                    language_elements = await languages_section.query_selector_all(
                        'li[class*="language-item"], span[class*="language-name"]'
                    )

                    for element in language_elements:
                        text = await element.text_content()
                        if text:
                            clean_language = sanitize_text(text)
                            if len(clean_language) >= 2 and clean_language not in languages:
                                languages.append(clean_language)

                    if languages:
                        log.info(f"Extracted {len(languages)} languages")
                        return languages

            log.debug("No languages found")
            return None

        except Exception as e:
            log.error(f"Error extracting languages: {e}")
            return None
