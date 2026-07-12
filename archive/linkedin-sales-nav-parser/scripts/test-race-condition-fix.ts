#!/usr/bin/env node

/**
 * Test Script: Race Condition Fix Verification
 * 
 * This script tests the fixes for:
 * 1. Race condition - sidebar not updating before extraction
 * 2. Missing LinkedIn profile URLs
 * 
 * Usage: npx ts-node scripts/test-race-condition-fix.ts "YOUR_SALES_NAV_URL"
 */

import { chromium } from 'playwright';
import * as path from 'path';
import { homedir } from 'os';
import Parser from '../src/parser';
import Logger from '../src/logger';

async function testRaceConditionFix() {
  console.log('🧪 Testing Race Condition & URL Extraction Fixes\n');
  
  const url = process.argv[2];
  if (!url) {
    console.error('❌ Please provide a Sales Navigator search URL');
    console.log('Usage: npx ts-node scripts/test-race-condition-fix.ts "YOUR_SALES_NAV_URL"');
    process.exit(1);
  }
  
  const logger = new Logger();
  const parser = new Parser(logger);
  
  // Get Chrome profile
  const chromeProfile = path.join(homedir(), 'Library', 'Application Support', 'Google', 'Chrome', 'Default');
  console.log(`Using Chrome profile: ${chromeProfile}\n`);
  
  // Launch browser
  const context = await chromium.launchPersistentContext(chromeProfile, {
    headless: false,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    viewport: { width: 1920, height: 1080 },
  });
  
  const page = await context.newPage();
  
  console.log(`Navigating to: ${url}\n`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  
  // Wait for results
  console.log('⏳ Waiting for search results...\n');
  await page.waitForSelector('.artdeco-list__item', { timeout: 10000 });
  
  // Get profile cards
  const cards = await page.$$('li.artdeco-list__item');
  console.log(`✓ Found ${cards.length} profile cards\n`);
  
  if (cards.length === 0) {
    console.error('❌ No profile cards found');
    await context.close();
    process.exit(1);
  }
  
  // Test first 5 profiles
  const testCount = Math.min(5, cards.length);
  console.log(`Testing first ${testCount} profiles...\n`);
  console.log('='.repeat(80));
  
  const results = {
    total: testCount,
    successful: 0,
    withLinkedInUrl: 0,
    withoutLinkedInUrl: 0,
    failed: 0,
    sidebarUpdateTimes: [] as number[],
  };
  
  for (let i = 0; i < testCount; i++) {
    console.log(`\n📋 Profile ${i + 1}/${testCount}`);
    console.log('-'.repeat(80));
    
    try {
      const card = cards[i];
      const startTime = Date.now();
      
      // Parse profile with new logic
      const profile = await parser.parseProfileCard(card, page);
      
      const endTime = Date.now();
      const duration = ((endTime - startTime) / 1000).toFixed(2);
      results.sidebarUpdateTimes.push(endTime - startTime);
      
      if (profile) {
        results.successful++;
        
        console.log(`✓ Successfully extracted profile in ${duration}s`);
        console.log(`  Name: ${profile.fullName}`);
        console.log(`  Company: ${profile.currentCompany}`);
        console.log(`  Location: ${profile.location}`);
        
        if (profile.profileUrl && profile.profileUrl.includes('/in/')) {
          results.withLinkedInUrl++;
          console.log(`  LinkedIn URL: ${profile.profileUrl} ✓`);
        } else {
          results.withoutLinkedInUrl++;
          console.log(`  LinkedIn URL: [NOT FOUND] ⚠️`);
        }
        
        console.log(`  Connection: ${profile.connectionDegree}`);
        console.log(`  Experience entries: ${profile.experience?.length || 0}`);
      } else {
        results.failed++;
        console.log(`❌ Failed to extract profile`);
      }
      
      // Small delay between profiles
      await page.waitForTimeout(2000);
      
    } catch (error) {
      results.failed++;
      console.log(`❌ Error: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  
  // Summary
  console.log('\n' + '='.repeat(80));
  console.log('📊 TEST RESULTS SUMMARY');
  console.log('='.repeat(80));
  console.log(`Total profiles tested: ${results.total}`);
  console.log(`Successful extractions: ${results.successful} (${((results.successful / results.total) * 100).toFixed(1)}%)`);
  console.log(`With LinkedIn URL: ${results.withLinkedInUrl} (${((results.withLinkedInUrl / results.successful) * 100).toFixed(1)}%)`);
  console.log(`Without LinkedIn URL: ${results.withoutLinkedInUrl} (${((results.withoutLinkedInUrl / results.successful) * 100).toFixed(1)}%)`);
  console.log(`Failed: ${results.failed}`);
  
  if (results.sidebarUpdateTimes.length > 0) {
    const avgTime = results.sidebarUpdateTimes.reduce((a, b) => a + b, 0) / results.sidebarUpdateTimes.length;
    const minTime = Math.min(...results.sidebarUpdateTimes);
    const maxTime = Math.max(...results.sidebarUpdateTimes);
    
    console.log(`\nSidebar update times:`);
    console.log(`  Average: ${(avgTime / 1000).toFixed(2)}s`);
    console.log(`  Min: ${(minTime / 1000).toFixed(2)}s`);
    console.log(`  Max: ${(maxTime / 1000).toFixed(2)}s`);
  }
  
  console.log('\n' + '='.repeat(80));
  
  // Evaluation
  if (results.successful === results.total) {
    console.log('✅ ALL TESTS PASSED - Race condition fix working!');
  } else if (results.successful > 0) {
    console.log('⚠️  PARTIAL SUCCESS - Some profiles failed');
  } else {
    console.log('❌ ALL TESTS FAILED - Fix needs adjustment');
  }
  
  if (results.withLinkedInUrl / results.successful >= 0.8) {
    console.log('✅ LinkedIn URL extraction working well (>80% success rate)');
  } else if (results.withLinkedInUrl > 0) {
    console.log('⚠️  LinkedIn URL extraction needs improvement');
  } else {
    console.log('❌ LinkedIn URL extraction not working');
  }
  
  console.log('\n💡 Press Ctrl+C to exit (browser will stay open for inspection)');
  
  // Keep browser open for inspection
  await new Promise(() => {});
}

testRaceConditionFix().catch(console.error);
