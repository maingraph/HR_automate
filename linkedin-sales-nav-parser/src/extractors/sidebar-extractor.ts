import { Page } from 'playwright';
import Logger from '../utils/logger';
import { SIDEBAR_SELECTORS, TEXT_PATTERNS, TIMEOUTS } from './selectors';
import { sanitizeText } from './text-utils';

/**
 * Extracts basic data from the sidebar (detailed profile view)
 */
export class SidebarExtractor {
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  /**
   * Extract name from sidebar
   */
  async extractNameFromSidebar(page: Page): Promise<string> {
    try {
      // Try to find aside first, then fallback to lead-details div
      let container: any = await page.$(SIDEBAR_SELECTORS.container[0]);
      if (!container) {
        this.logger.debug('No aside found, trying lead-details div');
        container = await page.$(SIDEBAR_SELECTORS.container[1]);
      }
      
      if (!container) {
        this.logger.warn('No sidebar container found');
        return '';
      }
      
      const containerText = await container.textContent();
      if (!containerText) {
        this.logger.warn('Sidebar container has no text content');
        return '';
      }
      
      this.logger.debug(`Sidebar text length: ${containerText.length} characters`);
      
      // Look for the name - it appears multiple times, but cleanest after "Basic lead information for"
      let nameMatch = containerText.match(TEXT_PATTERNS.nameAfterBasicInfo);
      if (nameMatch && nameMatch[1]) {
        this.logger.debug('Found name from "Basic lead information for" pattern');
        return sanitizeText(nameMatch[1]);
      }
      
      // Alternative: after "Profile details loaded for"
      nameMatch = containerText.match(TEXT_PATTERNS.nameAfterProfileDetails);
      if (nameMatch && nameMatch[1]) {
        this.logger.debug('Found name from "Profile details loaded for" pattern');
        return sanitizeText(nameMatch[1]);
      }
      
      // Fallback: look for name pattern (First Last) after connection degree
      const lines = containerText.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 0);
      this.logger.debug(`Parsed ${lines.length} lines from sidebar`);
      
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].match(/^\d+(st|nd|rd|th)$/)) {
          // Next non-empty line after connection degree might be name
          if (i + 1 < lines.length) {
            const potentialName = lines[i + 1];
            if (TEXT_PATTERNS.namePattern.test(potentialName)) {
              this.logger.debug('Found name after connection degree');
              return sanitizeText(potentialName);
            }
          }
        }
      }
      
      this.logger.warn('Could not find name in sidebar text');
      return '';
    } catch (error) {
      this.logger.error('Error extracting name from sidebar', error as Error);
      return '';
    }
  }

  /**
   * Extract headline from sidebar
   */
  async extractHeadlineFromSidebar(page: Page): Promise<string> {
    try {
      // Try to find aside first, then fallback to lead-details div
      let container: any = await page.$(SIDEBAR_SELECTORS.container[0]);
      if (!container) {
        this.logger.debug('No aside found for headline, trying lead-details div');
        container = await page.$(SIDEBAR_SELECTORS.container[1]);
      }
      
      if (!container) {
        this.logger.warn('No sidebar container found for headline');
        return '';
      }
      
      const containerText = await container.textContent();
      if (!containerText) {
        this.logger.warn('Sidebar has no text for headline extraction');
        return '';
      }
      
      // The headline appears right after the connection degree (3rd) and before location
      // Pattern: "3rd\nHead of Partnerships // Maximising Operations Performance\nWroclaw Metropolitan Area"
      
      // Look for text between connection degree and location/connections
      const headlineMatch = containerText.match(TEXT_PATTERNS.headline);
      if (headlineMatch && headlineMatch[2]) {
        const headline = headlineMatch[2].trim();
        if (headline.length > 5 && headline.length < 200) {
          this.logger.debug('Found headline between connection degree and location');
          return sanitizeText(headline);
        }
      }
      
      // Alternative: look for pattern after name and before location
      const lines = containerText.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 0);
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // Find connection degree line
        if (line.match(/^\d+(st|nd|rd|th)$/)) {
          // Next line should be headline
          if (i + 1 < lines.length) {
            const potentialHeadline = lines[i + 1];
            // Skip if it's a location (contains comma or Area)
            if (!potentialHeadline.includes('Area') && 
                !potentialHeadline.includes('connections') &&
                !potentialHeadline.includes('Viewed') &&
                potentialHeadline.length > 5 && 
                potentialHeadline.length < 200) {
              this.logger.debug('Found headline after connection degree line');
              return sanitizeText(potentialHeadline);
            }
          }
        }
      }
      
      this.logger.warn('Could not find headline in sidebar text');
      return '';
    } catch (error) {
      this.logger.error('Error extracting headline from sidebar', error as Error);
      return '';
    }
  }

  /**
   * Extract company from sidebar
   */
  async extractCompanyFromSidebar(page: Page): Promise<string> {
    try {
      // Try to find aside first, then fallback to lead-details div
      let container: any = await page.$(SIDEBAR_SELECTORS.container[0]);
      if (!container) {
        this.logger.debug('No aside found for company, trying lead-details div');
        container = await page.$(SIDEBAR_SELECTORS.container[1]);
      }
      
      if (!container) {
        this.logger.warn('No sidebar container found for company');
        return '';
      }
      
      const containerText = await container.textContent();
      if (!containerText) {
        this.logger.warn('Sidebar has no text for company extraction');
        return '';
      }
      
      // Look for "Head of Partnerships at Bezprawnik" pattern in the summary section
      // This appears near the top of the sidebar
      const atMatch = containerText.match(TEXT_PATTERNS.company);
      if (atMatch && atMatch[1]) {
        const company = atMatch[1].trim();
        // Make sure it's not a location or other text
        if (!company.includes('Area') && 
            !company.includes('connections') &&
            !company.match(/^\d+(st|nd|rd|th)$/) &&
            company.length > 1 && 
            company.length < 100) {
          this.logger.debug('Found company from "at" pattern');
          return sanitizeText(company);
        }
      }
      
      // Alternative: Look in the experience section for current role
      // Pattern: "Head of Partnerships\nBezprawnik\nJun 2024–Present"
      const expMatch = containerText.match(/experience[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n([A-Z][^\n]{1,80}?)\s*\n/i);
      if (expMatch && expMatch[1]) {
        const company = expMatch[1].trim();
        if (company.length > 1 && company.length < 100) {
          this.logger.debug('Found company from experience section');
          return sanitizeText(company);
        }
      }
      
      // Simpler pattern: look for company name after job title in experience
      const lines = containerText.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 0);
      for (let i = 0; i < lines.length; i++) {
        // Look for "Head of Partnerships at Bezprawnik"
        if (lines[i].includes(' at ')) {
          const parts = lines[i].split(' at ');
          if (parts.length === 2) {
            const company = parts[1].trim();
            if (company.length > 1 && company.length < 100) {
              this.logger.debug('Found company from job title line');
              return sanitizeText(company);
            }
          }
        }
      }
      
      this.logger.warn('Could not find company in sidebar text');
      return '';
    } catch (error) {
      this.logger.error('Error extracting company from sidebar', error as Error);
      return '';
    }
  }

  /**
   * Extract location from sidebar
   */
  async extractLocationFromSidebar(page: Page): Promise<string> {
    try {
      // Try to find aside first, then fallback to lead-details div
      let container: any = await page.$(SIDEBAR_SELECTORS.container[0]);
      if (!container) {
        this.logger.debug('No aside found for location, trying lead-details div');
        container = await page.$(SIDEBAR_SELECTORS.container[1]);
      }
      
      if (!container) {
        this.logger.warn('No sidebar container found for location');
        return '';
      }
      
      const containerText = await container.textContent();
      if (!containerText) {
        this.logger.warn('Sidebar has no text for location extraction');
        return '';
      }
      
      // Location appears after headline and before connections
      // Pattern: "Head of Partnerships...\nWroclaw Metropolitan Area\n500+ connections"
      
      // Look for location patterns - typically contains "Area", "Metropolitan", comma, or country names
      const lines = containerText.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 0);
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        
        // Skip lines that are clearly not locations
        if (line.includes('profile picture') || 
            line.includes('image') ||
            line.includes('reachable') ||
            line.includes('Viewed:')) {
          continue;
        }
        
        // Check if line looks like a location
        if ((line.includes('Metropolitan Area') || 
             line.includes('Area') ||
             line.includes(',') ||
             line.includes('Cyprus') ||
             line.includes('Poland') ||
             line.includes('Armenia') ||
             line.includes('Georgia') ||
             line.includes('Serbia') ||
             line.includes('Belarus') ||
             line.includes('Kazakhstan') ||
             line.includes('Russia') ||
             line.includes('United Arab Emirates') ||
             line.includes('Yerevan') ||
             line.includes('Limassol') ||
             line.includes('Wroclaw')) &&
            !line.includes('connections') &&
            !line.includes('Viewed') &&
            !line.match(/^\d+(st|nd|rd|th)$/) &&
            !line.includes('//') && // Not part of headline
            line.length > 3 && 
            line.length < 100) {
          this.logger.debug('Found location from text parsing');
          return sanitizeText(line);
        }
      }
      
      this.logger.warn('Could not find location in sidebar text');
      return '';
    } catch (error) {
      this.logger.error('Error extracting location from sidebar', error as Error);
      return '';
    }
  }

  /**
   * Extract profile URL from sidebar with retry logic
   */
  async extractProfileUrlWithRetry(page: Page, maxRetries: number = 3): Promise<string> {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const url = await this.extractProfileUrlFromSidebar(page);
      
      if (url && url.includes('/in/')) {
        this.logger.debug(`Found LinkedIn URL on attempt ${attempt + 1}`);
        return url;
      }
      
      if (attempt < maxRetries - 1) {
        this.logger.debug(`Retry ${attempt + 1}: LinkedIn URL not found, waiting...`);
        await page.waitForTimeout(TIMEOUTS.retryDelay);
      }
    }
    
    // Try alternative methods
    return await this.extractUrlFromAlternatives(page);
  }

  /**
   * Extract profile URL from sidebar
   */
  private async extractProfileUrlFromSidebar(page: Page): Promise<string> {
    try {
      // Look for the actual LinkedIn profile URL (not sales/lead) in the sidebar
      for (const selector of SIDEBAR_SELECTORS.profileUrl) {
        const element = await page.$(selector);
        if (element) {
          const href = await element.getAttribute('href');
          if (href && href.includes('/in/')) {
            this.logger.debug(`Found profile URL with selector: ${selector}`);
            // Construct full URL if relative
            if (href.startsWith('/')) {
              return `https://www.linkedin.com${href}`;
            }
            return href;
          }
        }
      }

      // Fallback: get sales lead URL from page URL or sidebar
      const url = page.url();
      if (url.includes('/sales/lead/')) {
        return url;
      }

      return '';
    } catch (error) {
      return '';
    }
  }

  /**
   * Extract URL from alternative methods
   */
  private async extractUrlFromAlternatives(page: Page): Promise<string> {
    // Method 1: Search in "Recent activity" section links
    try {
      const activityLinks = await page.$$('a[href*="linkedin.com"][href*="sectionType=content"]');
      for (const link of activityLinks) {
        const href = await link.getAttribute('href');
        if (href && href.includes('/in/')) {
          // Extract clean URL (remove query params)
          const cleanUrl = href.split('?')[0];
          this.logger.debug('Found LinkedIn URL from activity section');
          return cleanUrl;
        }
      }
    } catch (e) {
      this.logger.debug('Could not find URL in activity section');
    }
    
    // Method 2: Look for "View on LinkedIn" button (visible without clicking)
    try {
      const linkedInButton = await page.$('a[aria-label*="View on LinkedIn"], a[aria-label*="LinkedIn profile"]');
      if (linkedInButton) {
        const href = await linkedInButton.getAttribute('href');
        if (href && href.includes('/in/')) {
          this.logger.debug('Found LinkedIn URL from visible button');
          return href;
        }
      }
    } catch (e) {
      // Continue to next method
    }
    
    // Method 3: Search in all links on the page
    try {
      const allLinks = await page.$$('aside a[href*="/in/"], div[class*="lead-details"] a[href*="/in/"]');
      for (const link of allLinks) {
        const href = await link.getAttribute('href');
        if (href && href.includes('/in/') && !href.includes('/company/')) {
          this.logger.debug('Found LinkedIn URL from all links search');
          return href;
        }
      }
    } catch (e) {
      // Continue
    }
    
    // Method 4: Click "More actions" menu to find hidden LinkedIn URL
    // This is the last resort method that actively clicks the menu
    this.logger.debug('Trying More actions menu as last resort...');
    const urlFromMenu = await this.extractUrlFromMoreMenu(page);
    if (urlFromMenu) {
      return urlFromMenu;
    }
    
    // No LinkedIn profile URL found
    this.logger.warn('No LinkedIn profile URL found (profile may have privacy settings)');
    return '';
  }

  /**
   * Extract URL by clicking "More actions" menu
   * Uses JS native click to prevent sidebar from closing
   * IMPORTANT: Uses LinkedIn's unique data attributes to find the correct button
   */
  private async extractUrlFromMoreMenu(page: Page): Promise<string> {
    try {
      // Step 1: Find the sidebar container first
      const sidebarContainer = await page.$('aside, div[class*="lead-details"]');
      
      if (!sidebarContainer) {
        this.logger.debug('Sidebar container not found for More menu extraction');
        return '';
      }

      // Step 2: Find the More actions button INSIDE the sidebar using LinkedIn's unique attributes
      // LinkedIn uses: data-x--lead-actions-bar-overflow-menu and aria-label="Open actions overflow menu"
      const moreButtonSelectors = [
        'button[data-x--lead-actions-bar-overflow-menu]', // LinkedIn's unique data attribute (most reliable)
        'button[aria-label="Open actions overflow menu"]', // Exact English aria-label
        'button[aria-label*="overflow menu"]', // Partial match for overflow menu
        'button[aria-label="Открыть меню дополнительных действий"]', // Russian exact match
        'button[aria-label*="дополнительных действий"]', // Russian partial match
      ];

      let moreButton = null;
      let foundSelector = '';
      
      for (const selector of moreButtonSelectors) {
        try {
          moreButton = await sidebarContainer.$(selector);
          if (moreButton) {
            foundSelector = selector;
            this.logger.debug(`Found More button with selector: ${selector}`);
            break;
          }
        } catch (e) {
          continue;
        }
      }

      if (!moreButton) {
        this.logger.debug('More actions button not found in sidebar');
        return '';
      }

      // Step 3: Use JS native click via evaluate to prevent sidebar from closing
      // This bypasses Playwright's virtual mouse and prevents accidental backdrop clicks
      try {
        await moreButton.evaluate((button) => {
          (button as HTMLElement).click();
        });
        this.logger.debug('Clicked More actions button (JS native click via evaluate)');
      } catch (e) {
        this.logger.debug('Failed to click More button');
        return '';
      }

      // Step 4: Wait for menu to appear in DOM
      await page.waitForTimeout(500);

      // Step 5: Look for "View on LinkedIn" link in the opened menu
      // The menu typically has class "hue-menu-content" or similar
      const viewOnLinkedInSelectors = [
        '.hue-menu-content a[href*="linkedin.com/in/"]', // Menu content with LinkedIn URL
        'a[data-control-name="view_linkedin_profile"]', // LinkedIn's data attribute for this link
        'a[data-control-name*="view_linkedin"]', // Partial match
        'a[href*="linkedin.com/in/"]:not([href*="/company/"])', // Any LinkedIn profile URL (not company)
        'a:has-text("View on LinkedIn")', // English text
        'a:has-text("View LinkedIn profile")', // Alternative English text
        'a:has-text("Посмотреть профиль в LinkedIn")', // Russian text
      ];

      for (const selector of viewOnLinkedInSelectors) {
        try {
          const link = await page.$(selector);
          if (link) {
            const href = await link.getAttribute('href');
            if (href && href.includes('/in/') && !href.includes('/company/')) {
              this.logger.debug(`Found LinkedIn URL from More menu: ${href}`);
              
              // Close the menu by pressing Escape
              await page.keyboard.press('Escape');
              await page.waitForTimeout(200);
              
              return href;
            }
          }
        } catch (e) {
          continue;
        }
      }

      // No LinkedIn URL found in menu (privacy settings)
      this.logger.debug('Menu opened, but no public LinkedIn URL found (privacy settings)');
      
      // Close the menu if we didn't find the link
      await page.keyboard.press('Escape');
      await page.waitForTimeout(200);

      return '';
    } catch (error) {
      this.logger.debug('Error extracting URL from More menu');
      // Try to close menu if it's open
      try {
        await page.keyboard.press('Escape');
      } catch (e) {}
      return '';
    }
  }

  /**
   * Extract profile image from sidebar
   */
  async extractProfileImageFromSidebar(page: Page): Promise<string> {
    const selectors = [
      'aside img[alt*="profile"]',
      'aside img[class*="presence"]',
      'aside img[class*="photo"]',
      'div[class*="details-panel"] img[alt*="profile"]',
      'div[class*="lead-details"] img[alt*="profile"]',
      '[data-view-name="lead-detail-panel"] img.presence-entity__image',
      '[role="dialog"] img.presence-entity__image',
      '.artdeco-modal img.presence-entity__image',
      '[data-view-name="lead-detail-panel"] img[data-anonymize="headshot-photo"]',
      '[role="dialog"] img[data-anonymize="headshot-photo"]',
    ];

    for (const selector of selectors) {
      try {
        const element = await page.$(selector);
        if (element) {
          const src = await element.getAttribute('src');
          if (src && !src.includes('data:image') && src.includes('http')) {
            this.logger.debug(`Found profile image with selector: ${selector}`);
            return src;
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  /**
   * Extract connection degree from sidebar
   */
  async extractConnectionDegreeFromSidebar(page: Page): Promise<string> {
    try {
      const text = await page.textContent('body');
      if (!text) return 'Unknown';

      const degreeMatch = text.match(TEXT_PATTERNS.connectionDegree);
      if (degreeMatch) {
        return `${degreeMatch[1]}${degreeMatch[2]}`;
      }

      if (text.includes('1st')) return '1st';
      if (text.includes('2nd')) return '2nd';
      if (text.includes('3rd')) return '3rd';
      if (text.includes('3rd+')) return '3rd+';

      return 'Unknown';
    } catch (error) {
      return 'Unknown';
    }
  }

  /**
   * Extract premium status from sidebar
   */
  async extractPremiumStatusFromSidebar(page: Page): Promise<boolean> {
    try {
      const selectors = [
        '[data-test-icon="premium-icon"]',
        '.premium-icon',
        '[aria-label*="Premium"]',
      ];

      for (const selector of selectors) {
        const element = await page.$(selector);
        if (element) {
          return true;
        }
      }

      const text = await page.textContent('body');
      if (text && text.includes('Premium')) {
        return true;
      }

      return false;
    } catch (error) {
      return false;
    }
  }

  /**
   * Extract shared connections from sidebar
   */
  async extractSharedConnectionsFromSidebar(page: Page): Promise<number> {
    try {
      const text = await page.textContent('body');
      if (!text) return 0;

      const match = text.match(TEXT_PATTERNS.sharedConnections);
      if (match) {
        return parseInt(match[1], 10);
      }

      return 0;
    } catch (error) {
      return 0;
    }
  }

  /**
   * Extract years at company from sidebar
   */
  async extractYearsAtCompanyFromSidebar(page: Page): Promise<string | undefined> {
    try {
      const asideText = await page.$eval('aside', el => el.textContent);
      if (!asideText) return undefined;

      // Look for "2 yrs" pattern near the top (in the summary section)
      // Pattern: "Head of Partnerships at Bezprawnik\n2 yrs"
      const yearMatch = asideText.match(/(\d+)\s+yrs?(?:\s+(\d+)\s+mos?)?/i);
      if (yearMatch) {
        let result = '';
        if (yearMatch[1]) {
          const years = parseInt(yearMatch[1]);
          result += `${years} year${years !== 1 ? 's' : ''}`;
        }
        if (yearMatch[2]) {
          if (result) result += ' ';
          const months = parseInt(yearMatch[2]);
          result += `${months} month${months !== 1 ? 's' : ''}`;
        }
        this.logger.debug('Found years at company from text parsing');
        return result;
      }

      return undefined;
    } catch (error) {
      return undefined;
    }
  }

  /**
   * Extract industry from sidebar
   */
  async extractIndustryFromSidebar(page: Page): Promise<string | undefined> {
    try {
      const selectors = [
        '[data-anonymize="industry"]',
        '.profile-topcard__industry',
      ];

      for (const selector of selectors) {
        const element = await page.$(selector);
        if (element) {
          const text = await element.textContent();
          if (text && text.trim()) {
            return sanitizeText(text);
          }
        }
      }

      return undefined;
    } catch (error) {
      return undefined;
    }
  }

  /**
   * Extract about section from sidebar
   */
  async extractAboutFromSidebar(page: Page): Promise<string | undefined> {
    try {
      let container: any = await page.$(SIDEBAR_SELECTORS.container[0]);
      if (!container) {
        container = await page.$(SIDEBAR_SELECTORS.container[1]);
      }
      
      if (!container) {
        return undefined;
      }
      
      const containerText = await container.textContent();
      if (!containerText) {
        return undefined;
      }
      
      // Look for "About" section
      const aboutMatch = containerText.match(/About\s*\n\s*([^\n]+(?:\n(?!(?:Relationship|Recent activity|experience|Education|Featured skills|Languages))[^\n]+)*)/i);
      if (aboutMatch && aboutMatch[1]) {
        const about = aboutMatch[1].trim();
        // Remove "Show more" text if present
        const cleanAbout = about.replace(/…\s*Show more$/i, '').trim();
        if (cleanAbout.length > 10) {
          this.logger.debug('Found about section');
          return sanitizeText(cleanAbout);
        }
      }
      
      return undefined;
    } catch (error) {
      this.logger.debug('Error extracting about section');
      return undefined;
    }
  }
}
