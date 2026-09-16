"""Sales Navigator skills extractor — extracts skills and languages from sidebar."""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from app.core.logging import get_logger
from app.scrapers.salesnav_semantic_sections import read_profile_section
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
            await self._expand_section(page, "View all skills")
            semantic = await self._extract_semantic_list(page, r"Featured skills|Skills", "skill")
            if semantic:
                return semantic
            # Find sidebar container
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return await self._extract_semantic_list(page, r"Featured skills|Skills", "skill")

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
            return await self._extract_semantic_list(page, r"Featured skills|Skills", "skill")

        except Exception as e:
            log.error(f"Error extracting skills: {e}")
            return await self._extract_semantic_list(page, r"Featured skills|Skills", "skill")

    async def extract_languages_from_sidebar(self, page: Page) -> Optional[list[str]]:
        """Extract languages section from sidebar.

        Returns:
            List of language names
        """
        try:
            await self._expand_section(page, "Show all languages")
            semantic = await self._extract_semantic_list(page, r"^Languages$", "language")
            if semantic:
                return semantic
            # Find sidebar container
            container = await page.query_selector(SIDEBAR_SELECTORS["container"][0])
            if not container:
                container = await page.query_selector(SIDEBAR_SELECTORS["container"][1])

            if not container:
                return await self._extract_semantic_list(page, r"^Languages$", "language")

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
            return await self._extract_semantic_list(page, r"^Languages$", "language")

        except Exception as e:
            log.error(f"Error extracting languages: {e}")
            return await self._extract_semantic_list(page, r"^Languages$", "language")

    async def _extract_semantic_list(
        self, page: Page, heading_pattern: str, kind: str
    ) -> Optional[list[str]]:
        """Read modern drawer sections using visible headings, not CSS hashes."""
        try:
            section = await read_profile_section(page, heading_pattern)
            values: list[str] = []
            ignored = {
                "view all skills",
                "show all skills",
                "show all languages",
                "show more",
                "show less",
                "endorsement",
                "endorsements",
            }
            for value in section.get("lines") or []:
                clean = sanitize_text(value)
                lower = clean.lower()
                if (
                    not clean
                    or len(clean) > 120
                    or lower in {"featured skills and endorsements", "featured skills", "skills", "languages"}
                    or lower in ignored
                    or "endorsement" in lower
                ):
                    continue
                if clean not in values:
                    values.append(clean)
            if values:
                log.info("Extracted %s %s from semantic sidebar section", len(values), kind)
            return values or None
        except Exception:
            log.debug("No semantic %s section found", kind)
            return None

    async def _expand_section(self, page: Page, label: str) -> None:
        """Expand current drawer list before reading semantic lines."""
        try:
            controls = await page.query_selector_all("div.lead-sidesheet button, div.lead-sidesheet a")
            for button in controls:
                text = sanitize_text(await button.text_content() or "")
                if text.lower() == label.lower():
                    await button.click(force=True, timeout=3_000)
                    await page.wait_for_timeout(500)
                    return
        except Exception:
            log.debug("Could not expand %s", label)
