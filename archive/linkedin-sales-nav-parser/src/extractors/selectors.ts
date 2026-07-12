/**
 * Centralized DOM selectors for LinkedIn Sales Navigator
 * LinkedIn frequently changes their DOM structure, so we maintain multiple fallback selectors
 */

/**
 * Selectors for profile card elements (search results list)
 */
export const CARD_SELECTORS = {
  // Name selectors
  name: [
    '[data-anonymize="person-name"]',
    '.artdeco-entity-lockup__title',
    '.entity-result__title-text a',
    'a[data-control-name="view_lead_panel_via_search_lead_name"]',
    '.artdeco-entity-lockup__title a',
    'a.app-aware-link span[aria-hidden="true"]',
  ],

  // Headline selectors
  headline: [
    '[data-anonymize="title"]',
    '.artdeco-entity-lockup__subtitle',
    '.entity-result__primary-subtitle',
    '.artdeco-entity-lockup__subtitle span[aria-hidden="true"]',
  ],

  // Company selectors
  company: [
    '[data-anonymize="company-name"]',
    '.artdeco-entity-lockup__caption',
    '.entity-result__secondary-subtitle',
  ],

  // Location selectors
  location: [
    '[data-anonymize="location"]',
    '.artdeco-entity-lockup__caption',
    '.entity-result__secondary-subtitle',
  ],

  // Profile URL selectors
  profileUrl: [
    'a[href*="/sales/lead/"]',
    'a[href*="/sales/people/"]',
    'a[data-control-name="view_lead_panel_via_search_lead_name"]',
    '.artdeco-entity-lockup__title a',
  ],

  // Profile image selectors
  profileImage: [
    'img.presence-entity__image',
    'img[data-anonymize="headshot-photo"]',
    '.artdeco-entity-lockup__image img',
    'img.EntityPhoto-circle-3',
  ],

  // Premium status selectors
  premium: [
    '[data-test-icon="premium-icon"]',
    '.premium-icon',
    '[aria-label*="Premium"]',
    '.artdeco-entity-lockup__badge',
  ],

  // Industry selectors
  industry: [
    '[data-anonymize="industry"]',
    '.artdeco-entity-lockup__industry',
  ],

  // Clickable elements
  clickable: [
    'a[data-control-name="view_lead_panel_via_search_lead_name"]',
    '.artdeco-entity-lockup__title a',
    'a[href*="/sales/lead/"]',
    'a[href*="/sales/people/"]',
  ],
};

/**
 * Selectors for sidebar elements (detailed profile view)
 */
export const SIDEBAR_SELECTORS = {
  // Container selectors
  container: [
    'aside',
    'div[class*="lead-details"]',
  ],

  // Profile URL selectors (LinkedIn profile links)
  profileUrl: [
    'aside a[href*="linkedin.com/in/"]',
    'div[class*="lead-details"] a[href*="linkedin.com/in/"]',
    'a[aria-label*="View on LinkedIn"]',
    'a[aria-label*="LinkedIn profile"]',
    'aside a[href*="/in/"]',
    'div[class*="lead-details"] a[href*="/in/"]',
  ],

  // About section selectors
  about: [
    'section[data-x--lead-details--about]',
    'div[class*="about"]',
    'section:has(h2:text("About"))',
  ],

  // Experience section selectors
  experience: [
    'section[data-x--lead-details--experience]',
    'div[class*="experience"]',
    'section:has(h2:text("Experience"))',
  ],

  // Education section selectors
  education: [
    'section[data-x--lead-details--education]',
    'div[class*="education"]',
    'section:has(h2:text("Education"))',
  ],

  // Skills section selectors
  skills: [
    'section[data-x--lead-details--skills]',
    'div[class*="skills"]',
    'section:has(h2:text("Skills"))',
  ],

  // Languages section selectors
  languages: [
    'section[data-x--lead-details--languages]',
    'div[class*="languages"]',
    'section:has(h2:text("Languages"))',
  ],
};

/**
 * Selectors for the main search results list
 */
export const SEARCH_SELECTORS = {
  // Profile cards in search results
  profileCards: [
    'li.artdeco-list__item',
    'div[data-x--search-result]',
    '.search-results__result-item',
  ],

  // Search results container
  resultsContainer: [
    'ol.artdeco-list',
    'div[class*="search-results"]',
    'ul[class*="reusable-search__entity-result-list"]',
  ],
};

/**
 * Text patterns for extracting data from text content
 */
export const TEXT_PATTERNS = {
  // Connection degree patterns
  connectionDegree: /(\d+)(st|nd|rd|th)/i,

  // Shared connections patterns
  sharedConnections: /(\d+)\s+(shared|mutual)\s+connection/i,

  // Years at company patterns
  years: /(\d+)\s+(year|yr)s?/i,
  months: /(\d+)\s+(month|mo)s?/i,

  // Name patterns in sidebar
  nameAfterBasicInfo: /Basic lead information for\s+([^\n.]+)/,
  nameAfterProfileDetails: /Profile details loaded for\s+([^\n.]+)/,
  namePattern: /^[A-Z][a-z]+\s+[A-Z]/,

  // Headline pattern (between connection degree and location)
  headline: /\d+(st|nd|rd|th)\s*\n\s*([^\n]+?)\s*\n\s*(?:[A-Z][a-z]+|[\d]+\+?\s+connections)/,

  // Company pattern (after "at" or "@")
  company: /(?:at|@)\s+([A-Z][^\n]{1,80}?)\s*(?:\n|$)/,

  // Location pattern (contains comma or location keywords)
  location: /\b(Area|Region|State|Country)\b/i,
};

/**
 * Wait timeouts (in milliseconds)
 */
export const TIMEOUTS = {
  sidebarAppear: 3000,
  sidebarUpdate: 1000,
  maxSidebarWait: 15000,
  retryDelay: 2000,
  afterClick: 1000,
};
