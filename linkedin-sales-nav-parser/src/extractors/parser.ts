import { ElementHandle, Page } from 'playwright';
import { ProfileData } from '../core/types';
import Logger from '../utils/logger';
import { CardExtractor } from './card-extractor';
import { SidebarExtractor } from './sidebar-extractor';
import { ExperienceExtractor } from './experience-extractor';
import { EducationExtractor } from './education-extractor';
import { SkillsExtractor } from './skills-extractor';
import { CARD_SELECTORS, SIDEBAR_SELECTORS, SEARCH_SELECTORS, TIMEOUTS } from './selectors';
import { fuzzyMatch } from './text-utils';

/**
 * Main parser that orchestrates all extractors
 */
class Parser {
  private logger: Logger;
  private cardExtractor: CardExtractor;
  private sidebarExtractor: SidebarExtractor;
  private experienceExtractor: ExperienceExtractor;
  private educationExtractor: EducationExtractor;
  private skillsExtractor: SkillsExtractor;

  constructor(logger: Logger) {
    this.logger = logger;
    this.cardExtractor = new CardExtractor(logger);
    this.sidebarExtractor = new SidebarExtractor(logger);
    this.experienceExtractor = new ExperienceExtractor(logger);
    this.educationExtractor = new EducationExtractor(logger);
    this.skillsExtractor = new SkillsExtractor(logger);
  }

  /**
   * Parse a profile card and extract all data
   */
  async parseProfileCard(card: ElementHandle, page: Page): Promise<ProfileData | null> {
    try {
      // STEP 1: Try to get expected data from card BEFORE clicking
      let expectedName = await this.cardExtractor.extractName(card);
      const expectedCompany = await this.cardExtractor.extractCompany(card);
      
      this.logger.debug(`Clicking profile: ${expectedName || '(empty)'} at ${expectedCompany || '(empty)'}`);
      
      // STEP 2: Click on the profile card to open the sidebar
      await this.clickProfileCard(card, page);
      
      // STEP 3: Wait for sidebar to appear
      await this.waitForSidebarToAppear(page);
      
      // STEP 4: If card name is empty, extract from sidebar for verification
      if (!expectedName || expectedName.trim() === '') {
        this.logger.debug('Card name empty, extracting from sidebar for verification');
        expectedName = await this.sidebarExtractor.extractNameFromSidebar(page);
        
        if (!expectedName) {
          this.logger.warn('Could not extract name from sidebar either');
          return null;
        }
        
        this.logger.debug(`Using sidebar name for verification: ${expectedName}`);
      }
      
      // STEP 5: Verify sidebar updated with correct profile
      await this.waitForSidebarToUpdate(page, expectedName, expectedCompany);
      
      // STEP 6: Extract data with retry logic
      const profileUrl = await this.sidebarExtractor.extractProfileUrlWithRetry(page, 3);
      
      // STEP 7: Extract other data from sidebar
      const fullName = await this.sidebarExtractor.extractNameFromSidebar(page);
      const headline = await this.sidebarExtractor.extractHeadlineFromSidebar(page);
      const currentCompany = await this.sidebarExtractor.extractCompanyFromSidebar(page);
      const location = await this.sidebarExtractor.extractLocationFromSidebar(page);
      const profileImageUrl = await this.sidebarExtractor.extractProfileImageFromSidebar(page);
      const connectionDegree = await this.sidebarExtractor.extractConnectionDegreeFromSidebar(page);
      const isPremium = await this.sidebarExtractor.extractPremiumStatusFromSidebar(page);
      const sharedConnections = await this.sidebarExtractor.extractSharedConnectionsFromSidebar(page);
      const yearsAtCompany = await this.sidebarExtractor.extractYearsAtCompanyFromSidebar(page);
      const industry = await this.sidebarExtractor.extractIndustryFromSidebar(page);
      
      // Extract detailed data
      const about = await this.sidebarExtractor.extractAboutFromSidebar(page);
      const experience = await this.experienceExtractor.extractExperienceFromSidebar(page);
      const education = await this.educationExtractor.extractEducationFromSidebar(page);
      const skills = await this.skillsExtractor.extractSkillsFromSidebar(page);
      const languages = await this.skillsExtractor.extractLanguagesFromSidebar(page);

      // Validate required fields
      if (!fullName) {
        this.logger.warn('Skipping profile: missing required fields (name)');
        return null;
      }

      return {
        fullName,
        headline: headline || '',
        currentCompany: currentCompany || '',
        location: location || '',
        profileUrl: profileUrl || '', // Only LinkedIn URLs, empty if not found
        profileImageUrl: profileImageUrl || '',
        connectionDegree: connectionDegree || 'Unknown',
        isPremium,
        sharedConnections,
        yearsAtCompany,
        industry,
        about,
        experience,
        education,
        skills,
        languages,
        scrapedAt: new Date().toISOString(),
      };
    } catch (error) {
      this.logger.error('Failed to parse profile card', error as Error);
      return null;
    }
  }

