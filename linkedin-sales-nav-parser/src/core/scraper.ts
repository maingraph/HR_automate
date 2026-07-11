import { chromium, Browser, Page, BrowserContext } from 'playwright';
import { ScraperConfig, ScraperOptions, ProfileData, Checkpoint } from './types';
import Logger from '../utils/logger';
import StealthUtilities from '../utils/stealth';
import RateLimiter from '../utils/rate-limiter';
import ChromeDetector from '../utils/chrome-detector';
import CheckpointManager from '../storage/checkpoint';
import DuplicateTracker from '../storage/duplicate-tracker';
import CSVExporter from '../storage/csv-exporter';
import Notifier from '../utils/notifier';
import Parser from '../extractors/parser';

class Scraper {
  private config: ScraperConfig;
  private options: ScraperOptions;
  private logger: Logger;
  private stealth: StealthUtilities;
  private rateLimiter: RateLimiter;
  private chromeDetector: ChromeDetector;
  private checkpointManager: CheckpointManager;
  private duplicateTracker: DuplicateTracker;
  private csvExporter: CSVExporter;
  private notifier: Notifier;
  private parser: Parser;
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private sessionId: string;
  private startTime: Date;
  private errorCount: number = 0;
  private warningCount: number = 0;

  constructor(config: ScraperConfig, options: ScraperOptions, logger: Logger) {
    this.config = config;
    this.options = options;
    this.logger = logger;
    this.stealth = new StealthUtilities(config);
    this.rateLimiter = new RateLimiter(config, logger);
    this.chromeDetector = new ChromeDetector(logger);
    this.checkpointManager = new CheckpointManager(logger);
    // Note: duplicateTracker will be initialized in scrape() after we have the search URL
    this.duplicateTracker = null as any; // Temporary, will be set in scrape()
    this.csvExporter = new CSVExporter(logger);
    this.notifier = new Notifier(logger, !options.noSound);
    this.parser = new Parser(logger);
    this.sessionId = this.generateSessionId();
    this.startTime = new Date();
  }

