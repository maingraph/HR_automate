"""Semantic section reader for current Sales Navigator profile drawers.

Sales Navigator CSS class names are generated and change often.  The visible
section headings (Education, Featured skills, Languages) are stable, so use
them as the extraction contract instead.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Page


async def read_profile_section(page: Page, heading_pattern: str) -> dict[str, Any]:
    """Return rendered lines and list-item data for a sidebar profile section."""
    return await page.evaluate(
        """pattern => {
          const clean = value => (value || '').replace(/\\s+/g, ' ').trim();
          const matcher = new RegExp(pattern, 'i');
          const heading = [...document.querySelectorAll('h1, h2, h3')]
            .find(node => matcher.test(clean(node.textContent)));
          if (!heading) return { lines: [], items: [] };
          const section = heading.closest('section')
            || heading.parentElement?.closest('section')
            || heading.parentElement;
          if (!section) return { lines: [], items: [] };
          const lines = (section.innerText || '').split('\\n').map(clean).filter(Boolean);
          const items = [...section.querySelectorAll('li')].map(item => ({
            text: clean(item.innerText),
            headings: [...item.querySelectorAll('h2, h3, h4')].map(node => clean(node.textContent)).filter(Boolean),
            paragraphs: [...item.querySelectorAll('p')].map(node => clean(node.textContent)).filter(Boolean),
            links: [...item.querySelectorAll('a[href]')].map(node => ({
              text: clean(node.textContent), href: node.href
            })).filter(link => link.text),
            years: [...item.querySelectorAll('time')].map(node => clean(node.textContent)).filter(Boolean),
          })).filter(item => item.text);
          return { lines, items };
        }""",
        heading_pattern,
    )
