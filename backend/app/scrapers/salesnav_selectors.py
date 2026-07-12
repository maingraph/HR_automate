"""Sales Navigator selectors — centralized DOM selectors with fallbacks.

LinkedIn changes DOM structure frequently. Multiple fallback selectors per field.
Last verified: May 2025
"""

# Profile card selectors (search results list)
CARD_SELECTORS = {
    "name": [
        '[data-anonymize="person-name"]',
        '.artdeco-entity-lockup__title',
        '.entity-result__title-text a',
        'a[data-control-name="view_lead_panel_via_search_lead_name"]',
        '.artdeco-entity-lockup__title a',
        'a.app-aware-link span[aria-hidden="true"]',
    ],
    "headline": [
        '[data-anonymize="title"]',
        '.artdeco-entity-lockup__subtitle',
        '.entity-result__primary-subtitle',
        '.artdeco-entity-lockup__subtitle span[aria-hidden="true"]',
    ],
    "company": [
        '[data-anonymize="company-name"]',
        '.artdeco-entity-lockup__caption',
        '.entity-result__secondary-subtitle',
    ],
    "location": [
        '[data-anonymize="location"]',
        '.artdeco-entity-lockup__caption',
        '.entity-result__secondary-subtitle',
    ],
    "profile_url": [
        'a[href*="/sales/lead/"]',
        'a[href*="/sales/people/"]',
        'a[data-control-name="view_lead_panel_via_search_lead_name"]',
        '.artdeco-entity-lockup__title a',
    ],
    "clickable": [
        'a[data-control-name="view_lead_panel_via_search_lead_name"]',
        '.artdeco-entity-lockup__title a',
        'a[href*="/sales/lead/"]',
        'a[href*="/sales/people/"]',
    ],
}

# Sidebar selectors (detailed profile view)
SIDEBAR_SELECTORS = {
    "container": [
        'aside',
        'div[class*="lead-details"]',
    ],
    "profile_url": [
        'aside a[href*="linkedin.com/in/"]',
        'div[class*="lead-details"] a[href*="linkedin.com/in/"]',
        'a[aria-label*="View on LinkedIn"]',
        'a[aria-label*="LinkedIn profile"]',
        'aside a[href*="/in/"]',
        'div[class*="lead-details"] a[href*="/in/"]',
    ],
    "about": [
        'section[data-x--lead-details--about]',
        'div[class*="about"]',
    ],
    "experience": [
        'section[data-x--lead-details--experience]',
        'div[class*="experience"]',
    ],
    "education": [
        'section[data-x--lead-details--education]',
        'div[class*="education"]',
    ],
    "skills": [
        'section[data-x--lead-details--skills]',
        'div[class*="skills"]',
    ],
    "languages": [
        'section[data-x--lead-details--languages]',
        'div[class*="languages"]',
    ],
}

# Search results selectors
SEARCH_SELECTORS = {
    "profile_cards": [
        'li.artdeco-list__item',
        'div[data-x--search-result]',
        '.search-results__result-item',
    ],
    "results_container": [
        'ol.artdeco-list',
        'div[class*="search-results"]',
        'ul[class*="reusable-search__entity-result-list"]',
    ],
}

# Timeouts (milliseconds)
TIMEOUTS = {
    "sidebar_appear": 3000,
    "sidebar_update": 1000,
    "max_sidebar_wait": 15000,
    "retry_delay": 2000,
    "after_click": 1000,
}
