"""Parse the raw HTML dumps from :mod:`walker` into a single profile JSON.

LinkedIn's DOM uses obfuscated, hashed class names that change every deploy,
so we parse by **content structure** and **tag hierarchy** instead:

- Profile header: ``<h2>`` containing the name, followed by a ``<p>`` with
  the headline, and location text nearby.
- Section pages: ``<main>`` contains a section label (``<p>Experience</p>``),
  then entries as nested ``<div>`` trees where the leaf ``<p>``/``<span>``
  tags hold the visible text.
- Each entry block is separated by sibling ``<div>`` wrappers — we identify
  them by looking for ``<a>`` tags (each entry links to the company/school)
  or by clustering <p> tags that share a common parent.

The output keeps both structured records and ``raw_text`` so downstream
consumers can re-parse if needed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


# Common noise strings that appear in LinkedIn footer / nav / sidebar
_NOISE = {
    "About", "Accessibility", "Talent Solutions", "Business Solutions",
    "Advertising", "Talent Insights", "Post a Job", "Mobile", "E-Commerce",
    "-small-business", "Security Center", "Privacy Policy", "User Agreement",
    "Cookie Policy", "Copyright", "Brand Policy", "Community Guidelines",
    "Language", "Sign in", "Join now", "Skip to content", "Dismiss",
    "Learn more", "Get the App", "Add a different account",
}

_NAV_LINKS = {
    "My Network", "Messaging", "Notifications", "Jobs", "Home",
    "Feed", "Search", "0 notifications", "1 notification",
}

_SECTION_TITLES = {
    "Experience", "Education", "Skills", "About", "Languages",
    "Certifications", "Licenses", "Projects", "Publications",
    "Honors", "Volunteer Experience", "Recommendations",
    "Interests", "Volunteering", "Posts", "Test Scores",
    "Featured",
}

_FOOTER_LINKS = {
    "Careers", "Marketing Solutions", "Sales Solutions", "Learning",
    "Newsletters", "Solutions", "Community", "Safety Center",
    "About", "Accessibility", "Talent Solutions", "Business Solutions",
    "Advertising", "Talent Insights", "Post a Job", "Mobile",
    "E-Commerce", "Security Center", "Privacy Policy", "User Agreement",
    "Cookie Policy", "Copyright", "Brand Policy", "Community Guidelines",
    "Language", "Sign in", "Join now", "Small Business",
    "Questions?", "Help Center", "Manage your account and privacy",
    "Recommendation transparency",
}

# URL patterns that indicate non-entry (footer/nav/sidebar) links
_SKIP_HREF_PATTERNS = (
    "/company/linkedin", "/help/", "/legal/", "/psettings/",
    "/learning/", "/talent/", "/business/", "/advertiser/",
    "/sales/", "/messaging/", "/feed/", "/mynetwork/",
    "/details/", "/login", "/authwall", "/checkpoint/",
    "/notifications", "/settings/", "/directory/",
)


def _is_noise(text: str) -> bool:
    if not text:
        return True
    if text in _NOISE or text in _NAV_LINKS or text in _FOOTER_LINKS:
        return True
    if text.startswith(("· ", "·  ", "0 notifications", "1 notification")):
        return True
    if re.match(r"^\d+\s*(st|nd|rd|th)\s*", text):
        return True
    if text.lower() in ("message", "connect", "follow", "more...", "save",
                          "share", "send", "connect", "unfollow", "skip to content"):
        return True
    if "Please check your URL" in text:
        return True
    if len(text) < 3:
        return True
    return False


def _extract_overview_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract name, headline, location from the profile overview page."""
    result: Dict[str, Any] = {}
    main = soup.find("main") or soup

    # Name: find h2 that contains a person's name pattern (2+ capitalized words)
    for h in main.find_all(["h1", "h2"]):
        text = _clean(h.get_text(" "))
        if text and len(text) < 80 and not _is_noise(text):
            if text not in _SECTION_TITLES and not text.isdigit():
                # Person names usually have 2+ space-separated words starting with uppercase
                if re.match(r"^[A-Z][a-z]+\s+[A-Z]", text):
                    result["name"] = text
                    break

    # Headline: find a <p> that's NOT a section title and contains separator pipes |
    # LinkedIn headlines often use | to separate keywords
    for p in main.find_all("p"):
        text = _clean(p.get_text(" "))
        if text and text != result.get("name") and "|" in text and len(text) > 20:
            if not _is_noise(text) and text not in _SECTION_TITLES:
                result["headline"] = text
                break

    # Fallback: search for common headline keywords
    if not result.get("headline"):
        for p in main.find_all("p"):
            text = _clean(p.get_text(" "))
            if (text and text != result.get("name") and not _is_noise(text)
                    and len(text) > 15 and len(text) < 300):
                if any(kw in text for kw in (" at ", " | ", "Head of", "Director", 
                                              "Manager", "Developer", "Engineer",
                                              "Founder", "CEO", "CTO")):
                    result["headline"] = text
                    break

    # Location: find text matching city, country pattern
    for el in main.find_all(["span"]):
        text = _clean(el.get_text(" "))
        if text and len(text) < 60 and len(text) > 5 and text != result.get("name"):
            if re.match(r"^[A-ZÀ-ÿ][a-zà-ÿ]+(?:[\s,]+[A-ZÀ-ÿ][a-zà-ÿ]+)+$", text):
                if "," in text or "Area" in text or "Region" in text:
                    result["location"] = text
                    break

    return result


