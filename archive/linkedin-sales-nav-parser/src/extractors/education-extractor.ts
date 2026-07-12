import { Page } from 'playwright';
import Logger from '../utils/logger';
import { SIDEBAR_SELECTORS } from './selectors';
import { sanitizeText } from './text-utils';
import { EducationEntry } from '../core/types';

/**
 * Extracts education data from the sidebar
 */
export class EducationExtractor {
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  /**
   * Extract education section from sidebar
   */
  async extractEducationFromSidebar(page: Page): Promise<EducationEntry[] | undefined> {
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
      
      const education: EducationEntry[] = [];
      
      // Look for education section
      const eduSectionMatch = containerText.match(/Education\s*\n([\s\S]*?)(?:\n\s*Featured skills|\n\s*Languages|\n\s*Timeline|$)/i);
      if (eduSectionMatch && eduSectionMatch[1]) {
        const eduText = eduSectionMatch[1];
        const lines = eduText.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 0);
        
        let i = 0;
        while (i < lines.length) {
          const line = lines[i];
          
          // School name is usually the first line (longer, not a year)
          if (!line.match(/^\d{4}/) && line.length > 5 && line.length < 150) {
            const school = line;
            let degree = '';
            let field = '';
            let duration = '';
            
            // Next line might be degree
            if (i + 1 < lines.length) {
              const nextLine = lines[i + 1];
              if (!nextLine.match(/^\d{4}/) && nextLine.length < 100) {
                degree = nextLine;
                i++;
                
                // Check if there's a field of study on the same line or next
                if (degree.includes(',')) {
                  const parts = degree.split(',');
                  degree = parts[0].trim();
                  field = parts.slice(1).join(',').trim();
                } else if (i + 1 < lines.length) {
                  const nextLine2 = lines[i + 1];
                  if (!nextLine2.match(/^\d{4}/) && nextLine2.length < 100) {
                    field = nextLine2;
                    i++;
                  }
                }
              }
            }
            
            // Next line might be duration
            if (i + 1 < lines.length) {
              const nextLine = lines[i + 1];
              if (nextLine.match(/^\d{4}/)) {
                duration = nextLine;
                i++;
              }
            }
            
            if (school) {
              education.push({
                school: sanitizeText(school),
                degree: degree ? sanitizeText(degree) : undefined,
                field: field ? sanitizeText(field) : undefined,
                duration: duration ? sanitizeText(duration) : undefined,
              });
            }
          }
          
          i++;
        }
      }
      
      if (education.length > 0) {
        this.logger.debug(`Found ${education.length} education entries`);
        return education;
      }
      
      return undefined;
    } catch (error) {
      this.logger.debug('Error extracting education');
      return undefined;
    }
  }
}
