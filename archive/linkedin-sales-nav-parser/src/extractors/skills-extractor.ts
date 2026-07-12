import { Page } from 'playwright';
import Logger from '../utils/logger';
import { SIDEBAR_SELECTORS } from './selectors';
import { sanitizeText } from './text-utils';
import { SkillEntry, LanguageEntry } from '../core/types';

/**
 * Extracts skills and languages data from the sidebar
 */
export class SkillsExtractor {
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  /**
   * Extract skills section from sidebar
   */
  async extractSkillsFromSidebar(page: Page): Promise<SkillEntry[] | undefined> {
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
      
      const skills: SkillEntry[] = [];
      
      // Look for skills section
      const skillsSectionMatch = containerText.match(/Featured skills and endorsements\s*\n([\s\S]*?)(?:\n\s*View all skills|\n\s*Languages|\n\s*Timeline|$)/i);
      if (skillsSectionMatch && skillsSectionMatch[1]) {
        const skillsText = skillsSectionMatch[1];
        const lines = skillsText.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 0);
        
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          
          // Skip "View all skills" line
          if (line.includes('View all skills')) {
            continue;
          }
          
          // Check if next line is endorsements
          let endorsements = 0;
          if (i + 1 < lines.length) {
            const nextLine = lines[i + 1];
            const endorsementMatch = nextLine.match(/(\d+)\s+endorsement/i);
            if (endorsementMatch) {
              endorsements = parseInt(endorsementMatch[1]);
              i++; // Skip the endorsement line
            }
          }
          
          // If line doesn't contain "endorsement", it's a skill name
          if (!line.match(/\d+\s+endorsement/i) && line.length > 1 && line.length < 100) {
            skills.push({
              name: sanitizeText(line),
              endorsements: endorsements || undefined,
            });
          }
        }
      }
      
      if (skills.length > 0) {
        this.logger.debug(`Found ${skills.length} skills`);
        return skills;
      }
      
      return undefined;
    } catch (error) {
      this.logger.debug('Error extracting skills');
      return undefined;
    }
  }

  /**
   * Extract languages section from sidebar
   */
  async extractLanguagesFromSidebar(page: Page): Promise<LanguageEntry[] | undefined> {
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
      
      const languages: LanguageEntry[] = [];
      
      // Look for languages section
      const langSectionMatch = containerText.match(/Languages\s*\n([\s\S]*?)(?:\n\s*Timeline|$)/i);
      if (langSectionMatch && langSectionMatch[1]) {
        const langText = langSectionMatch[1];
        const lines = langText.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 0);
        
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          
          // Language name
          if (line.length > 1 && line.length < 50 && !line.includes('proficiency')) {
            let proficiency = '';
            
            // Next line might be proficiency
            if (i + 1 < lines.length) {
              const nextLine = lines[i + 1];
              if (nextLine.includes('proficiency') || nextLine.includes('Native') || 
                  nextLine.includes('Professional') || nextLine.includes('Elementary')) {
                proficiency = nextLine;
                i++;
              }
            }
            
            languages.push({
              name: sanitizeText(line),
              proficiency: proficiency ? sanitizeText(proficiency) : undefined,
            });
          }
        }
      }
      
      if (languages.length > 0) {
        this.logger.debug(`Found ${languages.length} languages`);
        return languages;
      }
      
      return undefined;
    } catch (error) {
      this.logger.debug('Error extracting languages');
      return undefined;
    }
  }
}
