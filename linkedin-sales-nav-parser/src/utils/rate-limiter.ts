import { ScraperConfig, DelayType } from '../core/types';
import Logger from './logger';

class RateLimiter {
  private config: ScraperConfig;
  private logger: Logger;
  private profileCount: number = 0;

  constructor(config: ScraperConfig, logger: Logger) {
    this.config = config;
    this.logger = logger;
  }

  async delay(type: DelayType): Promise<void> {
    const delayConfig = this.config.delays[type];
    const min = delayConfig.min;
    const max = delayConfig.max;
    
    let delayMs = Math.floor(Math.random() * (max - min + 1)) + min;
    
    // Add randomization if enabled
    if (this.config.stealth.randomizeTimings) {
      const variance = delayMs * 0.2; // ±20%
      delayMs = delayMs + (Math.random() * variance * 2 - variance);
    }
    
    delayMs = Math.max(0, Math.floor(delayMs));
    
    if (type === 'betweenProfiles') {
      this.logger.info(`Delay: ${(delayMs / 1000).toFixed(1)} seconds (human behavior simulation)`);
    }
    
    await new Promise(resolve => setTimeout(resolve, delayMs));
  }

  shouldTakeBreak(profileCount: number): boolean {
    this.profileCount = profileCount;
    return profileCount > 0 && profileCount % this.config.breaks.afterProfiles === 0;
  }

  async takeBreak(): Promise<void> {
    const min = this.config.breaks.duration.min;
    const max = this.config.breaks.duration.max;
    let breakDuration = Math.floor(Math.random() * (max - min + 1)) + min;
    
    // Add randomization
    if (this.config.stealth.randomizeTimings) {
      const variance = breakDuration * 0.2;
      breakDuration = breakDuration + (Math.random() * variance * 2 - variance);
    }
    
    breakDuration = Math.max(0, Math.floor(breakDuration));
    
    this.logger.info(`⏸️  Taking a break (${this.profileCount} profiles scraped)`);
    this.logger.info(`Break duration: ${Math.floor(breakDuration / 1000)} seconds (human behavior simulation)`);
    
    await new Promise(resolve => setTimeout(resolve, breakDuration));
    
    this.logger.info('✓ Break complete, resuming...');
  }

  getRandomDelay(min: number, max: number): number {
    let delay = Math.floor(Math.random() * (max - min + 1)) + min;
    
    if (this.config.stealth.randomizeTimings) {
      const variance = delay * 0.2;
      delay = delay + (Math.random() * variance * 2 - variance);
    }
    
    return Math.max(0, Math.floor(delay));
  }

  reset(): void {
    this.profileCount = 0;
  }
}

export default RateLimiter;
