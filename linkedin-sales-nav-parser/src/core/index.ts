#!/usr/bin/env node

import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { ScraperConfig, ScraperOptions } from './types';
import Logger from '../utils/logger';
import Scraper from './scraper';
import DuplicateTracker from '../storage/duplicate-tracker';
import ChromeDetector from '../utils/chrome-detector';

const program = new Command();

program
  .name('linkedin-sales-nav-parser')
  .description('LinkedIn Sales Navigator parser with anti-detection features')
  .version('1.0.0');

program
  .option('--url <url>', 'Sales Navigator search URL')
  .option('--max-profiles <number>', 'Maximum profiles to scrape', parseInt)
  .option('--max-pages <number>', 'Maximum pages to scrape', parseInt)
  .option('--test', 'Test mode (limit to 10 profiles)')
  .option('--resume', 'Resume from last checkpoint')
  .option('--clear-history', 'Clear duplicate tracking history')
  .option('--list-profiles', 'List available Chrome profiles')
  .option('--no-sound', 'Disable completion sound')
  .option('--fresh', 'Start fresh (ignore previous tracking data)')
  .option('--no-dedup', 'Disable duplicate detection (scrape all profiles)')
  .option('--config <path>', 'Path to custom config file');

program.parse();

const options = program.opts() as ScraperOptions;

async function main() {
  const logger = new Logger();

  try {
    // Handle --list-profiles
    if (options.listProfiles) {
      logger.info('Listing available Chrome profiles...');
      const detector = new ChromeDetector(logger);
      const profiles = await detector.listAvailableProfiles();
      
      if (profiles.length === 0) {
        logger.warn('No Chrome profiles found');
      } else {
        logger.info(`Found ${profiles.length} Chrome profile(s):`);
        profiles.forEach((profile, index) => {
          logger.info(`  ${index + 1}. ${profile}`);
        });
      }
      return;
    }

    // Handle --clear-history
    if (options.clearHistory) {
      logger.info('Clearing duplicate tracking history...');
      // Use a dummy URL for clear-history since we're deleting the file anyway
      const tracker = new DuplicateTracker(logger, 'dummy-url-for-clear', false);
      await tracker.clearHistory();
      logger.success('✓ History cleared');
      return;
    }

    // Validate URL (unless resuming)
    if (!options.resume && !options.url) {
      logger.error('Error: --url is required (unless using --resume)');
      logger.info('Usage: npm start -- --url "YOUR_SALES_NAV_SEARCH_URL"');
      logger.info('Or: npm start -- --resume (to continue from last checkpoint)');
      process.exit(1);
    }

    // Validate URL format
    if (options.url && !options.url.includes('linkedin.com/sales')) {
      logger.error('Error: URL must be a LinkedIn Sales Navigator search URL');
      logger.info('Example: https://www.linkedin.com/sales/search/people?query=...');
      process.exit(1);
    }

    // Load configuration
    const configPath = options.configPath || path.join(process.cwd(), 'config', 'config.json');
    
    if (!fs.existsSync(configPath)) {
      logger.error(`Configuration file not found: ${configPath}`);
      process.exit(1);
    }

    const configData = fs.readFileSync(configPath, 'utf-8');
    const config: ScraperConfig = JSON.parse(configData);

    logger.info('Loading configuration from config/config.json');
    logger.success('Configuration loaded successfully');

    // Override config with CLI options
    if (options.maxProfiles) {
      config.limits.maxProfilesPerSession = options.maxProfiles;
    }
    if (options.maxPages) {
      config.limits.maxPagesPerSession = options.maxPages;
    }

    // Create and run scraper
    const scraper = new Scraper(config, options, logger);
    await scraper.scrape();

  } catch (error) {
    logger.error('Fatal error', error as Error);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('\n\nInterrupt received. Progress has been saved.');
  console.log('Run with --resume flag to continue from where you left off.');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\n\nTermination signal received. Progress has been saved.');
  process.exit(0);
});

// Run main function
main().catch((error) => {
  console.error('Unhandled error:', error);
  process.exit(1);
});