  async scrape(): Promise<void> {
    try {
      this.logger.header('LinkedIn Sales Navigator Scraper v1.0.0');
      this.logger.info('Initializing scraper...');
      this.logger.info('TIP: Make sure you are logged into LinkedIn Sales Navigator in Chrome before running');
      this.logger.info('If not logged in, you will have 2 minutes to complete the login');

      // Detect Chrome profile
      const chromeProfile = await this.chromeDetector.detectChromeProfile();
      this.logger.success('✓ Profile validated (LinkedIn session found)');

      // Connect to browser
      this.logger.info('Connecting to Chrome browser...');
      this.context = await chromium.launchPersistentContext(chromeProfile, {
        headless: this.config.browser.headless,
        executablePath: this.chromeDetector.getChromeExecutablePath(),
        viewport: { width: 1920, height: 1080 },
        userAgent: this.stealth.getRandomUserAgent(),
      });

      this.logger.success('✓ Connected successfully');

      // Create new page
      const page = await this.context.newPage();
      await this.stealth.setupStealthMode(page);

      // Determine search URL
      const searchUrl = this.options.url;
      if (!searchUrl) {
        throw new Error('No search URL provided');
      }

      // Initialize duplicate tracker - always in memory only (no persistence)
      this.duplicateTracker = new DuplicateTracker(this.logger, searchUrl, true); // Always fresh mode

      // Log duplicate detection status
      if (this.options.noDedup) {
        this.logger.warn('⚠️  Duplicate detection DISABLED (--no-dedup flag)');
        this.logger.warn('All profiles will be scraped, including duplicates');
      } else {
        this.logger.info('Duplicate detection enabled (use --no-dedup to disable)');
      }

      // Navigate to search
      this.logger.info('Navigating to Sales Navigator search...');
      this.logger.info(`URL: ${searchUrl}`);
      try {
        await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
      } catch (error) {
        // If navigation times out, check if we're on the page anyway
        const currentUrl = page.url();
        if (!currentUrl.includes('linkedin.com')) {
          throw error;
        }
        this.logger.warn('Navigation timeout, but page loaded - continuing...');
      }
      await this.rateLimiter.delay('pageLoad');
      
      // Check if we got redirected to login
      const currentUrl = page.url();
      if (currentUrl.includes('/sales/login') || currentUrl.includes('/login')) {
        this.logger.warn('Redirected to login page');
        this.logger.warn('Please log in to LinkedIn Sales Navigator in the browser window');
        this.logger.info('Waiting up to 3 minutes for you to complete login...');
        
        // Wait for user to login and navigate back to search
        let loggedIn = false;
        const maxAttempts = 36; // 3 minutes (36 * 5 seconds)
        
        for (let i = 0; i < maxAttempts; i++) {
          await page.waitForTimeout(5000);
          const url = page.url();
          
          if (url.includes('/sales/search') || url.includes('/sales/home')) {
            loggedIn = true;
            this.logger.success('✓ Login successful!');
            
            // If we're on home page, navigate to search
            if (url.includes('/sales/home')) {
              this.logger.info('Navigating to search URL...');
              try {
                await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
              } catch (error) {
                const currentUrl = page.url();
                if (!currentUrl.includes('linkedin.com')) {
                  throw error;
                }
                this.logger.warn('Navigation timeout, but page loaded - continuing...');
              }
            }
            break;
          }
        }
        
        if (!loggedIn) {
          throw new Error('Login timeout. Please try again and complete login within 3 minutes.');
        }
      }
      
      this.logger.success('✓ Page loaded');

      // Wait for results
      this.logger.info('Waiting for search results...');
      await this.waitForResults(page);
      this.logger.success('✓ Search results loaded');

      // Main scraping loop
      const allProfiles: ProfileData[] = [];
      let currentPage = 1;
      let totalScraped = 0;
      let profilesSkipped = 0;
      const maxProfiles = this.options.maxProfiles || this.config.limits.maxProfilesPerSession;
      const maxPages = this.options.maxPages || this.config.limits.maxPagesPerSession;
      const csvFilename = this.csvExporter.generateFilename();

      // Test mode override
      if (this.options.test) {
        this.logger.warn('TEST MODE: Limited to 3 profiles');
      }

      while (currentPage <= maxPages) {
        this.logger.separator();
        this.logger.info(`Processing page ${currentPage}...`);

        // Scroll to load all results
        this.logger.info('Scrolling to load all results on page...');
        await this.stealth.scrollToLoadAll(page);
        this.logger.success('✓ All results loaded');

        // Get all profile cards
        const cards = await this.parser.getAllProfileCards(page);
        
        if (cards.length === 0) {
          this.logger.warn('No profiles found on this page');
          break;
        }

        this.logger.info(`Found ${cards.length} profiles on page ${currentPage}`);
        this.logger.info('Starting extraction...');
        this.logger.separator();

        // Extract each profile
        for (let i = 0; i < cards.length; i++) {
          try {
            const card = cards[i];

            // Parse profile (this will click and open sidebar)
            const profile = await this.parser.parseProfileCard(card, page);
            
            if (!profile) {
              this.logger.warn(`Skipping profile ${i + 1} (failed to parse)`);
              continue;
            }

            // Check for duplicates (unless --no-dedup flag is set)
            let isDuplicate = false;
            if (!this.options.noDedup) {
              // Use URL if available (LinkedIn only), otherwise use name+company as identifier
              let identifier: string;
              
              if (profile.profileUrl && profile.profileUrl.trim() !== '' && profile.profileUrl.includes('/in/')) {
                // Normalize URL (remove query params and fragments for comparison)
                try {
                  const url = new URL(profile.profileUrl);
                  identifier = `${url.origin}${url.pathname}`;
                } catch (e) {
                  // If URL parsing fails, use as-is
                  identifier = profile.profileUrl;
                }
              } else {
                // For profiles without LinkedIn URL, use name+company as unique identifier
                identifier = `${profile.fullName}|${profile.currentCompany}`.toLowerCase();
                this.logger.debug(`Using name+company identifier for ${profile.fullName} (no LinkedIn URL)`);
              }

              if (this.duplicateTracker.isScraped(identifier)) {
                this.logger.warn(`Possible duplicate: ${profile.fullName} (marking as duplicate, still saving)`);
                isDuplicate = true;
                profilesSkipped++;
              }

              // Mark as scraped (in-memory only)
              await this.duplicateTracker.markAsScraped(identifier);
            }

            // Mark profile as possible duplicate if detected
            if (isDuplicate) {
              profile.possibleDuplicate = true;
            }

            // Log profile details
            this.logger.profile(profile, i + 1, cards.length);

            // Add to results
            allProfiles.push(profile);
            totalScraped++;

            // Human-like delay
            await this.rateLimiter.delay('betweenProfiles');

            // Random page interaction
            if (Math.random() > 0.7) {
              await this.stealth.randomPageInteraction(page);
            }

            // Take break if needed
            if (this.rateLimiter.shouldTakeBreak(totalScraped)) {
              await this.rateLimiter.takeBreak();
            }

            // Check for CAPTCHA
            if (await this.stealth.detectCaptcha(page)) {
              this.logger.error('CAPTCHA detected! Pausing scraper...');
              this.logger.warn('Please solve the CAPTCHA in the browser window');
              this.logger.warn('Saving current progress to CSV...');
              await this.notifier.notifyError('CAPTCHA detected');
              
              // Save what we have so far
              if (allProfiles.length > 0) {
                await this.csvExporter.exportToCSV(allProfiles, csvFilename);
                this.logger.success(`✓ Saved ${allProfiles.length} profiles before CAPTCHA`);
              }
              
              // Wait indefinitely for user to solve
              await new Promise(() => {});
            }

            // Check for warnings
            if (await this.stealth.detectWarning(page)) {
              this.logger.error('LinkedIn warning detected! Stopping scraper...');
              this.warningCount++;
              await this.notifier.notifyError('LinkedIn warning detected');
              break;
            }

            // Check limits
            if (this.options.test && totalScraped >= 3) {
              this.logger.info('Test mode limit reached (3 profiles)');
              break;
            }

            if (totalScraped >= maxProfiles) {
              this.logger.info('Max profiles reached');
              break;
            }

          } catch (error) {
            this.logger.error(`Error processing profile ${i + 1}`, error as Error);
            this.errorCount++;
            continue;
          }
        }

        // Save profiles from this page to CSV incrementally
        if (allProfiles.length > 0) {
          try {
            this.logger.info(`Saving ${allProfiles.length} profiles to CSV...`);
            if (currentPage > 1) {
              // Append to existing CSV
              await this.csvExporter.appendToCSV(allProfiles, csvFilename);
            } else {
              // Create new CSV for first page
              await this.csvExporter.exportToCSV(allProfiles, csvFilename);
            }
            this.logger.success(`✓ Saved ${allProfiles.length} profiles to CSV`);
            // Clear the array after saving to free memory
            allProfiles.length = 0;
          } catch (error) {
            this.logger.error('Failed to save profiles to CSV', error as Error);
          }
        }

        // Check if we should continue
        if (totalScraped >= maxProfiles || (this.options.test && totalScraped >= 3)) {
          break;
        }

        // Move to next page
        if (await this.hasNextPage(page)) {
          this.logger.info('Checking for next page...');
          this.logger.success('✓ Next page available');
          this.logger.info('Moving to next page...');
          
          await this.goToNextPage(page);
          await this.rateLimiter.delay('pageLoad');
          currentPage++;
          
          this.logger.success(`✓ Page ${currentPage} loaded`);
        } else {
          this.logger.info('No more pages available');
          break;
        }
      }

      // Final CSV export (for any remaining profiles)
      this.logger.separator();
      
      let csvPath: string;
      if (allProfiles.length > 0) {
        this.logger.info('Exporting remaining profiles to CSV...');
        if (totalScraped > allProfiles.length) {
          // Append remaining profiles to existing CSV
          await this.csvExporter.appendToCSV(allProfiles, csvFilename);
        } else {
          // Create new CSV if this is the only batch
          await this.csvExporter.exportToCSV(allProfiles, csvFilename);
        }
        csvPath = this.csvExporter.getOutputPath(csvFilename);
        // Clear memory
        allProfiles.length = 0;
      } else {
        // All profiles already saved incrementally
        this.logger.info('All profiles saved incrementally during scraping');
        csvPath = this.csvExporter.getOutputPath(csvFilename);
      }

      // Close browser
      this.logger.info('Closing browser connection...');
      await this.context.close();
      this.logger.success('✓ Cleanup complete');

      // Show summary
      const sessionDuration = this.logger.getSessionDuration();
      this.logger.summary({
        totalProfiles: totalScraped,
        profilesSkipped,
        pagesScraped: currentPage,
        sessionDuration,
        csvFile: csvPath,
        logFile: this.logger.getLogFilePath(),
        errors: this.errorCount,
        warnings: this.warningCount,
      });

      // Notify completion
      await this.notifier.notifyCompletion(totalScraped);

    } catch (error) {
      this.logger.error('Scraper failed', error as Error);
      await this.notifier.notifyError('Scraper failed');
      
      // Try to save any profiles we collected before the crash
      if (this.context) {
        try {
          await this.context.close();
        } catch (e) {
          // Ignore cleanup errors
        }
      }
      
      throw error;
    } finally {
      // Clean up in-memory data
      if (this.duplicateTracker) {
        // Clear the in-memory set
        this.duplicateTracker = null as any;
      }
    }
  }

