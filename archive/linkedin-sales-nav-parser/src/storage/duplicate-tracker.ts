import * as crypto from 'crypto';
import Logger from '../utils/logger';

/**
 * In-memory duplicate tracker (no persistence)
 * Tracks scraped profiles during the current session only
 */
class DuplicateTracker {
  private logger: Logger;
  private scrapedUrls: Set<string>;
  private searchUrlHash: string;

  constructor(logger: Logger, searchUrl: string, fresh: boolean = false) {
    this.logger = logger;
    this.scrapedUrls = new Set();
    this.searchUrlHash = this.generateSearchHash(searchUrl);
    
    // Always in-memory only (no persistence)
    this.logger.debug('Duplicate tracking: in-memory only (no persistence)');
  }

  private generateSearchHash(url: string): string {
    // Generate a hash of the search URL (without sessionId parameter)
    const urlWithoutSession = url.split('&sessionId=')[0];
    return crypto.createHash('md5').update(urlWithoutSession).digest('hex');
  }

  isScraped(identifier: string): boolean {
    return this.scrapedUrls.has(identifier);
  }

  async markAsScraped(identifier: string): Promise<void> {
    this.scrapedUrls.add(identifier);
    // No persistence - in-memory only
  }

  getScrapedCount(): number {
    return this.scrapedUrls.size;
  }

  async clearHistory(): Promise<void> {
    this.scrapedUrls.clear();
    this.logger.debug('In-memory duplicate tracking cleared');
  }
}

export default DuplicateTracker;
