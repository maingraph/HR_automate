import { chromium, Browser, Page, BrowserContext } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Script to extract raw sidebar HTML and text from LinkedIn profiles
 * This helps analyze patterns for AI-based extraction or improving selectors
 */

interface RawProfileData {
  profileIndex: number;
  cardName: string;
  cardCompany: string;
  cardHeadline: string;
  sidebarHTML: string;
  sidebarText: string;
  sidebarOuterHTML: string;
  timestamp: string;
  pageUrl: string;
}

class RawDataExtractor {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private outputDir: string;

  constructor() {
    this.outputDir = path.join(__dirname, '..', 'data', 'raw-extractions');
    // Create output directory if it doesn't exist
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
  }

  async run(searchUrl: string, maxProfiles: number = 10) {
    try {
      console.log('🚀 Starting raw data extraction...');
      console.log(`📊 Will extract ${maxProfiles} profiles`);
      console.log(`💾 Output directory: ${this.outputDir}`);
      console.log('');

      // Detect Chrome profile
      const chromeProfile = await this.detectChromeProfile();
      console.log('✓ Chrome profile detected');

      // Connect to browser
      console.log('🌐 Connecting to Chrome...');
      this.context = await chromium.launchPersistentContext(chromeProfile, {
        headless: false,
        executablePath: this.getChromeExecutablePath(),
        viewport: { width: 1920, height: 1080 },
      });

      const page = await this.context.newPage();
      console.log('✓ Connected to Chrome');

      // Navigate to search
      console.log('🔍 Navigating to Sales Navigator...');
      await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(3000);
      console.log('✓ Page loaded');

      // Wait for results
      console.log('⏳ Waiting for search results...');
      await page.waitForSelector('.artdeco-list__item, .entity-result, li.reusable-search__result-container', {
        timeout: 10000,
      });
      console.log('✓ Search results loaded');
      console.log('');

      // Scroll to load all results
      console.log('📜 Scrolling to load all results...');
      await this.scrollToLoadAll(page);
      console.log('✓ All results loaded');
      console.log('');

      // Get all profile cards
      const cards = await page.$$('li.artdeco-list__item, div[data-x--search-result], .search-results__result-item');
      console.log(`📋 Found ${cards.length} profile cards`);
      console.log('');

      const allRawData: RawProfileData[] = [];
      const limit = Math.min(maxProfiles, cards.length);

      // Extract raw data from each profile
      for (let i = 0; i < limit; i++) {
        try {
          console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
          console.log(`📝 Extracting profile ${i + 1}/${limit}`);
          console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);

          const card = cards[i];

          // Extract data from card first
          const cardName = await this.extractCardName(card);
          const cardCompany = await this.extractCardCompany(card);
          const cardHeadline = await this.extractCardHeadline(card);

          console.log(`👤 Card Name: ${cardName || '(empty)'}`);
          console.log(`🏢 Card Company: ${cardCompany || '(empty)'}`);
          console.log(`💼 Card Headline: ${cardHeadline || '(empty)'}`);

          // Click on the profile card to open sidebar
          console.log('🖱️  Clicking profile...');
          await this.clickCard(card);
          await page.waitForTimeout(2000);

          // Wait for sidebar to appear
          console.log('⏳ Waiting for sidebar...');
          await page.waitForSelector('aside, div[class*="lead-details"]', {
            timeout: 5000,
            state: 'visible',
          });
          await page.waitForTimeout(2000); // Give it time to fully load

          // Extract raw sidebar data
          console.log('📦 Extracting raw sidebar data...');
          const sidebarHTML = await this.extractSidebarHTML(page);
          const sidebarText = await this.extractSidebarText(page);
          const sidebarOuterHTML = await this.extractSidebarOuterHTML(page);

          console.log(`📏 HTML length: ${sidebarHTML.length} characters`);
          console.log(`📏 Text length: ${sidebarText.length} characters`);
          console.log(`📏 Outer HTML length: ${sidebarOuterHTML.length} characters`);

          const rawData: RawProfileData = {
            profileIndex: i + 1,
            cardName,
            cardCompany,
            cardHeadline,
            sidebarHTML,
            sidebarText,
            sidebarOuterHTML,
            timestamp: new Date().toISOString(),
            pageUrl: page.url(),
          };

          allRawData.push(rawData);
          console.log('✅ Profile data extracted');

          // Save individual profile data
          const filename = `profile_${i + 1}_${Date.now()}.json`;
          const filepath = path.join(this.outputDir, filename);
          fs.writeFileSync(filepath, JSON.stringify(rawData, null, 2));
          console.log(`💾 Saved to: ${filename}`);

          // Small delay between profiles
          await page.waitForTimeout(2000);

        } catch (error) {
          console.error(`❌ Error extracting profile ${i + 1}:`, error);
          continue;
        }
      }

      // Save combined data
      console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      console.log('💾 Saving combined data...');
      const combinedFilename = `all_profiles_${Date.now()}.json`;
      const combinedFilepath = path.join(this.outputDir, combinedFilename);
      fs.writeFileSync(combinedFilepath, JSON.stringify(allRawData, null, 2));
      console.log(`✅ Saved combined data to: ${combinedFilename}`);

      // Create summary
      const summary = {
        totalProfiles: allRawData.length,
        timestamp: new Date().toISOString(),
        searchUrl,
        profiles: allRawData.map(p => ({
          index: p.profileIndex,
          cardName: p.cardName,
          cardCompany: p.cardCompany,
          hasHTML: p.sidebarHTML.length > 0,
          hasText: p.sidebarText.length > 0,
        })),
      };

      const summaryFilepath = path.join(this.outputDir, `summary_${Date.now()}.json`);
      fs.writeFileSync(summaryFilepath, JSON.stringify(summary, null, 2));
      console.log(`📊 Saved summary to: summary_${Date.now()}.json`);

      console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      console.log('🎉 Extraction complete!');
      console.log(`📁 Output directory: ${this.outputDir}`);
      console.log(`📊 Total profiles extracted: ${allRawData.length}`);
      console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

      // Close browser
      await this.context.close();

    } catch (error) {
      console.error('❌ Fatal error:', error);
      if (this.context) {
        await this.context.close();
      }
      throw error;
    }
  }

  private async extractCardName(card: any): Promise<string> {
    const selectors = [
      '[data-anonymize="person-name"]',
      '.artdeco-entity-lockup__title',
      '.entity-result__title-text a',
      'a[data-control-name="view_lead_panel_via_search_lead_name"]',
      '.artdeco-entity-lockup__title a',
      'a.app-aware-link span[aria-hidden="true"]',
    ];

    for (const selector of selectors) {
      try {
        const element = await card.$(selector);
        if (element) {
          const text = await element.textContent();
          if (text && text.trim()) {
            return text.trim();
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  private async extractCardCompany(card: any): Promise<string> {
    const selectors = [
      '[data-anonymize="company-name"]',
      '.artdeco-entity-lockup__caption',
      '.entity-result__secondary-subtitle',
    ];

    for (const selector of selectors) {
      try {
        const element = await card.$(selector);
        if (element) {
          const text = await element.textContent();
          if (text && text.trim()) {
            return text.trim();
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  private async extractCardHeadline(card: any): Promise<string> {
    const selectors = [
      '[data-anonymize="title"]',
      '.artdeco-entity-lockup__subtitle',
      '.entity-result__primary-subtitle',
      '.artdeco-entity-lockup__subtitle span[aria-hidden="true"]',
    ];

    for (const selector of selectors) {
      try {
        const element = await card.$(selector);
        if (element) {
          const text = await element.textContent();
          if (text && text.trim()) {
            return text.trim();
          }
        }
      } catch (error) {
        continue;
      }
    }
    return '';
  }

  private async clickCard(card: any): Promise<void> {
    const selectors = [
      'a[data-control-name="view_lead_panel_via_search_lead_name"]',
      '.artdeco-entity-lockup__title a',
      'a[href*="/sales/lead/"]',
      'a[href*="/sales/people/"]',
    ];

    for (const selector of selectors) {
      try {
        const element = await card.$(selector);
        if (element) {
          await element.click();
          return;
        }
      } catch (error) {
        continue;
      }
    }

    // Fallback: click the card itself
    await card.click();
  }

  private async extractSidebarHTML(page: Page): Promise<string> {
    try {
      // Try aside first
      const asideContainer = await page.$('aside');
      if (asideContainer) {
        const html = await asideContainer.innerHTML();
        return html;
      }

      // Fallback to lead-details div
      const divContainer = await page.$('div[class*="lead-details"]');
      if (divContainer) {
        const html = await divContainer.innerHTML();
        return html;
      }

      return '';
    } catch (error) {
      return '';
    }
  }

  private async extractSidebarText(page: Page): Promise<string> {
    try {
      // Try aside first
      const asideContainer = await page.$('aside');
      if (asideContainer) {
        const text = await asideContainer.textContent();
        return text || '';
      }

      // Fallback to lead-details div
      const divContainer = await page.$('div[class*="lead-details"]');
      if (divContainer) {
        const text = await divContainer.textContent();
        return text || '';
      }

      return '';
    } catch (error) {
      return '';
    }
  }

  private async extractSidebarOuterHTML(page: Page): Promise<string> {
    try {
      // Try aside first
      const asideContainer = await page.$('aside');
      if (asideContainer) {
        const html = await page.evaluate((el) => el.outerHTML, asideContainer);
        return html;
      }

      // Fallback to lead-details div
      const divContainer = await page.$('div[class*="lead-details"]');
      if (divContainer) {
        const html = await page.evaluate((el) => el.outerHTML, divContainer);
        return html;
      }

      return '';
    } catch (error) {
      return '';
    }
  }

  private async scrollToLoadAll(page: Page): Promise<void> {
    await page.evaluate(async () => {
      const scrollableElement = document.querySelector('.search-results-container') || document.body;
      const scrollHeight = scrollableElement.scrollHeight;
      const scrollStep = 300;
      let currentScroll = 0;

      while (currentScroll < scrollHeight) {
        scrollableElement.scrollBy(0, scrollStep);
        currentScroll += scrollStep;
        await new Promise(resolve => setTimeout(resolve, 200));
      }
    });

    await page.waitForTimeout(1000);
  }

  private async detectChromeProfile(): Promise<string> {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const possiblePaths = [
      path.join(homeDir, 'Library/Application Support/Google/Chrome/Default'),
      path.join(homeDir, 'Library/Application Support/Google/Chrome/Profile 1'),
      path.join(homeDir, 'AppData/Local/Google/Chrome/User Data/Default'),
      path.join(homeDir, '.config/google-chrome/Default'),
    ];

    for (const profilePath of possiblePaths) {
      if (fs.existsSync(profilePath)) {
        return profilePath;
      }
    }

    throw new Error('Could not find Chrome profile. Please make sure Chrome is installed.');
  }

  private getChromeExecutablePath(): string {
    const platform = process.platform;

    if (platform === 'darwin') {
      return '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
    } else if (platform === 'win32') {
      return 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
    } else {
      return '/usr/bin/google-chrome';
    }
  }
}

// Main execution
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.error('❌ Error: Please provide a Sales Navigator search URL');
    console.log('\nUsage:');
    console.log('  npm run extract-raw -- "YOUR_SALES_NAV_URL"');
    console.log('  npm run extract-raw -- "YOUR_SALES_NAV_URL" 20  # Extract 20 profiles');
    console.log('\nExample:');
    console.log('  npm run extract-raw -- "https://www.linkedin.com/sales/search/people?query=..."');
    process.exit(1);
  }

  const searchUrl = args[0];
  const maxProfiles = args[1] ? parseInt(args[1], 10) : 10;

  if (!searchUrl.includes('linkedin.com/sales')) {
    console.error('❌ Error: URL must be a LinkedIn Sales Navigator search URL');
    process.exit(1);
  }

  const extractor = new RawDataExtractor();
  await extractor.run(searchUrl, maxProfiles);
}

main().catch(error => {
  console.error('❌ Fatal error:', error);
  process.exit(1);
});