def _extract_section_entries(main: Tag) -> List[Dict[str, Any]]:
    """Extract structured entries from a details section page.

    LinkedIn renders each entry as a block of <p> tags inside nested <div>s.
    We find <a> tags (each entry links to company/school/profile), group the
    <p> tags under their nearest common ancestor, and filter noise.
    """
    entries: List[Dict[str, Any]] = []
    seen_keys: set = set()

    # Method 1: Find entry containers by their <a> anchor links
    for a in main.find_all("a", href=True):
        href = a.get("href", "")
        if any(skip in href for skip in _SKIP_HREF_PATTERNS):
            continue
        # Also skip if href is just "/" or very short
        if len(href) < 5 or href == "/":
            continue
        # Skip footer/nav links (they link to /company/, /learning/, etc.)
        link_text = _clean(a.get_text(" "))
        if link_text in _FOOTER_LINKS or link_text in _NAV_LINKS:
            continue

        # Walk up 4-6 levels to find the entry container div
        container = a
        for _ in range(5):
            if container.parent and container.parent.name in ("div", "section", "li"):
                container = container.parent
            else:
                break

        # Extract all <p> texts in this container
        paragraphs = container.find_all("p")
        texts = [_clean(p.get_text(" ")) for p in paragraphs]
        texts = [t for t in texts if t and not _is_noise(t) and t not in _SECTION_TITLES]

        if not texts:
            continue

        primary = texts[0]
        secondary = texts[1] if len(texts) > 1 else ""
        metadata = [t for t in texts[2:] if len(t) < 100] if len(texts) > 2 else []

        # Find longer descriptive text (not in a <p> that's just a label)
        description = ""
        for p in container.find_all("p"):
            t = _clean(p.get_text(" "))
            if len(t) > 150 and t != primary and t != secondary:
                description = t[:500]
                break

        entry_key = (primary[:60], secondary[:30] if secondary else "")
        if primary and entry_key not in seen_keys:
            seen_keys.add(entry_key)
            entry: Dict[str, Any] = {"primary": primary}
            if secondary and secondary != primary:
                entry["secondary"] = secondary
            if metadata:
                entry["metadata"] = metadata
            if description:
                entry["description"] = description
            if href.startswith("/"):
                entry["link"] = "https://www.linkedin.com" + href
            elif href.startswith("http"):
                entry["link"] = href
            entries.append(entry)

    return entries


def _extract_section_title(main: Tag) -> str:
    """Find the section title (Experience, Education, etc.)."""
    for p in main.find_all("p"):
        text = _clean(p.get_text(" "))
        if text in ("Experience", "Education", "Skills", "About", "Languages",
                     "Certifications", "Licenses", "Projects", "Publications",
                     "Honors", "Volunteer Experience", "Recommendations",
                     "Interests", "Volunteering", "Posts", "Test Scores"):
            return text
    return ""


class SectionParser:
    """Parse one ``.html`` dump into a section dict."""

    @classmethod
    def parse_file(cls, section_slug: str, html_path: Path) -> Dict[str, Any]:
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup

        entries = _extract_section_entries(main)
        title = _extract_section_title(main)
        raw_text = _clean(soup.get_text(" "))

        return {
            "section": section_slug,
            "title": title or section_slug.title(),
            "entry_count": len(entries),
            "entries": entries,
            "raw_text": raw_text[:8000],
        }


def merge_profile(
    slug: str,
    section_paths: Dict[str, Path],
    overview_html: Path,
) -> Dict[str, Any]:
    """Run ``SectionParser`` over each dump and return one combined profile."""
    overview_soup = BeautifulSoup(
        overview_html.read_text(encoding="utf-8", errors="ignore"), "html.parser"
    )
    overview_meta = _extract_overview_metadata(overview_soup)

    profile: Dict[str, Any] = {
        "username": slug,
        "source_url": f"https://www.linkedin.com/in/{slug}/",
        "name": overview_meta.get("name"),
        "headline": overview_meta.get("headline"),
        "location": overview_meta.get("location"),
        "sections": {},
    }

    for section_slug, path in section_paths.items():
        parsed = SectionParser.parse_file(section_slug, path)
        if section_slug != "overview" and not parsed["entries"]:
            continue
        profile["sections"][section_slug] = parsed

    return profile


def write_outputs(
    profile: Dict[str, Any],
    out_dir: Path,
) -> Tuple[Path, Path]:
    """Persist both pretty-printed JSON and a human-readable summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "profile.json"
    summary_path = out_dir / "profile_summary.txt"

    json_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    lines: List[str] = []
    if profile.get("name"):
        lines.append(profile["name"])
    if profile.get("headline"):
        lines.append(profile["headline"])
    if profile.get("location"):
        lines.append(profile["location"])
    lines.append("Source: " + profile["source_url"])
    lines.append("")

    for section_slug, section in profile["sections"].items():
        lines.append(f"== {section_slug.upper()} ({section['entry_count']} entries) ==")
        for entry in section["entries"]:
            primary = entry.get("primary", "")
            secondary = entry.get("secondary", "")
            meta = " · ".join(entry.get("metadata", []) or [])
            line = f"  - {primary}"
            if secondary and secondary != primary:
                line += f"  |  {secondary}"
            if meta:
                line += f"  ({meta})"
            lines.append(line)
            if entry.get("description"):
                lines.append(f"      {entry['description'][:280]}")
        lines.append("")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, summary_path
