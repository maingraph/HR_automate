import { Page } from 'playwright';
import Logger from '../utils/logger';
import { SIDEBAR_SELECTORS } from './selectors';
import { sanitizeText } from './text-utils';
import { ExperienceEntry } from '../core/types';

/**
 * Extracts experience data from the sidebar
 */
export class ExperienceExtractor {
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  /**
   * Extract experience section from sidebar
   */
  async extractExperienceFromSidebar(page: Page): Promise<ExperienceEntry[] | undefined> {
    try {
      // Use DOM-based extraction instead of text parsing
      let container: any = await page.$(SIDEBAR_SELECTORS.container[0]);
      if (!container) {
        container = await page.$(SIDEBAR_SELECTORS.container[1]);
      }
      
      if (!container) {
        return undefined;
      }
      
      // STEP 1: Try to click "Show more" or "Show all" button to expand all experiences
      await this.expandAllExperiences(page);
      
      const experience: ExperienceEntry[] = [];
      
      // Find all experience entry elements using the class we found in the HTML
      const experienceEntries = await container.$$('li[class*="experience-entry"]');
      
      if (experienceEntries.length === 0) {
        this.logger.debug('No experience entries found using DOM selector');
        return undefined;
      }
      
      this.logger.debug(`Found ${experienceEntries.length} experience entries using DOM`);
      
      // Extract data from each entry
      for (const entry of experienceEntries) {
        try {
          // Extract title
          const titleElement = await entry.$('[data-anonymize="job-title"]');
          const title = titleElement ? await titleElement.textContent() : null;
          
          // Extract company
          const companyElement = await entry.$('[data-anonymize="company-name"]');
          const company = companyElement ? await companyElement.textContent() : null;
          
          // Extract date range - look for the span with the specific class
          const dateElements = await entry.$$('span[class*="aPktgOMiFRRKWEmHFKHOkBGcyUKfUHAcqyQI"]');
          let dateRange = null;
          if (dateElements.length > 0) {
            dateRange = await dateElements[0].textContent();
          }
          
          // Extract duration (e.g., "2 yrs") - it's usually in the same <p> as the date
          let duration = null;
          if (dateRange) {
            // Find the parent <p> element and get all text
            const dateParent = await entry.$('p[class*="_bodyText_1e5nen"][class*="_sizeXSmall_1e5nen"]:has(span[class*="aPktgOMiFRRKWEmHFKHOkBGcyUKfUHAcqyQI"])');
            if (dateParent) {
              const fullDateText = await dateParent.textContent();
              if (fullDateText) {
                // Extract duration pattern like "2 yrs" or "1 yr 3 mos"
                const durationMatch = fullDateText.match(/(\d+\s+(?:yr|mo|year|month)s?(?:\s+\d+\s+(?:yr|mo|year|month)s?)?)/i);
                if (durationMatch) {
                  duration = durationMatch[1];
                }
              }
            }
          }
          
          // Extract location - look for the <p> with the specific class
          const locationElement = await entry.$('p[class*="ynAatejktGJGyTaATOFatmgcBydwPXbc"]');
          const location = locationElement ? await locationElement.textContent() : null;
          
          // Only add if we have at least title and company
          if (title && company) {
            const cleanTitle = sanitizeText(title);
            const cleanCompany = sanitizeText(company);
            
            // Skip if title or company is too short or looks like noise
            if (cleanTitle.length >= 3 && cleanCompany.length >= 2) {
              const expEntry: ExperienceEntry = {
                title: cleanTitle,
                company: cleanCompany,
                duration: '', // Default to empty string
              };
              
              if (dateRange) {
                const cleanDate = sanitizeText(dateRange);
                if (duration) {
                  expEntry.duration = `${cleanDate} (${sanitizeText(duration)})`;
                } else {
                  expEntry.duration = cleanDate;
                }
              }
              
              if (location) {
                expEntry.location = sanitizeText(location);
              }
              
              experience.push(expEntry);
              this.logger.debug(`Extracted: ${cleanTitle} at ${cleanCompany}`);
            }
          }
        } catch (entryError) {
          this.logger.debug(`Error extracting individual experience entry: ${entryError}`);
          continue;
        }
      }
      
      if (experience.length > 0) {
        this.logger.info(`Extracted ${experience.length} experience entries`);
        return experience;
      }
      
      this.logger.debug('No valid experience entries extracted');
      return undefined;
    } catch (error) {
      this.logger.error('Error extracting experience', error as Error);
      return undefined;
    }
  }

  /**
   * Expand all experiences by clicking "Show more" or "Show all" button
   */
  private async expandAllExperiences(page: Page): Promise<void> {
    try {
      // Possible selectors for "Show more" or "Show all experiences" button
      const showMoreSelectors = [
        'button:has-text("Show all")',
        'button:has-text("Show more")',
        'button[aria-label*="Show all"]',
        'button[aria-label*="Show more"]',
        'button[aria-label*="experience"]',
        'aside button:has-text("Show")',
        'div[class*="lead-details"] button:has-text("Show")',
        // Russian variants
        'button:has-text("Показать все")',
        'button:has-text("Показать больше")',
      ];

      for (const selector of showMoreSelectors) {
        try {
          const button = await page.$(selector);
          if (button) {
            // Check if button is visible and in the experience section
            const isVisible = await button.isVisible();
            if (!isVisible) continue;
            
            // Get button text to verify it's the right button
            const buttonText = await button.textContent();
            if (!buttonText) continue;
            
            // Only click if it mentions "experience" or "all" or is a generic "Show more"
            const lowerText = buttonText.toLowerCase();
            if (lowerText.includes('experience') || 
                lowerText.includes('all') || 
                lowerText.includes('show more') ||
                lowerText.includes('показать')) {
              
              this.logger.debug(`Found "Show more" button: "${buttonText.trim()}"`);
              
              // Use JS native click to avoid sidebar closing issues
              await page.$eval(selector, (btn) => {
                (btn as HTMLElement).click();
              });
              
              this.logger.debug('Clicked "Show more" button to expand experiences');
              
              // Wait for content to expand
              await page.waitForTimeout(800);
              return;
            }
          }
        } catch (e) {
          // Try next selector
          continue;
        }
      }
      
      this.logger.debug('No "Show more" button found for experiences (all may already be visible)');
    } catch (error) {
      this.logger.debug('Error expanding experiences, continuing with visible entries');
    }
  }
}