  /**
   * Click on a profile card to open the sidebar
   */
  private async clickProfileCard(card: ElementHandle, page: Page): Promise<void> {
    try {
      // Try to find and click the profile link/button
      for (const selector of CARD_SELECTORS.clickable) {
        const element = await card.$(selector);
        if (element) {
          await element.click();
          this.logger.debug('Clicked profile to open sidebar');
          return;
        }
      }

      // Fallback: click the card itself
      await card.click();
      this.logger.debug('Clicked profile card');
    } catch (error) {
      this.logger.warn('Failed to click profile card');
    }
  }

  /**
   * Wait for sidebar to appear (without verification)
   */
  private async waitForSidebarToAppear(page: Page): Promise<void> {
    try {
      await page.waitForSelector(SIDEBAR_SELECTORS.container.join(', '), { 
        timeout: TIMEOUTS.sidebarAppear, 
        state: 'visible' 
      });
      // Give it a moment to start loading content
      await page.waitForTimeout(TIMEOUTS.afterClick);
      this.logger.debug('✓ Sidebar appeared');
    } catch (e) {
      this.logger.warn('Sidebar did not appear, proceeding anyway');
      await page.waitForTimeout(2000);
    }
  }

  /**
   * Wait for sidebar to update with the correct profile
   * This prevents race conditions where we extract data from the wrong profile
   */
  private async waitForSidebarToUpdate(
    page: Page,
    expectedName: string,
    expectedCompany: string
  ): Promise<void> {
    const maxAttempts = 15; // 15 seconds max
    let lastSeenName = '';
    
    // Verify the content matches what we clicked
    for (let i = 0; i < maxAttempts; i++) {
      await page.waitForTimeout(TIMEOUTS.sidebarUpdate);
      
      try {
        const sidebarName = await this.sidebarExtractor.extractNameFromSidebar(page);
        lastSeenName = sidebarName;
        
        // Fuzzy match (handles slight variations)
        const nameMatch = fuzzyMatch(sidebarName, expectedName);
        
        if (nameMatch) {
          this.logger.debug(`✓ Sidebar updated in ${i + 1}s: ${sidebarName}`);
          // Give it one more second to fully load all content
          await page.waitForTimeout(TIMEOUTS.afterClick);
          return;
        }
        
        this.logger.debug(`⏳ Waiting for sidebar to update... (${i + 1}s) Expected: ${expectedName}, Got: ${sidebarName}`);
      } catch (error) {
        // Continue waiting
        this.logger.debug(`⏳ Waiting for sidebar content... (${i + 1}s)`);
      }
    }
    
    // If we get here, sidebar didn't update - throw error
    throw new Error(
      `Sidebar did not update after 15s.\n` +
      `Expected: ${expectedName}\n` +
      `Got: ${lastSeenName || 'no name found'}`
    );
  }

  /**
   * Get all profile cards from the search results page
   */
  async getAllProfileCards(page: Page): Promise<ElementHandle[]> {
    try {
      // Wait for results to load
      await page.waitForSelector('.artdeco-list__item, .entity-result, li.reusable-search__result-container', {
        timeout: 10000,
      });

      // Get all profile cards
      for (const selector of SEARCH_SELECTORS.profileCards) {
        const cards = await page.$$(selector);
        if (cards.length > 0) {
          this.logger.info(`Found ${cards.length} profile cards using selector: ${selector}`);
          return cards;
        }
      }

      this.logger.warn('No profile cards found');
      return [];
    } catch (error) {
      this.logger.error('Failed to get profile cards', error as Error);
      return [];
    }
  }
}

export default Parser;