  private async waitForResults(page: Page): Promise<void> {
    try {
      // First check if we need to login
      const loginSelectors = [
        'input[type="email"]',
        'input[type="password"]',
        '#username',
        '#password',
        'form[data-test-id="sign-in-form"]',
      ];

      let needsLogin = false;
      for (const selector of loginSelectors) {
        const element = await page.$(selector);
        if (element) {
          needsLogin = true;
          break;
        }
      }

      if (needsLogin) {
        this.logger.warn('LinkedIn login page detected');
        this.logger.warn('Please log in to LinkedIn in the browser window');
        this.logger.info('Waiting up to 2 minutes for you to complete login...');
        
        // Wait for login to complete (up to 2 minutes)
        await page.waitForSelector('.artdeco-list__item, .entity-result, li.reusable-search__result-container, .search-results-container, [data-view-name="search-results-list"]', {
          timeout: 120000, // 2 minutes
        });
        
        this.logger.success('✓ Login successful, search results loaded');
        return;
      }

      // If no login needed, wait for results with longer timeout and more selectors
      this.logger.info('Waiting for search results to load...');
      
      const resultSelectors = [
        '.artdeco-list__item',
        '.entity-result',
        'li.reusable-search__result-container',
        '.search-results-container',
        '[data-view-name="search-results-list"]',
        'ol.search-results__list',
        '.search-results__list',
        'ul[class*="search-results"]',
      ];

      // Try each selector
      let found = false;
      for (const selector of resultSelectors) {
        try {
          await page.waitForSelector(selector, { timeout: 5000 });
          this.logger.debug(`Found results using selector: ${selector}`);
          found = true;
          break;
        } catch (e) {
          // Try next selector
          continue;
        }
      }

      if (!found) {
        // Debug: Get page title and URL
        const title = await page.title();
        const url = page.url();
        this.logger.error(`Page title: ${title}`);
        this.logger.error(`Page URL: ${url}`);
        
        // Check if we're on the right page
        if (!url.includes('linkedin.com/sales')) {
          throw new Error('Not on LinkedIn Sales Navigator. Please provide a valid Sales Navigator search URL.');
        }
        
        // Take a screenshot for debugging
        const screenshotPath = '/Users/imjustchilling/Desktop/linkedin-sales-nav-parser/debug-screenshot.png';
        await page.screenshot({ path: screenshotPath });
        this.logger.warn(`Screenshot saved to: ${screenshotPath}`);
        
        throw new Error('Could not find search results on the page. The page structure may have changed.');
      }

    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Search results did not load. Please check the URL and ensure you are logged into LinkedIn Sales Navigator.');
    }
  }

  private async hasNextPage(page: Page): Promise<boolean> {
    try {
      const nextButtonSelectors = [
        'button[aria-label="Next"]',
        'button.artdeco-pagination__button--next',
        'button[data-test-pagination-page-btn="next"]',
        '.artdeco-pagination__button--next:not([disabled])',
      ];

      for (const selector of nextButtonSelectors) {
        const button = await page.$(selector);
        if (button) {
          const isDisabled = await button.isDisabled();
          if (!isDisabled) {
            return true;
          }
        }
      }

      return false;
    } catch (error) {
      return false;
    }
  }

  private async goToNextPage(page: Page): Promise<void> {
    try {
      const nextButtonSelectors = [
        'button[aria-label="Next"]',
        'button.artdeco-pagination__button--next',
        'button[data-test-pagination-page-btn="next"]',
      ];

      for (const selector of nextButtonSelectors) {
        const button = await page.$(selector);
        if (button) {
          const isDisabled = await button.isDisabled();
          if (!isDisabled) {
            await button.click();
            await this.stealth.waitForNetworkIdle(page);
            return;
          }
        }
      }

      throw new Error('Could not find next page button');
    } catch (error) {
      throw new Error('Failed to navigate to next page');
    }
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

export default Scraper;
