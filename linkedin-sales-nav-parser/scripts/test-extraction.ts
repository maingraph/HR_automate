#!/usr/bin/env node

import { chromium } from 'playwright';
import * as fs from 'fs';

async function testExtraction() {
  console.log('Starting extraction test...');
  
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

    // Get sidebar text
    let container: any = await page.$('aside');
    if (!container) {
      console.log('No aside found, trying lead-details');
      container = await page.$('div[class*="lead-details"]');
    }

    if (container) {
      const text = await container.textContent();
      console.log('\n=== SIDEBAR TEXT ===');
      console.log(text);
      console.log('\n=== END SIDEBAR TEXT ===');
      
      // Save to file
      fs.writeFileSync('/Users/imjustchilling/Desktop/linkedin-sales-nav-parser/test-sidebar.txt', text || '');
      console.log('\nSaved to test-sidebar.txt');
      
      // Test experience extraction
      console.log('\n=== TESTING EXPERIENCE EXTRACTION ===');
      const expMatch = text?.match(/(?:[A-Z][a-z]+'s|Matt's) experience\s*\n([\s\S]*?)(?:\n\s*Education|\n\s*Featured skills|\n\s*Languages|\n\s*Timeline|$)/i);
      if (expMatch) {
        console.log('Experience section found!');
        console.log('Length:', expMatch[1].length);
        console.log('First 500 chars:', expMatch[1].substring(0, 500));
      } else {
        console.log('Experience section NOT found');
        console.log('Searching for "experience" in text...');
        const expIndex = text?.toLowerCase().indexOf('experience');
        if (expIndex && expIndex > -1) {
          console.log('Found "experience" at position:', expIndex);
          console.log('Context:', text?.substring(expIndex, expIndex + 200));
        }
      }
    }

    // Wait before closing
    console.log('\nWaiting 5 seconds before closing...');
    await page.waitForTimeout(5000);
  }

  await context.close();
  console.log('Done!');
}

testExtraction().catch(console.error);
