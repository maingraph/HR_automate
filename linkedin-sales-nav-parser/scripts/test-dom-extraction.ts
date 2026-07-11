#!/usr/bin/env node
import { chromium } from 'playwright';
import * as fs from 'fs';

async function testDOMExtraction() {
  console.log('Starting DOM extraction test...');
  
  const url = process.argv[2];
  if (!url) {
    console.error('Please provide a URL');
    process.exit(1);
  }

  const context = await chromium.launchPersistentContext(
    '/Users/imjustchilling/Library/Application Support/Google/Chrome/Default',
    {
      headless: false,
      viewport: { width: 1920, height: 1080 },
    }
  );

  const page = await context.newPage();
  
  console.log('Navigating to:', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);

  // Wait for results
  await page.waitForSelector('.artdeco-list__item', { timeout: 10000 });
  console.log('Results loaded');

  // Get first profile card
  const cards = await page.$$('li.artdeco-list__item');
  console.log(`Found ${cards.length} profile cards`);

  if (cards.length > 0) {
    console.log('\n=== Clicking first profile ===');
    const firstCard = cards[0];
    
    // Click it
    const clickableSelectors = [
      'a[data-control-name="view_lead_panel_via_search_lead_name"]',
      '.artdeco-entity-lockup__title a',
      'a[href*="/sales/lead/"]',
    ];

    for (const selector of clickableSelectors) {
      const element = await firstCard.$(selector);
      if (element) {
        await element.click();
        console.log('Clicked with selector:', selector);
        break;
      }
    }

    // Wait for sidebar
    await page.waitForTimeout(4000);

    // Try to find experience section using DOM
    console.log('\n=== ANALYZING EXPERIENCE SECTION DOM ===');
    
    // Get the sidebar container
    const sidebar = await page.$('div[class*="lead-details"]');
    if (sidebar) {
      // Try to find experience section
      const experienceSelectors = [
        'section[data-section="experience"]',
        'div[id*="experience"]',
        'section:has-text("experience")',
        'div:has-text("experience")',
      ];

      for (const selector of experienceSelectors) {
        try {
          const expSection = await sidebar.$(selector);
          if (expSection) {
            console.log(`\nFound experience section with selector: ${selector}`);
            const html = await expSection.innerHTML();
            console.log('HTML length:', html.length);
            console.log('First 500 chars:', html.substring(0, 500));
            break;
          }
        } catch (e) {
          // Continue
        }
      }

      // Try to find all list items in sidebar
      console.log('\n=== LOOKING FOR LIST ITEMS ===');
      const listItems = await sidebar.$$('li, div[class*="position"], div[class*="experience"]');
      console.log(`Found ${listItems.length} potential experience items`);

      // Analyze first few items
      for (let i = 0; i < Math.min(3, listItems.length); i++) {
        console.log(`\n--- Item ${i + 1} ---`);
        const item = listItems[i];
        const html = await item.innerHTML();
        console.log('HTML:', html.substring(0, 300));
        
        // Try to find title, company, date
        const titleSelectors = [
          'div[class*="title"]',
          'span[class*="title"]',
          'h3',
          'h4',
        ];

        for (const sel of titleSelectors) {
          const titleEl = await item.$(sel);
          if (titleEl) {
            const text = await titleEl.textContent();
            console.log(`  Title (${sel}):`, text?.trim());
          }
        }
      }

      // Save full sidebar HTML
      const fullHTML = await sidebar.innerHTML();
      fs.writeFileSync('/Users/imjustchilling/Desktop/linkedin-sales-nav-parser/sidebar-dom.html', fullHTML);
      console.log('\n✓ Saved full sidebar HTML to sidebar-dom.html');
    }

    // Wait before closing
    console.log('\nWaiting 5 seconds before closing...');
    await page.waitForTimeout(5000);
  }

  await context.close();
  console.log('Done!');
}

testDOMExtraction().catch(console.error);
