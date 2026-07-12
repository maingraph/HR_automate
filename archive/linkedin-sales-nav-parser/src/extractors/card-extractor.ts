import { ElementHandle } from 'playwright';
import Logger from '../utils/logger';
import { CARD_SELECTORS, TEXT_PATTERNS } from './selectors';
import { sanitizeText } from './text-utils';

/**
 * Extracts data from profile cards in search results
 */
export class CardExtractor {
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  /**
   * Extract name from profile card
   */
  async extractName(card: ElementHandle): Promise<string> {
    for (const selector of CARD_SELECTORS.name) {
      try {
        const element = await card.$(selector);
        if (element) {
          const text = await element.textContent();
          if (text && text.trim()) {
            return sanitizeText(text);
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  /**
   * Extract headline from profile card
   */
  async extractHeadline(card: ElementHandle): Promise<string> {
    for (const selector of CARD_SELECTORS.headline) {
      try {
        const element = await card.$(selector);
        if (element) {
          const text = await element.textContent();
          if (text && text.trim()) {
            return sanitizeText(text);
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  /**
   * Extract company from profile card
   */
  async extractCompany(card: ElementHandle): Promise<string> {
    for (const selector of CARD_SELECTORS.company) {
      try {
        const element = await card.$(selector);
        if (element) {
          const text = await element.textContent();
          if (text && text.trim()) {
            return sanitizeText(text);
          }
        }
      } catch (error) {
        continue;
      }
    }

    // Try to extract from headline if not found
    const headline = await this.extractHeadline(card);
    if (headline.includes(' at ')) {
      const parts = headline.split(' at ');
      if (parts.length > 1) {
        return sanitizeText(parts[1]);
      }
    }

    return '';
  }

  /**
   * Extract location from profile card
   */
  async extractLocation(card: ElementHandle): Promise<string> {
    for (const selector of CARD_SELECTORS.location) {
      try {
        const elements = await card.$$(selector);
        for (const element of elements) {
          const text = await element.textContent();
          if (text && text.trim() && !text.includes('•')) {
            const sanitized = sanitizeText(text);
            // Check if it looks like a location (contains comma or common location words)
            if (sanitized.includes(',') || TEXT_PATTERNS.location.test(sanitized)) {
              return sanitized;
            }
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  /**
   * Extract profile URL from profile card
   */
  async extractProfileUrl(card: ElementHandle): Promise<string> {
    for (const selector of CARD_SELECTORS.profileUrl) {
      try {
        const element = await card.$(selector);
        if (element) {
          const href = await element.getAttribute('href');
          if (href) {
            // Construct full URL if relative
            if (href.startsWith('/')) {
              return `https://www.linkedin.com${href}`;
            }
            return href;
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  /**
   * Extract profile image URL from profile card
   */
  async extractProfileImage(card: ElementHandle): Promise<string> {
    for (const selector of CARD_SELECTORS.profileImage) {
      try {
        const element = await card.$(selector);
        if (element) {
          const src = await element.getAttribute('src');
          if (src && !src.includes('data:image')) {
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
   * Extract connection degree from profile card
   */
  async extractConnectionDegree(card: ElementHandle): Promise<string> {
    try {
      const text = await card.textContent();
      if (!text) return 'Unknown';

      // Look for degree indicators
      const degreeMatch = text.match(TEXT_PATTERNS.connectionDegree);
      if (degreeMatch) {
        return `${degreeMatch[1]}${degreeMatch[2]}`;
      }

      // Check for specific text
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
   * Extract premium status from profile card
   */
  async extractPremiumStatus(card: ElementHandle): Promise<boolean> {
    try {
      for (const selector of CARD_SELECTORS.premium) {
        const element = await card.$(selector);
        if (element) {
          return true;
        }
      }

      // Check text content for "Premium"
      const text = await card.textContent();
      if (text && text.includes('Premium')) {
        return true;
      }

      return false;
    } catch (error) {
      return false;
    }
  }

  /**
   * Extract shared connections count from profile card
   */
  async extractSharedConnections(card: ElementHandle): Promise<number> {
    try {
      const text = await card.textContent();
      if (!text) return 0;

      // Look for patterns like "15 shared connections" or "15 mutual connections"
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
   * Extract years at company from profile card
   */
  async extractYearsAtCompany(card: ElementHandle): Promise<string | undefined> {
    try {
      const text = await card.textContent();
      if (!text) return undefined;

      // Look for patterns like "3 years 2 months" or "2 yrs"
      const yearMatch = text.match(TEXT_PATTERNS.years);
      const monthMatch = text.match(TEXT_PATTERNS.months);

      if (yearMatch || monthMatch) {
        let result = '';
        if (yearMatch) {
          result += `${yearMatch[1]} year${parseInt(yearMatch[1]) !== 1 ? 's' : ''}`;
        }
        if (monthMatch) {
          if (result) result += ' ';
          result += `${monthMatch[1]} month${parseInt(monthMatch[1]) !== 1 ? 's' : ''}`;
        }
        return result;
      }

      return undefined;
    } catch (error) {
      return undefined;
    }
  }

  /**
   * Extract industry from profile card
   */
  async extractIndustry(card: ElementHandle): Promise<string | undefined> {
    try {
      for (const selector of CARD_SELECTORS.industry) {
        const element = await card.$(selector);
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
}
