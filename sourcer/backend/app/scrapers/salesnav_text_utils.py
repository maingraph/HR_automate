"""Text utilities for Sales Navigator extraction."""
import re
from typing import Optional


def sanitize_text(text: Optional[str]) -> str:
    """Clean and normalize extracted text."""
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    # Remove common noise
    text = text.replace('​', '')  # Zero-width space
    text = text.replace('\xa0', ' ')   # Non-breaking space

    return text


def fuzzy_match(text1: Optional[str], text2: Optional[str], threshold: float = 0.8) -> bool:
    """Fuzzy match two strings (handles slight variations).

    Args:
        text1: First string
        text2: Second string
        threshold: Similarity threshold (0.0-1.0)

    Returns:
        True if strings are similar enough
    """
    if not text1 or not text2:
        return False

    # Normalize
    t1 = sanitize_text(text1).lower()
    t2 = sanitize_text(text2).lower()

    # Exact match
    if t1 == t2:
        return True

    # Contains match
    if t1 in t2 or t2 in t1:
        return True

    # Simple similarity: count matching words
    words1 = set(t1.split())
    words2 = set(t2.split())

    if not words1 or not words2:
        return False

    intersection = words1 & words2
    union = words1 | words2

    similarity = len(intersection) / len(union)

    return similarity >= threshold


# Text patterns for extraction
PATTERNS = {
    "connection_degree": re.compile(r'(\d+)(st|nd|rd|th)', re.IGNORECASE),
    "shared_connections": re.compile(r'(\d+)\s+(shared|mutual)\s+connection', re.IGNORECASE),
    "years": re.compile(r'(\d+)\s+(year|yr)s?', re.IGNORECASE),
    "months": re.compile(r'(\d+)\s+(month|mo)s?', re.IGNORECASE),
    "name_after_basic_info": re.compile(r'Basic lead information for\s+([^\n.]+)'),
    "name_after_profile_details": re.compile(r'Profile details loaded for\s+([^\n.]+)'),
    "name_pattern": re.compile(r'^[A-Z][a-z]+\s+[A-Z]'),
    "headline": re.compile(r'\d+(st|nd|rd|th)\s*\n\s*([^\n]+?)\s*\n\s*(?:[A-Z][a-z]+|[\d]+\+?\s+connections)'),
    "company": re.compile(r'(?:at|@)\s+([A-Z][^\n]{1,80}?)\s*(?:\n|$)'),
}
