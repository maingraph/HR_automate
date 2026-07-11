import { chromium } from 'playwright';
import * as path from 'path';
import { homedir } from 'os';

async function diagnose() {
  console.log('🔍 LinkedIn Sales Navigator Diagnostic Tool\n');
  
  // Get Chrome profile
  const chromeProfile = path.join(homedir(), 'Library', 'Application Support', 'Google', 'Chrome', 'Default');
  console.log(`Using Chrome profile: ${chromeProfile}\n`);
  
  // Get URL from command line
  const url = process.argv[2];
  if (!url) {
    console.error('❌ Please provide a Sales Navigator search URL');
    console.log('Usage: npm run diagnose -- "YOUR_SALES_NAV_URL"');
    process.exit(1);
  }
  
  console.log(`Navigating to: ${url}\n`);
  
  // Launch browser
  const context = await chromium.launchPersistentContext(chromeProfile, {
    headless: false,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  
  const page = await context.newPage();
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  
  console.log('⏳ Waiting 10 seconds for page to fully load...\n');
  await page.waitForTimeout(10000);
  
  console.log('📊 Analyzing page structure...\n');
  
  // Get page info
  const title = await page.title();
  const currentUrl = page.url();
  console.log(`Page Title: ${title}`);
  console.log(`Current URL: ${currentUrl}\n`);
  
  // Check for various selectors
  const selectorsToCheck = [
    'li',
    'ul',
    'ol',
    '[class*="list"]',
    '[class*="result"]',
    '[class*="search"]',
    '[data-view-name]',
    '.artdeco-list',
    '.artdeco-list__item',
    '.entity-result',
    'li.reusable-search__result-container',
    '.search-results-container',
    '[data-view-name="search-results-list"]',
    'ol.search-results__list',
  ];
  
  console.log('🔎 Checking selectors:\n');
  
  for (const selector of selectorsToCheck) {
    const elements = await page.$$(selector);
    if (elements.length > 0) {
      console.log(`✅ ${selector} - Found ${elements.length} element(s)`);
    }
  }
  
  console.log('\n📝 Getting all class names on the page...\n');
  
  // Get all unique class names
  const classNames = await page.evaluate(() => {
    const classes = new Set<string>();
    document.querySelectorAll('*').forEach(el => {
      el.classList.forEach(cls => classes.add(cls));
    });
    return Array.from(classes).sort();
  });
  
  // Filter for relevant classes
  const relevantClasses = classNames.filter(cls => 
    cls.includes('list') || 
    cls.includes('result') || 
    cls.includes('search') ||
    cls.includes('item') ||
    cls.includes('card') ||
    cls.includes('profile')
  );
  
  console.log('Relevant class names found:');
  relevantClasses.slice(0, 50).forEach(cls => console.log(`  - ${cls}`));
  
  if (relevantClasses.length > 50) {
    console.log(`  ... and ${relevantClasses.length - 50} more`);
  }
  
  console.log('\n📝 Getting data attributes...\n');
  
  // Get all data attributes
  const dataAttrs = await page.evaluate(() => {
    const attrs = new Set<string>();
    document.querySelectorAll('*').forEach(el => {
      Array.from(el.attributes).forEach(attr => {
        if (attr.name.startsWith('data-')) {
          attrs.add(attr.name);
        }
      });
    });
    return Array.from(attrs).sort();
  });
  
  console.log('Data attributes found:');
  dataAttrs.slice(0, 30).forEach(attr => console.log(`  - ${attr}`));
  
  if (dataAttrs.length > 30) {
    console.log(`  ... and ${dataAttrs.length - 30} more`);
  }
  
  console.log('\n🎯 Looking for profile/person elements...\n');
  
  // Try to find profile cards
  const profileSelectors = [
    '[class*="profile"]',
    '[class*="person"]',
    '[class*="lead"]',
    '[data-view-name*="profile"]',
    '[data-view-name*="lead"]',
  ];
  
  for (const selector of profileSelectors) {
    const elements = await page.$$(selector);
    if (elements.length > 0) {
      console.log(`✅ ${selector} - Found ${elements.length} element(s)`);
      
      // Get the first element's HTML
      if (elements[0]) {
        const html = await elements[0].evaluate(el => el.outerHTML.substring(0, 200));
        console.log(`   Sample: ${html}...`);
      }
    }
  }
  
  console.log('\n✅ Diagnostic complete!');
  console.log('\nPress Ctrl+C to exit (browser will stay open for manual inspection)');
  
  // Keep browser open
  await new Promise(() => {});
}

diagnose().catch(console.error);
